"""Fixture MCP server for the trace harness's own tests.

Implements the 4 proposed tools (prepare_day_brief, resolve_day_change,
continue_on_personal_device, withdraw_request) against the REAL reference
kernel, over Streamable HTTP (MCP 2025-11-25).

THIS IS A TEST FIXTURE, NOT THE PRODUCT SERVER (J3 owns that). It exists so
the harness's HTTP adapter path is proven end-to-end without depending on
another seat. Tenant/owner arrive via X-Tenant/X-Owner headers — fixture
identity, NOT production auth (production authenticates outside model
control, dossier §16.12).

Run: python fixtureserver.py [port]  (also importable: start(port) -> server)
Test-only reset: POST /__reset clears kernel state between worlds.
"""
import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/home/hatch/workspace/earshot-broker-trees/j07/packages/kernel")
from kernel import Kernel, Fact, Label  # noqa: E402

PUBLIC = "*"


def to_fact(d: dict) -> Fact:
    return Fact(d["key"], d["value"],
                Label(frozenset(d["readers"]), frozenset(d.get("topics", ()))))


class FixtureState:
    def __init__(self):
        self.kernel = Kernel()
        self.world_facts = {}  # tenant -> tuple[Fact, ...]
        self.sessions = set()


def _public_projection(kernel, facts):
    return list(kernel.public_projection(tuple(facts)))


class Handler(BaseHTTPRequestHandler):
    state: FixtureState = None
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send_json(self, obj, status=200, extra=()):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, obj, status=200, extra=()):
        # We answer with plain JSON (legal per spec); adapter also parses SSE.
        self._send_json(obj, status, extra)

    def _rpc_error(self, req_id, code, message, status=200):
        self._send_json({"jsonrpc": "2.0", "id": req_id,
                         "error": {"code": code, "message": message}}, status)

    def do_POST(self):
        if self.path == "/__reset":
            self.state.kernel = Kernel()
            self._send_json({"ok": True})
            return
        if self.path != "/mcp":
            self._send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            msg = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._rpc_error(None, -32700, "Parse error", 400)
            return
        method = msg.get("method")
        req_id = msg.get("id")
        tenant = self.headers.get("X-Tenant", "")
        owner = self.headers.get("X-Owner", "")

        if method == "initialize":
            sid = secrets.token_urlsafe(16)
            self.state.sessions.add(sid)
            self._send_sse({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "earshot-fixture", "version": "0.1.0"},
                }}, extra=[("Mcp-Session-Id", sid)])
        elif method == "notifications/initialized":
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif method == "tools/list":
            self._send_json({"jsonrpc": "2.0", "id": req_id,
                             "result": {"tools": _tool_defs()}})
        elif method == "tools/call":
            self._handle_call(msg, req_id, tenant, owner)
        else:
            self._rpc_error(req_id, -32601, "Method not found")

    def _handle_call(self, msg, req_id, tenant, owner):
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        k = self.state.kernel
        facts = tuple(self.state.world_facts.get(tenant, ()))
        now = 1000.0
        try:
            if name == "prepare_day_brief":
                r = k.accept(tenant, owner, args["request_key"], facts, now)
                result = {"request_ref": r["receipt"],
                          "request_state": "accepted",
                          "public_facts": _public_projection(k, facts)}
            elif name == "resolve_day_change":
                _own(k, args["request_ref"], tenant, owner)
                # The change is processed privately; nothing private returned.
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted",
                          "public_facts": _public_projection(k, facts)}
            elif name == "continue_on_personal_device":
                _own(k, args["request_ref"], tenant, owner)
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted", "public_facts": []}
            elif name == "withdraw_request":
                _own(k, args["request_ref"], tenant, owner)
                k.revoke(args["request_ref"], tenant, owner)
                result = {"request_ref": args["request_ref"],
                          "request_state": "accepted", "public_facts": []}
            else:
                self._rpc_error(req_id, -32601, "Unknown tool")
                return
        except PermissionError:
            # Uniform generic denial: no existence oracle (kernel contract).
            self._rpc_error(req_id, -32001, "Unavailable")
            return
        except (KeyError, TypeError):
            self._rpc_error(req_id, -32602, "Invalid params")
            return
        self._send_json({"jsonrpc": "2.0", "id": req_id, "result": result})


def _own(kernel, receipt, tenant, owner):
    c = kernel._capsules.get(receipt)
    if (not c or c["tenant"] != tenant or c["owner"] != owner
            or c["revoked"]):
        raise PermissionError("Unavailable")


def _tool_defs():
    return [
        {"name": "prepare_day_brief",
         "description": "Fixture implementation of the proposed tool.",
         "inputSchema": {"type": "object",
                         "properties": {
                             "date": {"type": "string"},
                             "timezone": {"type": "string"},
                             "request_key": {"type": "string", "minLength": 16}},
                         "required": ["date", "timezone", "request_key"]}},
        {"name": "resolve_day_change",
         "description": "Fixture implementation of the proposed tool.",
         "inputSchema": {"type": "object",
                         "properties": {
                             "change": {"type": "string"},
                             "request_key": {"type": "string", "minLength": 16},
                             "request_ref": {"type": "string"}},
                         "required": ["change", "request_key", "request_ref"]}},
        {"name": "continue_on_personal_device",
         "description": "Fixture implementation of the proposed tool.",
         "inputSchema": {"type": "object",
                         "properties": {
                             "request_key": {"type": "string", "minLength": 16},
                             "request_ref": {"type": "string"}},
                         "required": ["request_key", "request_ref"]}},
        {"name": "withdraw_request",
         "description": "Fixture implementation of the proposed tool.",
         "inputSchema": {"type": "object",
                         "properties": {
                             "request_key": {"type": "string", "minLength": 16},
                             "request_ref": {"type": "string"}},
                         "required": ["request_key", "request_ref"]}},
    ]


def start(port: int) -> ThreadingHTTPServer:
    state = FixtureState()
    Handler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.state = state
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    srv = start(port)
    print(f"earshot-fixture MCP server on 127.0.0.1:{port}/mcp", flush=True)
    threading.Event().wait()
