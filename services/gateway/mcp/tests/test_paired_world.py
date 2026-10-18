"""Paired-world invariance at the wire — Seam 3 (S3).

Counterfactual privacy (dossier §3.3, §14.3): change the hidden world and the
FULL HTTP response body must not change — modulo the two opaque values (the
request ref and the plan id, both random by design, both shape-pinned).

The subtle point this suite gets right: byte-identical counterfactuals are
secret-swaps under FIXED audiences. mom-vs-mom+guest is NOT byte-identical —
the audience legitimately differs, so the planner generalizes further. The
tests pin both directions:

  FIXED audience, swapped secret  -> byte-identical (the guarantee)
  CHANGED audience, same secret   -> MAY differ (legitimate; and the diff is
                                     itself constant-shape)

Plus a negative control (mislabel the secret block public -> the body MUST
differ and MUST contain the secret token: proves the suite has teeth), an
open-mode utility test (anti-over-redaction), and chunked-turn invariance.
"""
import json
import unittest

from earshot.gateway.mcp.tests.harness import start_server, stop_server  # noqa: E402
from earshot.gateway.mcp import fixtures as F  # noqa: E402

PORT_A = 8893
PORT_B = 8894
PORT_C = 8895
PORT_D = 8901
DATE = "2026-10-19"
TZ = "Asia/Kolkata"

SECRET_TOKENS = ("Prenatal", "Therapy", "City Clinic", "Mind Care", "930")


def world_prenatal():
    return F.strict_world("Prenatal checkup", "City Clinic")


def world_therapy():
    return F.strict_world("Therapy session", "Mind Care Center")


def world_mislabeled():
    """NEGATIVE CONTROL: the secret block mislabeled household-public.

    If the planner/assembler ever let a mislabeled secret through, the wire
    body must differ from the strict world's AND contain the secret token.
    """
    w = F.strict_world("Prenatal checkup", "City Clinic")
    busy = tuple(
        F.BusyBlock(b.start_min, b.end_min, b.title, b.location,
                    public_title=True, readers=frozenset({"priya", "mom"}))
        if b.start_min == 930 else b
        for b in w.busy)
    return F.FixtureWorld(w.name, w.tenant, w.owner,
                          w.public_derived_schedule, w.protect_existence,
                          busy, w.flex, w.public_facts)


def normalized_body(client, tool, args):
    """Full wire body with the two opaque values normalized at the dict
    level. The ref and plan_id are random per world by design; everything
    else must be byte-identical across paired worlds."""
    b = client.tool(tool, args)
    r = b["result"]
    sc = dict(r["structuredContent"])
    sc["request_ref"] = "<REF>"
    sc["_meta"] = dict(sc["_meta"])
    sc["_meta"]["earshot/plan_id"] = "<PLAN>"
    text = r["content"][0]["text"]
    # The envelope property: content[0].text IS the speak text, verbatim.
    assert text == sc["speak"], "envelope violated: content != speak"
    canon = {"speak": text, "structuredContent": sc,
             "isError": r["isError"]}
    return json.dumps(canon, sort_keys=True)


class PairedWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv_a, cls.a = start_server(PORT_A, world_prenatal)
        cls.srv_b, cls.b = start_server(PORT_B, world_therapy)
        cls.srv_c, cls.c = start_server(PORT_C, F.empty_world)
        cls.srv_d, cls.d = start_server(PORT_D, world_mislabeled)
        for cl in (cls.a, cls.b, cls.c, cls.d):
            cl.initialize()
        # FIXED cover audience for the invariance pairs: mom is credibly
        # present in both worlds. (The audience is the room's knowledge —
        # fixed across a pair by construction.)
        for srv in (cls.srv_a, cls.srv_b, cls.srv_c, cls.srv_d):
            srv.broker.set_fixture_audience(["priya", "mom"])

    @classmethod
    def tearDownClass(cls):
        for s in (cls.srv_a, cls.srv_b, cls.srv_c, cls.srv_d):
            stop_server(s)

    def _brief(self, client, key, **kw):
        args = {"date": DATE, "timezone": TZ, "request_key": key}
        args.update(kw)
        return normalized_body(client, "prepare_day_brief", args)

    def _ref_of(self, client, key):
        b = client.tool("prepare_day_brief",
                        {"date": DATE, "timezone": TZ, "request_key": key})
        return b["result"]["structuredContent"]["request_ref"]

    # -- the guarantee: fixed audience, swapped secret -> byte-identical -----

    def test_brief_invariant_across_secret_titles(self):
        pa = self._brief(self.a, "paired-key-00000001")
        pb = self._brief(self.b, "paired-key-00000001")
        self.assertEqual(pa, pb)

    def test_brief_invariant_secret_vs_no_secret(self):
        pa = self._brief(self.a, "paired-key-00000002")
        pc = self._brief(self.c, "paired-key-00000002")
        self.assertEqual(pa, pc)

    def test_next_chunk_invariant_across_secret_titles(self):
        """Chunked turns: every chunk byte-identical across the secret swap."""
        ra = self._ref_of(self.a, "paired-chunk-000003")
        rb = self._ref_of(self.b, "paired-chunk-000003")
        for i in range(4):
            na = self._brief(self.a, f"paired-chunk-a-{i}",
                             continuation_ref=ra)
            nb = self._brief(self.b, f"paired-chunk-b-{i}",
                             continuation_ref=rb)
            self.assertEqual(na, nb)

    def test_brief_leaks_no_secret_tokens(self):
        for client in (self.a, self.b, self.c):
            blob = self._brief(client, "paired-key-00000004")
            for token in SECRET_TOKENS:
                self.assertNotIn(token, blob)

    def test_resolve_invariant_across_worlds(self):
        def resolve_body(client, key):
            ref = self._ref_of(client, key)
            return normalized_body(client, "resolve_day_change", {
                "request_ref": ref,
                "change": {"kind": "find_alternative_window",
                           "duration_minutes": 20,
                           "window_start": "2026-10-19T14:00:00+05:30",
                           "window_end": "2026-10-19T18:00:00+05:30"},
                "request_key": key + "-r"})
        ra = resolve_body(self.a, "paired-key-00000005")
        rb = resolve_body(self.b, "paired-key-00000005")
        rc = resolve_body(self.c, "paired-key-00000005")
        self.assertEqual(ra, rb)
        self.assertEqual(ra, rc)

    # -- the negative control: the suite must have teeth --------------------

    def test_negative_control_mislabeled_secret_changes_body(self):
        """Mislabel the secret block household-public: the body MUST differ
        from the strict world's and MUST contain the secret token. If this
        ever passes while the invariance tests pass, the suite is blind."""
        pa = self._brief(self.a, "paired-key-00000006")
        pd = self._brief(self.d, "paired-key-00000006")
        self.assertNotEqual(pa, pd)
        self.assertIn("Prenatal", pd)

    # -- the other direction: changed audience MAY differ (legitimately) -----

    def test_changed_audience_may_differ_but_stays_constant_shape(self):
        """Mom leaves mid-stream: the next chunk re-plans against fresh
        belief. The body may differ (the audience legitimately changed) but
        it must still be constant-shape: fixed suffix, no counts."""
        self.srv_a.broker.set_fixture_audience(["priya"])  # mom leaves
        try:
            blob = self._brief(self.a, "paired-key-00000007")
        finally:
            self.srv_a.broker.set_fixture_audience(["priya", "mom"])
        body = json.loads(blob)
        speak = body["speak"]
        self.assertTrue(speak.endswith("The rest of your day is on your phone."))
        for token in SECRET_TOKENS:
            self.assertNotIn(token, blob)

    # -- open-mode utility: no over-redaction --------------------------------

    def test_open_mode_owner_hears_own_appointment(self):
        """Owner alone: the planner speaks the owner's own appointment at d4
        (in a later chunk — constant shape must not mean constant silence).
        Walks the chunked turns to prove the appointment is delivered."""
        self.srv_a.broker.set_fixture_audience(["priya"])
        try:
            key0 = "paired-key-00000008"
            b = self.a.tool("prepare_day_brief",
                            {"date": DATE, "timezone": TZ, "request_key": key0})
            sc = b["result"]["structuredContent"]
            self.assertEqual(sc["mode"], "open")
            speaks = [b["result"]["content"][0]["text"]]
            ref = sc["request_ref"]
            for i in range(6):
                if "next" not in sc["followups"]:
                    break
                b = self.a.tool(
                    "prepare_day_brief",
                    {"date": DATE, "timezone": TZ,
                     "request_key": f"paired-key-00000008-n{i}",
                     "continuation_ref": ref})
                sc = b["result"]["structuredContent"]
                speaks.append(b["result"]["content"][0]["text"])
        finally:
            self.srv_a.broker.set_fixture_audience(["priya", "mom"])
        self.assertTrue(any("Prenatal checkup" in s for s in speaks),
                        f"appointment never spoken: {speaks}")

    # -- opaque values: random, but shape-pinned ------------------------------

    def test_ref_and_plan_id_shapes_constant(self):
        for client in (self.a, self.b, self.c):
            b = client.tool("prepare_day_brief",
                            {"date": DATE, "timezone": TZ,
                             "request_key": "paired-key-00000009"})
            sc = b["result"]["structuredContent"]
            self.assertRegex(sc["request_ref"], r"^[A-Za-z0-9_-]{32}$")
            self.assertRegex(sc["_meta"]["earshot/plan_id"], r"^pln_[0-9a-f]{16}$")
            self.assertEqual(sc["_meta"]["earshot/table_version"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
