"""Tests: confirm queue — it can only make you quieter."""
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent))

from slowlane.confirm import ConfirmError, ConfirmQueue  # noqa: E402
from slowlane.models import SecrecyEdge  # noqa: E402


def _edge(conf=0.45, direction="TIGHTEN"):
    return SecrecyEdge(type="hidden_from", target="mom", until="2026-11-15",
                       provenance="inferred", confidence=conf,
                       direction=direction)


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.q = ConfirmQueue(ttl_s=100, clock=self.clock)

    def test_ambiguous_edge_queued(self):
        entry = self.q.submit_edge(_edge(conf=0.45), "Keep from Mom?")
        self.assertEqual(len(self.q.pending()), 1)
        self.assertEqual(entry.kind, "edge_confirm")

    def test_high_confidence_not_queued(self):
        with self.assertRaises(ConfirmError):
            self.q.submit_edge(_edge(conf=0.9), "Keep from Mom?")

    def test_low_confidence_not_queued(self):
        with self.assertRaises(ConfirmError):
            self.q.submit_edge(_edge(conf=0.2), "Keep from Mom?")

    def test_loosen_never_queued(self):
        with self.assertRaises(ConfirmError):
            self.q.submit_edge(_edge(direction="LOOSEN", conf=0.5), "Release?")

    def test_unauthenticated_loosen_rejected_not_queued(self):
        with self.assertRaises(ConfirmError):
            self.q.submit_loosen(_edge(direction="LOOSEN"), "Release?",
                                 authenticated=False)
        self.assertEqual(len(self.q.pending()), 0)

    def test_authenticated_loosen_queued(self):
        entry = self.q.submit_loosen(_edge(direction="LOOSEN"), "Release?",
                                     authenticated=True)
        self.assertEqual(entry.kind, "loosen_request")

    def test_loosen_confirm_requires_auth(self):
        entry = self.q.submit_loosen(_edge(direction="LOOSEN"), "Release?",
                                     authenticated=True)
        with self.assertRaises(ConfirmError):
            self.q.resolve(entry.id, "confirmed", authenticated=False)
        # entry still pending
        self.assertEqual(len(self.q.pending()), 1)

    def test_resolve_confirmed(self):
        entry = self.q.submit_edge(_edge(conf=0.45), "Keep from Mom?")
        r = self.q.resolve(entry.id, "confirmed", authenticated=True)
        self.assertEqual(r.decision, "confirmed")
        self.assertEqual(len(self.q.pending()), 0)

    def test_double_resolve_raises(self):
        entry = self.q.submit_edge(_edge(conf=0.45), "Keep from Mom?")
        self.q.resolve(entry.id, "rejected", authenticated=False)
        with self.assertRaises(ConfirmError):
            self.q.resolve(entry.id, "rejected", authenticated=False)

    def test_expiry_tightens(self):
        self.q.submit_edge(_edge(conf=0.45), "Keep from Mom?")
        self.clock.now += 200  # past ttl
        expired = self.q.sweep()
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].decision, "expired_tighten")
        self.assertEqual(len(self.q.pending()), 0)

    def test_no_expiry_before_ttl(self):
        self.q.submit_edge(_edge(conf=0.45), "Keep from Mom?")
        self.assertEqual(self.q.sweep(), [])


if __name__ == "__main__":
    unittest.main()
