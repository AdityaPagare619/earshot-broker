"""Gate truth table: the monotone acceptance rule, nailed down (S4)."""
import unittest

from edges import Confirmation, EdgeProposal
from gate import MonotoneGate


def prop(**kw):
    base = dict(type="hidden_from", target="mom", until=None,
                confidence=0.9, direction="TIGHTEN", reason="t")
    base.update(kw)
    return EdgeProposal(**base)


class GateTest(unittest.TestCase):
    def test_tighten_above_threshold_accepted(self):
        e = MonotoneGate.accept(prop(confidence=0.6))
        self.assertIsNotNone(e)
        self.assertEqual(e.provenance, "inferred")

    def test_tighten_below_threshold_dropped(self):
        self.assertIsNone(MonotoneGate.accept(prop(confidence=0.59)))

    def test_declared_source_preserved(self):
        e = MonotoneGate.accept(prop(confidence=1.0, claimed_source="declared"))
        self.assertEqual(e.provenance, "declared")

    def test_loosen_without_confirmation_dropped(self):
        self.assertIsNone(MonotoneGate.accept(prop(direction="LOOSEN")))

    def test_loosen_with_wrong_principal_dropped(self):
        c = Confirmation(principal="mallory", scope="s", at=1.0)
        self.assertIsNone(
            MonotoneGate.accept(prop(direction="LOOSEN"), confirmation=c,
                                owner="priya"))

    def test_loosen_with_valid_confirmation_accepted(self):
        c = Confirmation(principal="priya", scope="s", at=1.0)
        e = MonotoneGate.accept(prop(direction="LOOSEN", confidence=0.99),
                                confirmation=c, owner="priya")
        self.assertIsNotNone(e)
        self.assertEqual(e.provenance, "confirmed")
        self.assertEqual(e.direction, "LOOSEN")

    def test_loosen_confirmation_wrong_type_dropped(self):
        self.assertIsNone(
            MonotoneGate.accept(prop(direction="LOOSEN"),
                                confirmation="confirmed", owner="priya"))

    def test_garbage_enums_dropped_not_raised(self):
        self.assertIsNone(MonotoneGate.accept(prop(type="vaporize")))
        self.assertIsNone(MonotoneGate.accept(prop(direction="SIDEWAYS")))
        self.assertIsNone(MonotoneGate.accept(prop(target="   ")))

    def test_nan_inf_confidence_dropped(self):
        self.assertIsNone(MonotoneGate.accept(prop(confidence=float("nan"))))
        self.assertIsNone(MonotoneGate.accept(prop(confidence=float("inf"))))
        self.assertIsNone(MonotoneGate.accept(prop(confidence=1.5)))
        self.assertIsNone(MonotoneGate.accept(prop(confidence=True)))

    def test_until_empty_string_normalized(self):
        e = MonotoneGate.accept(prop(until=""))
        self.assertIsNotNone(e)
        self.assertIsNone(e.until)

    def test_non_proposal_dropped(self):
        self.assertIsNone(MonotoneGate.accept("hidden_from mom"))
        self.assertIsNone(MonotoneGate.accept(None))


if __name__ == "__main__":
    unittest.main()
