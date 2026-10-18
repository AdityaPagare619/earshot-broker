"""GatewayPort backend tests: mcp path over real HTTP, kernel_direct path."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "packages", "kernel"))
from gateway_port import GatewayPort
from protocol_conformance_harness import run_harness


class GatewayPortTests(unittest.TestCase):
    def test_kernel_direct_is_default_without_url(self):
        os.environ.pop("EARSHOT_GATEWAY_URL", None)
        p = GatewayPort()
        self.assertEqual(p.backend, "kernel_direct")
        st = p.connect()
        self.assertIn("prepare_day_brief", st["tools"])
        res = p.call_tool("prepare_day_brief",
                          {"date": "2026-10-18", "timezone": "Asia/Kolkata",
                           "request_key": "k" * 20})
        self.assertEqual(res["request_state"], "accepted")
        self.assertIn("request_ref", res)
        # The sealed-speech contract carries no private markers in cover...
        # (default port audience: live path, no declarations)
        self.assertEqual(res["speak_policy"], "verbatim_no_elaboration")

    def test_mcp_backend_over_real_http(self):
        server, state, port = run_harness()
        try:
            p = GatewayPort(gateway_url=f"http://127.0.0.1:{port}/mcp")
            self.assertEqual(p.backend, "mcp")
            st = p.connect()
            self.assertIsNone(st["degraded"])
            self.assertIn("prepare_day_brief", st["tools"])
            res = p.call_tool("prepare_day_brief", {"date": "2026-10-18"})
            self.assertEqual(res["structuredContent"],
                             {"echo": "prepare_day_brief"})
            self.assertIn("_round_trip_ms", res)
        finally:
            server.shutdown()

    def test_mcp_backend_failure_is_visible_not_silent(self):
        p = GatewayPort(gateway_url="http://127.0.0.1:1/mcp")
        st = p.connect()
        self.assertIsNotNone(st["degraded"])
        self.assertIsNotNone(p.degraded)

    def test_personal_surface_requires_auth(self):
        p = GatewayPort()
        acc = p.call_tool("prepare_day_brief",
                          {"date": "2026-10-18", "timezone": "Asia/Kolkata",
                           "request_key": "k" * 21})
        denied = p.open_personal(acc["request_ref"], authenticated=False)
        self.assertFalse(denied["ok"])
        ok = p.open_personal(acc["request_ref"], authenticated=True)
        self.assertTrue(ok["ok"])
        self.assertTrue(any("Prenatal" in f["value"] for f in ok["facts"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
