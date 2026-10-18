"""Test-only mini MCP server (Streamable HTTP) for client conformance tests.

Implements just enough of MCP 2025-11-25 to verify the client's wire
behavior: initialize negotiation (incl. version mismatch), session headers,
notifications/initialized, tools/list, tools/call, resources/list,
JSON-RPC errors, and SSE-vs-JSON response framing.

This is TEST INFRASTRUCTURE, not a product component. It never ships as the
gateway; J3 owns the real server.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL_VERSION = "2025-11-25"


class HarnessState:
    def __init__(self, protocol_version=PROTOCOL_VERSION, sse_framing=True,
                 session_id="harness-session-1"):
        self.protocol_version = protocol_version
        self.sse_framing = sse_framing
        self.session_id = session_id
        self.seen = []  # (method, headers snapshot, payload)
        self.fail_next_with: int | None = None


def make_handler(state: HarnessState):
    class H(BaseHTTPRequestHandler):
        def _snapshot(self):
            return {"mcp-session-id": self.headers.get("Mcp-Session-Id"),
                    "mcp-protocol-version": self.headers.get("MCP-Protocol-Version"),
                    "accept": self.headers.get("Accept")}

        def _send(self, obj, session=True):
            if self.path == "/mcp-bare":
                body = json.dumps(obj).encode()
            elif state.sse_framing:
                body = ("event: message\ndata: " + json.dumps(obj) + "\n\n").encode()
            else:
                body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            if session and state.session_id:
                self.send_header("Mcp-Session-Id", state.session_id)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            method = payload.get("method", "")
            state.seen.append((method, self._snapshot(), payload))
            if state.fail_next_with:
                code = state.fail_next_with
                state.fail_next_with = None
                self.send_response(code)
                self.end_headers()
                return
            rid = payload.get("id")
            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()
                return
            if method == "initialize":
                self._send({"jsonrpc": "2.0", "id": rid, "result": {
                    "protocolVersion": state.protocol_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "harness", "version": "0.0.1"}}})
            elif method == "tools/list":
                self._send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [
                    {"name": "prepare_day_brief",
                     "inputSchema": {"type": "object"}}]}})
            elif method == "tools/call":
                name = payload["params"]["name"]
                if name == "boom":
                    self._send({"jsonrpc": "2.0", "id": rid, "error": {
                        "code": -32000, "message": "simulated tool failure"}})
                else:
                    self._send({"jsonrpc": "2.0", "id": rid, "result": {
                        "content": [{"type": "text", "text": "ok"}],
                        "structuredContent": {"echo": name}}})
            elif method == "resources/list":
                self._send({"jsonrpc": "2.0", "id": rid, "result": {
                    "resources": [{"uri": "ui://harness/card",
                                   "name": "card"}]}})
            else:
                self._send({"jsonrpc": "2.0", "id": rid, "error": {
                    "code": -32601, "message": "unknown method"}})

        def log_message(self, *args):
            pass

    return H


def run_harness(port=0, **kwargs) -> tuple[ThreadingHTTPServer, HarnessState, int]:
    state = HarnessState(**kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state, server.server_address[1]
