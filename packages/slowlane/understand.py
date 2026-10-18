"""Fixture understander (S1).

Deterministic heuristics that produce UnderstandOutput from an item's
fixture-visible fields. Labeled FIXTURE throughout: confidence is fixed at
0.6 (fixtures don't do confidence), topics come from term matching against
the injected lexicon, entities from a small alias table.

S4-grade inference (deterministic heuristics + LLM-shaped interface) plugs
into the same UnderstandOutput contract later. This module never invents
edges — it only describes what the item appears to contain.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

from .models import Item, UnderstandOutput
from .translit import normalize
from .verifier import TopicLexicon

# ---------------------------------------------------------------------------
# Fixture data (S6's household pack replaces all of this — it is injected,
# never hardcoded, everywhere except this fixture module).
# ---------------------------------------------------------------------------

# topic -> {lang: terms}. Sensitivity per topic lives alongside.
FIXTURE_TOPICS: Dict[str, Dict[str, frozenset]] = {
    "health": {
        "en": frozenset({"clinic", "doctor", "hospital", "checkup",
                         "therapy", "prescription", "medical"}),
        "hi": frozenset({"डॉक्टर", "अस्पताल", "क्लिनिक", "इलाज", "दवा"}),
        "hi-Latn": frozenset({"doctor", "daktar", "aspatal", "clinic",
                              "ilaaj", "dava"}),
    },
    # The truly sensitive reproductive terms live in their own topic with a
    # stricter depth: generic "appointment"/"doctor" may generalize to d3,
    # "pregnancy" may not.
    "health.reproductive": {
        "en": frozenset({"pregnancy", "prenatal"}),
        "hi": frozenset({"गर्भ", "प्रेगनेंसी"}),
        "hi-Latn": frozenset({"garbh"}),
    },
    "gift": {
        # NOTE: "package"/"delivery" stay out (logistics, used by templates
        # at d2), but "order"/"shipped" mark gift-ness: a shipment email is
        # how the "data understood itself" demo beat fires.
        "en": frozenset({"gift", "surprise", "birthday", "present",
                         "order", "shipped"}),
        "hi": frozenset({"तोहफा", "उपहार", "सरप्राइज", "जन्मदिन"}),
        "hi-Latn": frozenset({"tohfa", "uphaar", "surprise", "janmdin"}),
    },
    "finance": {
        "en": frozenset({"bank", "payment", "invoice", "salary", "loan",
                         "debt", "account", "balance"}),
        "hi": frozenset({"बैंक", "पैसा", "भुगतान", "कर्ज", "खाता"}),
        "hi-Latn": frozenset({"bank", "paisa", "bhugtan", "karz", "khata"}),
    },
    "work": {
        "en": frozenset({"meeting", "standup", "interview", "office",
                         "deadline", "review", "client"}),
        "hi": frozenset({"मीटिंग", "इंटरव्यू", "ऑफिस", "डेडलाइन"}),
        "hi-Latn": frozenset({"meeting", "interview", "office", "deadline"}),
    },
}

FIXTURE_TOPIC_SENSITIVITY: Dict[str, float] = {
    "health": 0.8, "health.reproductive": 0.95,
    "gift": 0.7, "finance": 0.85, "work": 0.5,
}

# Canonical entity -> aliases (multilingual by construction: the verifier
# normalizes both sides identically, so Hindi-script aliases catch
# Hindi-script leaks).
FIXTURE_ENTITIES: Dict[str, FrozenSet[str]] = {
    "Cloudnine": frozenset({"cloudnine", "क्लाउडनाइन", "cloud nine"}),
    "Dr. Mehta": frozenset({"dr mehta", "dr. mehta", "mehta", "डॉ. मेहता",
                             "डॉक्टर मेहता", "daktar mehta"}),
    "OB-GYN": frozenset({"ob-gyn", "obgyn", "ob gyn"}),
    "Maya": frozenset({"maya", "माया"}),
    "Instax": frozenset({"instax", "इंस्टैक्स"}),
}

# Entity -> max depth it may appear at (fixture policy: names of clinics and
# doctors are d4-only; gift recipients d3 — the gift *exists* at d3 but the
# recipient edge hides it from the target).
FIXTURE_ENTITY_MAX_DEPTH: Dict[str, int] = {
    "Cloudnine": 4, "Dr. Mehta": 4, "OB-GYN": 4,
    "Maya": 3, "Instax": 3,
}

FIXTURE_TOPIC_MAX_DEPTH: Dict[str, int] = {
    "health": 3, "health.reproductive": 4,
    "gift": 3, "finance": 4, "work": 2,
}


def fixture_lexicon() -> TopicLexicon:
    """The lexicon the fixture verifier checks against. S6's pack replaces it."""
    return TopicLexicon(
        terms={t: {lang: terms for lang, terms in langs.items()}
               for t, langs in FIXTURE_TOPICS.items()}
    )


class FixtureUnderstander:
    """FIXTURE: keyword heuristics over normalized text. Honest about what it
    is — a stand-in with the right output shape, not a model."""

    def __init__(self, lexicon: TopicLexicon | None = None):
        self.lexicon = lexicon or fixture_lexicon()

    def understand(self, item: Item, text_hint: str = "") -> UnderstandOutput:
        """Produce UnderstandOutput for an item.

        text_hint: fixture-visible text describing the item (in production this
        is resolved from the vault inside the slow lane; the fixture takes it
        as an explicit, labeled parameter).
        """
        hay = f" {normalize(text_hint)} "
        topics = []
        for topic, langs in self.lexicon.terms.items():
            terms = set()
            for lang_terms in langs.values():
                terms |= set(lang_terms)
            if any(f" {normalize(t).strip()} " in hay for t in terms):
                topics.append(topic)

        entities: Dict[str, FrozenSet[str]] = {}
        sensitive: Dict[str, int] = {}
        for canonical, aliases in FIXTURE_ENTITIES.items():
            if any(f" {normalize(a).strip()} " in hay for a in aliases):
                entities[canonical] = aliases
                sensitive[canonical] = FIXTURE_ENTITY_MAX_DEPTH.get(canonical, 4)

        sensitive_topics = {t: FIXTURE_TOPIC_MAX_DEPTH.get(t, 4) for t in topics}
        sensitivity = max(
            [FIXTURE_TOPIC_SENSITIVITY.get(t, 0.5) for t in topics] or [0.5]
        )
        # Unknown content fails private: no topics matched -> sensitivity 1.0.
        if not topics:
            sensitivity = 1.0

        return UnderstandOutput(
            item_id=item.id,
            topics=tuple(topics),
            entities=entities,
            sensitive=sensitive,
            sensitive_topics=sensitive_topics,
            sensitivity=sensitivity,
            confidence=0.6,  # FIXTURE: fixtures don't do confidence
            lang_detected=item.lang_detected,
        )
