"""Tool behavior tests — the 4 tools against the real kernel (J3).

Includes the J6-R1 regression: request_key guessing across owners/tenants
must not leak receipts; unknown vs forbidden references are indistinguishable.
"""
import unittest

from harness import Client, start_server

PORT = 8892
DATE = "2026-10-19"
TZ = "Asia/Kolkata"


def brief_args(key):
    return {"date": DATE, "timezone": TZ, "request_key": key}


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.c = start_server(PORT)
        cls.c.initialize()
        cls.member = Client(PORT, cls.srv.auth.member_token)
        cls.member.initialize()
        cls.other = Client(PORT, cls.srv.auth.other_tenant_token)
        cls.other.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    # -- prepare_day_brief -------------------------------------------------

    def test_brief_happy_path(self):
        b = self.c.tool("prepare_day_brief", brief_args("brief-happy-000001"))
        r = b["result"]["structuredContent"]
        self.assertEqual(r["request_state"], "accepted")
        self.assertTrue(20 <= len(r["request_ref"]) <= 128)
        self.assertEqual(r["public_facts"],
                         ["Collect groceries after 6.", "Dinner prep at 7 PM."])
        # text and structuredContent derive from the same projection
        import json
        self.assertEqual(json.loads(b["result"]["content"][0]["text"]), r)

    def test_brief_idempotent_same_key(self):
        b1 = self.c.tool("prepare_day_brief", brief_args("brief-idem-00000002"))
        b2 = self.c.tool("prepare_day_brief", brief_args("brief-idem-00000002"))
        self.assertEqual(b1["result"]["structuredContent"]["request_ref"],
                         b2["result"]["structuredContent"]["request_ref"])

    def test_brief_conflicting_key_reuse_rejected(self):
        args = brief_args("brief-conflict-00003")
        self.c.tool("prepare_day_brief", args)
        bad = dict(args, date="2026-10-20")
        b = self.c.tool("prepare_day_brief", bad)
        self.assertEqual(b["error"]["code"], -32602)
        self.assertIn("request_key", b["error"]["message"])

    def test_brief_bad_date(self):
        b = self.c.tool("prepare_day_brief", brief_args("k4").copy() | {"date": "2026-13-99"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_brief_bad_timezone(self):
        b = self.c.tool("prepare_day_brief",
                        {"date": DATE, "timezone": "Mars/Olympus",
                         "request_key": "brief-badtz-0000004"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_brief_short_key(self):
        b = self.c.tool("prepare_day_brief",
                        {"date": DATE, "timezone": TZ, "request_key": "short"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_brief_extra_property_rejected(self):
        args = brief_args("brief-extra-000005") | {"tenant": "house-a"}
        b = self.c.tool("prepare_day_brief", args)
        self.assertEqual(b["error"]["code"], -32602)

    # -- J6-R1: cross-owner / cross-tenant key guessing ---------------------

    def test_same_key_different_owner_yields_different_receipt(self):
        """Guessing the victim's request_key must not return their receipt."""
        key = "r1-shared-key-0000006"
        b_owner = self.c.tool("prepare_day_brief", brief_args(key))
        b_member = self.member.tool("prepare_day_brief", brief_args(key))
        self.assertNotEqual(
            b_owner["result"]["structuredContent"]["request_ref"],
            b_member["result"]["structuredContent"]["request_ref"])

    def test_member_cannot_use_owner_ref(self):
        b = self.c.tool("prepare_day_brief", brief_args("r1-owner-ref-000007"))
        ref = b["result"]["structuredContent"]["request_ref"]
        # Same tenant, non-owner member tries the owner's reference.
        r = self.member.tool("continue_on_personal_device",
                             {"request_ref": ref, "request_key": "r1-mem-key-0000008"})
        self.assertEqual(r["error"]["code"], -32603)
        self.assertEqual(r["error"]["message"], "Unavailable")

    def test_unknown_ref_indistinguishable_from_forbidden(self):
        r1 = self.c.tool("continue_on_personal_device",
                         {"request_ref": "esh_" + "x" * 40,
                          "request_key": "r1-unk-0000000009"})
        # other tenant, validly-shaped but nonexistent ref
        r2 = self.other.tool("continue_on_personal_device",
                             {"request_ref": "esh_" + "y" * 40,
                              "request_key": "r1-unk-0000000010"})
        self.assertEqual(r1["error"], r2["error"])
        self.assertEqual(r1["error"]["message"], "Unavailable")

    # -- resolve_day_change --------------------------------------------------

    def _mk_ref(self, key):
        b = self.c.tool("prepare_day_brief", brief_args(key))
        return b["result"]["structuredContent"]["request_ref"]

    def test_resolve_strict_returns_no_time(self):
        ref = self._mk_ref("res-strict-00000011")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "find_alternative_window", "duration_minutes": 20,
                       "window_start": "2026-10-19T14:00:00+05:30",
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "res-strict-key-00012"})
        r = b["result"]["structuredContent"]
        self.assertEqual(r["request_state"], "accepted")
        # Strict fixture: no time suggestion — window/no-window is secret-dependent.
        self.assertEqual(r["public_facts"], [])

    def test_resolve_add_block_is_draft_only(self):
        ref = self._mk_ref("res-draft-000000013")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "add_flexible_block", "duration_minutes": 20,
                       "window_start": "2026-10-19T14:00:00+05:30",
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "res-draft-key-000014"})
        r = b["result"]["structuredContent"]
        self.assertIn("Draft prepared", r["public_facts"][0])

    def test_resolve_bad_duration(self):
        ref = self._mk_ref("res-baddur-0000015")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "find_alternative_window", "duration_minutes": 241,
                       "window_start": "2026-10-19T14:00:00+05:30",
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "res-baddur-key-0016"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_resolve_inverted_window(self):
        ref = self._mk_ref("res-invwin-0000017")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "find_alternative_window", "duration_minutes": 20,
                       "window_start": "2026-10-19T18:00:00+05:30",
                       "window_end": "2026-10-19T14:00:00+05:30"},
            "request_key": "res-invwin-key-0018"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_resolve_bad_kind(self):
        ref = self._mk_ref("res-badkind-000019")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "teleport", "duration_minutes": 20,
                       "window_start": "2026-10-19T14:00:00+05:30",
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "res-badkind-key-020"})
        self.assertEqual(b["error"]["code"], -32602)

    def test_resolve_naive_datetime_rejected(self):
        ref = self._mk_ref("res-naive-00000021")
        b = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "find_alternative_window", "duration_minutes": 20,
                       "window_start": "2026-10-19T14:00:00",   # no offset
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "res-naive-key-00022"})
        self.assertEqual(b["error"]["code"], -32602)

    # -- continue_on_personal_device ------------------------------------------

    def test_continue_queues_idempotently(self):
        ref = self._mk_ref("cont-q-00000000023")
        a1 = {"request_ref": ref, "request_key": "cont-q-key-00000024"}
        r1 = self.c.tool("continue_on_personal_device", a1)
        r2 = self.c.tool("continue_on_personal_device", a1)
        self.assertEqual(r1["result"]["structuredContent"]["request_state"], "accepted")
        self.assertEqual(r1["result"], r2["result"])
        # queued, never delivered: the outbox holds it, no delivery claim made
        self.assertIn("queued", r1["result"]["structuredContent"]["public_facts"][0].lower())

    # -- withdraw_request -------------------------------------------------------

    def test_withdraw_then_ref_unusable(self):
        ref = self._mk_ref("wd-0000000000000025")
        w = self.c.tool("withdraw_request",
                        {"request_ref": ref, "request_key": "wd-key-0000000026"})
        self.assertEqual(w["result"]["structuredContent"]["request_state"], "accepted")
        self.assertIn("cannot be retracted",
                      w["result"]["structuredContent"]["public_facts"][0])
        r = self.c.tool("continue_on_personal_device",
                        {"request_ref": ref, "request_key": "wd-key-0000000027"})
        self.assertEqual(r["error"]["message"], "Unavailable")

    # -- error hygiene ------------------------------------------------------------

    def test_errors_carry_no_private_values(self):
        import json as _j
        secret_marker = "Prenatal"
        b = self.c.tool("prepare_day_brief", brief_args("err-hyg-00000028"))
        ref = b["result"]["structuredContent"]["request_ref"]
        bad = self.c.tool("resolve_day_change", {
            "request_ref": ref,
            "change": {"kind": "nope", "duration_minutes": 20,
                       "window_start": "2026-10-19T14:00:00+05:30",
                       "window_end": "2026-10-19T18:00:00+05:30"},
            "request_key": "err-hyg-key-00029"})
        blob = _j.dumps(bad)
        self.assertNotIn(secret_marker, blob)
        self.assertNotIn("City Clinic", blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
