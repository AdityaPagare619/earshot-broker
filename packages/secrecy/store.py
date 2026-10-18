"""EdgeStore — the graph's single choke point (S4).

There is deliberately NO ``add_edge()``. Edges enter the graph only as
``EdgeProposal``s through ``add()``, which applies ``MonotoneGate.accept()``
internally. If you are looking for a way to write an edge directly: it does not
exist, and its absence is the security property (SEAT_VERDICT.md P2).

Expiry (``until``) is evaluated at read time: expired edges are invisible to
``active_edges()`` and to clearance computation. An expired secret edge does not
linger — but note the direction is safe either way: expiry of a TIGHTEN edge can
only *restore* the compiled base clearance, never exceed it.
"""
from __future__ import annotations

import time
from datetime import date as date_cls

from .edges import Confirmation, EdgeProposal, SecrecyEdge, normalize_until
from .gate import MonotoneGate


def _expired(edge: SecrecyEdge, now: float) -> bool:
    until = normalize_until(edge.until)
    if until is None:
        return False
    try:
        return date_cls.fromisoformat(until).isoformat() < \
            time.strftime("%Y-%m-%d", time.gmtime(now))
    except ValueError:
        # Unparseable expiry: fail closed — treat as never expiring.
        return False


class EdgeStore:
    """In-memory graph. Item id -> list of accepted edges, insertion ordered."""

    def __init__(self) -> None:
        self._edges: dict[str, list[SecrecyEdge]] = {}

    def add(self, item_id: str, proposal: EdgeProposal, *,
            confirmation: Confirmation | None = None,
            owner: str | None = None,
            now: float | None = None) -> SecrecyEdge | None:
        """Propose an edge. Returns the accepted SecrecyEdge, or None if the
        gate dropped it. ``now`` is injectable for time-travel tests."""
        _ = now  # accepted-at is not stored; expiry is read-time. Kept for API symmetry.
        edge = MonotoneGate.accept(proposal, confirmation=confirmation,
                                   owner=owner)
        if edge is None:
            return None
        self._edges.setdefault(item_id, []).append(edge)
        return edge

    def active_edges(self, item_id: str, now: float | None = None) -> tuple[SecrecyEdge, ...]:
        """Edges for an item whose ``until`` has not passed."""
        now = time.time() if now is None else now
        return tuple(e for e in self._edges.get(item_id, [])
                     if not _expired(e, now))

    def all_edges(self, item_id: str) -> tuple[SecrecyEdge, ...]:
        """Including expired — for audit, never for decisions."""
        return tuple(self._edges.get(item_id, []))

    def item_ids(self) -> tuple[str, ...]:
        return tuple(self._edges.keys())
