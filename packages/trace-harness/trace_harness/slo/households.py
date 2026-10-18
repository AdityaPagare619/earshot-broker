"""Synthetic households for the SLO lab.

A Household has 4-6 people with roles, a 30-day calendar of Episodes, and
seeded secrets with ground-truth non-audiences. Everything is drawn from a
seeded RNG: re-running with the same seed reproduces the households
bit-for-bit. All strings are FIXTURE (see lexicon.py).

Design notes:
- Secret days and public items are seeded INDEPENDENTLY. This matters: the
  existence-AUC test needs P(secret day) independent of everything the
  listener can observe except the policy's own behavior.
- Audience and secret presence are seeded independently too, so "cover mode"
  cannot leak secret existence through correlation.
- Belief noise is a fixture model of uncertainty (missed detections, phantom
  guests), not a sensor claim.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import lexicon as L

DAYS = 30
SLOTS = ("morning", "evening")


@dataclass(frozen=True)
class Person:
    id: str
    role: str  # owner|partner|child|elder|guest


@dataclass(frozen=True)
class Secret:
    id: str
    topic: str
    sensitivity: float
    non_audience_roles: tuple
    clearance: dict  # role -> depth int
    text: dict       # lang -> str (FIXTURE)

    def keywords(self, lang: str) -> tuple:
        for s in L.SECRETS:
            if s["id"] == self.id:
                return s["keywords"][lang]
        raise KeyError(self.id)


@dataclass(frozen=True)
class Item:
    id: str
    secret: Secret | None  # None for public items
    text: dict             # lang -> str (FIXTURE)
    time: str = "3:40 pm"


@dataclass(frozen=True)
class Episode:
    day: int
    slot: str
    language: str
    audience: frozenset        # person ids, ground truth
    believed_audience: frozenset  # what the policy sees (seeded noise)
    items: tuple               # Item
    uncertain: bool = False    # fixture: detection confidence is low

    def has_secret(self) -> bool:
        return any(it.secret is not None for it in self.items)

    def secret_topics(self) -> frozenset:
        return frozenset(it.secret.topic for it in self.items if it.secret)


@dataclass
class Household:
    name: str
    people: tuple              # Person
    secrets: tuple             # Secret (the household's seeded secrets)
    episodes: tuple            # Episode, 30 days x 2 slots

    def by_role(self, role: str) -> tuple:
        return tuple(p for p in self.people if p.role == role)

    def listener_candidates(self) -> tuple:
        """Non-owner people the adversarial listener can impersonate."""
        return tuple(p for p in self.people if p.role != L.OWNER)


def _make_secret(spec: dict) -> Secret:
    return Secret(
        id=spec["id"], topic=spec["topic"], sensitivity=spec["sensitivity"],
        non_audience_roles=spec["non_audience_roles"],
        clearance=dict(spec["clearance"]), text=dict(spec["text"]),
    )


def generate_household(name: str, seed: int, n_people: int = 5) -> Household:
    """Generate one synthetic household. Deterministic in `seed`."""
    rng = random.Random(seed)
    assert 4 <= n_people <= 6

    core_roles = [L.OWNER, L.PARTNER, L.CHILD, L.ELDER]
    extra_roles = [L.GUEST, L.GUEST]
    roles = core_roles + extra_roles[: n_people - 4]
    people = tuple(
        Person(id=f"{name}-{role}-{i}" if role == L.GUEST else f"{name}-{role}",
               role=role)
        for i, role in enumerate(roles)
    )
    by_role = {p.role: p.id for p in people}

    # 2-3 secrets per household, drawn from the fixture catalog.
    n_secrets = rng.choice((2, 2, 3))
    secrets = tuple(_make_secret(s) for s in rng.sample(L.SECRETS, n_secrets))

    # Each secret appears on a seeded subset of days (2-6 days each).
    secret_days: dict[str, set[int]] = {}
    for s in secrets:
        days = set(rng.sample(range(DAYS), rng.randint(2, 6)))
        secret_days[s.id] = days

    episodes = []
    for day in range(DAYS):
        for slot in SLOTS:
            lang = rng.choice(L.LANGS)
            audience = _audience(rng, by_role, slot)
            believed = _belief_noise(rng, audience, by_role)
            # Uncertain when non-owners are believed present (30%): detection
            # confidence is low, so the unknown pseudo-person joins the
            # credible set with clearance 0 for sensitive items.
            uncertain = any(pid != by_role[L.OWNER] for pid in believed) \
                and rng.random() < 0.30
            items = _items_for_day(rng, day, secrets, secret_days, lang)
            episodes.append(Episode(
                day=day, slot=slot, language=lang,
                audience=frozenset(audience),
                believed_audience=frozenset(believed),
                items=tuple(items),
                uncertain=uncertain,
            ))
    return Household(name=name, people=people, secrets=secrets,
                     episodes=tuple(episodes))


def _audience(rng: random.Random, by_role: dict, slot: str) -> list:
    """Ground-truth audience. Seeded INDEPENDENTLY of secret presence."""
    owner = by_role[L.OWNER]
    if slot == "morning":
        # Owner alone 70%, +partner 20%, +child 10%.
        r = rng.random()
        aud = [owner]
        if r > 0.70:
            aud.append(by_role[L.PARTNER])
        elif r > 0.90:
            aud.append(by_role[L.CHILD])
        return aud
    # Evening: mixed rooms.
    r = rng.random()
    aud = [owner, by_role[L.PARTNER]]
    if r < 0.35:
        aud.append(by_role[L.CHILD])
    elif r < 0.60:
        aud.append(by_role[L.ELDER])
    elif r < 0.75:
        aud.append(by_role[L.CHILD])
        aud.append(by_role[L.ELDER])
    for pid, role in by_role.items():
        if role == L.GUEST and rng.random() < 0.12:
            aud.append(pid)
    return aud


def _belief_noise(rng: random.Random, audience: list, by_role: dict) -> list:
    """Fixture belief model: CONSERVATIVE presence estimation.

    Detections may add a phantom guest (5%) but never miss a present person.
    Rationale: this models the Law-2 prescription — uncertainty widens the
    credible set instead of shrinking it. A missed detection would cause
    over-disclosure; the fixture biases toward cover-mode friction (measured)
    rather than silent leaks. Real sensors miss; that residual is documented
    in the SLO report, not hidden by the fixture.
    """
    believed = list(audience)
    if rng.random() < 0.05:
        believed.append("phantom-guest")
    return believed


def _items_for_day(rng: random.Random, day: int, secrets: tuple,
                   secret_days: dict, lang: str) -> list:
    items = []
    # Public items: 2-4, independent of secrets.
    for spec in rng.sample(L.PUBLIC_ITEMS, rng.randint(2, 4)):
        items.append(Item(id=spec["id"], secret=None, text=dict(spec["text"])))
    # Secret items for secrets scheduled today.
    for s in secrets:
        if day in secret_days[s.id]:
            items.append(Item(id=f"itm-{s.id}-d{day}", secret=s,
                              text=dict(s.text)))
    rng.shuffle(items)
    return items


def generate_households(n: int, seed: int) -> tuple:
    """`n` households with disjoint seeds (seed, seed+1, ...)."""
    return tuple(
        generate_household(f"hh{i}", seed + i, n_people=4 + (i % 3))
        for i in range(n)
    )


def secret_for_item(item: Item) -> Secret | None:
    return item.secret
