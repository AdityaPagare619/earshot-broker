"""Tests for integration.py — the switch must change behavior, not just flags."""
import importlib.util
import unittest
from pathlib import Path

from ..gate import ProfileGate, ProfileViolation
from ..integration import ArbiterState, Heartbeat, ReleasePath, StaleEvidence
from ..profiles import PROFILES


def _kernel():
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location(
        "earshot_kernel", root / "packages" / "kernel" / "kernel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _live_heartbeat(now=1000.0):
    return lambda: Heartbeat(alive=True, observed_at=now)


def _ready_arbiter():
    return lambda: ArbiterState(ready=True)


class TestIntegrationProfileA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = _kernel()

    def setUp(self):
        self.k = self.__class__.k
        self.path = ReleasePath(
            ProfileGate(PROFILES["public_persistent_host"]),
            self.k.Kernel(), _live_heartbeat(), _ready_arbiter())

    def test_public_release_returns_only_public_facts(self):
        k = self.k
        pub = k.Fact("weather", "Rain.", k.Label(frozenset({"*"})))
        pri = k.Fact("appt", "Clinic.", k.Label(frozenset({"alice"})))
        out = self.path.public_release("t1", "alice", "rk-1", (pub, pri), 1000.0)
        self.assertEqual(out["public_facts"], ["Rain."])
        self.assertEqual(out["state"], "accepted")
        self.assertTrue(out["request_ref"])  # opaque receipt, always created

    def test_public_release_empty_facts_still_receipted(self):
        out = self.path.public_release("t1", "alice", "rk-2", (), 1000.0)
        self.assertEqual(out["public_facts"], [])
        self.assertTrue(out["request_ref"])

    def test_audience_scoped_release_refused_in_profile_a(self):
        k = self.k
        fact = k.Fact("a", "v", k.Label(frozenset({"alice"})))
        ctx = k.Context("t1", "alice", frozenset({"alice"}), 1, 1000.0,
                        True, True, True, 1)
        with self.assertRaises(ProfileViolation):
            self.path.audience_scoped_release("t1", fact, ctx, 1000.0)


class TestIntegrationProfileB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = _kernel()

    def setUp(self):
        self.k = self.__class__.k
        self.path = ReleasePath(
            ProfileGate(PROFILES["controlled_host_demo"]),
            self.k.Kernel(), _live_heartbeat(), _ready_arbiter())

    def _ctx(self, epoch=1, observed_at=1000.0):
        k = self.k
        return k.Context("t1", "alice", frozenset({"alice"}), epoch,
                         observed_at, True, True, True, 1)

    def test_lease_release_works_with_live_heartbeat(self):
        k = self.k
        fact = k.Fact("brief", "Leave at 2.", k.Label(frozenset({"alice"})))
        self.assertEqual(
            self.path.audience_scoped_release("t1", fact, self._ctx(), 1000.0),
            "Leave at 2.")

    def test_stale_heartbeat_denies_release(self):
        k = self.k
        fact = k.Fact("brief", "Leave at 2.", k.Label(frozenset({"alice"})))
        path = ReleasePath(
            ProfileGate(PROFILES["controlled_host_demo"]), k.Kernel(),
            lambda: Heartbeat(alive=True, observed_at=900.0),  # 100s stale
            _ready_arbiter())
        with self.assertRaises(StaleEvidence):
            path.audience_scoped_release("t1", fact, self._ctx(), 1000.0)

    def test_dead_heartbeat_denies_release(self):
        k = self.k
        fact = k.Fact("brief", "Leave at 2.", k.Label(frozenset({"alice"})))
        path = ReleasePath(
            ProfileGate(PROFILES["controlled_host_demo"]), k.Kernel(),
            lambda: Heartbeat(alive=False, observed_at=1000.0),
            _ready_arbiter())
        with self.assertRaises(StaleEvidence):
            path.audience_scoped_release("t1", fact, self._ctx(), 1000.0)

    def test_epoch_change_invalidates_lease(self):
        # Simulates the walk-in: prepare under epoch 1, redeem under epoch 2.
        k = self.k
        fact = k.Fact("brief", "Leave at 2.", k.Label(frozenset({"alice"})))
        kernel = k.Kernel()
        path = ReleasePath(ProfileGate(PROFILES["controlled_host_demo"]),
                           kernel, _live_heartbeat(), _ready_arbiter())
        lease = kernel.prepare(fact, self._ctx(epoch=1), 1000.0)
        self.assertIsNotNone(lease)
        # redeem directly under a new epoch must fail (kernel-level guarantee)
        self.assertIsNone(kernel.redeem(lease, self._ctx(epoch=2), 1000.0))


if __name__ == "__main__":
    unittest.main()
