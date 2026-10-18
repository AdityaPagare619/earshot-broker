"""Room declarations — the `room` tool's state (S4).

The asymmetric-trust table is applied AT INGEST, here, not in S2's fusion.
Each declaration carries its trust class as data (``can_add`` / ``can_remove`` /
``max_loosen_sensitivity``), so S2's belief fusion consumes it — and a fusion
that ignores the trust class is visibly, testably wrong (SEAT_VERDICT.md
finding #5).

Trust table (FINAL-ARCHITECTURE.md §4 Law 2, DATAFLOW-PIPELINE.md Stage 3.1):

| declaration            | source          | can_add | can_remove | loosen cap         |
|------------------------|-----------------|---------|------------|--------------------|
| "<person> is here"      | voice or app    | True    | False      | —                  |
| "I'm alone"            | voice / app     | False   | True       | sensitivity < 0.7  |
| "private now"          | app+authenticated| False  | True       | none (full)        |
| any presence hint      | any             | True    | False      | — (tighten-only)   |

Voice can never fully clear a room: "I'm alone" only loosens low-sensitivity
items within its half-life. Full clearing is an authenticated act.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Declaration:
    person: str            # who the declaration is about ("mom", "unknown")
    kind: str              # "present" | "absent"
    source: str            # "voice" | "app"
    authenticated: bool
    timestamp: float
    can_add: bool          # may raise P(person present)
    can_remove: bool       # may lower P(person present)
    max_loosen_sensitivity: float | None  # None = uncapped


#: Voice "I'm alone" only loosens items below this sensitivity.
VOICE_ALONE_SENSITIVITY_CAP = 0.7


def classify(kind: str, source: str, authenticated: bool) -> tuple[bool, bool, float | None]:
    """The asymmetric-trust table. Pure function — S2 can reuse it directly."""
    if kind == "present":
        return True, False, None
    # kind == "absent"
    if source == "app" and authenticated:
        return False, True, None
    return False, True, VOICE_ALONE_SENSITIVITY_CAP


class DeclarationLog:
    """Append-only log of room declarations. In-memory; per process."""

    def __init__(self) -> None:
        self._log: list[Declaration] = []

    def declare(self, person: str, kind: str, source: str = "voice",
                authenticated: bool = False,
                timestamp: float | None = None) -> Declaration:
        if kind not in ("present", "absent"):
            raise ValueError(f"bad declaration kind: {kind!r}")
        if source not in ("voice", "app"):
            raise ValueError(f"bad declaration source: {source!r}")
        can_add, can_remove, cap = classify(kind, source, authenticated)
        decl = Declaration(
            person=person.strip().lower() or "unknown",
            kind=kind, source=source, authenticated=authenticated,
            timestamp=time.time() if timestamp is None else timestamp,
            can_add=can_add, can_remove=can_remove,
            max_loosen_sensitivity=cap,
        )
        self._log.append(decl)
        return decl

    def since(self, t: float) -> tuple[Declaration, ...]:
        return tuple(d for d in self._log if d.timestamp >= t)

    def all(self) -> tuple[Declaration, ...]:
        return tuple(self._log)


# --- deterministic declaration parsing ("Mom's here" / "I'm alone") ---------

_PRESENT_RES = [
    re.compile(r"^\s*([a-z]+(?:\s+[a-z]+)?)\s*(?:'s|is)\s+here\s*[.!]?\s*$"),
    re.compile(r"^\s*(?:we have|there are)\s+guests?\s+.*$"),
]
_ABSENT_RES = [
    re.compile(r"^\s*i(?:'m| am)\s+alone\s*[.!]?\s*$"),
    re.compile(r"^\s*([a-z]+(?:\s+[a-z]+)?)\s+(?:left|has left|'s left)\s*[.!]?\s*$"),
]
_PRIVATE_NOW_RE = re.compile(r"^\s*private\s+now\s*[.!]?\s*$")


def parse_declaration(text: str) -> tuple[str, str] | None:
    """Parse a spoken declaration → (person, kind) or None if unparseable.

    Unparseable input is NOT a failure of the tool — the tool records nothing
    and answers room-safe. Failing closed on parse means: no declaration, no
    state change, no leak.
    """
    t = text.strip().lower()
    if _PRIVATE_NOW_RE.match(t):
        return ("owner", "absent")  # voice "private now": treated as "I'm alone"
    for rx in _ABSENT_RES:
        m = rx.match(t)
        if m:
            if "alone" in t:
                return ("owner", "absent")
            return (m.group(1), "absent")
    for rx in _PRESENT_RES:
        m = rx.match(t)
        if m:
            if "guest" in t:
                return ("role:guest", "present")
            return (m.group(1), "present")
    return None
