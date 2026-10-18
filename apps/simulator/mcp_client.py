"""Real MCP client over Streamable HTTP — stdlib only, protocol pinned 2025-11-25.

Speaks initialize / notifications/initialized / tools/list / tools/call with
correct session handling (Mcp-Session-Id), MCP-Protocol-Version headers, and
SSE-or-JSON response parsing. No SDK dependency: exact wire control, zero
install, reproducible.

This is the controlled host's integration surface (dossier §10.3). It is
protocol-tested against tests/protocol_conformance_harness.py; it does not
depend on any particular server implementation beyond the pinned spec.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Optional

PROTOCOL_VERSION = "2025-11-25"
_MCP_VERSION_HEADER = "MCP-Protocol-Version"
_SESSION_HEADER = "Mcp-Session-Id"


class McpError(Exception):
    """A JSON-RPC error response or a transport-level failure."""


@dataclass
class McpClient:
    url: str
    timeout: float = 10.0
    client_name: str = "earshot-simulator"
    client_version: str = "0.1.0"
    _session_id: Optional[str] = field(default=None, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    server_info: dict = field(default_factory=dict, init=False)
    server_capabilities: dict = field(default_factory=dict, init=False)

    # ---- low-level ----------------------------------------------------

    def _post(self, payload: dict | None) -> tuple[Any, dict]:
        """POST one JSON-RPC message; return (parsed result payload, headers)."""
        body = json.dumps(payload).encode() if payload is not None else b""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers[_SESSION_HEADER] = self._session_id
            headers[_MCP_VERSION_HEADER] = PROTOCOL_VERSION
        req = urllib.request.Request(self.url, data=body or None,
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers)
                status = resp.status
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise McpError(f"HTTP {e.code}: {detail}") from e
        except OSError as e:
            raise McpError(f"transport failure: {e}") from e
        if status == 202:
            return None, resp_headers  # accepted notification, no body
        return self._parse_message(raw), resp_headers

    @staticmethod
    def _parse_message(raw: str) -> Any:
        """Accept a bare JSON body or SSE-framed `data:` lines."""
        text = raw.strip()
        if not text:
            raise McpError("empty response body")
        if text.startswith("{") or text.startswith("["):
            return json.loads(text)
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    return json.loads(data)
        raise McpError(f"unparseable response: {text[:200]!r}")

    def _request(self, method: str, params: dict | None = None) -> Any:
        rid = self._next_id
        self._next_id += 1
        payload, headers = self._post(
            {"jsonrpc": "2.0", "id": rid, "method": method,
             "params": params or {}})
        sid = headers.get(_SESSION_HEADER) or headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        if not isinstance(payload, dict) or payload.get("id") != rid:
            raise McpError(f"mismatched response id for {method}: {payload!r}"[:300])
        if "error" in payload:
            err = payload["error"]
            raise McpError(f"{method}: {err.get('code')} {err.get('message')}")
        return payload.get("result")

    def _notify(self, method: str, params: dict | None = None) -> None:
        self._post({"jsonrpc": "2.0", "method": method,
                    "params": params or {}})

    # ---- session lifecycle --------------------------------------------

    def initialize(self) -> dict:
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"roots": {"listChanged": False},
                             "sampling": {},
                             "elicitation": {}},
            "clientInfo": {"name": self.client_name,
                           "version": self.client_version},
        })
        negotiated = result.get("protocolVersion")
        if negotiated != PROTOCOL_VERSION:
            raise McpError(
                f"server negotiated {negotiated!r}, expected {PROTOCOL_VERSION!r}")
        self.server_info = result.get("serverInfo", {})
        self.server_capabilities = result.get("capabilities", {})
        self._notify("notifications/initialized")
        return result

    # ---- tools ---------------------------------------------------------

    def list_tools(self) -> list[dict]:
        result = self._request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        result = self._request("tools/call",
                               {"name": name, "arguments": arguments or {}})
        # result: {content: [...], structuredContent?: ..., isError?: bool}
        return result

    # ---- resources (public-safe UI bundles only, §10.3) -----------------

    def list_resources(self) -> list[dict]:
        result = self._request("resources/list")
        return result.get("resources", [])

    def read_resource(self, uri: str) -> list[dict]:
        result = self._request("resources/read", {"uri": uri})
        return result.get("contents", [])

    # ---- convenience ----------------------------------------------------

    def connect(self) -> "McpClient":
        self.initialize()
        return self

    @property
    def connected(self) -> bool:
        return bool(self.server_info)
