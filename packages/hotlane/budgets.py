"""Exposure budgets (Law 5): disclosure is cumulative.

A 4-level lattice grades one utterance. Leaks are cumulative: "an appointment at
3:40" every Tuesday for nine weeks is a pattern. So we keep a decayed accumulator
per (listener, secret):

    L(p, s, t) = Σ_k  w(d_k) · exp(−(t − t_k) / τ_s)

k ranges over exposures of items linked to secret s while p was credible.
w(d) is the depth's leakage weight; τ_s is the secret's half-life in the
pack's units (long for health, short for gifts — supplied as DATA, never
inferred from strings here).

The budget B(s) = 1 − 0.75·s: at s=0.95 a single d3 exposure (w=0.5) nearly
exhausts it; at s=0.1 the budget is lenient. When L(p,s,t) + w(d*) would exceed
B(s) for any hidden_from listener, the planner steps the depth down. This is an
SRE-style error budget for inference — deliberately NOT formal differential
privacy (DESIGN.md R3).

The ledger is IMMUTABLE: record() returns a new ledger. The planner never
mutates it (DESIGN.md D8).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Exposure:
    """One assumed overhearing: listener p may have heard secret s at depth d."""
    person: str
    secret: str
    depth: int
    weight: float   # w(d) at record time — frozen so weight tables can evolve
    at: float       # timestamp


@dataclass(frozen=True)
class BudgetConfig:
    default_tau: float = 7 * 86400.0   # 7 days when the pack doesn't say (conservative)

    def budget_for(self, sensitivity: float) -> float:
        """B(s) = 1 − 0.75·s. Higher sensitivity -> tighter budget."""
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(f"sensitivity must be in [0,1], got {sensitivity!r}")
        return 1.0 - 0.75 * sensitivity


DEFAULT_BUDGET_CONFIG = BudgetConfig()


class ExposureLedger:
    """Immutable accumulator of (listener, secret) exposures.

    Internally a tuple of Exposure records; leakage() sums the decayed weights
    on demand. Household scale is tiny (tens of listeners × hundreds of items),
    so the O(n) scan is honest and auditable — no clever index to distrust.
    """

    __slots__ = ("_exposures", "_cfg")

    def __init__(
        self,
        exposures: Iterable[Exposure] = (),
        cfg: BudgetConfig = DEFAULT_BUDGET_CONFIG,
    ) -> None:
        self._exposures = tuple(exposures)
        self._cfg = cfg

    @property
    def exposures(self) -> tuple[Exposure, ...]:
        return self._exposures

    def record(self, exposures: Iterable[Exposure]) -> "ExposureLedger":
        """Return a NEW ledger with these exposures appended. Pure."""
        return ExposureLedger(self._exposures + tuple(exposures), self._cfg)

    def leakage(
        self,
        person: str,
        secret: str,
        now: float,
        tau: Mapping[str, float] | None = None,
    ) -> float:
        """L(p, s, t): decayed cumulative exposure weight."""
        tau = tau or {}
        total = 0.0
        for e in self._exposures:
            if e.person != person or e.secret != secret:
                continue
            dt = now - e.at
            if dt < 0:
                continue  # ignore future-dated records defensively
            tau_s = tau.get(secret, self._cfg.default_tau)
            total += e.weight * math.exp(-dt / tau_s)
        return total

    def would_exceed(
        self,
        person: str,
        secret: str,
        add_weight: float,
        sensitivity: float,
        now: float,
        tau: Mapping[str, float] | None = None,
    ) -> bool:
        """Would one more exposure at this weight breach the secret's budget?"""
        return (
            self.leakage(person, secret, now, tau) + add_weight
            > self._cfg.budget_for(sensitivity)
        )

    def __len__(self) -> int:
        return len(self._exposures)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ExposureLedger({len(self._exposures)} exposures)"


def initial_ledger(cfg: BudgetConfig = DEFAULT_BUDGET_CONFIG) -> ExposureLedger:
    """An empty ledger. Every household starts with no assumed overhearings."""
    return ExposureLedger((), cfg)
