"""RR-11 regression: idempotent replay must not bypass belief re-evaluation.

Threat: `_check_idem` returned the cached sealed response BEFORE audience /
belief evaluation, so replaying a request_key from a permissive audience
state returned the permissive speech after the room tightened (needs the
victim's bearer token + the key — i.e. the room-facing client itself).

Fix: the idempotency slot binds an audience epoch (declaration count +
secrecy edge count + fixture audience). A replay after the room changed
re-plans against current belief; a replay with no change still hits the
cache (no double exposure commit).
"""
import json
import unittest

from earshot.gateway.mcp.tests.harness import start_server, stop_server  # noqa: E402

PORT = 8907
DATE = "2026-10-19"
TZ = "Asia/Kolkata"


class ReplayEpochTests(unittest.TestCase):
    """Full HTTP path: replay across a belief change re-plans."""

    @classmethod
    def setUpClass(cls):
        cls._port = 8907

    def setUp(self):
        # Fresh broker per test: secrecy edges and declarations must not
        # leak across tests (the keep_secret edge is the point of one test
        # and pollution for the next).
        type(self)._port += 1
        self.srv, self.c = start_server(type(self)._port)
        self.c.initialize()

    def tearDown(self):
        stop_server(self.srv)

    def _brief(self, key, **kw):
        args = {"date": DATE, "timezone": TZ, "request_key": key}
        args.update(kw)
        return self.c.tool("prepare_day_brief", args)["result"]

    def _room(self, key, declaration):
        return self.c.tool("room", {"declaration": declaration,
                                    "request_key": key})["result"]

    def test_replay_after_room_tightens_replans(self):
        """Owner alone -> chunk 2 speaks the secret (open). Mom declared
        present via the room tool -> replaying the SAME chunk key must
        re-plan to cover mode, not return the cached secret-bearing chunk."""
        self.srv.broker.set_fixture_audience(["priya"])
        try:
            r1 = self._brief("rr11-room-000001")
            self.assertEqual(r1["structuredContent"]["mode"], "open")
            ref = r1["structuredContent"]["request_ref"]

            r2 = self._brief("rr11-room-000001-c2", continuation_ref=ref)
            self.assertIn("Prenatal", r2["content"][0]["text"])  # permissive

            # The live path: a real `room` declaration tightens the room.
            self.srv.broker.clear_fixture_audience()
            self._room("rr11-room-000001-decl", "mom is here")
            self.assertEqual(len(self.srv.broker.declarations.all()), 1)

            # Replay the secret-bearing chunk key.
            r3 = self._brief("rr11-room-000001-c2", continuation_ref=ref)
            sc3 = r3["structuredContent"]
            self.assertEqual(sc3["mode"], "cover")
            blob = json.dumps(r3)
            for token in ("Prenatal", "City Clinic", "930"):
                self.assertNotIn(token, blob)

            # ...and idempotency still holds *within* the new epoch: an
            # immediate replay is identical, no double planning.
            r4 = self._brief("rr11-room-000001-c2", continuation_ref=ref)
            self.assertEqual(r3["structuredContent"]["speak"],
                             r4["structuredContent"]["speak"])
            self.assertEqual(r3["structuredContent"]["request_ref"],
                             r4["structuredContent"]["request_ref"])
        finally:
            self.srv.broker.clear_fixture_audience()

    def test_replay_after_keep_secret_replans(self):
        """A keep_secret edge drops clearance -> replaying the secret chunk
        key must re-plan (secret gone), not serve the pre-edge speech."""
        self.srv.broker.set_fixture_audience(["priya"])
        try:
            r1 = self._brief("rr11-ks-000002-xx")
            ref = r1["structuredContent"]["request_ref"]
            r2 = self._brief("rr11-ks-000002-c2", continuation_ref=ref)
            self.assertIn("Prenatal", r2["content"][0]["text"])  # permissive

            self.c.tool("keep_secret",
                        {"instruction": "keep my medical stuff private from everyone",
                         "request_key": "rr11-ks-000002-ks"})
            self.assertTrue(self.srv.broker.secrecy.item_ids())

            r3 = self._brief("rr11-ks-000002-c2", continuation_ref=ref)
            for token in ("Prenatal", "City Clinic"):
                self.assertNotIn(token, json.dumps(r3))
        finally:
            self.srv.broker.clear_fixture_audience()

    def test_conflicting_params_still_rejected_across_epochs(self):
        """Reusing a key with different params is a client bug even when
        the room changed between the calls."""
        self.srv.broker.set_fixture_audience(["priya"])
        try:
            self._brief("rr11-conflict-000003")
            self.srv.broker.clear_fixture_audience()
            self._room("rr11-conflict-000003-decl", "mom is here")
            bad = self.c.tool("prepare_day_brief",
                              {"date": "2026-10-20", "timezone": TZ,
                               "request_key": "rr11-conflict-000003"})
            self.assertIn("error", bad)
            self.assertIn("conflicting request_key", bad["error"]["message"])
        finally:
            self.srv.broker.clear_fixture_audience()


if __name__ == "__main__":
    unittest.main()
