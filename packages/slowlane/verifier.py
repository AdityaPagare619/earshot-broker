"""Deterministic leak verifier (S1).

The verifier is the thing that bounds the model: every draft chain — fixture
or LLM — crosses these four checks before it can become speakable. The
verifier is never the model.

Checks (per DATAFLOW-PIPELINE.md 1.7):
1. entity leak: a sensitive entity must not appear below its allowed depth,
   in ANY rendition language (NFKC + casefold + transliteration, both sides).
2. topic lexicon: same, against the injected multilingual topic lexicon.
3. quasi-identifier: (time-bucket, weekday, location-type) repetition against a
   bounded exposure history — the "ninth Tuesday" check, v1.
4. monotonicity: a generalization must not ADD information going down.

Verdicts are values, not exceptions: the pipeline decides retry vs fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .models import DraftChain, UnderstandOutput
from .translit import normalize

# Depth indices used everywhere: d1..d4 (d0 is absorbed into constant shape).
_DEPTHS = (1, 2, 3, 4)


@dataclass(frozen=True)
class TopicLexicon:
    """Multilingual topic terms. Injected as data (S6's pack replaces the
    fixture). The verifier is language-blind; the lexicon is not."""
    terms: Dict[str, Dict[str, frozenset]]  # topic -> {lang: terms}


@dataclass(frozen=True)
class Verdict:
    passed: bool
    failures: Tuple[str, ...]
    checks_run: int


def _padded(text: str) -> str:
    return f" {normalize(text)} "


def _at(depths, d: int) -> str:
    """depths follows the frozen contract order (d4, d3, d2, d1)."""
    return depths[4 - d]


def _contains(haystack_norm_padded: str, needle: str) -> bool:
    """Token-boundary substring: 'ai' does not match 'said'."""
    return f" {normalize(needle).strip()} " in haystack_norm_padded


def _check_entities(chain: DraftChain, understand: UnderstandOutput) -> List[str]:
    failures = []
    for entity, max_depth in understand.sensitive.items():
        aliases = understand.entities.get(entity, frozenset({entity}))
        for lang, depths in chain.renditions.items():
            for d in _DEPTHS:
                if max_depth > d:  # entity may appear only at depths >= max_depth
                    text = _padded(_at(depths, d))
                    for alias in aliases:
                        if _contains(text, alias):
                            failures.append(
                                f"entity-leak: {entity!r} (alias {alias!r}) "
                                f"appears at d{d} [{lang}] but max_depth={max_depth}"
                            )
    return failures


def _check_topics(chain: DraftChain, understand: UnderstandOutput,
                  lexicon: TopicLexicon) -> List[str]:
    failures = []
    for topic, max_depth in understand.sensitive_topics.items():
        # Union of terms across ALL languages: a Hindi term hiding in an
        # "en"-labeled rendition is still a leak. Over-matching fails closed.
        terms = set()
        for lang_terms in lexicon.terms.get(topic, {}).values():
            terms |= set(lang_terms)
        for lang, depths in chain.renditions.items():
            for d in _DEPTHS:
                if max_depth > d:
                    text = _padded(_at(depths, d))
                    for term in terms:
                        if _contains(text, term):
                            failures.append(
                                f"topic-leak: topic {topic!r} term {term!r} "
                                f"appears at d{d} [{lang}] but max_depth={max_depth}"
                            )
    return failures


def _check_quasi(chain: DraftChain, quasi: Tuple[str, str, str],
                 history: List[Tuple[str, str, str, int]],
                 threshold: int = 3) -> List[str]:
    """v1 quasi-identifier check: if (time_bucket, weekday, location_type) has
    already been spoken at a revealing depth (d>=2) `threshold` times, speaking
    it again is a pattern leak. Threshold and window are explicit data.

    This is the weakest of the four checks (see SEAT_VERDICT.md) — shipped
    simply, labeled honestly.
    """
    revealing = [h for h in history
                 if h[0] == quasi[0] and h[1] == quasi[1] and h[2] == quasi[2]
                 and h[3] >= 2]
    if len(revealing) >= threshold:
        return [f"quasi-identifier: {quasi} already revealed "
                f"{len(revealing)}x at d>=2 (threshold {threshold})"]
    return []


def _entities_at(text_padded: str, understand: UnderstandOutput) -> frozenset:
    found = set()
    for entity, aliases in understand.entities.items():
        if any(_contains(text_padded, a) for a in aliases):
            found.add(entity)
    return frozenset(found)


def _topics_at(text_padded: str, understand: UnderstandOutput,
               lexicon: TopicLexicon) -> frozenset:
    found = set()
    for topic in understand.topics:
        # Union across languages, same as the leak check: a Hindi term in an
        # "en"-labeled rendition is still a topic occurrence.
        terms = set()
        for lang_terms in lexicon.terms.get(topic, {}).values():
            terms |= set(lang_terms)
        if any(_contains(text_padded, t) for t in terms):
            found.add(topic)
    return frozenset(found)


def _check_monotonicity(chain: DraftChain, understand: UnderstandOutput,
                        lexicon: TopicLexicon) -> List[str]:
    """A generalization must not ADD sensitive information going down.

    Approximated (per DATAFLOW-PIPELINE.md) by nesting entity/topic sets:
    entities(d) ⊆ entities(d+1), topics(d) ⊆ topics(d+1). Raw-token subset
    would reject legitimate hypernyms ("appointment" for "checkup").
    """
    failures = []
    for lang, depths in chain.renditions.items():
        ent_sets, top_sets = [], []
        for d in _DEPTHS:
            text = _padded(_at(depths, d))
            ent_sets.append(_entities_at(text, understand))
            top_sets.append(_topics_at(text, understand, lexicon))
        for i in range(3):  # d1<=d2, d2<=d3, d3<=d4
            added_e = ent_sets[i] - ent_sets[i + 1]
            added_t = top_sets[i] - top_sets[i + 1]
            if added_e or added_t:
                failures.append(
                    f"monotonicity: d{i+1} adds entities={sorted(added_e)} "
                    f"topics={sorted(added_t)} not in d{i+2} [{lang}]"
                )
    return failures


def verify(chain: DraftChain, understand: UnderstandOutput,
           lexicon: TopicLexicon,
           quasi: Tuple[str, str, str] = ("", "", ""),
           history: List[Tuple[str, str, str, int]] | None = None,
           quasi_threshold: int = 3) -> Verdict:
    """Run all four checks. Pure function. Never raises on content."""
    failures: List[str] = []
    checks = 0

    failures.extend(_check_entities(chain, understand)); checks += 1
    failures.extend(_check_topics(chain, understand, lexicon)); checks += 1
    failures.extend(_check_quasi(chain, quasi, history or [], quasi_threshold))
    checks += 1
    failures.extend(_check_monotonicity(chain, understand, lexicon)); checks += 1

    return Verdict(passed=not failures, failures=tuple(failures), checks_run=checks)
