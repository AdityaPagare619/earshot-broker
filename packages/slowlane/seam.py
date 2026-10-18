"""Seam 1 made executable (S1).

project_for_hotlane() is the quarantine boundary as a function: S2 builds
against it, and the counterfactual test asserts on its bytes.

Contract (brief §2, DATAFLOW-PIPELINE.md Seam 1):
- Allowed across: versioned TableRows (+ priors, passed separately).
- Forbidden across: raw item content, uncompiled items (they do not appear
  in the projection at all — not even as placeholders; a count of pending
  items would itself leak), inference traces, the secrecy graph.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .models import COMPILED, RELEASED, TableRow


@dataclass(frozen=True)
class RowView:
    """What the hot lane sees for one compiled item. There is no other shape:
    quarantined items do not appear in the projection at all — not even as
    placeholders. A *count* of pending items would itself leak ("something
    arrived 5s ago"); cover-mode assembly (S3) needs no per-item d0 entries
    to append its fixed suffix."""
    item_id: str
    state: str            # COMPILED|RELEASED
    row: TableRow         # always present: the ONLY thing crossing Seam 1


def project_for_hotlane(rows: Dict[str, TableRow],
                        states: Dict[str, str]) -> Dict[str, RowView]:
    """Build the hot-lane-visible projection.

    rows: item_id -> TableRow for items that have compiled rows.
    states: item_id -> quarantine state for every known item.

    Only COMPILED/RELEASED items appear — and only if a row exists for them.
    QUARANTINED and EXPIRED items are invisible here, EVEN IF a stale row
    exists (defense in depth: state, not row presence, decides). This is what
    makes the canonical counterfactual hold: an adversarial email arriving 5s
    before a briefing changes exactly zero bytes of this projection.
    """
    projection: Dict[str, RowView] = {}
    for item_id, state in states.items():
        if state in (COMPILED, RELEASED) and item_id in rows:
            projection[item_id] = RowView(item_id=item_id, state=state,
                                          row=rows[item_id])
    return projection


def projection_bytes(projection: Dict[str, RowView]) -> bytes:
    """Canonical byte encoding of a projection, for counterfactual equality.

    Deterministic: sorted keys, fixed field order, no timestamps, no memory
    addresses. Two projections with identical bytes expose identical
    hot-lane-visible state — the Seam 1 counterfactual asserts exactly this.
    """
    parts = []
    for item_id in sorted(projection):
        view = projection[item_id]
        r = view.row
        chain = "|".join(r.chain.depths)
        clr = ",".join(f"{k}={v}" for k, v in sorted(r.clearance.items()))
        parts.append(
            f"{item_id}|{view.state}|v{r.version}|s{r.sensitivity:.3f}"
            f"|{clr}|{chain}".encode()
        )
    return b"\n".join(parts)
