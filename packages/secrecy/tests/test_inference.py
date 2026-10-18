"""Heuristic inference on canonical fixtures (S4)."""
import unittest

from edges import EdgeProposal
from inference import (FixtureLLMProposer, HeuristicProposer, InferenceInput)


def item(**kw):
    base = dict(item_id="itm_1", kind="note", title="", notes="",
                participants=(), meta={})
    base.update(kw)
    return InferenceInput(**base)


class HeuristicTest(unittest.TestCase):
    def test_gift_for_names_recipient(self):
        ps = HeuristicProposer().propose(
            item(kind="delivery", title="Instax Mini 12 gift for Maya",
                 meta={"until": "2026-11-03"}))
        by_type = {}
        for p in ps:
            by_type.setdefault(p.type, []).append(p)
        self.assertIn("for", by_type)
        self.assertEqual(by_type["for"][0].target, "maya")
        hidden = [p for p in by_type.get("hidden_from", [])
                  if p.target == "maya"]
        self.assertTrue(hidden)
        self.assertEqual(hidden[0].until, "2026-11-03")

    def test_clinic_hides_from_guest_and_child(self):
        ps = HeuristicProposer().propose(
            item(title="OB-GYN checkup with Dr. Mehta at 3:40"))
        targets = {p.target for p in ps if p.type == "hidden_from"}
        self.assertIn("role:guest", targets)
        self.assertIn("role:child", targets)
        self.assertTrue(all(p.direction == "TIGHTEN" for p in ps))

    def test_financial_hides_from_guest(self):
        ps = HeuristicProposer().propose(item(title="Loan EMI due tomorrow"))
        targets = {p.target for p in ps if p.type == "hidden_from"}
        self.assertIn("role:guest", targets)
        self.assertNotIn("role:child", targets)

    def test_neutral_item_no_proposals(self):
        ps = HeuristicProposer().propose(
            item(title="Team standup at ten, groceries after five"))
        self.assertEqual(ps, [])

    def test_all_proposals_are_tighten(self):
        ps = HeuristicProposer().propose(
            item(title="Surprise birthday gift and dentist appointment"))
        self.assertTrue(ps)
        self.assertTrue(all(p.direction == "TIGHTEN" for p in ps))
        self.assertTrue(all(p.confidence >= 0.6 for p in ps))

    def test_confidences_are_documented_constants(self):
        import inference as inf
        self.assertEqual(inf.CONF_CLINIC, 0.75)
        self.assertEqual(inf.CONF_GIFT, 0.80)
        self.assertEqual(inf.CONF_MONEY, 0.70)


class FixtureLLMTest(unittest.TestCase):
    def test_fixture_never_emits_loosen(self):
        ps = FixtureLLMProposer().propose(
            item(kind="delivery", title="Instax Mini 12",
                 meta={"until": "2026-11-03"}))
        self.assertTrue(all(p.direction == "TIGHTEN" for p in ps))

    def test_fixture_names_maya(self):
        ps = FixtureLLMProposer().propose(
            item(kind="delivery", title="Instax Mini 12",
                 meta={"until": "2026-11-03"}))
        targets = {p.target for p in ps if p.type == "hidden_from"}
        self.assertIn("maya", targets)

    def test_proposer_interface_shape(self):
        # A future real model implements exactly this: propose() -> proposals.
        for cls in (HeuristicProposer, FixtureLLMProposer):
            ps = cls().propose(item(title="x"))
            self.assertTrue(all(isinstance(p, EdgeProposal) for p in ps))


if __name__ == "__main__":
    unittest.main()
