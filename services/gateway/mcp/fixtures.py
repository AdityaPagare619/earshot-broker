"""Synthetic fixture world for the EARSHOT MCP gateway (J3).

All data is synthetic, labeled FIXTURE. Two fixture profiles exercise the
declassification boundary honestly:
  STRICT   — private appointment existence is protected; public output must be
             invariant across secret swaps (paired-world test target).
  LENIENT  — the fixture policy explicitly declassifies coarse availability
             windows (dossier §6.4: declassification is explicit, small, typed).
"""
from __future__ import annotations

from dataclasses import dataclass

PUB = "*"


@dataclass(frozen=True)
class BusyBlock:
    """A busy interval. `title`/`location` are private unless labeled public."""
    start_min: int          # minutes after midnight, fixture date
    end_min: int
    title: str
    location: str
    public_title: bool = False   # explicit declassification of the title
    readers: frozenset = frozenset({"priya"})


@dataclass(frozen=True)
class FlexTask:
    name: str
    duration_min: int
    public_name: bool = False


@dataclass(frozen=True)
class FixtureWorld:
    name: str
    tenant: str
    owner: str
    public_derived_schedule: bool   # explicit declassification switch
    protect_existence: bool
    busy: tuple[BusyBlock, ...]
    flex: tuple[FlexTask, ...]
    public_facts: tuple[str, ...]   # durable-public facts, fixture-authored


def strict_world(secret_title: str = "Prenatal checkup", secret_location: str = "City Clinic") -> FixtureWorld:
    """Private appointment exists; its existence is protected."""
    return FixtureWorld(
        name="strict",
        tenant="house-a",
        owner="priya",
        public_derived_schedule=False,
        protect_existence=True,
        busy=(
            BusyBlock(600, 720, "Focus block", "home office"),
            BusyBlock(930, 960, secret_title, secret_location),
            BusyBlock(1140, 1170, "School pickup", "school gate", public_title=True,
                      readers=frozenset({"priya", "ravi"})),
        ),
        flex=(
            FlexTask("Call the bank", 20),
            FlexTask("Water the plants", 15, public_name=True),
        ),
        public_facts=(
            "Collect groceries after 6.",
            "Dinner prep at 7 PM.",
        ),
    )


def empty_world() -> FixtureWorld:
    """No private appointment at all. Paired-world counterpart to strict_world."""
    w = strict_world()
    kept = tuple(b for b in w.busy if b.start_min != 930)
    return FixtureWorld(w.name, w.tenant, w.owner, w.public_derived_schedule,
                        w.protect_existence, kept, w.flex, w.public_facts)


def lenient_world() -> FixtureWorld:
    """Coarse availability explicitly declassified by fixture policy."""
    w = strict_world()
    return FixtureWorld("lenient", w.tenant, w.owner, True, False,
                        w.busy, w.flex, w.public_facts)
