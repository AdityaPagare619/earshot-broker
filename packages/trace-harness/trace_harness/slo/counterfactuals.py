"""Counterfactual suites: the test grammar of the SLO lab.

Four canonical counterfactuals. Each is a pair of episodes differing ONLY in
the secret dimension under test; the property is public-view invariance
(text, segments, phone_sent, mode). Status/metadata are wire-layer dimensions
(covered by the existing harness's STATUS/STRUCTURED channels); timing-shape
is proxied by (segments, phone_sent) — constant shape implies constant work —
and measured for real at the wire layer.

The policies under test are pure functions of (episode, household): the
audience-transition and temporal narratives are carried by the *construction*
of the pairs (documented per suite). Stateful history across episodes is
S6's integration concern; these suites pin the per-decision invariance that
any stateful history must preserve.

Expected discrimination (asserted in tests/test_slo.py):
  sealed_speech: PASS all four
  v1_lattice:    PASS content_swap (the tell is content-independent);
                 FAIL remove_item / add_guest / replay_alone (existence leak)
  native:        FAIL all four
  keyword:       PASS content_swap (both redact); FAIL the other three
"""
from __future__ import annotations

from dataclasses import dataclass

from . import lexicon as L
from .households import Episode, Household, Item, Person, Secret


@dataclass(frozen=True)
class CounterfactualCase:
    name: str
    description: str
    episode_a: Episode
    episode_b: Episode


@dataclass
class SuiteResult:
    suite: str
    policy: str
    passed: bool
    detail: str


def public_view(spoken) -> dict:
    return {
        "voice_text": spoken.voice_text,
        "segments": spoken.segments,
        "phone_sent": spoken.phone_sent,
        "mode": spoken.mode,
    }


def _secret(spec_id: str) -> Secret:
    for spec in L.SECRETS:
        if spec["id"] == spec_id:
            return Secret(
                id=spec["id"], topic=spec["topic"],
                sensitivity=spec["sensitivity"],
                non_audience_roles=spec["non_audience_roles"],
                clearance=dict(spec["clearance"]), text=dict(spec["text"]),
            )
    raise KeyError(spec_id)


def _household() -> Household:
    # The scope is the FULL catalog: cover mode is computed against what
    # could be secret, so a guest-present clean day is shaped exactly like
    # a guest-present secret day.
    return Household(name="cf", people=(
        Person("cf-owner", L.OWNER),
        Person("cf-partner", L.PARTNER),
        Person("cf-guest", L.GUEST),
    ), secrets=tuple(_secret(s["id"]) for s in L.SECRETS), episodes=())


def _pub_items() -> list:
    return [Item(id=s["id"], secret=None, text=dict(s["text"]))
            for s in L.PUBLIC_ITEMS[:3]]


def _ep(day: int, audience: tuple, items: list, lang: str = "en") -> Episode:
    return Episode(day=day, slot="evening", language=lang,
                   audience=frozenset(audience),
                   believed_audience=frozenset(audience),
                   items=tuple(items))


def _secret_item(secret: Secret, day: int) -> Item:
    return Item(id=f"cf-{secret.id}-d{day}", secret=secret,
                text=dict(secret.text))


# ---------------------------------------------------------------------------
# Suite 1: content_swap — prenatal vs therapy. The secret's CONTENT changes
# with identical shape; a withheld secret must not leak its content.
# Audience includes a guest (clearance 0): both secrets fully withheld.
# ---------------------------------------------------------------------------
def suite_content_swap() -> CounterfactualCase:
    hh_aud = ("cf-owner", "cf-guest")
    ep_a = _ep(0, hh_aud, _pub_items() + [_secret_item(_secret("sec-health"), 0)])
    ep_b = _ep(0, hh_aud, _pub_items() + [_secret_item(_secret("sec-work"), 0)])
    return CounterfactualCase(
        name="content_swap",
        description="Withheld secret content changes (health vs work); "
                    "public view must not distinguish them.",
        episode_a=ep_a, episode_b=ep_b,
    )


# ---------------------------------------------------------------------------
# Suite 2: remove_item — the secret exists vs never existed, fixed audience
# (owner + guest; guest clearance 0 so the secret is fully withheld).
# Withheld items must leave no trace.
# ---------------------------------------------------------------------------
def suite_remove_item() -> CounterfactualCase:
    hh_aud = ("cf-owner", "cf-guest")
    ep_a = _ep(1, hh_aud, _pub_items() + [_secret_item(_secret("sec-health"), 1)])
    ep_b = _ep(1, hh_aud, _pub_items())
    return CounterfactualCase(
        name="remove_item",
        description="Withheld secret present vs absent; public view identical.",
        episode_a=ep_a, episode_b=ep_b,
    )


# ---------------------------------------------------------------------------
# Suite 3: add_guest — the guest arrives mid-day. Morning (owner alone) the
# secret was spoken at d4; evening the guest is present. The guest-present
# voice must be identical whether or not the household ever had the secret.
# (Policies are pure: the "morning" is narrative context for the regression
# story — a stateful host must preserve this per-decision invariance.)
# ---------------------------------------------------------------------------
def suite_add_guest() -> CounterfactualCase:
    guest_aud = ("cf-owner", "cf-guest")
    ep_a = _ep(2, guest_aud,
               _pub_items() + [_secret_item(_secret("sec-gift"), 2)])
    ep_b = _ep(2, guest_aud, _pub_items())
    return CounterfactualCase(
        name="add_guest",
        description="Guest arrives after a secret-carrying morning; the "
                    "guest-present voice must not depend on the secret.",
        episode_a=ep_a, episode_b=ep_b,
    )


# ---------------------------------------------------------------------------
# Suite 4: replay_alone — yesterday the owner was alone and heard the secret
# at d4; today a guest is present and the owner asks about "yesterday's
# appointments". The remembered secret is still withheld from the guest:
# today's voice must equal the no-secret world.
# ---------------------------------------------------------------------------
def suite_replay_alone() -> CounterfactualCase:
    guest_aud = ("cf-owner", "cf-guest")
    remembered = _secret_item(_secret("sec-finance"), 3)
    ep_a = _ep(3, guest_aud, _pub_items() + [remembered])
    ep_b = _ep(3, guest_aud, _pub_items())
    return CounterfactualCase(
        name="replay_alone",
        description="Yesterday's disclosed secret, recalled today with a guest "
                    "present; still withheld, no trace in the public view.",
        episode_a=ep_a, episode_b=ep_b,
    )


SUITES = (suite_content_swap, suite_remove_item, suite_add_guest,
          suite_replay_alone)


def run_all(policies: dict) -> list:
    """Run every suite against every policy. Returns list[SuiteResult]."""
    household = _household()
    results = []
    for build in SUITES:
        case = build()
        for pname, pfn in policies.items():
            sa = pfn(case.episode_a, household)
            sb = pfn(case.episode_b, household)
            va, vb = public_view(sa), public_view(sb)
            passed = va == vb
            detail = "identical public view" if passed else (
                f"A={va!r} B={vb!r}")
            results.append(SuiteResult(case.name, pname, passed, detail))
    return results
