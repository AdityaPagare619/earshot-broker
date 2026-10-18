"""Log-odds belief fusion with asymmetric trust (Law 2).

The room is a belief, not a fact. For each person we maintain logit P(present),
fused from signals that actually exist. The fusion is a PURE function of
(persons, signal log, priors, now) — the caller owns the signal log; the returned
BeliefState matches the frozen contract exactly ({person: logit}, timestamp).

Asymmetric trust (Law 6, arithmetic form):
  - beacons / declarations / hints ADD listeners freely,
  - only authenticated acts (or bounded "alone" declarations) REMOVE them,
  - Alexa hints are tighten-only BY CONSTRUCTION (no negative code path exists).

Person IDs are opaque labels. This module never parses them.

Signal conventions:
  - ALONE.person = the declarer (owner). The negative bump applies to everyone
    EXCEPT the declarer.
  - PRIVATE_NOW.person = the owner. The hard override applies to everyone else.
  - ALEXA_HINT.person = a specific person, or None to nudge everyone supplied
    (callers include UNKNOWN when the hint suggests unmodeled visitors).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from .contracts import BeliefState

# ---------------------------------------------------------------------------
# Signal kinds
# ---------------------------------------------------------------------------

BEACON_PRESENT = "beacon_present"      # phone on home network -> ADD (strong)
BEACON_ABSENT = "beacon_absent"        # phone off network -> weak REMOVE only
CALENDAR_GUEST = "calendar_guest"      # guest event -> ADD, never REMOVE
DECLARE_PRESENT = "declare_present"   # "X is here" -> ADD, sticky until X left
DECLARE_ABSENT = "declare_absent"     # "X left" -> cancels sticky + small REMOVE
ALONE = "alone"                        # "I'm alone" -> REMOVE others, decaying
ALEXA_HINT = "alexa_hint"              # host-LLM hint -> ADD only, NEVER REMOVE
PRIVATE_NOW = "private_now"            # authenticated phone tap -> REMOVE all, windowed

# The pseudo-person for unmodeled visitors. Its logit is caller-supplied
# (sensing owns the value; the math is ours).
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Signal:
    kind: str
    person: str | None = None   # target; declarer for ALONE/PRIVATE_NOW
    at: float = 0.0             # timestamp
    until: float | None = None  # bounded signals (guest events, private-now window)
    authenticated: bool = False  # PRIVATE_NOW must be authenticated


# ---------------------------------------------------------------------------
# Config: every number is a named, documented parameter — no magic constants.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FusionConfig:
    default_prior_logit: float = -2.0        # logit(0.12): strangers start unlikely
    beacon_present_bump: float = 3.0         # strong evidence someone is home
    beacon_present_halflife: float = 1800.0  # 30 min
    beacon_absent_bump: float = -0.5         # WEAK: phones get left in bedrooms
    beacon_absent_halflife: float = 1800.0
    calendar_guest_bump: float = 2.0         # ADD only; active within [at, until]
    declare_present_bump: float = 4.0        # sticky until DECLARE_ABSENT
    declare_absent_bump: float = -1.5        # cancels sticky; decays over 30 min
    declare_absent_halflife: float = 1800.0
    alone_bump: float = -3.0                 # REMOVE others...
    alone_halflife: float = 600.0            # ...with ~10 min half-life
    alexa_hint_bump: float = 1.5             # ADD only — no negative branch exists
    alexa_hint_halflife: float = 900.0
    private_now_logit: float = -6.0          # hard override: logit(0.0025)
    private_now_window: float = 300.0        # 5-minute rectangular window


DEFAULT_FUSION_CONFIG = FusionConfig()


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def sigmoid(logit: float) -> float:
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    e = math.exp(logit)
    return e / (1.0 + e)


def logit(p: float) -> float:
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0,1), got {p!r}")
    return math.log(p / (1.0 - p))


def _decay(dt: float, halflife: float) -> float:
    """Exponential decay factor; future signals (dt<0) count at full strength."""
    if dt < 0:
        dt = 0.0
    return 0.5 ** (dt / halflife)


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

def _active_private_now(
    sigs: list[Signal], now: float, cfg: FusionConfig
) -> Signal | None:
    """The currently-active authenticated PRIVATE_NOW, if any."""
    for s in sigs:
        if s.kind != PRIVATE_NOW or not s.authenticated:
            continue
        end = s.until if s.until is not None else s.at + cfg.private_now_window
        if s.at <= now <= end:
            return s
    return None


def fuse_belief(
    persons: Iterable[str],
    signals: Iterable[Signal],
    priors: Mapping[str, float],
    now: float,
    cfg: FusionConfig = DEFAULT_FUSION_CONFIG,
) -> BeliefState:
    """Recompute log-odds per person from priors + the full signal log.

    logit(p) = prior_logit(p) + Σ decayed signal contributions.

    Contributions follow the asymmetric trust table (DESIGN.md D2). Signals with
    `at > now` are ignored (no peeking into the future). An active authenticated
    PRIVATE_NOW hard-overrides every non-owner person to a near-zero logit —
    the one REMOVE the model can never trigger.
    """
    persons = list(dict.fromkeys(persons))  # dedupe, keep order
    sigs = [s for s in signals if s.at <= now]

    private = _active_private_now(sigs, now, cfg)

    log_odds: dict[str, float] = {}
    for p in persons:
        if private is not None and p != private.person:
            log_odds[p] = cfg.private_now_logit
            continue

        lo = priors.get(p, cfg.default_prior_logit)

        # Sticky DECLARE_PRESENT: the latest of (present, absent) per person wins.
        # Present sticks with no decay; absent cancels it and leaves a decaying
        # negative trace ("they just left").
        latest_declare: Signal | None = None
        for s in sigs:
            if s.person == p and s.kind in (DECLARE_PRESENT, DECLARE_ABSENT):
                if latest_declare is None or s.at > latest_declare.at:
                    latest_declare = s
        if latest_declare is not None:
            if latest_declare.kind == DECLARE_PRESENT:
                lo += cfg.declare_present_bump
            else:
                lo += cfg.declare_absent_bump * _decay(
                    now - latest_declare.at, cfg.declare_absent_halflife)

        for s in sigs:
            dt = now - s.at
            if s.kind == BEACON_PRESENT and s.person == p:
                lo += cfg.beacon_present_bump * _decay(dt, cfg.beacon_present_halflife)
            elif s.kind == BEACON_ABSENT and s.person == p:
                # WEAK remove only. Never strong: phones get left in bedrooms.
                lo += cfg.beacon_absent_bump * _decay(dt, cfg.beacon_absent_halflife)
            elif s.kind == CALENDAR_GUEST and s.person == p:
                # ADD only, active within [at, until]. There is no negative branch.
                end = s.until if s.until is not None else s.at + 86400.0
                if s.at <= now <= end:
                    lo += cfg.calendar_guest_bump
            elif s.kind == ALONE and s.person != p:
                # "I'm alone": REMOVE everyone except the declarer, ~10 min half-life.
                # Sensitivity gating (s >= 0.7 ignores ALONE) happens in the
                # planner (DESIGN.md D3), not here.
                lo += cfg.alone_bump * _decay(dt, cfg.alone_halflife)
            elif s.kind == ALEXA_HINT and (s.person == p or s.person is None):
                # Tighten-only BY CONSTRUCTION: no negative branch exists.
                lo += cfg.alexa_hint_bump * _decay(dt, cfg.alexa_hint_halflife)
            # DECLARE_* handled in the sticky block; PRIVATE_NOW above.

        log_odds[p] = lo

    return BeliefState(log_odds=log_odds, timestamp=now)


def initial_belief(
    persons: Iterable[str],
    priors: Mapping[str, float] | None = None,
    now: float = 0.0,
    cfg: FusionConfig = DEFAULT_FUSION_CONFIG,
) -> BeliefState:
    """Belief with no signals: pure priors. The honest starting point."""
    priors = priors or {}
    return BeliefState(
        log_odds={p: priors.get(p, cfg.default_prior_logit) for p in persons},
        timestamp=now,
    )
