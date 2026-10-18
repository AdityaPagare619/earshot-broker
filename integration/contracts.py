"""Frozen sealed-speech contracts (SEALED_SPEECH_BRIEF.md §2).

These dataclasses are the interface between the six seats. They do not change
mid-wave. Sibling seats' real modules will speak these exact types; the S6
fixtures below do too.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    id: str
    owner: str
    kind: str                      # event|reminder|delivery|note|message_summary
    source: str
    start: str
    end: str
    raw_ref: str                   # encrypted vault ref — NEVER raw content
    state: str                     # QUARANTINED|COMPILED|RELEASED|EXPIRED
    lang_detected: tuple           # e.g. ("en",) or ("hi", "hi-Latn")
    fields: dict = field(default_factory=dict)   # placeholder fields for renditions
    topics: tuple = ()             # dotted topic paths, e.g. ("health.reproductive",)


@dataclass(frozen=True)
class SecrecyEdge:
    type: str                      # about|for|hidden_from|cleared_to
    target: str                    # person id or role:child|role:guest|...
    until: str | None              # expiry, None if none
    provenance: str                # inferred|declared|confirmed
    confidence: float
    direction: str                 # TIGHTEN|LOOSEN (LOOSEN requires confirmed)


@dataclass(frozen=True)
class GeneralizationChain:
    depths: tuple                  # (d4, d3, d2, d1) strings; d0 = absorbed
    renditions: dict               # {lang: (d4,d3,d2,d1)} — compiled, verified


@dataclass(frozen=True)
class TableRow:
    """The ONLY thing the hot lane reads."""
    item_id: str
    sensitivity: float             # 0..1
    clearance: dict                # {person_or_role: depth_int}
    chain: GeneralizationChain
    version: int


@dataclass(frozen=True)
class BeliefState:
    log_odds: dict                 # {person: logit P(present)}
    timestamp: float
