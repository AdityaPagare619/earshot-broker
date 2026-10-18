"""Frozen data contracts for the sealed-speech architecture (S1 implements verbatim).

Copied exactly from SEALED_SPEECH_BRIEF.md §2. These dataclasses are the trust
boundary between the slow lane and the hot lane: the hot lane reads ONLY
TableRow. Drift from the brief is a contract violation — change the brief first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Tuple


# ---------------------------------------------------------------------------
# Frozen contracts (brief §2 — do not change mid-wave)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    id: str
    owner: str
    kind: str          # event|reminder|delivery|note|message_summary
    source: str
    start: str
    end: str
    raw_ref: str       # encrypted vault ref — NEVER raw content
    state: str         # QUARANTINED|COMPILED|RELEASED|EXPIRED
    lang_detected: Tuple[str, ...]  # e.g. ("en",) or ("hi", "hi-Latn")


@dataclass(frozen=True)
class SecrecyEdge:
    type: str          # about|for|hidden_from|cleared_to
    target: str        # person id or role:child|role:guest|...
    until: str | None  # expiry, "" if none
    provenance: str    # inferred|declared|confirmed
    confidence: float
    direction: str     # TIGHTEN|LOOSEN (LOOSEN requires confirmed)


@dataclass(frozen=True)
class GeneralizationChain:
    depths: Tuple[str, str, str, str]  # (d4, d3, d2, d1) strings, d0 = absorbed
    renditions: Dict[str, Tuple[str, str, str, str]]  # {lang: (d4,d3,d2,d1)}


@dataclass(frozen=True)
class TableRow:        # the ONLY thing the hot lane reads
    item_id: str
    sensitivity: float  # 0..1
    clearance: Dict[str, int]  # {person_or_role: depth_int}
    chain: GeneralizationChain
    version: int


@dataclass(frozen=True)
class BeliefState:
    log_odds: Dict[str, float]  # {person: logit P(present)}
    timestamp: float


# ---------------------------------------------------------------------------
# S1-internal contracts (consumed/produced inside the slow lane)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnderstandOutput:
    """What the understand step produces for render + edge inference (S4)."""
    item_id: str
    topics: Tuple[str, ...]                    # from the pack's fixed taxonomy
    entities: Dict[str, FrozenSet[str]]        # canonical name -> alias set
    sensitive: Dict[str, int]                  # entity -> max depth it may appear at
    sensitive_topics: Dict[str, int]           # topic -> max depth it may appear at
    sensitivity: float                         # 0..1; unknown -> 1.0 (fail private)
    confidence: float
    lang_detected: Tuple[str, ...]


@dataclass(frozen=True)
class RenderInput:
    """The ONLY thing a renderer may see. Raw content never enters the renderer
    directly: a real backend resolves vault_token inside the slow lane. The
    fixture backend ignores vault_token (and says so)."""
    item_id: str
    kind: str
    time_label: str      # e.g. "3:40 PM"
    daypart: str         # morning|afternoon|evening|night
    location_type: str   # clinic|home|office|store|unknown
    counterparty_role: str  # e.g. "doctor", "child", "" if none
    langs: Tuple[str, ...]
    vault_token: str = ""  # opaque; fixture backend must not use it


@dataclass(frozen=True)
class DraftChain:
    """An unverified generalization chain draft. Must pass the verifier before
    it can become a GeneralizationChain."""
    depths: Tuple[str, str, str, str]
    renditions: Dict[str, Tuple[str, str, str, str]]
    backend: str  # "fixture-template" | "llm" — labeled, always


# ---------------------------------------------------------------------------
# Quarantine state machine
# ---------------------------------------------------------------------------

QUARANTINED = "QUARANTINED"
COMPILED = "COMPILED"
RELEASED = "RELEASED"
EXPIRED = "EXPIRED"

_STATES = frozenset({QUARANTINED, COMPILED, RELEASED, EXPIRED})

# Legal transitions. COMPILED->COMPILED is recompile (version must increase;
# enforced by the compiler, not here). Anything -> EXPIRED.
_TRANSITIONS = frozenset({
    (QUARANTINED, COMPILED),
    (COMPILED, COMPILED),   # recompile
    (COMPILED, RELEASED),
    (QUARANTINED, EXPIRED),
    (COMPILED, EXPIRED),
    (RELEASED, EXPIRED),
})


class IllegalTransition(Exception):
    """A quarantine state transition that the machine forbids."""


def transition(item: Item, to: str) -> Item:
    """Return a new Item in state `to`, or raise IllegalTransition.

    Pure function: the state machine has no memory beyond the transition table.
    """
    if to not in _STATES:
        raise IllegalTransition(f"unknown state {to!r}")
    if (item.state, to) not in _TRANSITIONS:
        raise IllegalTransition(
            f"forbidden transition {item.state} -> {to} for item {item.id}"
        )
    return Item(
        id=item.id, owner=item.owner, kind=item.kind, source=item.source,
        start=item.start, end=item.end, raw_ref=item.raw_ref, state=to,
        lang_detected=item.lang_detected,
    )


def quarantine_new(item_id: str, owner: str, kind: str, source: str,
                   start: str = "", end: str = "",
                   lang_detected: Tuple[str, ...] = ("en",)) -> Item:
    """Ingest a new item. ALWAYS enters QUARANTINED — unconditionally.

    This is the constructor the pipeline must use: there is no code path that
    creates an Item in any other initial state.
    """
    return Item(
        id=item_id, owner=owner, kind=kind, source=source,
        start=start, end=end,
        raw_ref=f"vault://{owner}/{item_id}",  # vault ref, never content
        state=QUARANTINED,
        lang_detected=lang_detected,
    )
