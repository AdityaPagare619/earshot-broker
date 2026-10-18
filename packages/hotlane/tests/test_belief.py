"""Tests for log-odds belief fusion and the asymmetric trust table."""

import math
import unittest

from hotlane import (
    ALEXA_HINT,
    ALONE,
    BEACON_ABSENT,
    BEACON_PRESENT,
    CALENDAR_GUEST,
    DECLARE_ABSENT,
    DECLARE_PRESENT,
    PRIVATE_NOW,
    UNKNOWN,
    FusionConfig,
    fuse_belief,
    initial_belief,
    logit,
    sigmoid,
)
from hotlane.belief import DEFAULT_FUSION_CONFIG

from _helpers import PRIORS, sig

CFG = DEFAULT_FUSION_CONFIG
NOW = 1_000_000.0


class TestMathHelpers(unittest.TestCase):
    def test_sigmoid_logit_roundtrip(self):
        for p in (0.01, 0.12, 0.5, 0.9, 0.99):
            self.assertAlmostEqual(sigmoid(logit(p)), p, places=9)

    def test_logit_rejects_bounds(self):
        for bad in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                logit(bad)


class TestInitialBelief(unittest.TestCase):
    def test_priors_respected(self):
        b = initial_belief(["priya", "mom"], PRIORS, NOW)
        self.assertAlmostEqual(b.log_odds["priya"], PRIORS["priya"])
        self.assertAlmostEqual(b.log_odds["mom"], PRIORS["mom"])
        self.assertEqual(b.timestamp, NOW)

    def test_missing_prior_uses_default(self):
        b = initial_belief(["stranger"], PRIORS, NOW)
        self.assertAlmostEqual(b.log_odds["stranger"], CFG.default_prior_logit)

    def test_frozen_contract_shape(self):
        b = initial_belief(["priya"], PRIORS, NOW)
        self.assertEqual(set(b.log_odds), {"priya"})
        self.assertIsInstance(b.timestamp, float)


class TestBeaconSignals(unittest.TestCase):
    def test_beacon_present_raises_strongly(self):
        b = fuse_belief(
            ["mom"], [sig(BEACON_PRESENT, "mom", at=NOW)],
            {"mom": logit(0.1)}, NOW,
        )
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.1) + CFG.beacon_present_bump)

    def test_beacon_absent_is_weak_only(self):
        # The whole point: a missing phone must not nuke presence.
        b = fuse_belief(
            ["mom"], [sig(BEACON_ABSENT, "mom", at=NOW)],
            {"mom": logit(0.8)}, NOW,
        )
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.8) + CFG.beacon_absent_bump)
        self.assertGreater(sigmoid(b.log_odds["mom"]), 0.5)

    def test_beacon_present_decays(self):
        b0 = fuse_belief(["mom"], [sig(BEACON_PRESENT, "mom", at=NOW)],
                         {"mom": logit(0.1)}, NOW)
        b1 = fuse_belief(["mom"], [sig(BEACON_PRESENT, "mom", at=NOW)],
                         {"mom": logit(0.1)}, NOW + CFG.beacon_present_halflife)
        bump0 = b0.log_odds["mom"] - logit(0.1)
        bump1 = b1.log_odds["mom"] - logit(0.1)
        self.assertAlmostEqual(bump1 / bump0, 0.5, places=6)


class TestDeclarations(unittest.TestCase):
    def test_declare_present_is_sticky(self):
        # No decay: still full strength an hour later.
        b = fuse_belief(
            ["mom"], [sig(DECLARE_PRESENT, "mom", at=NOW)],
            {"mom": logit(0.1)}, NOW + 3600.0,
        )
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.1) + CFG.declare_present_bump)

    def test_declare_absent_cancels_sticky(self):
        b = fuse_belief(
            ["mom"],
            [sig(DECLARE_PRESENT, "mom", at=NOW),
             sig(DECLARE_ABSENT, "mom", at=NOW + 10)],
            {"mom": logit(0.1)}, NOW + 10,
        )
        # Sticky bump gone; only the decaying absent trace remains.
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.1) + CFG.declare_absent_bump, places=6)
        self.assertLess(b.log_odds["mom"], logit(0.1))

    def test_latest_declaration_wins(self):
        b = fuse_belief(
            ["mom"],
            [sig(DECLARE_ABSENT, "mom", at=NOW),
             sig(DECLARE_PRESENT, "mom", at=NOW + 10)],
            {"mom": logit(0.1)}, NOW + 10,
        )
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.1) + CFG.declare_present_bump)


class TestAlone(unittest.TestCase):
    def test_alone_lowers_others_not_declarer(self):
        b = fuse_belief(
            ["priya", "mom"], [sig(ALONE, "priya", at=NOW)],
            {"priya": logit(0.9), "mom": logit(0.8)}, NOW,
        )
        # Declarer untouched...
        self.assertAlmostEqual(b.log_odds["priya"], logit(0.9))
        # ...others pushed down hard.
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.8) + CFG.alone_bump)

    def test_alone_decays_with_ten_minute_halflife(self):
        kw = dict(persons=["mom"], signals=[sig(ALONE, "priya", at=NOW)],
                  priors={"mom": logit(0.8)})
        b0 = fuse_belief(now=NOW, **kw)
        b1 = fuse_belief(now=NOW + CFG.alone_halflife, **kw)
        d0 = b0.log_odds["mom"] - logit(0.8)
        d1 = b1.log_odds["mom"] - logit(0.8)
        self.assertAlmostEqual(d1 / d0, 0.5, places=6)
        self.assertAlmostEqual(d0, CFG.alone_bump)


class TestAlexaHintTightenOnly(unittest.TestCase):
    def test_hint_adds(self):
        b = fuse_belief(
            ["mom"], [sig(ALEXA_HINT, "mom", at=NOW)],
            {"mom": logit(0.2)}, NOW,
        )
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.2) + CFG.alexa_hint_bump)

    def test_hint_broadcast_adds_to_everyone(self):
        b = fuse_belief(
            ["priya", "mom"], [sig(ALEXA_HINT, None, at=NOW)],
            {"priya": logit(0.5), "mom": logit(0.5)}, NOW,
        )
        self.assertAlmostEqual(
            b.log_odds["priya"], logit(0.5) + CFG.alexa_hint_bump)
        self.assertAlmostEqual(
            b.log_odds["mom"], logit(0.5) + CFG.alexa_hint_bump)

    def test_hint_never_removes(self):
        # There is no negative branch: even a hint that *claims* emptiness
        # cannot lower anyone. (Structural property; also in test_properties.)
        for p in ("priya", "mom"):
            b = fuse_belief(
                [p], [sig(ALEXA_HINT, p, at=NOW)],
                {p: logit(0.5)}, NOW,
            )
            self.assertGreaterEqual(b.log_odds[p], logit(0.5))


class TestPrivateNow(unittest.TestCase):
    def test_authenticated_private_now_overrides(self):
        b = fuse_belief(
            ["priya", "mom"],
            [sig(PRIVATE_NOW, "priya", at=NOW, authenticated=True)],
            {"priya": logit(0.9), "mom": logit(0.9)}, NOW,
        )
        self.assertAlmostEqual(b.log_odds["mom"], CFG.private_now_logit)
        # Owner untouched.
        self.assertAlmostEqual(b.log_odds["priya"], logit(0.9))

    def test_unauthenticated_private_now_ignored(self):
        b = fuse_belief(
            ["mom"],
            [sig(PRIVATE_NOW, "priya", at=NOW, authenticated=False)],
            {"mom": logit(0.9)}, NOW,
        )
        self.assertAlmostEqual(b.log_odds["mom"], logit(0.9))

    def test_private_now_expires(self):
        b = fuse_belief(
            ["mom"],
            [sig(PRIVATE_NOW, "priya", at=NOW, authenticated=True)],
            {"mom": logit(0.9)}, NOW + CFG.private_now_window + 1,
        )
        self.assertAlmostEqual(b.log_odds["mom"], logit(0.9))


class TestCalendarGuest(unittest.TestCase):
    def test_guest_adds_within_window_only(self):
        s = sig(CALENDAR_GUEST, "mom", at=NOW, until=NOW + 3600)
        b_in = fuse_belief(["mom"], [s], {"mom": logit(0.1)}, NOW + 10)
        self.assertAlmostEqual(
            b_in.log_odds["mom"], logit(0.1) + CFG.calendar_guest_bump)
        b_out = fuse_belief(["mom"], [s], {"mom": logit(0.1)}, NOW + 7200)
        self.assertAlmostEqual(b_out.log_odds["mom"], logit(0.1))

    def test_guest_has_no_negative_branch(self):
        # Even after the window, the guest signal never pushes DOWN.
        s = sig(CALENDAR_GUEST, "mom", at=NOW, until=NOW + 3600)
        b = fuse_belief(["mom"], [s], {"mom": logit(0.5)}, NOW + 7200)
        self.assertGreaterEqual(b.log_odds["mom"], logit(0.5))


class TestSignalHygiene(unittest.TestCase):
    def test_future_signals_ignored(self):
        b = fuse_belief(
            ["mom"], [sig(BEACON_PRESENT, "mom", at=NOW + 9999)],
            {"mom": logit(0.1)}, NOW,
        )
        self.assertAlmostEqual(b.log_odds["mom"], logit(0.1))

    def test_unknown_person_in_roster(self):
        b = fuse_belief(
            ["priya", UNKNOWN], [], {"priya": logit(0.9)}, NOW,
        )
        self.assertIn(UNKNOWN, b.log_odds)
        self.assertAlmostEqual(
            b.log_odds[UNKNOWN], CFG.default_prior_logit)

    def test_fusion_is_pure(self):
        kw = dict(persons=["mom"], signals=[sig(BEACON_PRESENT, "mom", at=NOW)],
                  priors={"mom": logit(0.3)})
        b1 = fuse_belief(now=NOW, **kw)
        b2 = fuse_belief(now=NOW, **kw)
        self.assertEqual(b1.log_odds, b2.log_odds)


if __name__ == "__main__":
    unittest.main()
