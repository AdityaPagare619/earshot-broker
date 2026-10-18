"""Example 1 — the MCP server is real.

Spins up the REAL EARSHOT gateway (stdlib HTTP, MCP spec 2025-11-25) in a
thread on an ephemeral port, performs the spec handshake, then calls
`prepare_day_brief` over the wire and prints the sealed response.

What it proves: a Devpost judge can watch a genuine MCP tool call return a
constant-shape sealed response — `verbatim_no_elaboration`, opaque request
reference — with no mocks, no stubs, no theater. The minimal client below is
deliberately inline: the wire protocol is the point, not hidden in a helper.

Run:  python3 examples/mcp_tool_call.py
Exit: 0 with the spoken response printed, or non-zero on any contract breach.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from earshot.gateway.mcp import fixtures as F
from earshot.gateway.mcp import server as S
from earshot.wincompat import ensure_utf8_stdout


class MCPClient:
    """Minimal MCP client over Streamable HTTP (spec 2025-11-25). Stdlib only."""

    def __init__(self, port: int, token: str):
        self.base = f"http://127.0.0.1:{port}/mcp"
        self.token = token
        self.session: str | None = None
        self._id = 0

    def _post(self, msg: dict):
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, **msg}).encode()
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.token}"}
        if self.session:
            headers.update({"MCP-Session-Id": self.session,
                            "MCP-Protocol-Version": "2025-11-25"})
        req = urllib.request.Request(self.base, data=body,
                                     headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            status, resp_headers, data = resp.status, dict(resp.headers), resp.read()
            resp.close()
        except urllib.error.HTTPError as e:
            status, resp_headers, data = e.code, dict(e.headers), e.read()
        try:
            return status, resp_headers, json.loads(data.decode())
        except ValueError:
            return status, resp_headers, data  # e.g. 202 empty notification ack

    def initialize(self):
        s, h, b = self._post({
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "example", "version": "1"}}})
        assert s == 200, (s, b)
        assert b["result"]["protocolVersion"] == "2025-11-25", b
        self.session = h.get("MCP-Session-Id")
        assert self.session, "no session id returned"
        s2, _, b2 = self._post({"method": "notifications/initialized",
                                "params": {}})
        assert s2 == 202 and b2 == b"", (s2, b2)

    def tool(self, name: str, arguments: dict):
        s, _, b = self._post({"method": "tools/call",
                              "params": {"name": name, "arguments": arguments}})
        assert s == 200, (s, b)
        return b


def start_ephemeral():
    """Real server on 127.0.0.1, OS-chosen port. Returns (server, client)."""
    srv = S.ThreadedMCPServer(("127.0.0.1", 0), S.MCPHandler)
    srv.auth = S.auth_mod.AuthRegistry()
    srv.broker = S.broker_mod.Broker(world_factory=F.strict_world)
    srv.sessions, srv.latencies, srv.rate_windows = {}, [], {}
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    return srv, MCPClient(srv.server_address[1], srv.auth.owner_token)


def stop_server(srv):
    try:
        srv.shutdown()
    finally:
        srv.server_close()


def main() -> int:
    ensure_utf8_stdout()
    srv, client = start_ephemeral()
    try:
        client.initialize()
        body = client.tool("prepare_day_brief", {
            "date": "2026-10-19",
            "timezone": "Asia/Kolkata",
            "request_key": "example-day-brief-000001",
        })
        r = body["result"]["structuredContent"]

        # The sealed-speech wire contract, asserted — not narrated.
        assert r["request_state"] == "accepted", r
        assert r["speak_policy"] == "verbatim_no_elaboration", r
        assert 20 <= len(r["request_ref"]) <= 128, r

        print("[wire] initialize ok (MCP 2025-11-25, session bound)")
        print(f"[wire] request_ref: {r['request_ref']}")
        print(f"[speak] {r['speak']}")
        print("OK: real MCP tool call returned a sealed constant-shape response")
        return 0
    finally:
        stop_server(srv)


if __name__ == "__main__":
    raise SystemExit(main())
