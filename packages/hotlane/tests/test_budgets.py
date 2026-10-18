"""Tests for the exposure-budget accumulator."""

import math
import unittest

from earshot.hotlane import (
    BudgetConfig,
    Exposure,
    ExposureLedger,
    initial_ledger,
)
from earshot.hotlane.budgets import DEFAULT_BUDGET_CONFIG

CFG = DEFAULT_BUDGET_CONFIG
DAY = 86400.0


class TestBudgetFor(unittest.TestCase):
    def test_tighter_for_higher_sensitivity(self):
        self.assertGreater(CFG.budget_for(0.1), CFG.budget_for(0.9))

    def test_spec_values(self):
        # B(s) = 1 − 0.75·s
        self.assertAlmostEqual(CFG.budget_for(0.95), 0.2875)
        self.assertAlmostEqual(CFG.budget_for(0.0), 1.0)

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            CFG.budget_for(1.5)


class TestLeakage(unittest.TestCase):
    def test_empty_ledger_is_zero(self):
        led = initial_ledger()
        self.assertEqual(led.leakage("mom", "s1", 1000.0), 0.0)

    def test_single_exposure_no_decay(self):
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=4, weight=1.0, at=1000.0)])
        self.assertAlmostEqual(led.leakage("mom", "s1", 1000.0), 1.0)

    def test_exponential_decay(self):
        tau = DAY
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=4, weight=1.0, at=0.0)])
        self.assertAlmostEqual(
            led.leakage("mom", "s1", tau, {"s1": tau}), math.exp(-1), places=9)

    def test_per_secret_tau(self):
        led = initial_ledger().record([
            Exposure("mom", "health", depth=4, weight=1.0, at=0.0),
            Exposure("mom", "gift", depth=4, weight=1.0, at=0.0),
        ])
        tau = {"health": 30 * DAY, "gift": 3 * DAY}
        now = 6 * DAY
        # Gift secret decayed much more than health.
        self.assertLess(led.leakage("mom", "gift", now, tau),
                        led.leakage("mom", "health", now, tau))
        self.assertAlmostEqual(
            led.leakage("mom", "gift", now, tau), math.exp(-2), places=9)

    def test_default_tau_when_absent(self):
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=4, weight=1.0, at=0.0)])
        self.assertAlmostEqual(
            led.leakage("mom", "s1", CFG.default_tau),
            math.exp(-1), places=9)

    def test_accumulates_across_exposures(self):
        led = initial_ledger().record([
            Exposure("mom", "s1", depth=3, weight=0.5, at=0.0),
            Exposure("mom", "s1", depth=2, weight=0.2, at=0.0),
        ])
        self.assertAlmostEqual(led.leakage("mom", "s1", 0.0), 0.7)

    def test_isolated_per_listener_and_secret(self):
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=4, weight=1.0, at=0.0)])
        self.assertEqual(led.leakage("maya", "s1", 0.0), 0.0)
        self.assertEqual(led.leakage("mom", "s2", 0.0), 0.0)

    def test_future_dated_records_ignored(self):
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=4, weight=1.0, at=9999.0)])
        self.assertEqual(led.leakage("mom", "s1", 0.0), 0.0)


class TestImmutability(unittest.TestCase):
    def test_record_returns_new_ledger(self):
        led1 = initial_ledger()
        led2 = led1.record([Exposure("mom", "s1", 4, 1.0, 0.0)])
        self.assertEqual(len(led1), 0)
        self.assertEqual(len(led2), 1)
        self.assertIsNot(led1, led2)

    def test_exposures_tuple_visible(self):
        e = Exposure("mom", "s1", 4, 1.0, 0.0)
        led = initial_ledger().record([e])
        self.assertEqual(led.exposures, (e,))


class TestWouldExceed(unittest.TestCase):
    def test_breach_detection(self):
        # s=0.95 -> B=0.2875. Prior d3 exposure (w=0.5) already breaches alone.
        led = initial_ledger().record(
            [Exposure("mom", "s1", depth=3, weight=0.5, at=0.0)])
        self.assertTrue(
            led.would_exceed("mom", "s1", 0.05, 0.95, 0.0))

    def test_no_breach_when_room(self):
        led = initial_ledger()
        self.assertFalse(
            led.would_exceed("mom", "s1", 0.05, 0.95, 0.0))

    def test_low_sensitivity_lenient(self):
        # s=0.1 -> B=0.925. A d3 exposure fits; a d4 (w=1.0) still trips the
        # budget backstop even when lenient — full detail to a hidden_from
        # listener is blocked as well as by clearance (belt and suspenders).
        led = initial_ledger()
        self.assertFalse(
            led.would_exceed("mom", "s1", 0.5, 0.1, 0.0))
        self.assertTrue(
            led.would_exceed("mom", "s1", 1.0, 0.1, 0.0))


if __name__ == "__main__":
    unittest.main()
