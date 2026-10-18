"""Stage port interfaces (DESIGN.md D5).

Each port is the seam-facing contract a stage implements. S6 ships FIXTURE
implementations behind these ports; sibling seats (S1–S4) replace the fixtures
with real mechanisms without changing callers. Ports speak the frozen
dataclasses from contracts.py ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanItem:
    item_id: str
    depth: int                     # 0..4, the planned spoken depth
    action: str                    # SPEAK | PHONE | DEFER


@dataclass(frozen=True)
class Plan:
    items: tuple                   # tuple[PlanItem]
    cover_mode: bool
    credible_set: frozenset        # persons (and "unknown")
    table_version: int


@dataclass(frozen=True)
class Response:
    speak: str                     # verbatim speak text
    structured: dict               # {speak, speak_policy, mode, followups, screen_depth}
    meta: dict                     # {plan_id, table_version}
    phone_digest: str              # full content for the personal channel ("" if none)


class SlowLanePort:
    """S1. Item -> TableRow. Owns quarantine, understanding, verify, compile."""

    def ingest(self, item):
        """Item -> Item(state=QUARANTINED). Immediate, unconditional."""
        raise NotImplementedError

    def compile(self, item):
        """Item(QUARANTINED) -> (Item(COMPILED), TableRow)."""
        raise NotImplementedError


class SecrecyPort:
    """S4. Item -> SecrecyEdge list. Owns inference + the monotone gate."""

    def infer_edges(self, item):
        """Item -> list[SecrecyEdge] (candidates, ungated)."""
        raise NotImplementedError

    def accept(self, edges):
        """Apply the monotone gate. Returns accepted edges only."""
        raise NotImplementedError


class HotLanePort:
    """S2. (TableRows, BeliefState) -> Plan. Pure functions, no I/O."""

    def fuse_belief(self, signals, priors, now):
        """Signals + priors -> BeliefState (log-odds, asymmetric trust)."""
        raise NotImplementedError

    def credible_set(self, belief, sensitivity):
        """BeliefState + sensitivity -> frozenset(persons)."""
        raise NotImplementedError

    def plan(self, rows, belief, ledger):
        """Rows + belief + exposure ledger -> Plan (minimax + budgets)."""
        raise NotImplementedError


class ShapePort:
    """S3. Plan -> Response. Owns constant-shape assembly."""

    def assemble(self, plan, rows_by_id, pack, fields_by_id):
        """Plan -> Response. Cover-mode shape is a function of the credible
        set only — never of hidden content."""
        raise NotImplementedError

    def probe_response(self, query, plan, pack):
        """Probe-resistant answer: identical whether the item exists or not."""
        raise NotImplementedError
