"""FIXTURE — S2 (belief, planning, budgets) stand-in.

Pure functions behind the HotLanePort interface: log-odds belief fusion with
the asymmetric trust table, sensitivity-scaled credible sets, minimax planning,
and decayed exposure budgets. The math here is the real math from
DATAFLOW-PIPELINE.md §§3.1–3.4 — the fixture status is about the *signals*
(home agent beacons etc. are scripted), not the arithmetic.

Language-blind: every function here operates on person ids, floats, and ints.
No strings are inspected, ever.
"""

from __future__ import annotations

import math
import time

from ..contracts import BeliefState
from ..ports import HotLanePort, Plan, PlanItem

# Asymmetric trust (DATAFLOW-PIPELINE.md §3.1): what each signal may do.
# (may_add, may_remove, weight)
_SIGNAL_TRUST = {
    "beacon": (True, False, 2.0),     # phone on home wifi: adds, never removes
    "guest": (True, False, 2.5),       # calendar guest event: adds, never removes
    "declare": (True, False, 3.0),     # "X is here": adds, sticky
    "declare_left": (False, True, 3.0),
    "alone": (False, True, 1.5),       # "I'm alone": weak removal only
    "hint": (True, False, 1.0),        # Alexa hint: tighten-only, always
    "private_tap": (False, True, 4.0),  # authenticated phone tap: full removal
}

_UNKNOWN_PSEUDO = "unknown"


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


class FixtureHotLane(HotLanePort):
    """Belief fusion + credible sets + minimax planning + exposure budgets."""

    # -- belief ---------------------------------------------------------
    def fuse_belief(self, signals, priors, now):
        """signals: iterable of (person, kind). priors: {person: logit}.

        Asymmetric trust is structural: a signal kind can only move log-odds
        in its allowed direction. "I'm alone" can never *add* a listener; a
        beacon can never *remove* one.
        """
        log_odds = dict(priors)
        for person, kind in signals:
            may_add, may_remove, weight = _SIGNAL_TRUST[kind]
            current = log_odds.get(person, -4.0)  # strangers start firmly away
            if kind in ("declare_left", "alone", "private_tap"):
                if may_remove:
                    log_odds[person] = current - weight
            else:
                if may_add:
                    log_odds[person] = current + weight
        return BeliefState(log_odds=log_odds, timestamp=now)

    def credible_set(self, belief, sensitivity):
        """C = {p : P(p) >= eps(s)}, eps(s) = 0.5 - 0.45*s."""
        eps = 0.5 - 0.45 * sensitivity
        return frozenset(
            person for person, logit in belief.log_odds.items()
            if _sigmoid(logit) >= eps
        )

    # -- planning --------------------------------------------------------
    def plan(self, rows, belief, ledger):
        """Minimax over the credible set, capped by exposure budgets."""
        items = []
        table_version = 0
        for row in rows:
            table_version = max(table_version, row.version)
            credible = self.credible_set(belief, row.sensitivity)
            if not credible:
                depth = 4  # no credible listeners: owner alone, full detail
            else:
                depth = min(row.clearance.get(p, 0) for p in credible)
            depth = self._budget_cap(row, credible, depth, ledger)
            # Depth >= 2 speaks; depth 1 speaks vaguely (d1) + phone digest;
            # depth 0 defers entirely to the personal channel.
            action = "DEFER" if depth == 0 else ("PHONE" if depth == 1 else "SPEAK")
            items.append(PlanItem(item_id=row.item_id, depth=depth, action=action))
        # Cover mode: any credible listener not fully cleared for some in-scope
        # row. Computed from the credible SET and the table — never from hidden
        # content. That is what makes the shape constant.
        if not rows:
            return Plan(items=tuple(items), cover_mode=False,
                        credible_set=frozenset(), table_version=0)
        max_sens = max(r.sensitivity for r in rows)
        all_credible = self.credible_set(belief, max_sens)
        cover_mode = any(
            row.clearance.get(p, 0) < 4
            for row in rows for p in all_credible
        )
        return Plan(items=tuple(items), cover_mode=cover_mode,
                    credible_set=all_credible, table_version=table_version)

    def _budget_cap(self, row, credible, depth, ledger):
        """Exposure budget: decayed cumulative leakage per listener.

        L(p, s, t) = sum_k w(d_k) * exp(-(t - t_k) / tau). If speaking at
        `depth` would push any credible listener over the budget, step down.
        """
        weights = {4: 1.0, 3: 0.5, 2: 0.2, 1: 0.05, 0: 0.0}
        tau = 7 * 24 * 3600 if row.sensitivity >= 0.7 else 2 * 24 * 3600
        budget = 1.5 * row.sensitivity + 0.5
        now = time.time()
        d = depth
        while d > 0:
            over = False
            for person in credible:
                leaked = ledger.leakage(person, row.item_id, now, tau)
                if leaked + weights[d] > budget:
                    over = True
                    break
            if not over:
                break
            d -= 1
        return d


class ExposureLedger:
    """Per-listener exposure log. Deliberately over-attributes: anyone
    credibly present is assumed to have heard it."""

    def __init__(self):
        self.entries = []  # (person, item_id, depth, timestamp)

    def record(self, person, item_id, depth, timestamp=None):
        self.entries.append((person, item_id, depth, timestamp or time.time()))

    def leakage(self, person, item_id, now, tau):
        weights = {4: 1.0, 3: 0.5, 2: 0.2, 1: 0.05, 0: 0.0}
        total = 0.0
        for p, iid, depth, ts in self.entries:
            if p == person and iid == item_id:
                total += weights[depth] * math.exp(-(now - ts) / tau)
        return total
