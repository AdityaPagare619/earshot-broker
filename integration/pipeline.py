"""The integration pipeline: S1 -> S2 -> S3 -> S4 as one runnable path.

SealedSpeechPipeline wires the four fixture stages behind their ports:

    ingest (S1 quarantine) -> compile (S1) -> belief (S2) -> plan (S2)
        -> assemble (S3) -> respond

plus the S4 user-control verbs (room, keep_secret) and the personal-channel
outbox (digest, confirm cards, defer queue).

Every public method is labeled with the seam it exercises. The demo runner
(demo/five_beats.py) drives this pipeline; the tests assert its properties.
"""

from __future__ import annotations

import time
import uuid

from .contracts import Item
from .fixtures import (ExposureLedger, FixtureHotLane, FixtureSecrecy,
                       FixtureShape, FixtureSlowLane)

# The demo household. Persons map to pack roles in FixtureSlowLane._clearance.
HOUSEHOLD = ("priya", "rahul", "mom", "maya")


class SealedSpeechPipeline:
    """One runnable path through the sealed-speech architecture."""

    def __init__(self, pack, slowlane=None, hotlane=None, shape=None, secrecy=None):
        self.pack = pack
        self.secrecy = secrecy or FixtureSecrecy(pack)
        self.slowlane = slowlane or FixtureSlowLane(pack, self.secrecy)
        self.hotlane = hotlane or FixtureHotLane()
        self.shape = shape or FixtureShape(pack)
        self.ledger = ExposureLedger()
        self.items = {}          # item_id -> Item
        self.rows = {}           # item_id -> TableRow
        self.fields = {}         # item_id -> fields dict (rendition inputs)
        self.outbox = []         # personal-channel entries
        self.confirm_queue = []  # phone confirm cards
        self.belief = None
        self._pending_edges = []  # declared edges awaiting table application
        self._priors = {p: -4.0 for p in HOUSEHOLD}  # P≈0.018: firmly away
        self._priors["priya"] = 2.0                   # P≈0.88: owner home
        # Note the design working as intended: for a 0.95-sensitivity item,
        # eps = 0.0725, so even a 12% presence guess would make someone
        # credible. The away prior must be firm (-4.0), not casual.
        self._now = time.time()

    # -- S1: ingest + compile (Seam 1) --------------------------------------
    def ingest(self, kind, fields, source="fixture", owner="priya"):
        """New source data -> QUARANTINED immediately. Returns item_id."""
        item = Item(
            id=f"itm_{uuid.uuid4().hex[:8]}",
            owner=owner, kind=kind, source=source,
            start=fields.get("start", ""), end=fields.get("end", ""),
            raw_ref=f"vault://enc/{uuid.uuid4().hex[:8]}",
            state="NEW", lang_detected=(self.pack.name,),
            fields=dict(fields),
        )
        item = self.slowlane.ingest(item)
        assert item.state == "QUARANTINED"
        self.items[item.id] = item
        self.fields[item.id] = dict(fields, kind=kind)
        return item.id

    def compile_all(self):
        """QUARANTINED -> COMPILED. Returns (compiled_ids, confirm_cards)."""
        compiled = []
        for item_id, item in list(self.items.items()):
            if item.state != "QUARANTINED":
                continue
            new_item, row = self.slowlane.compile(item)
            self.items[item_id] = new_item
            self.rows[item_id] = row
            self.fields[item_id]["kind"] = item.kind
            compiled.append(item_id)
        # S4's inferred edges belong in the Disclosure Table, not just in the
        # secrecy fixture: recompute clearances with inference applied.
        self._recompile_with_edges()
        cards = list(self.confirm_queue)
        return compiled, cards

    # -- S4: user-control verbs ----------------------------------------------
    def room(self, declaration):
        """'Mom's here' / 'I'm alone' -> belief update. Returns what changed."""
        decl = declaration.lower()
        signals = []
        if "mom" in decl and "here" in decl:
            signals.append(("mom", "declare"))
            changed = "mom added to belief (sticky until 'mom left')"
        elif "alone" in decl:
            signals.append(("priya", "alone"))
            changed = "'alone' noted: weak removal only, low-sensitivity items"
        elif "guest" in decl:
            signals.append(("unknown", "guest"))
            changed = "unknown visitor added to belief"
        elif "left" in decl:
            signals.append(("mom", "declare_left"))
            changed = "mom removed from belief"
        else:
            changed = "no signal parsed (fixture: try \"mom's here\" / \"i'm alone\")"
        if signals:
            self.belief = self.hotlane.fuse_belief(signals, self._current_priors(), self._now)
        return changed

    def keep_secret(self, instruction):
        """One sentence -> instant TIGHTEN edge. Returns the edge or None."""
        edge = self.secrecy.handle_keep_secret(instruction, self.pack)
        if edge is None:
            self.confirm_queue.append(
                f"Couldn't parse {instruction!r} — clarify on your phone?")
            return None
        # Hot-patch: recompile affected rows with the new edge applied.
        # The edge carries its topic; only rows about that topic are affected.
        topic = self.secrecy._match_topic(instruction.lower(), self.pack)
        self._pending_edges.append((edge, topic))
        self._recompile_with_edges()
        return edge

    def _recompile_with_edges(self):
        for item_id, item in list(self.items.items()):
            if item.state != "COMPILED":
                continue
            topics = set(item.topics)
            edges = self.secrecy.accept(self.secrecy.infer_edges(item))
            for pending_edge, pending_topic in self._pending_edges:
                if pending_topic in topics or any(
                        t == pending_topic or t.startswith(pending_topic + ".")
                        for t in topics):
                    accepted = self.secrecy.accept([pending_edge])
                    edges = list(edges) + accepted
            clearance = self.slowlane._clearance(item, item.topics, edges)
            row = self.rows[item_id]
            self.rows[item_id] = type(row)(
                item_id=row.item_id, sensitivity=row.sensitivity,
                clearance=clearance, chain=row.chain, version=row.version + 1)

    # -- S2+S3: brief (Seams 2 and 3) ----------------------------------------
    def brief(self, signals=()):
        """Run belief -> plan -> assemble. Returns (Response, ledger_entries)."""
        if signals:
            self.belief = self.hotlane.fuse_belief(signals, self._current_priors(), self._now)
        elif self.belief is None:
            self.belief = self.hotlane.fuse_belief([], self._current_priors(), self._now)
        rows = [self.rows[iid] for iid in self.rows]
        plan = self.hotlane.plan(rows, self.belief, self.ledger)
        response = self.shape.assemble(plan, self.rows, self.pack, self.fields)
        # Ledger: over-attribute — everyone credible is assumed to have heard it.
        entries = []
        for pi in plan.items:
            for person in plan.credible_set:
                self.ledger.record(person, pi.item_id, pi.depth, self._now)
                entries.append((person, pi.item_id, pi.depth))
        # Personal outbox: the digest always goes to the phone in cover mode.
        if response.phone_digest:
            self.outbox.append(response.phone_digest)
        return response, {"plan": plan, "entries": entries,
                          "belief": {p: round(self._sigmoid(v), 2)
                                     for p, v in self.belief.log_odds.items()}}

    def ask_about(self, query):
        """Probe-resistant query path. Never answers from hidden content."""
        if self.belief is None:
            self.belief = self.hotlane.fuse_belief([], self._current_priors(), self._now)
        plan = self.hotlane.plan(list(self.rows.values()), self.belief, self.ledger)
        return self.shape.probe_response(query, plan, self.pack)

    # -- personal channel ------------------------------------------------------
    def phone_inbox(self):
        """What the owner's phone shows: digests + confirm cards."""
        return {"digests": list(self.outbox), "confirm_cards": list(self.confirm_queue)}

    def _current_priors(self):
        if self.belief is None:
            return dict(self._priors)
        return dict(self.belief.log_odds)

    @staticmethod
    def _sigmoid(x):
        import math
        return 1.0 / (1.0 + math.exp(-x))
