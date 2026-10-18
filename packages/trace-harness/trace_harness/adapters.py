"""Server adapters: one interface, two transports.

MCPHttpAdapter speaks Streamable HTTP (MCP 2025-11-25) to a target server
using only the standard library. KernelDirectAdapter drives the reference
kernel in-process; it is the self-test path, labeled as such, never a
substitute for the wire trace.
"""
import http.client
import json
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TraceStep:
    tool: str
    args: dict
    status: str  # "ok" | "error"
    result: Any  # result dict on ok; {"code": int, "message": str} on error
    duration_ms: float


class MCPHttpAdapter:
    """Minimal Streamable HTTP client (stdlib only).

    initialize -> notifications/initialized -> tools/call. Handles both
    `application/json` and `text/event-stream` (SSE) responses. The
    Mcp-Session-Id is used when the server returns one; the spec makes
    sessions optional, so sessionless servers work too.
    """

    def __init__(self, base_url: str, tenant: str, owner: str,
                 timeout: float = 15.0):
        self._parts = urllib.parse.urlparse(base_url)
        self.tenant = tenant
        self.owner = owner
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._next_id = 1

    def _conn(self) -> http.client.HTTPConnection:
        if self._parts.scheme == "https":
            return http.client.HTTPSConnection(
                self._parts.hostname, self._parts.port or 443,
                timeout=self.timeout)
        return http.client.HTTPConnection(
            self._parts.hostname, self._parts.port or 80,
            timeout=self.timeout)

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
            # Fixture identity channel. NOT production auth: production must
            # authenticate tenant/owner outside model control (dossier §16.12).
            "X-Tenant": self.tenant,
            "X-Owner": self.owner,
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload: dict) -> tuple:
        body = json.dumps(payload).encode()
        conn = self._conn()
        try:
            conn.request("POST", self._parts.path or "/", body, self._headers())
            resp = conn.getresponse()
            sid = resp.getheader("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, resp.getheader("Content-Type", ""), raw
        finally:
            conn.close()

    @staticmethod
    def _extract_json(status: int, ctype: str, raw: str) -> Any:
        if "text/event-stream" in ctype:
            for line in raw.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:])
            raise ValueError("SSE stream contained no data event")
        return json.loads(raw)

    def connect(self) -> None:
        status, ctype, raw = self._post({
            "jsonrpc": "2.0", "id": self._next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "trace-harness", "version": "0.1.0"},
            },
        })
        self._next_id += 1
        if status != 200:
            raise ConnectionError(f"initialize failed: HTTP {status}: {raw[:200]}")
        self._extract_json(status, ctype, raw)
        # initialized notification -> 202 expected
        status, _, _ = self._post({"jsonrpc": "2.0",
                                   "method": "notifications/initialized"})
        if status not in (200, 202):
            raise ConnectionError(f"initialized notification: HTTP {status}")

    def call(self, tool: str, args: dict) -> TraceStep:
        start = time.perf_counter()
        try:
            status, ctype, raw = self._post({
                "jsonrpc": "2.0", "id": self._next_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            })
            self._next_id += 1
            msg = self._extract_json(status, ctype, raw)
            if status != 200 or "error" in msg:
                err = msg.get("error", {})
                step = TraceStep(tool, args, "error",
                                 {"code": err.get("code"),
                                  "message": err.get("message")}, 0.0)
            else:
                step = TraceStep(tool, args, "ok", msg.get("result"), 0.0)
        except Exception as exc:  # transport failure is a trace event, not a crash
            step = TraceStep(tool, args, "error",
                             {"code": -32000, "message": f"transport: {type(exc).__name__}"},
                             0.0)
        step.duration_ms = (time.perf_counter() - start) * 1000.0
        return step

    def close(self) -> None:
        pass


class KernelDirectAdapter:
    """In-process adapter against the reference kernel.

    SELF-TEST ONLY. It exercises the same script/differ machinery without a
    wire, so harness bugs surface before we blame a server. Never presented
    as evidence about any server's public trace.
    """

    def __init__(self, kernel, tenant: str, owner: str, facts: tuple):
        self._k = kernel
        self.tenant = tenant
        self.owner = owner
        self._facts = facts
        self._now = 1000.0

    def connect(self) -> None:
        pass

    def _public(self, facts) -> list:
        return list(self._k.public_projection(facts))

    def call(self, tool: str, args: dict) -> TraceStep:
        start = time.perf_counter()
        try:
            if tool == "prepare_day_brief":
                r = self._k.accept(self.tenant, self.owner, args["request_key"],
                                   self._facts, self._now)
                result = {"request_ref": r["receipt"], "request_state": "accepted",
                          "public_facts": self._public(self._facts)}
            elif tool == "resolve_day_change":
                self._check_ref(args["request_ref"])
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted",
                          "public_facts": self._public(self._facts)}
            elif tool == "continue_on_personal_device":
                self._check_ref(args["request_ref"])
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted", "public_facts": []}
            elif tool == "withdraw_request":
                self._check_ref(args["request_ref"])
                self._k.revoke(args["request_ref"], self.tenant, self.owner)
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted", "public_facts": []}
            else:
                raise ValueError(f"unknown tool {tool}")
            step = TraceStep(tool, args, "ok", result, 0.0)
        except PermissionError:
            # Uniform generic error: no existence oracle (kernel contract).
            step = TraceStep(tool, args, "error",
                             {"code": -32001, "message": "Unavailable"}, 0.0)
        except Exception as exc:
            step = TraceStep(tool, args, "error",
                             {"code": -32602, "message": type(exc).__name__}, 0.0)
        step.duration_ms = (time.perf_counter() - start) * 1000.0
        return step

    def _check_ref(self, receipt: str) -> None:
        c = self._k._capsules.get(receipt)
        if (not c or c["tenant"] != self.tenant or c["owner"] != self.owner
                or c["revoked"]):
            raise PermissionError("Unavailable")

    def close(self) -> None:
        pass
