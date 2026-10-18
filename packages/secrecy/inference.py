"""Edge inference — Law 1, executable (S4).

Two proposers behind one interface:

- ``HeuristicProposer`` — deterministic, stdlib, no model. The production-safe
  default: gift/order patterns, clinic keywords, financial/legal keywords.
- ``FixtureLLMProposer`` — implements the SAME interface with canned,
  pessimistic outputs. It exists to prove the *gate* holds against an LLM-shaped
  backend, not to be smart. A real model plugs in later by implementing
  ``Proposer.propose()`` — without touching the gate.

SEAM DISCIPLINE: proposers never see raw item content. They receive
``InferenceInput`` — the normalized, non-raw fields Stage 1.2 extracts
(title words, kind, participants, structured metadata). The vault stays shut.

All heuristics are TIGHTEN-only with fixed, documented confidences. A heuristic
that cannot name its confidence does not ship.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from edges import EdgeProposal


@dataclass(frozen=True)
class InferenceInput:
    """Normalized, non-raw view of an item for inference.

    ``title``/``notes`` are the Stage-1.2-extracted short strings (already
    separated from raw content); ``participants`` are structured fields
    (e.g. calendar attendees, order recipient); ``meta`` carries kind-specific
    structured facts (e.g. {"is_gift_wrap": True}).
    """
    item_id: str
    kind: str  # event|reminder|delivery|note|message_summary
    title: str = ""
    notes: str = ""
    participants: tuple = ()
    meta: dict = field(default_factory=dict)


class Proposer(ABC):
    """LLM-shaped interface. A future real model implements exactly this."""

    @abstractmethod
    def propose(self, item: InferenceInput) -> list[EdgeProposal]:
        """Return UNTRUSTED proposals. The gate decides what becomes an edge."""


# --- deterministic heuristics ------------------------------------------------

def _words(text: str) -> set[str]:
    # Keep hyphenated compounds ("ob-gyn") intact; the bare hyphen split
    # would turn them into fragments no lexicon contains.
    return set(re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower()))


CLINIC_WORDS = frozenset({
    "clinic", "hospital", "doctor", "doctors", "appointment", "ob-gyn", "obgyn",
    "gynae", "therapy", "therapist", "dental", "dentist", "pharmacy", "diagnostic",
    "lab", "test", "pregnancy", "pregnant", "prenatal", "pediatric", "physio",
    "dermatologist", "cardiologist",
})
GIFT_WORDS = frozenset({
    "gift", "present", "surprise", "birthday", "anniversary", "secret santa",
})
MONEY_WORDS = frozenset({
    "bank", "loan", "salary", "credit", "debit", "debt", "investment", "emi",
    "tax", "insurance", "premium",
})
ROLE_CHILD = "role:child"
ROLE_GUEST = "role:guest"

# Fixed confidences — documented, never tuned silently.
CONF_CLINIC = 0.75
CONF_GIFT = 0.80
CONF_MONEY = 0.70
CONF_SURPRISE = 0.65

_GIFT_FOR_RE = re.compile(
    r"\bgift\b.*?\bfor\b\s+([a-z]+)|\bfor\b\s+(?:my\s+)?"
    r"(son|daughter|kid|kids|child|children|wife|husband|partner|mom|mother|dad|father)\b"
)


class HeuristicProposer(Proposer):
    """Deterministic TIGHTEN-only proposer. No model, no network, no surprises."""

    def propose(self, item: InferenceInput) -> list[EdgeProposal]:
        out: list[EdgeProposal] = []
        text = f"{item.title} {item.notes}"
        words = _words(text)

        # Gift / surprise: the non-audience is often named in the data itself.
        m = _GIFT_FOR_RE.search(text.lower())
        gift_hit = bool(words & GIFT_WORDS) or "gift" in item.meta.get("tags", ())
        if m:
            who = next((g for g in m.groups() if g), "child")
            target = who if who not in ("kid", "kids", "child", "children",
                                        "son", "daughter") else ROLE_CHILD
            out.append(EdgeProposal(
                type="for", target=target, until=None,
                confidence=CONF_GIFT, direction="TIGHTEN",
                reason="heuristic: gift-for pattern names the recipient"))
            out.append(EdgeProposal(
                type="hidden_from", target=target,
                until=item.meta.get("until"),
                confidence=CONF_GIFT, direction="TIGHTEN",
                reason="heuristic: gift kept from its recipient until given"))
        elif gift_hit or "surprise" in words:
            out.append(EdgeProposal(
                type="hidden_from", target=ROLE_CHILD, until=item.meta.get("until"),
                confidence=CONF_SURPRISE, direction="TIGHTEN",
                reason="heuristic: surprise/gift wording, recipient unnamed"))

        # Clinic / health: guests and children are not the audience.
        if words & CLINIC_WORDS:
            for target in (ROLE_GUEST, ROLE_CHILD):
                out.append(EdgeProposal(
                    type="hidden_from", target=target, until=None,
                    confidence=CONF_CLINIC, direction="TIGHTEN",
                    reason="heuristic: health-related wording"))

        # Money / legal: not for guests.
        if words & MONEY_WORDS:
            out.append(EdgeProposal(
                type="hidden_from", target=ROLE_GUEST, until=None,
                confidence=CONF_MONEY, direction="TIGHTEN",
                reason="heuristic: financial wording"))

        return out


class FixtureLLMProposer(Proposer):
    """LLM-shaped, pessimistic, fully deterministic.

    Simulates what a careful model backend *should* emit: TIGHTEN-only
    proposals with explicit confidences. Used to prove the gate — and the
    choke-point store — hold against an LLM-shaped backend. Fixture: labeled.
    """

    def propose(self, item: InferenceInput) -> list[EdgeProposal]:
        # A "model-like" response: structured, slightly richer than heuristics,
        # but obeying the same contract — TIGHTEN only, confidences stated.
        base = HeuristicProposer().propose(item)
        if item.kind == "delivery" and "instax" in item.title.lower():
            base = [p for p in base] + [EdgeProposal(
                type="hidden_from", target="maya",
                until=item.meta.get("until"),
                confidence=0.91, direction="TIGHTEN",
                reason="fixture-llm: order looks like a gift; recipient 'maya' "
                       "from order metadata")]
        # The fixture never emits LOOSEN. That is the point.
        return [p for p in base if p.direction == "TIGHTEN"]
