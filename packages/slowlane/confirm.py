"""Confirm queue (S1).

Ambiguous edges (0.3 <= confidence < 0.6) and loosening proposals wait here
for an authenticated owner decision — off the hot path, on the phone.

The queue can only make the system quieter:
- Unresolved entries EXPIRE into TIGHTEN (fail private). Dead letters are
  fail-open timers; this queue has none.
- Loosening without authenticated=True is REJECTED, not queued.
- The queue emits decisions; S4's monotone gate consumes them.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .models import SecrecyEdge


@dataclass(frozen=True)
class ConfirmEntry:
    id: str
    kind: str            # "edge_confirm" | "loosen_request"
    edge: SecrecyEdge
    created_at: float
    expires_at: float
    # human-readable prompt for the phone card, e.g.
    # "Keep this from Maya until Nov 3?"
    prompt: str


@dataclass(frozen=True)
class Resolution:
    entry_id: str
    decision: str        # "confirmed" | "rejected" | "expired_tighten"
    authenticated: bool
    resolved_at: float


class ConfirmError(Exception):
    """Queue misuse: unknown entry, double resolution, unauthenticated loosen."""


class ConfirmQueue:
    """Off-hot-path confirmation. Resolutions are recorded; the queue itself
    holds no clearances and grants nothing."""

    DEFAULT_TTL_S = 7 * 24 * 3600  # a week; explicit data, not magic

    def __init__(self, ttl_s: float = DEFAULT_TTL_S,
                 clock=time.time) -> None:
        self._entries: Dict[str, ConfirmEntry] = {}
        self._resolutions: List[Resolution] = []
        self._ids = itertools.count(1)
        self._ttl_s = ttl_s
        self._clock = clock

    def submit_edge(self, edge: SecrecyEdge, prompt: str) -> ConfirmEntry:
        """Submit an ambiguous edge (0.3 <= confidence < 0.6) for confirmation.

        High-confidence TIGHTEN edges (>= 0.6) never enter the queue — they
        apply immediately (S4's gate). LOOSEN edges are rejected here outright:
        loosening is an authenticated act, not a queueable proposal.
        """
        if edge.direction == "LOOSEN":
            raise ConfirmError(
                "LOOSEN edges are never queued: loosening requires an "
                "authenticated act at submission time"
            )
        if not (0.3 <= edge.confidence < 0.6):
            raise ConfirmError(
                f"edge confidence {edge.confidence} out of queue band "
                "[0.3, 0.6): apply directly or discard, do not queue"
            )
        return self._enqueue("edge_confirm", edge, prompt)

    def submit_loosen(self, edge: SecrecyEdge, prompt: str,
                      authenticated: bool) -> ConfirmEntry:
        """A loosening proposal. Rejected immediately unless authenticated —
        never parked in the queue hoping for auth later."""
        if not authenticated:
            raise ConfirmError(
                "unauthenticated loosen request rejected (not queued)"
            )
        if edge.direction != "LOOSEN":
            raise ConfirmError("submit_loosen requires a LOOSEN edge")
        return self._enqueue("loosen_request", edge, prompt)

    def _enqueue(self, kind: str, edge: SecrecyEdge, prompt: str) -> ConfirmEntry:
        now = self._clock()
        entry = ConfirmEntry(
            id=f"cfm_{next(self._ids)}",
            kind=kind, edge=edge,
            created_at=now, expires_at=now + self._ttl_s,
            prompt=prompt,
        )
        self._entries[entry.id] = entry
        return entry

    def resolve(self, entry_id: str, decision: str,
                authenticated: bool) -> Resolution:
        """decision: "confirmed" | "rejected". Loosening confirmations require
        authenticated=True. Double resolution raises."""
        entry = self._entries.get(entry_id)
        if entry is None:
            raise ConfirmError(f"unknown confirm entry {entry_id}")
        if decision not in ("confirmed", "rejected"):
            raise ConfirmError(f"bad decision {decision!r}")
        if entry.kind == "loosen_request" and not authenticated:
            raise ConfirmError(
                "cannot confirm a loosening without authentication"
            )
        resolution = Resolution(entry_id=entry_id, decision=decision,
                                authenticated=authenticated,
                                resolved_at=self._clock())
        del self._entries[entry_id]
        self._resolutions.append(resolution)
        return resolution

    def sweep(self, now: float | None = None) -> List[Resolution]:
        """Expire overdue entries INTO TIGHTEN. Returns what expired."""
        now = self._clock() if now is None else now
        expired = []
        for entry_id, entry in list(self._entries.items()):
            if entry.expires_at <= now:
                resolution = Resolution(
                    entry_id=entry_id, decision="expired_tighten",
                    authenticated=False, resolved_at=now,
                )
                del self._entries[entry_id]
                self._resolutions.append(resolution)
                expired.append(resolution)
        return expired

    def pending(self) -> List[ConfirmEntry]:
        return list(self._entries.values())

    def resolutions(self) -> List[Resolution]:
        return list(self._resolutions)
