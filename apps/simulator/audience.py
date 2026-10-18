"""Audience event source for the controlled host.

Two origins, both honestly labeled (dossier §12.2 — no face enrollment in the
competition MVP, no claimed real-world listener detection):

- "manual": the household guest-mode control. A guest can restrict sharing
  without enrolling an identity (dossier decision 19).
- "scripted": timed sensor events for the demo (e.g. "Mom enters at t+8s").
  Labeled simulated in the UI and in every event.

Events carry monotonic sequence numbers and observed/received timestamps. The
arbiter rejects seq-regressed or time-anomalous events; stale evidence degrades
to UNKNOWN rather than upgrading disclosure (dossier §6.6).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from arbiter import AudienceEvent


@dataclass
class SensorScript:
    """One scripted room event, for the demo path."""
    at_offset: float  # seconds after script start
    listeners: frozenset
    label: str  # human description, e.g. "Mom enters"


class AudienceSource:
    """Produces AudienceEvents from manual controls and demo scripts."""

    def __init__(self, owner: str, zone: str = "living-room"):
        self._owner = owner
        self._zone = zone
        self._seq = 0
        self._lock = threading.Lock()
        self._script: list[SensorScript] = []
        self._script_start: float | None = None
        self._fired: set[int] = set()
        self._last_listeners: frozenset = frozenset({owner})

    # ---- manual guest-mode control --------------------------------------

    def manual_set(self, listeners: frozenset[str]) -> AudienceEvent:
        """Household restriction control. No identity required to restrict."""
        return self._emit(frozenset(listeners), source="manual")

    def manual_guest_enters(self, guest_label: str = "guest") -> AudienceEvent:
        with self._lock:
            current = self._current_listeners_locked()
        return self._emit(current | frozenset({guest_label}), source="manual")

    def manual_guest_leaves(self, guest_label: str = "guest") -> AudienceEvent:
        with self._lock:
            current = self._current_listeners_locked()
        return self._emit(current - frozenset({guest_label}), source="manual")

    # ---- scripted demo sensor --------------------------------------------

    def load_script(self, steps: list[SensorScript]) -> None:
        with self._lock:
            self._script = sorted(steps, key=lambda s: s.at_offset)
            self._script_start = time.time()
            self._fired = set()

    def poll_script(self) -> list[AudienceEvent]:
        """Return any scripted events whose time has come (labeled scripted)."""
        out: list[AudienceEvent] = []
        with self._lock:
            if self._script_start is None:
                return out
            elapsed = time.time() - self._script_start
            for i, step in enumerate(self._script):
                if i not in self._fired and elapsed >= step.at_offset:
                    self._fired.add(i)
                    out.append(self._make_event(
                        frozenset(step.listeners), source="scripted"))
        return out

    # ---- internals --------------------------------------------------------

    def _current_listeners_locked(self) -> frozenset:
        return self._last_listeners or frozenset({self._owner})

    def _make_event(self, listeners: frozenset, source: str) -> AudienceEvent:
        self._seq += 1
        now = time.time()
        self._last_listeners = frozenset(listeners)
        return AudienceEvent(seq=self._seq, observed_at=now, received_at=now,
                             listeners=frozenset(listeners), source=source,
                             zone=self._zone)

    def _emit(self, listeners: frozenset, source: str) -> AudienceEvent:
        with self._lock:
            return self._make_event(listeners, source)
