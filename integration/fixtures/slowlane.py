"""FIXTURE — S1 (quarantine + slow lane) stand-in.

Implements the SlowLanePort: ingest() quarantines immediately and
unconditionally; compile() runs a deterministic heuristic pipeline
(classify -> edges -> monotone gate -> render -> verify -> TableRow).

The real S1 seat replaces this with its LLM understand/render stages and its
full deterministic verifier. The seam contract is identical: only versioned
TableRows cross Seam 1.
"""

from __future__ import annotations

from dataclasses import replace

from ..contracts import GeneralizationChain, Item, TableRow
from ..ports import SlowLanePort
from .secrecy import FixtureSecrecy


class FixtureSlowLane(SlowLanePort):
    """Quarantine state machine + heuristic compile pipeline."""

    def __init__(self, pack, secrecy=None):
        self.pack = pack
        self.secrecy = secrecy or FixtureSecrecy()
        self._version = 0

    # -- Seam 1: quarantine ------------------------------------------------
    def ingest(self, item):
        """New items are QUARANTINED immediately. No exceptions, no delay."""
        return replace(item, state="QUARANTINED")

    # -- compile ------------------------------------------------------------
    def compile(self, item):
        """QUARANTINED item -> (COMPILED item, TableRow)."""
        if item.state != "QUARANTINED":
            raise ValueError(f"compile() requires QUARANTINED, got {item.state}")
        topics = self._classify(item)
        item = replace(item, topics=tuple(topics))
        edges = self.secrecy.accept(self.secrecy.infer_edges(item))
        chain = self._render(item)
        self._verify(item, chain)          # deterministic verifier (fixture)
        clearance = self._clearance(item, topics, edges)
        sensitivity = max(self.pack.taxonomy[t]["sensitivity"] for t in topics)
        self._version += 1
        row = TableRow(
            item_id=item.id,
            sensitivity=sensitivity,
            clearance=clearance,
            chain=chain,
            version=self._version,
        )
        return replace(item, state="COMPILED"), row

    # -- heuristic stages (stand-ins for the LLM stages) --------------------
    def _classify(self, item):
        """Keyword scan against the pack lexicon. The real S1 uses an LLM;
        this fixture is deliberately dumber — and still tighten-only.

        Scans SOURCE content fields only (title/location/sender/items), never
        pack-derived labels like category: classifying on our own labels
        would be circular.
        """
        text = " ".join(str(item.fields.get(k, "")) for k in
                        ("title", "location", "sender", "items")).lower()
        hits = []
        for topic, node in self.pack.lexicon.items():
            terms = list(node.get("terms", ()))
            for alias_terms in (node.get("aliases") or {}).values():
                terms.extend(alias_terms)
            if any(term.lower() in text for term in terms):
                hits.append(topic)
        if not hits:
            # Unknown topic: fail closed on sensitivity, open on classification.
            return ("relationship",)
        # Most specific (deepest dotted path) wins ties.
        hits.sort(key=lambda t: (-len(t.split(".")), t))
        return (hits[0],)

    def _render(self, item):
        """Build the generalization chain from pack renditions.

        Fixture for the LLM render stage: the pack's per-language renditions
        ARE the pre-verified chains. The verifier below still checks them —
        trust, but verify, even for data.
        """
        renditions = self.pack.renditions.get(item.kind) or self.pack.templates.get(item.kind)
        depths = tuple(renditions[d].format(**{k: str(item.fields.get(k, "")) for k in
                     ("title", "time", "daypart", "location", "sender", "items", "category")})
                       for d in ("d4", "d3", "d2", "d1"))
        return GeneralizationChain(depths=depths, renditions={self.pack.name: depths})

    def _verify(self, item, chain):
        """Deterministic leak check on the drafted chain (fixture).

        For each topic of the item: no lexicon term/alias for that topic may
        appear in depths BELOW d4's specificity... precisely: d3..d1 must not
        contain any term from the item's own topic lexicon. (d4 is the full
        detail depth — it may name things; the minimax planner decides who
        hears d4.) Violation -> ValueError: the item stays QUARANTINED.
        """
        terms = []
        for topic in item.topics:
            node = self.pack.lexicon.get(topic, {})
            terms.extend(node.get("terms", ()))
            for alias_terms in (node.get("aliases") or {}).values():
                terms.extend(alias_terms)
        lowered_terms = [t.lower() for t in terms]
        for depth, text in zip(("d3", "d2", "d1"), chain.depths[1:]):
            low = text.lower()
            for term in lowered_terms:
                if term and term in low:
                    raise ValueError(
                        f"verifier: term {term!r} leaks at {depth} for item {item.id} "
                        f"— item stays QUARANTINED")
        # NOTE: a strict word-subset monotonicity check is intentionally NOT
        # asserted here — template chains legitimately introduce generic words
        # ("appointment") absent from d4. The term check above is the
        # load-bearing one; S1's real verifier owns the full check.

    def _clearance(self, item, topics, edges):
        """clearance[person_or_role] = min(applicable edges, role defaults).

        Starts from role defaults; every hidden_from edge lowers the target's
        clearance to the edge-implied depth (fixture: hidden_from -> 0 for the
        target person/role on the item's topics).
        """
        clearance = {}
        persons = ("priya", "rahul", "mom", "maya", "unknown")
        person_roles = {"priya": "partner", "rahul": "partner", "mom": "elder",
                        "maya": "child", "unknown": "unknown"}
        for person in persons:
            role = person_roles[person]
            node = self.pack.roles[role]
            # Topic overrides REPLACE the default for that topic (they refine
            # it — an elder may hear more about health, less about nothing).
            # Edges, applied below, only ever lower via min().
            depth = node["default_clearance"]
            for topic in topics:
                override = (node.get("topic_overrides") or {}).get(topic)
                if override is None and "." in topic:
                    override = (node.get("topic_overrides") or {}).get(
                        topic.rsplit(".", 1)[0])
                if override is not None:
                    depth = override
            clearance[person] = depth
        for edge in edges:
            if edge.type == "hidden_from":
                target = edge.target
                if target.startswith("role:"):
                    role = target.split(":", 1)[1]
                    for person, prole in person_roles.items():
                        if prole == role:
                            clearance[person] = 0
                else:
                    clearance[target] = 0
        return clearance
