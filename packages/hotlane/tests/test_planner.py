"""Tests for the minimax planner: Law 3 + budget caps + decisions."""

import unittest

from earshot.hotlane import (
    ALONE,
    BEACON_PRESENT,
    DEFER,
    PHONE,
    SPEAK,
    UNKNOWN,
    Exposure,
    ExposureLedger,
    TableRow,
    effective_clearance,
    initial_ledger,
    logit,
    plan_briefing,
    plan_item,
)
from earshot.hotlane.belief import initial_belief

from hotlane.tests._helpers import PRIORS, make_row, sig

NOW = 1_000_000.0
ROLES = {"maya": frozenset({"role:child"}), "mom": frozenset({"role:guest"})}


def belief_all(persons, p_each, extra=None):
    priors = {person: logit(p_each) for person in persons}
    if extra:
        priors.update(extra)
    return initial_belief(persons, priors, NOW)


class TestEffectiveClearance(unittest.TestCase):
    def test_person_key_wins(self):
        self.assertEqual(
            effective_clearance({"priya": 4, "role:guest": 1}, "priya", ROLES), 4)

    def test_role_fallback(self):
        self.assertEqual(
            effective_clearance({"role:child": 1}, "maya", ROLES), 1)

    def test_min_over_person_and_role(self):
        self.assertEqual(
            effective_clearance({"maya": 3, "role:child": 1}, "maya", ROLES), 1)

    def test_no_match_fails_closed_to_zero(self):
        self.assertEqual(effective_clearance({"priya": 4}, "stranger", ROLES), 0)

    def test_unknown_defaults_zero(self):
        self.assertEqual(effective_clearance({"priya": 4}, UNKNOWN, ROLES), 0)

    def test_corrupt_depth_raises_loudly(self):
        with self.assertRaises(ValueError):
            effective_clearance({"priya": 7}, "priya", ROLES)
        with self.assertRaises(ValueError):
            effective_clearance({"priya": "high"}, "priya", ROLES)


class TestMinimax(unittest.TestCase):
    def test_speaks_to_worst_credible_listener(self):
        row = make_row(clearance={"priya": 4, "mom": 1})
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        plan, _ = plan_item(row, b, owner="priya", now=NOW)
        self.assertEqual(plan.d_minimax, 1)
        self.assertEqual(plan.decision, SPEAK)
        self.assertEqual(plan.depth, 1)
        self.assertTrue(plan.cover_mode)

    def test_owner_alone_speaks_fully(self):
        row = make_row(clearance={"priya": 4, "mom": 0})
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {"mom": logit(0.001), UNKNOWN: logit(0.001)})
        # mom/unknown below threshold even at s=0.9 (ε≈0.095)
        plan, _ = plan_item(row, b, owner="priya", now=NOW)
        self.assertEqual(plan.credible, frozenset({"priya"}))
        self.assertEqual(plan.decision, SPEAK)
        self.assertEqual(plan.depth, 4)
        self.assertFalse(plan.cover_mode)

    def test_empty_credible_set_fails_closed(self):
        # Belief says nobody is credible — NOT "nobody is there".
        row = make_row(clearance={"priya": 4})
        b = initial_belief(["priya", UNKNOWN],
                           {"priya": logit(0.001), UNKNOWN: logit(0.001)}, NOW)
        plan, _ = plan_item(row, b, owner="priya", now=NOW)
        # Degenerate -> treated as unknown visitor, clearance 0.
        self.assertEqual(plan.depth, 0)
        self.assertNotEqual(plan.decision, SPEAK)


class TestDecisions(unittest.TestCase):
    def test_zero_depth_owner_present_is_phone(self):
        row = make_row(sensitivity=0.9, clearance={"priya": 4, "mom": 0})
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        plan, pending = plan_item(row, b, owner="priya", now=NOW)
        self.assertEqual(plan.decision, PHONE)
        self.assertEqual(plan.depth, 0)
        self.assertEqual(pending, ())  # d0 exposes nothing

    def test_zero_depth_owner_absent_is_defer(self):
        row = make_row(sensitivity=0.9, clearance={"priya": 0, "mom": 0})
        # Owner not credible (P=0.01); mom is. d*=0 and no owner -> DEFER.
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {"priya": logit(0.01), UNKNOWN: logit(0.001)})
        plan, _ = plan_item(row, b, owner="priya", now=NOW)
        self.assertNotIn("priya", plan.credible)
        self.assertEqual(plan.decision, DEFER)
        self.assertEqual(plan.depth, 0)

    def test_speak_records_pending_exposures(self):
        row = make_row(sensitivity=0.2,
                       clearance={"priya": 4, "mom": 4})
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        plan, pending = plan_item(row, b, owner="priya", now=NOW)
        self.assertEqual(plan.decision, SPEAK)
        self.assertEqual(plan.depth, 4)
        # Over-attribution: everyone credible is assumed to have heard it.
        self.assertEqual({e.person for e in pending}, {"priya", "mom"})
        self.assertTrue(all(e.weight == 1.0 and e.at == NOW for e in pending))


class TestBudgetCap(unittest.TestCase):
    def test_ninth_tuesday_steps_down(self):
        # Mom already heard d3 (w=0.5) recently; s=0.95 -> B=0.2875.
        # d*=1 (w=0.05) would breach -> step to 0 -> PHONE.
        row = make_row(item_id="itm_appt", sensitivity=0.95,
                       clearance={"priya": 4, "mom": 1})
        ledger = initial_ledger().record(
            [Exposure("mom", "itm_appt", 3, 0.5, NOW - 100)])
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        plan, _ = plan_item(
            row, b, owner="priya",
            hidden_from={"itm_appt": frozenset({"mom"})},
            ledger=ledger, now=NOW,
        )
        self.assertEqual(plan.d_minimax, 1)   # minimax wanted d1...
        self.assertEqual(plan.depth, 0)        # ...budget forced d0
        self.assertEqual(plan.decision, PHONE)  # owner present -> phone

    def test_budget_ignores_non_hidden_listeners(self):
        # Heavy exposure toward priya (not hidden_from) must not move mom's
        # budget. Both ledgers must plan identically: d4->d3->d2, because
        # w(d4)=1.0 and w(d3)=0.5 both exceed B(0.95)=0.2875 for hidden mom
        # (budget backstop), while w(d2)=0.2 fits.
        row = make_row(item_id="itm_x", sensitivity=0.95,
                       clearance={"priya": 4, "mom": 4})
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        kw = dict(owner="priya",
                  hidden_from={"itm_x": frozenset({"mom"})}, now=NOW)
        led_with_priya = initial_ledger().record(
            [Exposure("priya", "itm_x", 4, 1.0, NOW - 100)])
        plan1, _ = plan_item(row=row, belief=b, ledger=led_with_priya, **kw)
        plan2, _ = plan_item(row=row, belief=b, ledger=initial_ledger(), **kw)
        self.assertEqual((plan1.decision, plan1.depth), (SPEAK, 2))
        self.assertEqual((plan2.decision, plan2.depth), (SPEAK, 2))

    def test_old_exposures_decay_out(self):
        # A d3 exposure 60 days ago (τ=7d) has decayed to ~nothing.
        row = make_row(item_id="itm_y", sensitivity=0.95,
                       clearance={"priya": 4, "mom": 1})
        ledger = initial_ledger().record(
            [Exposure("mom", "itm_y", 3, 0.5, NOW - 60 * 86400)])
        b = belief_all(["priya", "mom", UNKNOWN], 0.99,
                       {UNKNOWN: logit(0.001)})
        plan, _ = plan_item(
            row, b, owner="priya",
            hidden_from={"itm_y": frozenset({"mom"})},
            ledger=ledger, now=NOW,
        )
        self.assertEqual(plan.decision, SPEAK)
        self.assertEqual(plan.depth, 1)


class TestPlanBriefing(unittest.TestCase):
    def test_alone_ignored_for_high_sensitivity(self):
        # Owner says "I'm alone"; mom's beacon says she's home.
        signals = [sig(ALONE, "priya", at=NOW),
                   sig(BEACON_PRESENT, "mom", at=NOW)]
        # mom: prior 0.2 + beacon(+3) + alone(−3, decayed 0) -> net P=0.2,
        # below ε(0.5)=0.275 when ALONE applies, above ε(0.9)=0.095 without it.
        priors = {"priya": logit(0.95), "mom": logit(0.2)}
        high = make_row(item_id="hi", sensitivity=0.9,
                        clearance={"priya": 4, "mom": 0})
        low = make_row(item_id="lo", sensitivity=0.5,
                       clearance={"priya": 4, "mom": 4})
        plan = plan_briefing(
            signals=signals, priors=priors, rows=[high, low],
            owner="priya", ledger=initial_ledger(),
            unknown_logit=logit(0.001), now=NOW,
        )
        by_id = {p.item_id: p for p in plan.items}
        # High-sensitivity: ALONE ignored -> mom credible -> d*=0 -> PHONE.
        self.assertIn("mom", by_id["hi"].credible)
        self.assertEqual(by_id["hi"].decision, PHONE)
        # Low-sensitivity: ALONE applies -> mom not credible -> SPEAK(4).
        self.assertNotIn("mom", by_id["lo"].credible)
        self.assertEqual(by_id["lo"].decision, SPEAK)
        self.assertEqual(by_id["lo"].depth, 4)

    def test_planner_is_pure_ledger_untouched(self):
        row = make_row(clearance={"priya": 4, "mom": 4})
        ledger = initial_ledger()
        plan = plan_briefing(
            signals=[], priors={"priya": logit(0.99), "mom": logit(0.99)},
            rows=[row], owner="priya", ledger=ledger,
            unknown_logit=logit(0.001), now=NOW,
        )
        self.assertEqual(len(ledger), 0)  # untouched
        self.assertEqual(len(plan.pending_exposures), 2)  # priya + mom
        # Speaker commits AFTER speaking:
        ledger2 = ledger.record(plan.pending_exposures)
        self.assertEqual(len(ledger2), 2)

    def test_belief_snapshot_matches_frozen_contract(self):
        row = make_row()
        plan = plan_briefing(
            signals=[], priors={"priya": logit(0.9)}, rows=[row],
            owner="priya", unknown_logit=logit(0.01), now=NOW,
        )
        self.assertEqual(set(plan.belief.log_odds), {"priya", UNKNOWN})
        self.assertEqual(plan.belief.timestamp, NOW)
        self.assertEqual(plan.max_table_version, 1)

    def test_secret_of_mapping(self):
        # Two items, one secret: budgets shared across items.
        r1 = make_row(item_id="a", sensitivity=0.95,
                      clearance={"priya": 4, "mom": 2})
        r2 = make_row(item_id="b", sensitivity=0.95,
                      clearance={"priya": 4, "mom": 2})
        ledger = initial_ledger().record(
            [Exposure("mom", "secretS", 3, 0.5, NOW - 100)])
        plan = plan_briefing(
            signals=[], priors={"priya": logit(0.99), "mom": logit(0.99)},
            rows=[r1, r2], owner="priya", ledger=ledger,
            secret_of={"a": "secretS", "b": "secretS"},
            hidden_from={"secretS": frozenset({"mom"})},
            unknown_logit=logit(0.001), now=NOW,
        )
        for p in plan.items:
            self.assertEqual(p.secret_id, "secretS")
            # 0.5 prior + w(2)=0.2 > 0.2875 -> stepped to 0 -> PHONE
            self.assertEqual(p.decision, PHONE)


if __name__ == "__main__":
    unittest.main()
