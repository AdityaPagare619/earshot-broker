"""Adversarial listener for the SLO lab.

A keyword-based, fixture-vocabulary listener that hears ONLY what was spoken
in each listener's presence and tries to (a) classify days as secret-carrying
vs clean, and (b) infer secret topics. It is EXPLICITLY a lower bound on
adversary strength: anything this listener catches, a stronger adversary
catches too. The reverse is NOT claimed — a 0.5 AUC here does not prove no
adversary could do better. That honesty is load-bearing.

Two tasks:
- existence: score(day's heard voice texts) -> float. Higher = more secret-like.
- inference: guess_topic(all heard voice texts) -> topic. Compared vs base rate.
"""
from __future__ import annotations

from . import lexicon as L

TELL_WEIGHT = 3.0  # tell phrases ("private item") are stronger than keywords


def heard_texts(pairs, person_id: str) -> list:
    """Voice texts (lang, text) from (episode, spoken) pairs where person_id
    was in the ground-truth audience."""
    return [(ep.language, sp.voice_text) for ep, sp in pairs
            if person_id in ep.audience]


class AdversarialListener:
    """Fixture-vocabulary listener. Deterministic. Labeled lower bound."""

    def __init__(self, person_id: str, role: str):
        self.person_id = person_id
        self.role = role

    def existence_score(self, heard: list) -> float:
        """Secret-likeness score for a batch of (lang, text) heard texts."""
        score = 0.0
        for lang, text in heard:
            low = text.lower()
            for kw in L.secret_keywords(lang):
                if kw.lower() in low:
                    score += 1.0
            for tell in L.TELL_PHRASES[lang]:
                if tell.lower() in low:
                    score += TELL_WEIGHT
        return score

    def guess_topic(self, heard: list) -> str:
        """Argmax topic by keyword hits; ties break alphabetically (deterministic,
        so a signal-free listener guesses at exactly the base rate)."""
        langs = {lang for lang, _ in heard}
        best, best_score = None, -1.0
        for topic in sorted(L.TOPICS):
            s = 0.0
            for lang in langs:
                for kw in L.topic_keywords(topic, lang):
                    for _, text in heard:
                        if kw.lower() in text.lower():
                            s += 1.0
            if s > best_score:
                best, best_score = topic, s
        return best
