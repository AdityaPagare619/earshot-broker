"""Baseline speaker policies for the SLO lab.

Four pure functions with an identical input shape (Episode + Household) and
output shape (Spoken). Any behavioral difference between them is policy, not
data. All four receive the policy's *believed* audience; native/keyword ignore
it (they are dumb baselines — that is the point).

The sealed_speech policy mirrors kernel.public_projection semantics: it speaks
only what the audience is cleared for, in constant shape. It is a policy-layer
model of the sealed-speech design, NOT the server (that is S6's integration).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import lexicon as L
from .households import Episode, Household, Item


@dataclass(frozen=True)
class Spoken:
    voice_text: str
    phone_text: str
    phone_sent: bool
    mode: str                    # "full" | "cover"
    depths: dict                 # {item_id: depth_int} — the decision record
    segments: int                # voice segments (timing-shape proxy)


def _role_of(household: Household, person_id: str) -> str:
    for p in household.people:
        if p.id == person_id:
            return p.role
    return L.GUEST  # phantom-guest and unknowns: least privilege


# The unknown pseudo-person: clearance 0 for anything sensitive.
_UNKNOWN = "unknown"


def _clearance_with_unknown(item: Item, role: str) -> int:
    if role == _UNKNOWN:
        return 0
    return _clearance(item, role)


def _scope_cover(episode: Episode, household: Household) -> bool:
    """Cover mode from the SCOPE's possible secrets, not the actual items.

    Per Law 4: cover is computed against what *could* be secret (the
    household's secret catalog), never against whether a secret happens to
    be present today. A guest-present clean day looks exactly like a
    guest-present secret day — that constancy is the mechanism.
    """
    roles = [_role_of(household, pid) for pid in episode.believed_audience]
    non_owners = [r for r in roles if r != L.OWNER]
    if not non_owners or not household.secrets:
        return False
    uncertain = episode.uncertain or "phantom-guest" in episode.believed_audience
    for s in household.secrets:
        for r in non_owners:
            c = s.clearance.get(r, 0)
            if uncertain and s.sensitivity > 0.3:
                c = 0  # the unknown pseudo-person joins: clearance 0
            if c < 4:
                return True
    return False


def _clearance(item: Item, role: str) -> int:
    if item.secret is None:
        return 4
    return item.secret.clearance.get(role, 0)


def _text(item: Item, lang: str) -> str:
    return item.text[lang]


def _generalize(item: Item, depth: int, lang: str) -> str | None:
    """Generalized rendition at depth, or None if absorbed (d0)."""
    if depth >= 4:
        return _text(item, lang)
    if depth <= 0:
        return None
    return L.GENERALIZE[lang][depth].format(time=item.time)


# ---------------------------------------------------------------------------
# Baseline 1: native — says everything. The "no protection" control.
# ---------------------------------------------------------------------------
def native(episode: Episode, household: Household) -> Spoken:
    lang = episode.language
    texts = [_text(it, lang) for it in episode.items]
    return Spoken(
        voice_text=" ".join(texts),
        phone_text="",
        phone_sent=False,
        mode="full",
        depths={it.id: 4 for it in episode.items},
        segments=len(texts),
    )


# ---------------------------------------------------------------------------
# Baseline 2: keyword filter — deny-list redaction. Deliberately leaky:
# partial coverage, per-item tells, count oracle. The "naive fix" control.
# ---------------------------------------------------------------------------
def keyword(episode: Episode, household: Household) -> Spoken:
    lang = episode.language
    deny = L.DENY_LISTS[lang]
    redact = L.KEYWORD_REDACT[lang]
    texts, depths = [], {}
    for it in episode.items:
        low = _text(it, lang).lower()
        if any(w in low for w in deny):
            texts.append(redact)
            depths[it.id] = 0
        else:
            texts.append(_text(it, lang))
            depths[it.id] = 4
    return Spoken(
        voice_text=" ".join(texts),
        phone_text="",
        phone_sent=False,
        mode="cover" if any(d == 0 for d in depths.values()) else "full",
        depths=depths,
        segments=len(texts),
    )


# ---------------------------------------------------------------------------
# Baseline 3: v1 4-level lattice — FULL / ABSTRACT / EXISTENCE / SILENT.
# The EXISTENCE tell ("One private item...") is the leak under test.
# ---------------------------------------------------------------------------
def v1_lattice(episode: Episode, household: Household) -> Spoken:
    lang = episode.language
    roles = [_role_of(household, pid) for pid in episode.believed_audience]
    owner_present = L.OWNER in roles
    texts, depths, phone_items = [], {}, []
    tell = L.V1_EXISTENCE_TELL[lang]
    for it in episode.items:
        dstar = min(_clearance(it, r) for r in roles) if roles else 0
        depths[it.id] = dstar
        if dstar >= 4:
            texts.append(_text(it, lang))
        elif dstar >= 2:
            texts.append(_generalize(it, 2, lang))
        elif owner_present:
            texts.append(tell)  # <-- the existence leak
            phone_items.append(_text(it, lang))
        # else SILENT: omitted entirely
    return Spoken(
        voice_text=" ".join(texts),
        phone_text=" ".join(phone_items),
        phone_sent=bool(phone_items),
        mode="cover" if any(d < 4 for d in depths.values()) else "full",
        depths=depths,
        segments=len(texts),
    )


# ---------------------------------------------------------------------------
# Baseline 4: sealed speech — constant shape.
# Cover mode iff some believed non-owner is not fully cleared for the scope.
# In cover: cleared depths spoken via verified templates, fixed suffix ALWAYS
# appended (even when nothing was withheld), phone digest ALWAYS sent silently.
# No counts, no ordinals. d0 items are absorbed — they leave no trace.
# ---------------------------------------------------------------------------
def sealed_speech(episode: Episode, household: Household) -> Spoken:
    lang = episode.language
    roles = [_role_of(household, pid) for pid in episode.believed_audience]
    cover = _scope_cover(episode, household)
    texts, depths = [], {}
    for it in episode.items:
        eff_roles = list(roles)
        if it.secret is not None and it.secret.sensitivity > 0.3 and (
                episode.uncertain or "phantom-guest" in episode.believed_audience):
            eff_roles = eff_roles + [_UNKNOWN]
        dstar = min((_clearance_with_unknown(it, r) for r in eff_roles), default=4)
        if not cover:
            dstar = 4
        depths[it.id] = dstar
        rendered = _generalize(it, dstar, lang)
        if rendered is not None:
            texts.append(rendered)
    if cover:
        texts.append(L.FIXED_SUFFIX[lang])
        phone_text = " ".join(_text(it, lang) for it in episode.items)
        phone_sent = True
    else:
        phone_text = ""
        phone_sent = False
    return Spoken(
        voice_text=" ".join(texts),
        phone_text=phone_text,
        phone_sent=phone_sent,
        mode="cover" if cover else "full",
        depths=depths,
        segments=len(texts),
    )


POLICIES = {
    "native": native,
    "keyword": keyword,
    "v1_lattice": v1_lattice,
    "sealed_speech": sealed_speech,
}
