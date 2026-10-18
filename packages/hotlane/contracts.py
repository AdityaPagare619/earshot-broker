"""Frozen contracts for the sealed-speech hot lane (S2).

These dataclasses are copied VERBATIM from SEALED_SPEECH_BRIEF.md §2 ("Frozen
contracts"). They do not change mid-wave. If the brief's contracts evolve, this
module is updated to match exactly — never extended unilaterally.

NOTE for S6 integration: S1/S4 will need these same types. This module is the
reference definition; converge on one shared home at integration time.
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


@dataclass(frozen=True)
class SecrecyEdge:
    type: str                      # about|for|hidden_from|cleared_to
    target: str                    # person id or role:child|role:guest|...
    until: str | None              # expiry, "" if none
    provenance: str                # inferred|declared|confirmed
    confidence: float
    direction: str                 # TIGHTEN|LOOSEN (LOOSEN requires confirmed)


@dataclass(frozen=True)
class GeneralizationChain:
    depths: tuple                  # (d4, d3, d2, d1) strings, d0 = absorbed
    renditions: dict               # {lang: (d4,d3,d2,d1)} — compiled, verified


@dataclass(frozen=True)
class TableRow:                    # the ONLY thing the hot lane reads
    item_id: str
    sensitivity: float             # 0..1
    clearance: dict                # {person_or_role: depth_int}
    chain: GeneralizationChain
    version: int


@dataclass(frozen=True)
class BeliefState:
    log_odds: dict                 # {person: logit P(present)}
    timestamp: float
