"""Household Secrecy Graph — edge types (S4).

Law 1: every secret has a non-audience. Edges name *who an item is kept from*
(or about/for whom it exists), not how "sensitive" it is in the abstract.

The frozen contract (SEALED_SPEECH_BRIEF §2) is implemented verbatim. Two types
cross this module:

- ``EdgeProposal`` — UNTRUSTED. Produced by heuristic/LLM proposers. Carries no
  authority; it is a suggestion the gate may accept or drop.
- ``SecrecyEdge`` — TRUSTED. Can only be minted by ``MonotoneGate.accept()``.
  ``EdgeStore`` never accepts a raw edge (there is no such API).

``Confirmation`` is the only way to mint ``provenance="confirmed"``. It is a
separate type that proposers cannot produce: the gate takes it as an explicit
argument, and only the authenticated phone path (S1's confirm queue / the
personal channel) mints it. A proposer literally cannot spell "confirmed".
"""
from __future__ import annotations

from dataclasses import dataclass


# --- vocabulary (frozen) ----------------------------------------------------

EDGE_TYPES = ("about", "for", "hidden_from", "cleared_to")
PROVENANCES = ("inferred", "declared", "confirmed")
DIRECTIONS = ("TIGHTEN", "LOOSEN")

#: Confidence at or above which an unconfirmed TIGHTEN proposal is accepted.
TIGHTEN_THRESHOLD = 0.6


@dataclass(frozen=True)
class SecrecyEdge:
    """A trusted secrecy-graph edge. Minted ONLY by MonotoneGate.accept()."""
    type: str          # about|for|hidden_from|cleared_to
    target: str        # person id or role:child|role:guest|...
    until: str | None  # expiry ISO date, or None/"" for none
    provenance: str    # inferred|declared|confirmed
    confidence: float  # 0..1
    direction: str     # TIGHTEN|LOOSEN (LOOSEN requires confirmed)


@dataclass(frozen=True)
class EdgeProposal:
    """An untrusted edge suggestion from a proposer (heuristic or LLM-shaped).

    Note what is ABSENT: there is no ``provenance`` field settable to
    "confirmed". The gate assigns provenance; "confirmed" additionally requires
    a ``Confirmation`` token the proposer cannot mint.
    """
    type: str
    target: str
    until: str | None
    confidence: float
    direction: str
    reason: str  # heuristic/model rationale — audit trail, never secret content
    claimed_source: str = "inferred"  # "inferred" | "declared" (voice user act)


@dataclass(frozen=True)
class Confirmation:
    """Authenticated owner act authorizing a LOOSEN. Minted ONLY by the
    authenticated phone path — never by a proposer, never by voice."""
    principal: str   # owner id, must match the item owner
    scope: str       # human-readable scope, e.g. "edge:itm_7f3a->mom"
    at: float        # unix timestamp


def normalize_until(until: str | None) -> str | None:
    """The frozen contract allows None or "" for 'no expiry'."""
    if until is None:
        return None
    until = until.strip()
    return until or None
