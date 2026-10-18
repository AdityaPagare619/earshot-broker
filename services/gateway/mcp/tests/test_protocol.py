"""Protocol compliance tests — MCP 2025-11-25 Streamable HTTP (J3).

Every assertion targets a MUST/SHOULD from the transport spec, verified
first-hand. No SDK, no mocks: real HTTP against the real server.
"""
import unittest

from harness import Client, start_server

PORT = 8891


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.c = start_server(PORT)
        cls.c.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    # -- lifecycle ------------------------------------------------------

    def test_initialize_negotiates_2025_11_25(self):
        c = Client(PORT, self.srv.auth.owner_token)
        body = c.initialize()
        self.assertEqual(body["result"]["serverInfo"]["name"], "earshot-broker")
        caps = body["result"]["capabilities"]
        self.assertIn("tools", caps)

    def test_initialize_newer_client_negotiates_down(self):
        # A client proposing 2026-07-28 gets our pinned 2025-11-25 answer.
        c = Client(PORT, self.srv.auth.owner_token)
        s, _, b = c.call({"method": "initialize",
                          "params": {"protocolVersion": "2026-07-28",
                                     "capabilities": {},
                                     "clientInfo": {"name": "x", "version": "1"}}})
        self.assertEqual(s, 200)
        self.assertEqual(b["result"]["protocolVersion"], "2025-11-25")

    def test_initialize_requires_auth(self):
        c = Client(PORT, None)
        s, _, _ = c.call({"method": "initialize",
                          "params": {"protocolVersion": "2025-11-25",
                                     "capabilities": {}, "clientInfo": {}}})
        self.assertEqual(s, 401)

    def test_initialize_bad_token_rejected(self):
        c = Client(PORT, "esh_dev_bogus")
        s, _, b = c.call({"method": "initialize",
                          "params": {"protocolVersion": "2025-11-25",
                                     "capabilities": {}, "clientInfo": {}}})
        self.assertEqual(s, 401)

    def test_initialize_bad_params(self):
        c = Client(PORT, self.srv.auth.owner_token)
        s, _, b = c.call({"method": "initialize", "params": {"capabilities": {}}})
        self.assertEqual(s, 200)
        self.assertEqual(b["error"]["code"], -32602)

    # -- session management ----------------------------------------------

    def test_missing_session_id_is_400(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        c.session = None  # drop it
        s, _, b = c.post({"jsonrpc": "2.0", "id": 99, "method": "tools/list",
                          "params": {}})
        # No session header at all -> 400 (auth header still present).
        self.assertEqual(s, 400)

    def test_unknown_session_id_is_404(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        c.session = "esh_deadbeef_nope"
        s, _, _ = c.post({"jsonrpc": "2.0", "id": 99, "method": "tools/list",
                          "params": {}})
        self.assertEqual(s, 404)

    def test_expired_session_is_404(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        self.srv.sessions[c.session]["last_seen"] -= 4000  # > 30 min idle
        s, _, _ = c.post({"jsonrpc": "2.0", "id": 99, "method": "tools/list",
                          "params": {}})
        self.assertEqual(s, 404)

    def test_version_header_mismatch_is_400(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        s, _, _ = c.post({"jsonrpc": "2.0", "id": 99, "method": "tools/list",
                          "params": {}},
                         headers={"MCP-Protocol-Version": "2026-07-28"})
        self.assertEqual(s, 400)

    # -- transport surface -------------------------------------------------

    def test_tools_list_names(self):
        s, _, b = self.c.call({"method": "tools/list", "params": {}})
        self.assertEqual(s, 200)
        names = [t["name"] for t in b["result"]["tools"]]
        # S4: the surface grew to the final 6 tools (room + keep_secret).
        self.assertEqual(names, ["prepare_day_brief", "resolve_day_change",
                                 "continue_on_personal_device",
                                 "withdraw_request", "room", "keep_secret"])

    def test_tools_list_schemas_bounded(self):
        s, _, b = self.c.call({"method": "tools/list", "params": {}})
        for t in b["result"]["tools"]:
            sch = t["inputSchema"]
            self.assertEqual(sch["type"], "object")
            self.assertFalse(sch.get("additionalProperties", True))

    def test_get_is_405(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/mcp",
            headers={"Authorization": f"Bearer {self.srv.auth.owner_token}"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 405)

    def test_delete_is_405(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/mcp", method="DELETE",
            headers={"Authorization": f"Bearer {self.srv.auth.owner_token}"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 405)

    def test_wrong_path_is_404(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.base = f"http://127.0.0.1:{PORT}/nope"
        s, _, _ = c.call({"method": "tools/list", "params": {}})
        self.assertEqual(s, 404)

    def test_invalid_origin_is_403(self):
        c = Client(PORT, self.srv.auth.owner_token)
        s, _, _ = c.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                          "params": {}},
                         headers={"Origin": "https://evil.example"})
        self.assertEqual(s, 403)

    def test_localhost_origin_allowed(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        s, _, b = c.post({"jsonrpc": "2.0", "id": 77, "method": "tools/list",
                          "params": {}},
                         headers={"Origin": "http://127.0.0.1:3000"})
        self.assertEqual(s, 200)

    def test_oversize_body_is_413(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        s, _, _ = c.raw_post(b"x" * ((1 << 20) + 1))
        self.assertEqual(s, 413)

    def test_malformed_json_is_parse_error(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        s, _, b = c.raw_post(b"{not json")
        body = __import__("json").loads(b.decode())
        self.assertEqual(s, 200)
        self.assertEqual(body["error"]["code"], -32700)

    def test_unknown_method(self):
        s, _, b = self.c.call({"method": "prompts/list", "params": {}})
        self.assertEqual(s, 200)
        self.assertEqual(b["error"]["code"], -32601)

    def test_unknown_tool(self):
        s, _, b = self.c.call({"method": "tools/call",
                               "params": {"name": "get_secret", "arguments": {}}})
        self.assertEqual(s, 200)
        self.assertIn("error", b)

    def test_batch_rejected(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        s, _, b = c.raw_post(b'[{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}]')
        body = __import__("json").loads(b.decode())
        self.assertEqual(body["error"]["code"], -32600)

    # -- resources (public-safe only) --------------------------------------

    def test_resources_empty_before_brief(self):
        s, _, b = self.c.call({"method": "resources/list", "params": {}})
        self.assertEqual(s, 200)
        self.assertEqual(b["result"]["resources"], [])

    def test_day_card_resource(self):
        c = Client(PORT, self.srv.auth.owner_token)
        c.initialize()
        b = c.tool("prepare_day_brief",
                   {"date": "2026-10-19", "timezone": "Asia/Kolkata",
                    "request_key": "card-key-0000000001"})
        ref = b["result"]["structuredContent"]["request_ref"]
        s, _, bl = c.call({"method": "resources/list", "params": {}})
        self.assertEqual(len(bl["result"]["resources"]), 1)
        res = bl["result"]["resources"][0]
        self.assertEqual(res["uri"], "ui://earshot/day-card")
        s, _, br = c.call({"method": "resources/read",
                           "params": {"uri": "ui://earshot/day-card"}})
        import json as _j
        card = _j.loads(br["result"]["contents"][0]["text"])
        self.assertEqual(card["request_ref"], ref)
        # S3: the card is the sealed-speech contract — no public_facts list,
        # no counts, fixed suffix always appended.
        self.assertEqual(card["speak_policy"], "verbatim_no_elaboration")
        self.assertNotIn("public_facts", card)
        self.assertTrue(card["speak"].endswith("The rest of your day is on your phone."))
        blob = _j.dumps(card)
        for token in ("Prenatal", "Therapy", "Clinic", "930"):
            self.assertNotIn(token, blob)

    def test_resources_read_unknown_uri(self):
        s, _, b = self.c.call({"method": "resources/read",
                               "params": {"uri": "ui://earshot/secrets"}})
        self.assertEqual(s, 200)
        self.assertEqual(b["error"]["code"], -32602)

    def test_rate_limit(self):
        tok = self.srv.auth.add("house-a", "priya")
        c = Client(PORT, tok)
        c.initialize()
        codes = set()
        for i in range(105):
            s, _, _ = c.post({"jsonrpc": "2.0", "id": i, "method": "tools/list",
                              "params": {}})
            codes.add(s)
        self.assertIn(429, codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
