"""FIXTURE — S4 (secrecy graph + monotone gate) stand-in.

Deterministic heuristics behind the SecrecyPort interface. The real S4 seat
replaces this module with its inference engine; callers see no difference.
Every edge this fixture proposes is TIGHTEN-only, so the monotone gate is the
only thing standing between a heuristic and the Disclosure Table — exactly as
in the real design.

Honest label: heuristic inference, not an LLM. The monotone gate is real.
"""

from __future__ import annotations

import re  # noqa: F401  (kept for handle_keep_secret patterns)

from ..contracts import SecrecyEdge
from ..ports import SecrecyPort

# Deterministic heuristic rules: (topic_pattern, edge_type, target, until, confidence)
# These stand in for the slow lane's LLM "understand" step. They only ever
# TIGHTEN — a heuristic is never allowed to loosen.
_HEURISTICS = (
    # A gift delivery is kept from the person it is for.
    ("gift", "for", None, None, 0.91),          # target filled from fields
    ("gift", "hidden_from", None, None, 0.91),
    # Reproductive health is kept from guests and children by default.
    ("health.reproductive", "hidden_from", "role:guest", None, 0.88),
    ("health.reproductive", "hidden_from", "role:child", None, 0.88),
    # Finance is kept from children and unknown visitors.
    ("finance", "hidden_from", "role:child", None, 0.82),
    ("finance", "hidden_from", "role:unknown", None, 0.8),
    # Legal is kept from everyone but the owner and partner by default.
    ("legal", "hidden_from", "role:guest", None, 0.85),
    ("legal", "hidden_from", "role:child", None, 0.85),
)

class FixtureSecrecy(SecrecyPort):
    """Heuristic edge inference + the real monotone acceptance gate."""

    def __init__(self, pack=None):
        # The pack supplies language-specific gift words. Hardcoding them
        # would be a language conditional in disguise — the exact thing the
        # Household Pack exists to prevent.
        self.pack = pack

    def _gift_words(self):
        if self.pack is not None:
            node = self.pack.lexicon.get("gift", {})
            words = list(node.get("terms", ()))
            for alias_terms in (node.get("aliases") or {}).values():
                words.extend(alias_terms)
            return words
        # Port-compatibility fallback (no pack): Latin list, documented.
        return ["instax", "gift", "present", "surprise", "toy", "lego"]

    def infer_edges(self, item):
        edges = []
        topics = set(item.topics)
        gift_words = [w.lower() for w in self._gift_words()]
        for pattern, etype, target, until, conf in _HEURISTICS:
            if not any(t == pattern or t.startswith(pattern + ".") for t in topics):
                continue
            resolved = target
            if etype == "for":
                title = item.fields.get("title", "").lower()
                if any(w and w in title for w in gift_words):
                    giftee = item.fields.get("for_person")
                    if giftee:
                        edges.append(SecrecyEdge("for", giftee, until, "inferred", conf, "TIGHTEN"))
                        edges.append(SecrecyEdge("hidden_from", giftee, until, "inferred", conf, "TIGHTEN"))
                        continue
            if resolved is None:
                continue
            edges.append(SecrecyEdge(etype, resolved, until, "inferred", conf, "TIGHTEN"))
        return edges

    def accept(self, edges):
        """The monotone acceptance rule — this is the real gate, not a fixture.

        accept(edge) = (direction == TIGHTEN and confidence >= 0.6)
                       or provenance == "confirmed"
        Nothing unconfirmed ever loosens. Nothing low-confidence applies.
        """
        accepted = []
        for edge in edges:
            if edge.provenance == "confirmed":
                accepted.append(edge)
            elif edge.direction == "TIGHTEN" and edge.confidence >= 0.6:
                accepted.append(edge)
            # Everything else is dropped SILENTLY from the table's perspective —
            # but loudly in the confirm queue (the pipeline surfaces it).
        return accepted

    # -- the two user-control verbs (S4 also owns these) ---------------------

    def handle_keep_secret(self, instruction, pack):
        """One spoken sentence -> instant TIGHTEN edge. Fixture parser.

        Real S4 uses an LLM; this fixture matches a small set of shapes:
        "never mention <topic words> in front of <person>" /
        "keep <thing> from <person> [until <date>]".
        Unparseable -> returns None (the pipeline then asks for clarification
        on the phone — never guesses).
        """
        text = instruction.lower()
        m = re.search(r"never mention (.+?) in front of (\w+)", text)
        if not m:
            m = re.search(r"keep (.+?) from (\w+)(?: until ([\w ]+))?", text)
            if not m:
                return None
            topic_words, person = m.group(1), m.group(2)
            until = m.group(3)
        else:
            topic_words, person = m.group(1), m.group(2)
            until = None
        topic = self._match_topic(topic_words, pack)
        return SecrecyEdge("hidden_from", person, until, "declared", 1.0, "TIGHTEN")

    def _match_topic(self, words, pack):
        """Match instruction words to a topic via lexicon terms first, then
        topic-name leaves. Conservative fallback: a broad topic."""
        for dotted, node in pack.lexicon.items():
            terms = list(node.get("terms", ()))
            for alias_terms in (node.get("aliases") or {}).values():
                terms.extend(alias_terms)
            if any(t.lower() in words for t in terms):
                return dotted
        for dotted in pack.taxonomy:
            leaf = dotted.split(".")[-1]
            if leaf in words or words in leaf:
                return dotted
        return "relationship"
