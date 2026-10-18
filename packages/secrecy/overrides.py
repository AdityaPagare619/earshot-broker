"""Effective clearance — the hot-patch overlay (S4).

``effective_clearance(item_id, base, store, now)`` computes what the hot lane
may actually use: the compiled base clearance (S1's TableRow.clearance) with
every active TIGHTEN edge applied via ``min()``.

Monotone by construction: the overlay can only LOWER a depth, never raise one.
``keep_secret`` is "immediate" because this function reads the live store —
no async recompile stands between the spoken sentence and the safety effect.

Output shape is EXACTLY the frozen ``TableRow.clearance`` shape
(``{person_or_role: depth_int}``) — the S1/S2 interface contract (DESIGN.md §4).

Edge-type semantics here:
- ``hidden_from`` → target's depth becomes 0 (min with 0). The safety-critical
  direction; fully handled.
- ``cleared_to`` / ``about`` / ``for`` → recorded in the graph for S1's compiler
  (richer clearance computation); the overlay does not raise on them. The overlay
  never loosens, so informational edges are left to compilation.
"""
from __future__ import annotations

import time

from store import EdgeStore


#: Edges stored under this item id apply to every item (standing rules such
#: as keep_secret sentences). Consulted alongside item-specific edges.
GLOBAL_SCOPE = "*"


def effective_clearance(item_id: str, base: dict[str, int],
                        store: EdgeStore,
                        now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    result = {k: int(v) for k, v in base.items()}
    edges = list(store.active_edges(item_id, now))
    if item_id != GLOBAL_SCOPE:
        edges += list(store.active_edges(GLOBAL_SCOPE, now))
    for edge in edges:
        if edge.direction != "TIGHTEN":
            continue  # belt-and-braces; the store only holds gated edges
        if edge.type == "hidden_from":
            target = edge.target
            result[target] = min(result.get(target, 0), 0)
    return result
