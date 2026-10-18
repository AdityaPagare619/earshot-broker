"""EARSHOT hot lane — belief, planning & budgets (S2).

Pure functions implementing Laws 2, 3, 5 of the Sealed-Speech Architecture:

  belief.fuse_belief(persons, signals, priors, now) -> BeliefState
      Log-odds fusion with asymmetric trust. The caller owns the signal log;
      the returned BeliefState matches the frozen contract exactly.

  credible.credible_set(state, sensitivity) -> frozenset
      ε(s) = 0.5 − 0.45·s. Includes the `unknown` pseudo-person when credible.

  planner.plan_briefing(signals=..., priors=..., rows=..., owner=...,
                        ledger=...) -> BriefingPlan
      The S3 entry point. Minimax planning + exposure budgets. Pure: returns
      pending_exposures; commit them AFTER speaking via ledger.record().

  budgets.ExposureLedger — immutable (listener, secret) exposure accumulator.

Everything operates on (item_id, depth:int, clearance:int) — integers and
labels, NEVER strings. The hot path is language-blind by construction.

Stdlib only. No I/O. No NLP. No sensing.
"""

from .belief import (
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
    Signal,
    fuse_belief,
    initial_belief,
    logit,
    sigmoid,
    DEFAULT_FUSION_CONFIG,
)
from .budgets import (
    BudgetConfig,
    Exposure,
    ExposureLedger,
    initial_ledger,
    DEFAULT_BUDGET_CONFIG,
)
from .chain import (
    D0,
    D1,
    D2,
    D3,
    D4,
    DEPTHS,
    LEAKAGE_WEIGHT,
    MIN_SPEAK_DEPTH,
    SPEAKABLE,
    is_speakable,
    leakage_weight,
    render,
    validate_chain,
)
from .contracts import (
    BeliefState,
    GeneralizationChain,
    Item,
    SecrecyEdge,
    TableRow,
)
from .credible import (
    CredibleConfig,
    credible_set,
    epsilon,
    DEFAULT_CREDIBLE_CONFIG,
)
from .planner import (
    DEFER,
    PHONE,
    SPEAK,
    BriefingPlan,
    ItemPlan,
    PlannerConfig,
    effective_clearance,
    plan_briefing,
    plan_item,
    DEFAULT_PLANNER_CONFIG,
)

__all__ = [
    # entry points
    "plan_briefing", "plan_item", "fuse_belief", "credible_set",
    "initial_belief", "initial_ledger",
    # plans
    "BriefingPlan", "ItemPlan", "SPEAK", "PHONE", "DEFER",
    # belief
    "Signal", "FusionConfig", "DEFAULT_FUSION_CONFIG", "UNKNOWN",
    "BEACON_PRESENT", "BEACON_ABSENT", "CALENDAR_GUEST",
    "DECLARE_PRESENT", "DECLARE_ABSENT", "ALONE", "ALEXA_HINT", "PRIVATE_NOW",
    "sigmoid", "logit",
    # credible sets
    "CredibleConfig", "DEFAULT_CREDIBLE_CONFIG", "epsilon",
    # budgets
    "Exposure", "ExposureLedger", "BudgetConfig", "DEFAULT_BUDGET_CONFIG",
    # chains / depths
    "D0", "D1", "D2", "D3", "D4", "DEPTHS", "SPEAKABLE",
    "LEAKAGE_WEIGHT", "MIN_SPEAK_DEPTH",
    "leakage_weight", "is_speakable", "render", "validate_chain",
    "effective_clearance",
    # frozen contracts
    "BeliefState", "GeneralizationChain", "Item", "SecrecyEdge", "TableRow",
    # configs
    "PlannerConfig", "DEFAULT_PLANNER_CONFIG",
]
