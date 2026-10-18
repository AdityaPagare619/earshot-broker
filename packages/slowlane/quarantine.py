"""Quarantine store (S1).

The store is the operational face of the state machine in models.py: it holds
items, enforces that publication requires COMPILED state, and answers the one
question the seam cares about — "what may the hot lane see?"
"""
from __future__ import annotations

from typing import Dict, List

from .models import (
    COMPILED, EXPIRED, Item, IllegalTransition, QUARANTINED, RELEASED,
    quarantine_new, transition,
)


class QuarantineError(Exception):
    """Store-level quarantine violation."""


class QuarantineStore:
    """Holds items across their lifecycle. Single-threaded owner semantics:
    one store per slow-lane worker; no shared mutable state across workers."""

    def __init__(self) -> None:
        self._items: Dict[str, Item] = {}

    def ingest(self, item_id: str, owner: str, kind: str, source: str,
               start: str = "", end: str = "",
               lang_detected: tuple = ("en",)) -> Item:
        """New items ALWAYS enter QUARANTINED. There is no other entry point."""
        if item_id in self._items:
            raise QuarantineError(f"duplicate ingest of {item_id}")
        item = quarantine_new(item_id, owner, kind, source, start, end,
                              lang_detected)
        assert item.state == QUARANTINED  # structural, not aspirational
        self._items[item_id] = item
        return item

    def get(self, item_id: str) -> Item:
        return self._items[item_id]

    def transition(self, item_id: str, to: str) -> Item:
        item = self._items[item_id]
        new_item = transition(item, to)  # raises IllegalTransition
        self._items[item_id] = new_item
        return new_item

    def compiled_items(self) -> List[Item]:
        """Items the hot lane is allowed to know exist in compiled form."""
        return [i for i in self._items.values() if i.state == COMPILED]

    def quarantined_items(self) -> List[Item]:
        """Items that must be invisible above d0."""
        return [i for i in self._items.values() if i.state == QUARANTINED]

    def __len__(self) -> int:
        return len(self._items)
