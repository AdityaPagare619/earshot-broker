"""Tests: quarantine store — the operational face of Seam 1."""
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))

from earshot.slowlane.models import COMPILED, IllegalTransition, QUARANTINED  # noqa: E402
from earshot.slowlane.quarantine import QuarantineError, QuarantineStore  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.store = QuarantineStore()

    def test_ingest_always_quarantined(self):
        item = self.store.ingest("itm_1", "priya", "event", "gcal")
        self.assertEqual(item.state, QUARANTINED)
        self.assertEqual(len(self.store.quarantined_items()), 1)
        self.assertEqual(len(self.store.compiled_items()), 0)

    def test_duplicate_ingest_rejected(self):
        self.store.ingest("itm_1", "priya", "event", "gcal")
        with self.assertRaises(QuarantineError):
            self.store.ingest("itm_1", "priya", "event", "gcal")

    def test_no_backdoor_to_compiled(self):
        # There is no store method that creates a COMPILED item directly:
        # the only path is transition() through the state machine.
        item = self.store.ingest("itm_1", "priya", "event", "gcal")
        with self.assertRaises(IllegalTransition):
            self.store.transition("itm_1", "RELEASED")  # skip COMPILED
        self.assertEqual(self.store.get("itm_1").state, QUARANTINED)

    def test_transition_records(self):
        self.store.ingest("itm_1", "priya", "event", "gcal")
        item = self.store.transition("itm_1", COMPILED)
        self.assertEqual(item.state, COMPILED)
        self.assertEqual(len(self.store.compiled_items()), 1)


if __name__ == "__main__":
    unittest.main()
