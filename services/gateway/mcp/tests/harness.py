"""Shared in-process test harness for the EARSHOT MCP gateway (J3).

Spins up the real server (stdlib HTTP) in a thread — no mocks, no stubs.
Every test exercises the actual wire: real HTTP, real JSON-RPC, real kernel.
"""
import json
import threading
import time
import urllib.request
import urllib.error
from earshot.gateway.mcp import server as S  # noqa: E402


class Client:
    """Minimal spec-shaped MCP client over Streamable HTTP."""

    def __init__(self, port, token=None):
        self.base = f"http://127.0.0.1:{port}/mcp"
        self.token = token
        self.session = None
        self._id = 0

    def _headers(self, extra=None):
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.session:
            h["MCP-Session-Id"] = self.session
            h["MCP-Protocol-Version"] = "2025-11-25"
        h.update(extra or {})
        return h

    def raw_post(self, body: bytes, headers=None):
        req = urllib.request.Request(self.base, data=body,
                                     headers=self._headers(headers), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def post(self, msg, headers=None):
        s, h, b = self.raw_post(json.dumps(msg).encode(), headers)
        try:
            return s, h, json.loads(b.decode())
        except ValueError:
            return s, h, b

    def call(self, msg):
        self._id += 1
        msg = dict(msg)
        msg.setdefault("jsonrpc", "2.0")
        msg.setdefault("id", self._id)
        return self.post(msg)

    def initialize(self, version="2025-11-25"):
        s, h, b = self.call({"method": "initialize",
                             "params": {"protocolVersion": version,
                                        "capabilities": {},
                                        "clientInfo": {"name": "harness", "version": "1"}}})
        assert s == 200, f"initialize failed: {s} {b}"
        assert b["result"]["protocolVersion"] == "2025-11-25", b
        # Header dict from urllib: exact casing as sent by server.
        sid = h.get("MCP-Session-Id")
        assert sid, f"no session id in {sorted(h)}"
        assert all(0x21 <= ord(ch) <= 0x7E for ch in sid), "non-visible-ASCII session id"
        self.session = sid
        # notifications/initialized -> 202, empty
        s2, _, b2 = self.post({"jsonrpc": "2.0", "method": "notifications/initialized",
                               "params": {}})
        assert s2 == 202 and b2 == b"", (s2, b2)
        return b

    def tool(self, name, arguments):
        s, _, b = self.call({"method": "tools/call",
                             "params": {"name": name, "arguments": arguments}})
        assert s == 200, (s, b)
        return b


def start_server(port, world_factory=None):
    """Start a real server in a thread. Returns (server, client-for-owner)."""
    from earshot.gateway.mcp import fixtures as F
    srv = S.ThreadedMCPServer(("127.0.0.1", port), S.MCPHandler)
    srv.auth = S.auth_mod.AuthRegistry()
    srv.broker = S.broker_mod.Broker(world_factory=world_factory or F.strict_world)
    srv.sessions = {}
    srv.latencies = []
    srv.rate_windows = {}
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    return srv, Client(port, srv.auth.owner_token)


def stop_server(srv):
    """Release the port: shutdown() stops serving, server_close() frees the socket."""
    try:
        srv.shutdown()
    finally:
        srv.server_close()
