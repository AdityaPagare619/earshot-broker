"""The Monotone Acceptance Gate (S4) — Law 6, executable.

``accept = (direction == TIGHTEN and confidence >= 0.6) or
           (direction == LOOSEN and valid Confirmation)``

This module is the ONLY place that converts an ``EdgeProposal`` into a
``SecrecyEdge``. ``EdgeStore.add()`` calls it internally; there is no other
entry point. The gate is total or it is theater (SEAT_VERDICT.md finding #2).

Semantics, nailed down:

- TIGHTEN + confidence >= 0.6 → accepted. Provenance becomes "declared" iff the
  proposal's claimed_source is "declared" (an explicit user act such as
  keep_secret); otherwise "inferred".
- TIGHTEN + confidence < 0.6 → dropped (returned None). A false tightening only
  costs utility, but a threshold keeps the graph auditable and the property
  tests meaningful.
- LOOSEN + a Confirmation whose principal matches the item owner → accepted with
  provenance "confirmed".
- LOOSEN + anything else (no confirmation, wrong principal, claimed
  provenance="confirmed" smuggled in a proposal) → dropped. There is no field
  on EdgeProposal that can carry confirmation; the token travels separately.
- Garbage enums, NaN/infinite confidence, empty target → dropped (fail closed).
  The gate never raises on hostile input; it returns None.
"""
from __future__ import annotations

import math

from .edges import (
    DIRECTIONS,
    EDGE_TYPES,
    PROVENANCES,
    TIGHTEN_THRESHOLD,
    Confirmation,
    EdgeProposal,
    SecrecyEdge,
    normalize_until,
)


class MonotoneGate:
    """Stateless choke point. All methods are pure."""

    @staticmethod
    def accept(proposal: EdgeProposal,
               confirmation: Confirmation | None = None,
               owner: str | None = None) -> SecrecyEdge | None:
        if not isinstance(proposal, EdgeProposal):
            return None
        if proposal.type not in EDGE_TYPES:
            return None
        if proposal.direction not in DIRECTIONS:
            return None
        if not isinstance(proposal.target, str) or not proposal.target.strip():
            return None
        conf = proposal.confidence
        if not isinstance(conf, (int, float)) or isinstance(conf, bool):
            return None
        if not math.isfinite(conf) or not 0.0 <= conf <= 1.0:
            return None
        until = normalize_until(proposal.until)

        if proposal.direction == "TIGHTEN":
            if conf < TIGHTEN_THRESHOLD:
                return None
            provenance = ("declared" if proposal.claimed_source == "declared"
                          else "inferred")
            return SecrecyEdge(
                type=proposal.type,
                target=proposal.target.strip(),
                until=until,
                provenance=provenance,
                confidence=float(conf),
                direction="TIGHTEN",
            )

        # LOOSEN: the only path is a valid, owner-bound Confirmation.
        if (confirmation is not None
                and isinstance(confirmation, Confirmation)
                and owner is not None
                and confirmation.principal == owner):
            return SecrecyEdge(
                type=proposal.type,
                target=proposal.target.strip(),
                until=until,
                provenance="confirmed",
                confidence=float(conf),
                direction="LOOSEN",
            )
        return None
