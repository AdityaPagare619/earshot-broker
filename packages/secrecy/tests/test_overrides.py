"""Effective clearance: min-only overlay; counterfactual invariance (S4)."""
import unittest

from earshot.secrecy.edges import EdgeProposal
from earshot.secrecy.overrides import effective_clearance
from earshot.secrecy.store import EdgeStore


def prop(**kw):
    base = dict(type="hidden_from", target="mom", until=None,
                confidence=0.9, direction="TIGHTEN", reason="t")
    base.update(kw)
    return EdgeProposal(**base)


BASE = {"priya": 4, "ravi": 4, "mom": 2, "role:guest": 1, "role:child": 1}
NOW = 1_730_000_000.0


class OverridesTest(unittest.TestCase):
    def test_hidden_from_zeroes_target(self):
        s = EdgeStore()
        s.add("itm_1", prop())
        out = effective_clearance("itm_1", BASE, s, NOW)
        self.assertEqual(out["mom"], 0)
        self.assertEqual(out["priya"], 4)  # untouched

    def test_unknown_target_defaults_to_zero_floor(self):
        s = EdgeStore()
        s.add("itm_1", prop(target="stranger"))
        out = effective_clearance("itm_1", BASE, s, NOW)
        self.assertEqual(out["stranger"], 0)

    def test_output_shape_matches_tablerow_clearance(self):
        s = EdgeStore()
        out = effective_clearance("itm_1", BASE, s, NOW)
        self.assertTrue(all(isinstance(k, str) and isinstance(v, int)
                            for k, v in out.items()))

    def test_informational_edges_do_not_raise(self):
        s = EdgeStore()
        s.add("itm_1", prop(type="for", target="maya"))
        s.add("itm_1", prop(type="about", target="health"))
        out = effective_clearance("itm_1", BASE, s, NOW)
        for k, v in BASE.items():
            self.assertLessEqual(out[k], v)

    def test_counterfactual_injected_loosen_changes_nothing(self):
        # The seam-I counterfactual: an injected LOOSEN proposal must leave
        # effective clearance byte-identical to the pre-injection world.
        s = EdgeStore()
        s.add("itm_1", prop())  # legitimate tighten
        before = effective_clearance("itm_1", BASE, s, NOW)
        # Adversary injects: LOOSEN with max confidence, no confirmation.
        s.add("itm_1", prop(direction="LOOSEN", confidence=1.0,
                            target="mom"),
              owner="priya")
        after = effective_clearance("itm_1", BASE, s, NOW)
        self.assertEqual(before, after)

    def test_global_scope_edges_apply_to_every_item(self):
        from earshot.secrecy.overrides import GLOBAL_SCOPE
        s = EdgeStore()
        s.add(GLOBAL_SCOPE, prop(target="mom"))
        # Item-specific call sees the global edge...
        out = effective_clearance("itm_9", BASE, s, NOW)
        self.assertEqual(out["mom"], 0)
        # ...and the global scope itself never double-applies.
        out2 = effective_clearance(GLOBAL_SCOPE, BASE, s, NOW)
        self.assertEqual(out2["mom"], 0)

    def test_expired_edge_restores_base(self):
        s = EdgeStore()
        s.add("itm_1", prop(until="2020-01-01"))
        out = effective_clearance("itm_1", BASE, s, NOW)
        self.assertEqual(out, {k: int(v) for k, v in BASE.items()})


if __name__ == "__main__":
    unittest.main()
