"""Property tests: the mathematical guarantees of the hot lane.

K1. Sensitivity monotonicity:  s1 <= s2  ==>  C(s1) ⊆ C(s2).
    (Fail-closed is continuous; more sensitivity never shrinks the audience.)
K2. Fail-closed under uncertainty: as beliefs -> maximum uncertainty (P=0.5),
    EVERYONE is credible for any sensitivity. Uncertainty costs utility, never
    privacy.
K3. Adding presence only quiets: adding ADD-kind signals never increases a
    planned speak depth.
K4. Language-blindness: permuting rendition strings changes nothing about
    depths/decisions. (The hot path never reads content.)

Negative control (Law 6): a forged ALEXA_HINT claiming "nobody is here" removes
nobody — tighten-only inputs cannot loosen, by construction.
"""

import random
import unittest

from hotlane import (
    ALEXA_HINT,
    ALONE,
    BEACON_PRESENT,
    CALENDAR_GUEST,
    DECLARE_PRESENT,
    UNKNOWN,
    GeneralizationChain,
    TableRow,
    credible_set,
    initial_belief,
    initial_ledger,
    logit,
    plan_briefing,
    plan_item,
    sigmoid,
)
from hotlane.belief import fuse_belief

from _helpers import PRIORS, make_row, sig

NOW = 1_000_000.0
PERSONS = ["priya", "mom", "maya", "ravi"]


def random_belief(rng, persons=PERSONS):
    priors = {p: logit(rng.uniform(0.02, 0.98)) for p in persons}
    priors[UNKNOWN] = logit(rng.uniform(0.001, 0.4))
    return initial_belief(persons + [UNKNOWN], priors, NOW)


class TestK1SensitivityMonotonicity(unittest.TestCase):
    def test_credible_set_grows_with_sensitivity(self):
        rng = random.Random(20261018)
        for _ in range(300):
            state = random_belief(rng)
            s1 = rng.random()
            s2 = rng.uniform(s1, 1.0)  # s1 <= s2
            c1 = credible_set(state, s1)
            c2 = credible_set(state, s2)
            self.assertTrue(
                c1 <= c2,
                f"K1 violated: s1={s1:.3f} s2={s2:.3f} C1={c1} C2={c2}")

    def test_planned_depth_nonincreasing_in_sensitivity(self):
        # Same belief, same clearances: higher sensitivity -> depth never rises.
        # (Credible set grows, minimax over a larger set can only stay or drop.)
        # Restricted to non-degenerate beliefs: when C(s) is empty the planner
        # fail-closes to d=0 via the unknown visitor, which is excess caution
        # (safe direction), not a monotonicity violation that leaks.
        # The degenerate case is pinned separately in test_planner.
        rng = random.Random(77)
        for _ in range(100):
            state = random_belief(rng)
            clearance = {p: rng.randint(0, 4) for p in PERSONS}
            sets = [credible_set(state, s) for s in (0.1, 0.5, 0.9)]
            if any(len(c) == 0 for c in sets):
                continue  # degenerate: covered by the fail-closed pin
            depths = []
            for s in (0.1, 0.5, 0.9):
                row = make_row(sensitivity=s, clearance=clearance)
                plan, _ = plan_item(row, state, owner="priya", now=NOW)
                depths.append(plan.d_minimax)
            self.assertTrue(
                depths[0] >= depths[1] >= depths[2],
                f"K1 violated: depths={depths} clearance={clearance}")


class TestK2FailClosedUnderUncertainty(unittest.TestCase):
    def test_max_uncertainty_includes_everyone(self):
        # logit 0 -> P=0.5 for everyone; ε(s) <= 0.5 for all s >= 0.
        state = initial_belief(
            PERSONS + [UNKNOWN], {p: 0.0 for p in PERSONS + [UNKNOWN]}, NOW)
        for s in (0.0, 0.2, 0.5, 0.9, 1.0):
            cs = credible_set(state, s)
            self.assertEqual(
                cs, frozenset(PERSONS + [UNKNOWN]),
                f"K2 violated at s={s}: {cs}")

    def test_uncertainty_never_speaks_above_certain_depth(self):
        # With everyone maximally uncertain and clearance 0 for non-owners,
        # the minimax depth is 0 regardless of sensitivity.
        state = initial_belief(
            PERSONS + [UNKNOWN], {p: 0.0 for p in PERSONS + [UNKNOWN]}, NOW)
        row = make_row(sensitivity=0.9,
                       clearance={"priya": 4, "mom": 0, "maya": 0, "ravi": 0})
        plan, _ = plan_item(row, state, owner="priya", now=NOW)
        self.assertEqual(plan.d_minimax, 0)
        self.assertNotEqual(plan.decision, "speak")


class TestK3PresenceOnlyQuiets(unittest.TestCase):
    ADD_KINDS = (BEACON_PRESENT, CALENDAR_GUEST, DECLARE_PRESENT, ALEXA_HINT)

    def test_adding_presence_never_raises_depth(self):
        rng = random.Random(4242)
        for trial in range(120):
            persons = PERSONS + [UNKNOWN]
            priors = {p: logit(rng.uniform(0.05, 0.95)) for p in persons}
            base_signals = [
                sig(BEACON_PRESENT, rng.choice(PERSONS), at=NOW - rng.uniform(0, 3000))
                for _ in range(rng.randint(0, 3))
            ]
            extra = sig(rng.choice(self.ADD_KINDS),
                        rng.choice(PERSONS + [None]), at=NOW)
            clearance = {p: rng.randint(0, 4) for p in PERSONS}
            row = make_row(sensitivity=rng.uniform(0.1, 0.9), clearance=clearance)

            def depth_for(signals):
                plan = plan_briefing(
                    signals=signals, priors=priors, rows=[row], owner="priya",
                    ledger=initial_ledger(), unknown_logit=logit(0.01), now=NOW,
                )
                return plan.items[0].depth

            d_base = depth_for(base_signals)
            d_more = depth_for(base_signals + [extra])
            self.assertLessEqual(
                d_more, d_base,
                f"K3 violated on trial {trial}: {d_base} -> {d_more}")


class TestK4LanguageBlindness(unittest.TestCase):
    def test_rendition_permutation_changes_nothing(self):
        # Same rows except every string swapped for another language's.
        # Decisions and depths must be bit-identical: the planner never reads
        # content.
        def row_with(lang, tag):
            chain = GeneralizationChain(
                depths=(f"d4-{tag}", f"d3-{tag}", f"d2-{tag}", f"d1-{tag}"),
                renditions={lang: (f"d4-{tag}", f"d3-{tag}",
                                     f"d2-{tag}", f"d1-{tag}")},
            )
            return TableRow(item_id="itm", sensitivity=0.85,
                            clearance={"priya": 4, "mom": 2},
                            chain=chain, version=3)

        kw = dict(
            signals=[sig(BEACON_PRESENT, "mom", at=NOW)],
            priors={"priya": logit(0.95), "mom": logit(0.6)},
            owner="priya", ledger=initial_ledger(),
            unknown_logit=logit(0.01), now=NOW,
        )
        plan_en = plan_briefing(rows=[row_with("en", "EN")], **kw)
        plan_hi = plan_briefing(rows=[row_with("hi", "HI")], **kw)
        a, b = plan_en.items[0], plan_hi.items[0]
        self.assertEqual(
            (a.decision, a.depth, a.d_minimax, a.cover_mode, a.credible),
            (b.decision, b.depth, b.d_minimax, b.cover_mode, b.credible))


class TestNegativeControlTightenOnly(unittest.TestCase):
    def test_forged_empty_room_hint_removes_nobody(self):
        # NEGATIVE CONTROL for Law 6: an adversary forges an ALEXA_HINT
        # claiming the room is empty. Because hints are ADD-only by
        # construction, the credible set can only grow, never shrink.
        rng = random.Random(999)
        for _ in range(200):
            state = random_belief(rng)
            # A hint "for" nobody in particular (broadcast): still only adds.
            hinted = fuse_belief(
                PERSONS + [UNKNOWN],
                [sig(ALEXA_HINT, None, at=NOW)],
                {p: logit(sigmoid(lo)) for p, lo in state.log_odds.items()},
                NOW,
            )
            # Reconstruct priors from the state so the ONLY difference is the hint.
            for s in (0.2, 0.6, 0.95):
                c_before = credible_set(state, s)
                c_after = credible_set(hinted, s)
                self.assertTrue(
                    c_before <= c_after,
                    f"tighten-only violated at s={s}: {c_before} -> {c_after}")

    def test_alone_is_the_only_voice_remove_and_it_is_gated(self):
        # Voice ALONE is the sole unauthenticated REMOVE, and the planner
        # ignores it for s >= 0.7. Pin both halves.
        signals = [sig(ALONE, "priya", at=NOW)]
        priors = {"priya": logit(0.95), "mom": logit(0.6)}
        kw = dict(signals=signals, priors=priors, owner="priya",
                  ledger=initial_ledger(), unknown_logit=logit(0.001), now=NOW)
        hi = make_row(item_id="hi", sensitivity=0.7,
                      clearance={"priya": 4, "mom": 0})
        lo = make_row(item_id="lo", sensitivity=0.69,
                      clearance={"priya": 4, "mom": 4})
        plan = plan_briefing(rows=[hi, lo], **kw)
        by_id = {p.item_id: p for p in plan.items}
        # s=0.7: ALONE ignored -> mom (P=0.6 >= ε(0.7)=0.185) credible -> d*=0.
        self.assertIn("mom", by_id["hi"].credible)
        self.assertEqual(by_id["hi"].decision, "phone")
        # s=0.69: ALONE applies -> mom pushed to ~0 -> not credible -> SPEAK(4).
        self.assertNotIn("mom", by_id["lo"].credible)
        self.assertEqual(by_id["lo"].depth, 4)


if __name__ == "__main__":
    unittest.main()
