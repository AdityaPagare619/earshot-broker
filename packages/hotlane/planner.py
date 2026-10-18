"""Minimax planner (Law 3): speak to the worst credible listener.

For each item:
    C      = credible set at the item's sensitivity
             (ALONE signals ignored when sensitivity >= 0.7 — DESIGN.md D3)
    d_min  = min effective clearance over C   (person -> roles -> fail-closed 0)
    d*     = d_min stepped down by exposure budgets for hidden_from listeners
    decision = SPEAK(d*) | PHONE + SPEAK(d0) | DEFER + SPEAK(d0)

The planner is PURE: it never mutates the ledger. It returns pending exposures;
the speaker (S3) commits them via ExposureLedger.record() after speaking.

Everything here operates on (item_id, depth:int, clearance:int) — integers and
labels, never strings. The hot path is language-blind by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .belief import (
    ALONE,
    UNKNOWN,
    FusionConfig,
    Signal,
    fuse_belief,
    initial_belief,  # noqa: F401  (re-exported for convenience)
    DEFAULT_FUSION_CONFIG,
)
from .budgets import (
    BudgetConfig,
    Exposure,
    ExposureLedger,
    DEFAULT_BUDGET_CONFIG,
)
from .chain import D0, MIN_SPEAK_DEPTH, SPEAKABLE, leakage_weight
from .contracts import BeliefState, TableRow
from .credible import CredibleConfig, DEFAULT_CREDIBLE_CONFIG, credible_set

# Decisions. PHONE and DEFER both imply SPEAK(d0) shape-wise; they differ in
# what happens on the personal channel (digest now vs. held for later).
SPEAK = "speak"
PHONE = "phone"
DEFER = "defer"


@dataclass(frozen=True)
class PlannerConfig:
    fusion: FusionConfig = DEFAULT_FUSION_CONFIG
    credible: CredibleConfig = DEFAULT_CREDIBLE_CONFIG
    budgets: BudgetConfig = DEFAULT_BUDGET_CONFIG
    # Voice "I'm alone" is ignored for items at/above this sensitivity (D3).
    alone_max_sensitivity: float = 0.7
    # Fallback logit for the unknown pseudo-person when the caller doesn't
    # supply one. Callers SHOULD supply unknown_logit from context.
    default_unknown_logit: float = -2.0


DEFAULT_PLANNER_CONFIG = PlannerConfig()


@dataclass(frozen=True)
class ItemPlan:
    item_id: str
    secret_id: str
    decision: str            # SPEAK | PHONE | DEFER
    depth: int               # speak depth (d* for SPEAK, 0 for PHONE/DEFER)
    d_minimax: int           # minimax depth BEFORE the budget cap (evidence)
    credible: frozenset      # credible set the decision was taken against
    cover_mode: bool         # True if anyone besides the owner is credible
    sensitivity: float


@dataclass(frozen=True)
class BriefingPlan:
    items: tuple[ItemPlan, ...]
    belief: BeliefState       # full-signal belief snapshot (frozen contract)
    pending_exposures: tuple[Exposure, ...]  # commit AFTER speaking
    max_table_version: int
    now: float


def _check_depth(depth: int, where: str) -> int:
    """Corrupt table rows must fail loudly, never silently mis-speak."""
    if not isinstance(depth, int) or depth not in (0, 1, 2, 3, 4):
        raise ValueError(f"{where}: clearance depth must be an int in 0..4, "
                         f"got {depth!r}")
    return depth


def effective_clearance(
    clearance: Mapping[str, int],
    person: str,
    roles: Mapping[str, frozenset] | None = None,
) -> int:
    """Resolve a person's effective clearance: person id, then roles, else 0.

    min() over all matching entries — fail closed. No match at all -> 0
    (fail closed). `roles` maps person -> frozenset of role labels
    (e.g. {"role:child"}); S6's pack provides it.
    """
    roles = roles or {}
    candidates = []
    if person in clearance:
        candidates.append(_check_depth(clearance[person], f"clearance[{person!r}]"))
    for role in roles.get(person, ()):
        if role in clearance:
            candidates.append(_check_depth(clearance[role], f"clearance[{role!r}]"))
    if not candidates:
        return 0
    return min(candidates)


def _roster(
    signals: Sequence[Signal],
    priors: Mapping[str, float],
) -> list[str]:
    """Everyone the fusion should consider: priors + signal persons + UNKNOWN."""
    roster: list[str] = []
    for p in list(priors.keys()) + [s.person for s in signals if s.person]:
        if p not in roster:
            roster.append(p)
    if UNKNOWN not in roster:
        roster.append(UNKNOWN)
    return roster


def plan_item(
    row: TableRow,
    belief: BeliefState,
    *,
    owner: str,
    roles: Mapping[str, frozenset] | None = None,
    hidden_from: Mapping[str, frozenset] | None = None,
    secret_of: Mapping[str, str] | None = None,
    ledger: ExposureLedger | None = None,
    tau: Mapping[str, float] | None = None,
    now: float = 0.0,
    cfg: PlannerConfig = DEFAULT_PLANNER_CONFIG,
) -> tuple[ItemPlan, tuple[Exposure, ...]]:
    """Plan a single item against a pre-fused belief. Pure.

    Returns (ItemPlan, pending_exposures). The caller commits exposures after
    speaking via ledger.record().
    """
    hidden_from = hidden_from or {}
    secret_of = secret_of or {}
    ledger = ledger if ledger is not None else ExposureLedger(cfg=cfg.budgets)
    tau = tau or {}

    secret_id = secret_of.get(row.item_id, row.item_id)
    hidden = hidden_from.get(secret_id, frozenset())

    C = credible_set(belief, row.sensitivity, cfg=cfg.credible)
    if not C:
        # Degenerate: belief says nobody is credible. NOT "nobody is there" —
        # sensors can be wrong. Fail closed via the unknown visitor.
        C = frozenset({UNKNOWN})

    d_minimax = min(effective_clearance(row.clearance, p, roles) for p in C)

    # Exposure-budget cap: step down while any hidden_from listener would
    # breach the secret's budget at the candidate depth.
    d_star = d_minimax
    while d_star > D0:
        w = leakage_weight(d_star)
        breach = any(
            ledger.would_exceed(p, secret_id, w, row.sensitivity, now, tau)
            for p in C
            if p in hidden
        )
        if not breach:
            break
        d_star -= 1

    cover_mode = any(p != owner for p in C)

    if d_star >= MIN_SPEAK_DEPTH:
        decision, depth = SPEAK, d_star
        pending = tuple(
            Exposure(person=p, secret=secret_id, depth=d_star,
                     weight=leakage_weight(d_star), at=now)
            for p in C
        )
    elif owner in C:
        decision, depth, pending = PHONE, D0, ()
    else:
        decision, depth, pending = DEFER, D0, ()

    plan = ItemPlan(
        item_id=row.item_id,
        secret_id=secret_id,
        decision=decision,
        depth=depth,
        d_minimax=d_minimax,
        credible=C,
        cover_mode=cover_mode,
        sensitivity=row.sensitivity,
    )
    return plan, pending


def plan_briefing(
    *,
    signals: Sequence[Signal],
    priors: Mapping[str, float],
    rows: Sequence[TableRow],
    owner: str,
    ledger: ExposureLedger | None = None,
    roles: Mapping[str, frozenset] | None = None,
    hidden_from: Mapping[str, frozenset] | None = None,
    secret_of: Mapping[str, str] | None = None,
    tau: Mapping[str, float] | None = None,
    unknown_logit: float | None = None,
    now: float = 0.0,
    cfg: PlannerConfig = DEFAULT_PLANNER_CONFIG,
) -> BriefingPlan:
    """Plan a full briefing. Pure — returns pending exposures, commits nothing.

    Fuses belief twice: once with all signals, once without ALONE signals.
    Items at/above `alone_max_sensitivity` use the no-ALONE belief (D3): a voice
    "I'm alone" can never unlock a high-sensitivity item.
    """
    signals = list(signals)
    ledger = ledger if ledger is not None else ExposureLedger(cfg=cfg.budgets)
    roster = _roster(signals, priors)

    priors_full: dict[str, float] = dict(priors)
    priors_full.setdefault(
        UNKNOWN,
        unknown_logit if unknown_logit is not None else cfg.default_unknown_logit,
    )

    belief_full = fuse_belief(roster, signals, priors_full, now, cfg.fusion)
    belief_no_alone = fuse_belief(
        roster, [s for s in signals if s.kind != ALONE], priors_full, now, cfg.fusion
    )

    items: list[ItemPlan] = []
    pending: list[Exposure] = []
    max_version = 0
    for row in rows:
        belief = (
            belief_full
            if row.sensitivity < cfg.alone_max_sensitivity
            else belief_no_alone
        )
        item_plan, expos = plan_item(
            row, belief, owner=owner, roles=roles, hidden_from=hidden_from,
            secret_of=secret_of, ledger=ledger, tau=tau, now=now, cfg=cfg,
        )
        items.append(item_plan)
        pending.extend(expos)
        max_version = max(max_version, row.version)

    return BriefingPlan(
        items=tuple(items),
        belief=belief_full,
        pending_exposures=tuple(pending),
        max_table_version=max_version,
        now=now,
    )
