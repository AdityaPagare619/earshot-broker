"""Paired-world invariance at the wire (J3).

Counterfactual privacy (dossier §3.3, §14.3): change the hidden world —
appointment absent vs present, prenatal vs therapy title — and the PUBLIC
trace must not change. Compared at the HTTP layer: full JSON-RPC response
bodies, with only the opaque request_ref normalized (refs are random per
world by design; their randomness must not encode secret data either —
same shape asserted).
"""
import json
import re
import unittest

from harness import start_server  # noqa: E402  (inserts mcp/ into sys.path)
import fixtures as F  # noqa: E402

PORT_A = 8893
PORT_B = 8894
PORT_C = 8895
DATE = "2026-10-19"
TZ = "Asia/Kolkata"


def world_prenatal():
    return F.strict_world("Prenatal checkup", "City Clinic")


def world_therapy():
    return F.strict_world("Therapy session", "Mind Care Center")


def normalized_body(client, tool, args):
    """Full response with the opaque ref normalized at the dict level.

    The ref is random per world by design; everything else must be
    byte-identical across paired worlds.
    """
    b = client.tool(tool, args)
    r = b["result"]
    sc = dict(r["structuredContent"])
    sc["request_ref"] = "<REF>"
    text = json.loads(r["content"][0]["text"])
    text["request_ref"] = "<REF>"
    canon = {"structuredContent": sc, "isError": r["isError"],
             "text": json.dumps(text, sort_keys=True)}
    return json.dumps(canon, sort_keys=True)


class PairedWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv_a, cls.a = start_server(PORT_A, world_prenatal)
        cls.srv_b, cls.b = start_server(PORT_B, world_therapy)
        cls.srv_c, cls.c = start_server(PORT_C, F.empty_world)
        for cl in (cls.a, cls.b, cls.c):
            cl.initialize()

    @classmethod
    def tearDownClass(cls):
        for s in (cls.srv_a, cls.srv_b, cls.srv_c):
            s.shutdown()

    def _brief(self, client, key):
        return normalized_body(client, "prepare_day_brief",
                               {"date": DATE, "timezone": TZ, "request_key": key})

    def test_brief_invariant_across_secret_titles(self):
        pa = self._brief(self.a, "paired-key-00000001")
        pb = self._brief(self.b, "paired-key-00000001")
        self.assertEqual(pa, pb)

    def test_brief_invariant_secret_vs_no_secret(self):
        pa = self._brief(self.a, "paired-key-00000002")
        pc = self._brief(self.c, "paired-key-00000002")
        self.assertEqual(pa, pc)

    def test_brief_leaks_no_secret_tokens(self):
        for client in (self.a, self.b):
            blob = self._brief(client, "paired-key-00000003")
            for token in ("Prenatal", "Therapy", "Clinic", "Mind Care", "930", "15:30"):
                self.assertNotIn(token, blob)

    def test_resolve_invariant_across_worlds(self):
        def resolve_body(client, key):
            b = client.tool("prepare_day_brief",
                            {"date": DATE, "timezone": TZ, "request_key": key})
            ref = b["result"]["structuredContent"]["request_ref"]
            return normalized_body(client, "resolve_day_change", {
                "request_ref": ref,
                "change": {"kind": "find_alternative_window", "duration_minutes": 20,
                           "window_start": "2026-10-19T14:00:00+05:30",
                           "window_end": "2026-10-19T18:00:00+05:30"},
                "request_key": key + "-r"})
        ra = resolve_body(self.a, "paired-key-00000004")
        rb = resolve_body(self.b, "paired-key-00000004")
        rc = resolve_body(self.c, "paired-key-00000004")
        self.assertEqual(ra, rb)
        self.assertEqual(ra, rc)

    def test_ref_shape_constant(self):
        # The opaque ref must not vary in a secret-dependent way: fixed
        # token_urlsafe(24) shape in every world.
        for client in (self.a, self.b, self.c):
            b = client.tool("prepare_day_brief",
                            {"date": DATE, "timezone": TZ,
                             "request_key": "paired-key-00000005"})
            ref = b["result"]["structuredContent"]["request_ref"]
            self.assertRegex(ref, r"^[A-Za-z0-9_-]{32}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
