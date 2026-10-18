"""Credible sets (Law 2): who might be listening.

The room is a belief, not a fact. For an item of sensitivity s, the credible set
is everyone whose presence probability clears a threshold that SCALES WITH
SENSITIVITY:

    ε(s) = 0.5 − 0.45·s        # s=0.1 -> ε≈0.46 ; s=0.95 -> ε≈0.07

A grocery list tolerates uncertainty. A pregnancy does not: at s=0.95, a 7%
suspicion that Mom is home is enough to include her.

Fail-closed is continuous, not a single 0.6 cliff. Maximum uncertainty
(logit -> 0, P -> 0.5) includes EVERYONE for any s >= 0, because ε(s) <= 0.5
always. Uncertainty widens the credible set, which costs utility — never privacy.
That monotonicity is property-tested (tests/test_properties.py::K1).
"""

from __future__ import annotations

from dataclasses import dataclass

from .belief import UNKNOWN, sigmoid
from .contracts import BeliefState


@dataclass(frozen=True)
class CredibleConfig:
    # Sensitivity at/above which voice "alone" declarations are ignored (D3).
    alone_max_sensitivity: float = 0.7


DEFAULT_CREDIBLE_CONFIG = CredibleConfig()


def epsilon(sensitivity: float) -> float:
    """Sensitivity-scaled inclusion threshold. Higher sensitivity -> lower bar."""
    if not 0.0 <= sensitivity <= 1.0:
        raise ValueError(f"sensitivity must be in [0,1], got {sensitivity!r}")
    return 0.5 - 0.45 * sensitivity


def credible_set(
    state: BeliefState,
    sensitivity: float,
    include_unknown: bool = True,
    cfg: CredibleConfig = DEFAULT_CREDIBLE_CONFIG,  # noqa: ARG001
) -> frozenset[str]:
    """Everyone credibly present for an item of this sensitivity.

    `state.log_odds` must contain every person of interest INCLUDING `unknown`
    when `include_unknown` is True — the caller supplies unknown's logit (sensing
    owns the value). Persons missing from log_odds are simply not considered;
    callers should always fuse over the full household roster.
    """
    eps = epsilon(sensitivity)
    members = set()
    for person, lo in state.log_odds.items():
        if person == UNKNOWN and not include_unknown:
            continue
        if sigmoid(lo) >= eps:
            members.add(person)
    return frozenset(members)
