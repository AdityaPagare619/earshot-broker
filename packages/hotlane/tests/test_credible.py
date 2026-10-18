"""Tests for credible sets and the sensitivity-scaled threshold."""

import unittest

from hotlane import UNKNOWN, credible_set, epsilon, logit
from hotlane.belief import initial_belief

from _helpers import PRIORS


class TestEpsilon(unittest.TestCase):
    def test_endpoints(self):
        self.assertAlmostEqual(epsilon(0.0), 0.5)
        self.assertAlmostEqual(epsilon(1.0), 0.05)

    def test_spec_example(self):
        # ε(s) = 0.5 − 0.45·s  →  s=0.1 ⇒ ε≈0.46 ; s=0.95 ⇒ ε≈0.07
        self.assertAlmostEqual(epsilon(0.1), 0.455, places=3)
        self.assertAlmostEqual(epsilon(0.95), 0.0725, places=4)

    def test_monotone_decreasing(self):
        prev = epsilon(0.0)
        for i in range(1, 101):
            cur = epsilon(i / 100)
            self.assertLess(cur, prev)
            prev = cur

    def test_rejects_out_of_range(self):
        for bad in (-0.1, 1.1, 2.0):
            with self.assertRaises(ValueError):
                epsilon(bad)


class TestCredibleSet(unittest.TestCase):
    def test_high_sensitivity_includes_weak_suspicion(self):
        # Mom at P=0.1: excluded for a grocery list, included for a pregnancy.
        state = initial_belief(
            ["priya", "mom"],
            {"priya": logit(0.99), "mom": logit(0.1)},
        )
        low = credible_set(state, 0.1)
        high = credible_set(state, 0.95)
        self.assertNotIn("mom", low)
        self.assertIn("mom", high)
        self.assertIn("priya", low)
        self.assertIn("priya", high)

    def test_unknown_pseudo_person(self):
        # P(unknown)=0.3 >= ε(0.5)=0.275 -> included.
        state = initial_belief(
            ["priya", UNKNOWN],
            {"priya": logit(0.99), UNKNOWN: logit(0.3)},
        )
        # P(unknown)=0.01 < ε(0.5) -> excluded.
        state2 = initial_belief(
            ["priya", UNKNOWN],
            {"priya": logit(0.99), UNKNOWN: logit(0.01)},
        )
        self.assertIn(UNKNOWN, credible_set(state, 0.5))
        self.assertNotIn(UNKNOWN, credible_set(state2, 0.5))

    def test_include_unknown_flag(self):
        state = initial_belief(
            ["priya", UNKNOWN],
            {"priya": logit(0.99), UNKNOWN: logit(0.9)},
        )
        self.assertIn(UNKNOWN, credible_set(state, 0.5, include_unknown=True))
        self.assertNotIn(UNKNOWN, credible_set(state, 0.5, include_unknown=False))

    def test_boundary_inclusive(self):
        # P exactly at ε is included (>=).
        s = 0.5
        p_at = 0.5 - 0.45 * s  # == epsilon(s)
        state = initial_belief(["mom"], {"mom": logit(p_at)})
        self.assertIn("mom", credible_set(state, s))

    def test_returns_frozenset(self):
        state = initial_belief(["priya"], {"priya": logit(0.99)})
        cs = credible_set(state, 0.5)
        self.assertIsInstance(cs, frozenset)


if __name__ == "__main__":
    unittest.main()
