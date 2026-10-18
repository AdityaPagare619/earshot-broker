"""MCP client conformance tests (stdlib unittest; no pytest needed)."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp_client import McpClient, McpError, PROTOCOL_VERSION

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling test helper
from protocol_conformance_harness import run_harness


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.server, self.state, self.port = run_harness()
        self.url = f"http://127.0.0.1:{self.port}/mcp"

    def tearDown(self):
        self.server.shutdown()

    def test_initialize_negotiates_pinned_version(self):
        c = McpClient(self.url).connect()
        self.assertTrue(c.connected)
        self.assertEqual(c.server_info["name"], "harness")
        methods = [m for m, _, _ in self.state.seen]
        self.assertIn("initialize", methods)
        self.assertIn("notifications/initialized", methods)

    def test_wrong_protocol_version_rejected(self):
        server, state, port = run_harness(protocol_version="2026-07-28")
        try:
            with self.assertRaises(McpError):
                McpClient(f"http://127.0.0.1:{port}/mcp").connect()
        finally:
            server.shutdown()

    def test_session_id_sent_after_init(self):
        c = McpClient(self.url).connect()
        c.list_tools()
        by_method = {m: h for m, h, _ in self.state.seen}
        self.assertEqual(by_method["tools/list"]["mcp-session-id"],
                         "harness-session-1")
        self.assertEqual(by_method["tools/list"]["mcp-protocol-version"],
                         PROTOCOL_VERSION)

    def test_tools_list_and_call(self):
        c = McpClient(self.url).connect()
        tools = c.list_tools()
        self.assertEqual([t["name"] for t in tools], ["prepare_day_brief"])
        res = c.call_tool("prepare_day_brief", {"date": "2026-10-18"})
        self.assertEqual(res["structuredContent"], {"echo": "prepare_day_brief"})
        self.assertEqual(res["content"][0]["text"], "ok")

    def test_tool_error_raises(self):
        c = McpClient(self.url).connect()
        with self.assertRaises(McpError) as cm:
            c.call_tool("boom", {})
        self.assertIn("simulated tool failure", str(cm.exception))

    def test_unknown_method_error_raises(self):
        c = McpClient(self.url).connect()
        with self.assertRaises(McpError):
            c._request("nope/method")

    def test_bare_json_response_parsed(self):
        server, state, port = run_harness()
        try:
            c = McpClient(f"http://127.0.0.1:{port}/mcp-bare").connect()
            # /mcp-bare returns bare JSON instead of SSE framing
            self.assertTrue(c.connected)
            self.assertEqual(c.list_tools()[0]["name"], "prepare_day_brief")
        finally:
            server.shutdown()

    def test_http_error_raises(self):
        self.state.fail_next_with = 500
        c = McpClient(self.url)
        with self.assertRaises(McpError) as cm:
            c.initialize()
        self.assertIn("HTTP 500", str(cm.exception))

    def test_connection_refused_raises(self):
        c = McpClient("http://127.0.0.1:1/mcp", timeout=1)
        with self.assertRaises(McpError):
            c.initialize()

    def test_resources(self):
        c = McpClient(self.url).connect()
        res = c.list_resources()
        self.assertEqual(res[0]["uri"], "ui://harness/card")


if __name__ == "__main__":
    unittest.main(verbosity=2)
