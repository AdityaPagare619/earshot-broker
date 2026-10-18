"""Tests: frozen contracts + quarantine state machine.

Run: python3 test_models.py (from this directory), or
PYTHONPATH=<repo> python3 -m unittest discover -s packages/slowlane/tests
"""
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.slowlane.models import (  # noqa: E402
    COMPILED, EXPIRED, QUARANTINED, RELEASED,
    IllegalTransition, Item, quarantine_new, transition,
)


def _item(state=QUARANTINED):
    return Item(id="itm_1", owner="priya", kind="event", source="gcal",
                start="2026-10-21T15:40+05:30", end="2026-10-21T16:00+05:30",
                raw_ref="vault://priya/itm_1", state=state,
                lang_detected=("en",))


class FrozenTest(unittest.TestCase):
    def test_frozen_dataclasses(self):
        item = _item()
        with self.assertRaises(Exception):
            item.state = COMPILED  # frozen

    def test_raw_ref_is_vault_ref_not_content(self):
        item = quarantine_new("itm_9", "priya", "event", "gcal")
        self.assertTrue(item.raw_ref.startswith("vault://"))
        self.assertNotIn("Oncology", item.raw_ref)


class QuarantineNewTest(unittest.TestCase):
    def test_new_items_always_quarantined(self):
        for kind in ("event", "reminder", "delivery", "note", "message_summary"):
            item = quarantine_new("x", "priya", kind, "gcal")
            self.assertEqual(item.state, QUARANTINED)


class TransitionsTest(unittest.TestCase):
    def test_legal_path(self):
        item = _item(QUARANTINED)
        item = transition(item, COMPILED)
        self.assertEqual(item.state, COMPILED)
        item = transition(item, RELEASED)
        self.assertEqual(item.state, RELEASED)
        item = transition(item, EXPIRED)
        self.assertEqual(item.state, EXPIRED)

    def test_recompile_stays_compiled(self):
        item = transition(_item(QUARANTINED), COMPILED)
        item = transition(item, COMPILED)
        self.assertEqual(item.state, COMPILED)

    def test_expire_from_any_state(self):
        for state in (QUARANTINED, COMPILED, RELEASED):
            item = transition(_item(state), EXPIRED)
            self.assertEqual(item.state, EXPIRED)

    def test_illegal_transitions_raise(self):
        illegal = [
            (QUARANTINED, RELEASED),   # skip compile
            (QUARANTINED, QUARANTINED),
            (COMPILED, QUARANTINED),   # no de-compilation
            (RELEASED, COMPILED),       # no un-release
            (EXPIRED, COMPILED),        # expired is terminal
            (RELEASED, QUARANTINED),
        ]
        for frm, to in illegal:
            with self.assertRaises(IllegalTransition, msg=f"{frm}->{to}"):
                transition(_item(frm), to)

    def test_unknown_state_raises(self):
        with self.assertRaises(IllegalTransition):
            transition(_item(), "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
