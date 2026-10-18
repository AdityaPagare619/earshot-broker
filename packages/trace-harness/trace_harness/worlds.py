"""Paired synthetic worlds.

A World is a synthetic tenant setup: an owner, a set of labeled facts, and a
request script. A WorldPair differs ONLY in a secret — the harness runs the
same script against both and compares the public trace.

All fixtures are synthetic. Nothing here touches real data, real calendars,
or real identity.
"""
from dataclasses import dataclass, field
from typing import Any

PUB = frozenset({"*"})


def pub(key: str, value: str) -> dict:
    return {"key": key, "value": value, "readers": ("*",), "topics": ()}


def priv(key: str, value: str, owner: str, topics: tuple = ("health",)) -> dict:
    return {"key": key, "value": value, "readers": (owner,), "topics": topics}


@dataclass(frozen=True)
class World:
    """One synthetic world: tenant, owner, facts, and the request script.

    facts: tuple of fact dicts (see pub()/priv()).
    script: tuple of steps; each step is {"tool": name, "args": {...}}.
    The string "{receipt}" inside args is replaced with the request_ref
    returned by the most recent prepare_day_brief step.
    """

    name: str
    tenant: str
    owner: str
    facts: tuple
    script: tuple


@dataclass(frozen=True)
class WorldPair:
    """Two worlds differing only in the secret under test."""

    name: str
    description: str
    world_a: World
    world_b: World


def _script(*tools: tuple) -> tuple:
    return tuple({"tool": name, "args": dict(args)} for name, args in tools)


_PREPARE = (
    "prepare_day_brief",
    {"date": "2026-10-20", "timezone": "Asia/Kolkata",
     "request_key": "rk-pair-0001-min16chars"},
)


def builtin_pairs() -> tuple:
    """The five paired-world fixtures from dossier §14.3."""
    pairs = []

    pub_facts = (
        pub("weather", "Rain is forecast."),
        pub("news", "Markets closed flat."),
    )

    # 1. no private event vs one private event
    pairs.append(WorldPair(
        name="no_private_vs_one_private",
        description="World B has one private health fact; world A has none. "
                    "The public trace must be identical.",
        world_a=World("a", "tenant-pair1", "priya", pub_facts, _script(_PREPARE)),
        world_b=World("b", "tenant-pair1", "priya",
                      pub_facts + (priv("appt", "Prenatal checkup 3pm", "priya"),),
                      _script(_PREPARE)),
    ))

    # 2. prenatal vs therapy title (same slot, different secret content)
    pairs.append(WorldPair(
        name="prenatal_vs_therapy",
        description="The secret's *content* changes (prenatal vs therapy) with "
                    "identical shape. Public trace must not distinguish them.",
        world_a=World("a", "tenant-pair2", "priya",
                      pub_facts + (priv("appt", "Prenatal checkup 3pm", "priya"),),
                      _script(_PREPARE,
                              ("resolve_day_change",
                               {"change": "move it one hour later",
                                "request_key": "rk-pair-0002-min16chars",
                                "request_ref": "{receipt}"}))),
        world_b=World("b", "tenant-pair2", "priya",
                      pub_facts + (priv("appt", "Therapy session 3pm", "priya"),),
                      _script(_PREPARE,
                              ("resolve_day_change",
                               {"change": "move it one hour later",
                                "request_key": "rk-pair-0002-min16chars",
                                "request_ref": "{receipt}"}))),
    ))

    # 3. reordered private records
    priv1 = priv("appt1", "Dental cleaning 10am", "priya", ("health",))
    priv2 = priv("appt2", "Call accountant 4pm", "priya", ("finance",))
    pairs.append(WorldPair(
        name="reordered_private_records",
        description="Same secrets, different record order. Public trace must "
                    "be order-independent.",
        world_a=World("a", "tenant-pair3", "priya", pub_facts + (priv1, priv2),
                      _script(_PREPARE)),
        world_b=World("b", "tenant-pair3", "priya", pub_facts + (priv2, priv1),
                      _script(_PREPARE)),
    ))

    # 4. private source error vs private no-match
    pairs.append(WorldPair(
        name="source_error_vs_no_match",
        description="World A has a private fact flagged as a source error; "
                    "world B has no such fact. The error must not surface.",
        world_a=World("a", "tenant-pair4", "priya",
                      pub_facts + (priv("src", "CALENDAR_SYNC_ERROR: token expired",
                                       "priya", ("system",)),),
                      _script(_PREPARE,
                              ("resolve_day_change",
                               {"change": "retry the sync",
                                "request_key": "rk-pair-0004-min16chars",
                                "request_ref": "{receipt}"}))),
        world_b=World("b", "tenant-pair4", "priya", pub_facts,
                      _script(_PREPARE,
                              ("resolve_day_change",
                               {"change": "retry the sync",
                                "request_key": "rk-pair-0004-min16chars",
                                "request_ref": "{receipt}"}))),
    ))

    # 5. one private event vs several
    pairs.append(WorldPair(
        name="one_vs_several_private",
        description="World B has three private facts; world A has one. The "
                    "public trace must not reveal the count.",
        world_a=World("a", "tenant-pair5", "priya",
                      pub_facts + (priv("appt", "Prenatal checkup 3pm", "priya"),),
                      _script(_PREPARE,
                              ("continue_on_personal_device",
                               {"request_key": "rk-pair-0005-min16chars",
                                "request_ref": "{receipt}"}),
                              ("withdraw_request",
                               {"request_key": "rk-pair-0005b-min16chars",
                                "request_ref": "{receipt}"}))),
        world_b=World("b", "tenant-pair5", "priya",
                      pub_facts + (
                          priv("appt", "Prenatal checkup 3pm", "priya"),
                          priv("rx", "Prescription refill due", "priya"),
                          priv("lab", "Lab results pending", "priya"),
                      ),
                      _script(_PREPARE,
                              ("continue_on_personal_device",
                               {"request_key": "rk-pair-0005-min16chars",
                                "request_ref": "{receipt}"}),
                              ("withdraw_request",
                               {"request_key": "rk-pair-0005b-min16chars",
                                "request_ref": "{receipt}"}))),
    ))

    return tuple(pairs)
