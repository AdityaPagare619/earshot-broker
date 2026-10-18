"""Sealed-task broker: the 6 MCP tools against the real kernel (J3 + S4).

Every tool binds (tenant, owner) from the verified auth context — never from
arguments. Private computation happens inside the boundary; only explicitly
authorized public facts cross it. All error messages are secret-free.

S4 addition: `room` and `keep_secret` user-control tools, backed by the
secrecy graph (packages/secrecy) — choke-point edge store, monotone gate,
declaration log with asymmetric trust at ingest."""
from __future__ import annotations

import json
import secrets
import time
from datetime import date as date_cls
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import fixtures
from .fixtures import FixtureWorld

# --- kernel (single source of truth: packages/kernel/kernel.py, FROZEN) ---
from earshot.kernel import Context, Fact, Kernel, Label, PUBLIC

# --- secrecy package (S4): graph + monotone gate + declarations ------------
from earshot.secrecy.store import EdgeStore
from earshot.secrecy.declarations import DeclarationLog, parse_declaration
from earshot.secrecy.parse import parse_keep_secret
from earshot.secrecy.overrides import GLOBAL_SCOPE, effective_clearance

# --- hotlane package (S2): belief fusion, credible sets, minimax planner ---
from earshot.hotlane import (
    ALONE,
    DECLARE_ABSENT,
    DECLARE_PRESENT,
    GeneralizationChain,
    Signal,
    TableRow,
    initial_ledger,
    logit,
    plan_briefing,
)

# --- Seam 3 (S3): constant-shape assembly ----------------------------------
from . import shape as shape_mod
from .shape import (
    AssemblyInput,
    assemble,
    new_plan_id,
    planned_from_briefing,
    tables_for_world,
    take_chunk,
    terminal_assembly,
    FIXTURE_TABLE_VERSION,
    CHUNK_SIZE,
)

PUB = PUBLIC  # '*'


class BrokerError(Exception):
    """Safe, secret-free error. `code` is a JSON-RPC error code.

    `data` carries only public affordances (never secret-derived values);
    it is rendered as the JSON-RPC error's `data` member.
    """

    def __init__(self, code: int, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# Dossier §9: unknown vs forbidden reference are indistinguishable.
UNAVAILABLE = -32603
# J4-C3: a task denial is never a bare dead end. The continuation pointer is
# IDENTICAL for unknown and forbidden references, so it cannot oracle.
CONTINUATION = "personal_inbox"


def _unavailable() -> BrokerError:
    return BrokerError(UNAVAILABLE, "Unavailable",
                       data={"continuation": CONTINUATION})


# --- validation (server-side, including cross-field constraints) ---

def _check(cond: bool, field: str) -> None:
    if not cond:
        # Field name only — never the offending value (could be secret-bearing).
        raise BrokerError(INVALID_PARAMS, f"invalid params: '{field}'")


def validate_date(value) -> None:
    _check(isinstance(value, str), "date")
    try:
        date_cls.fromisoformat(value)
    except ValueError:
        raise BrokerError(INVALID_PARAMS, "invalid params: 'date'")


def validate_timezone(value) -> None:
    _check(isinstance(value, str) and 1 <= len(value) <= 80, "timezone")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise BrokerError(INVALID_PARAMS, "invalid params: 'timezone'")


def validate_request_key(value) -> None:
    _check(isinstance(value, str) and 16 <= len(value) <= 128, "request_key")


def validate_request_ref(value) -> None:
    _check(isinstance(value, str) and 20 <= len(value) <= 128, "request_ref")


def validate_change(value) -> dict:
    _check(isinstance(value, dict), "change")
    kind = value.get("kind")
    _check(kind in ("add_flexible_block", "find_alternative_window"), "change.kind")
    dur = value.get("duration_minutes")
    _check(isinstance(dur, int) and not isinstance(dur, bool) and 5 <= dur <= 240,
           "change.duration_minutes")
    try:
        start = datetime.fromisoformat(value.get("window_start", ""))
        end = datetime.fromisoformat(value.get("window_end", ""))
    except (ValueError, TypeError, AttributeError):
        raise BrokerError(INVALID_PARAMS, "invalid params: 'change.window_start/window_end'")
    _check(start.tzinfo is not None and end.tzinfo is not None,
           "change.window_start/window_end")
    _check(end > start, "change.window_start/window_end")
    return {"kind": kind, "duration_minutes": dur,
            "window_start": start, "window_end": end}


# --- private interval solver (inside the boundary) ---

def _busy_minutes(world: FixtureWorld) -> list[tuple[int, int]]:
    iv = sorted((b.start_min, b.end_min) for b in world.busy)
    merged: list[list[int]] = []
    for s, e in iv:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def free_windows(busy: list[tuple[int, int]], lo: int = 0, hi: int = 1440,
                 min_len: int = 5) -> list[tuple[int, int]]:
    out, cur = [], lo
    for s, e in busy:
        if s - cur >= min_len:
            out.append((cur, s))
        cur = max(cur, e)
    if hi - cur >= min_len:
        out.append((cur, hi))
    return out


def find_window(busy: list[tuple[int, int]], duration: int,
                win_start: int, win_end: int) -> int | None:
    """First start minute of a `duration`-long free slot inside the window."""
    for fs, fe in free_windows(busy, win_start, win_end, duration):
        if fe - fs >= duration:
            return fs
    return None


def _fmt_time(m: int) -> str:
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mm:02d} {suffix}"


# --- label construction: private by default (dossier decision #21) ---

def _facts_for_world(world: FixtureWorld) -> tuple:
    facts = []
    for text in world.public_facts:
        facts.append(Fact(key=f"public:{text[:24]}", value=text,
                          label=Label(frozenset({PUB}))))
    for b in world.busy:
        label = Label(frozenset(b.readers), frozenset({"calendar"}))
        facts.append(Fact(key=f"busy:{b.start_min}-{b.end_min}",
                          value=f"{b.title} at {_fmt_time(b.start_min)}",
                          label=label))
    return tuple(facts)


# --- the broker ---

class Broker:
    """Owns kernel, task registry, idempotency store, outbox. In-memory."""

    def __init__(self, world_factory=fixtures.strict_world):
        self.kernel = Kernel()
        self._world_factory = world_factory
        self._tasks: dict[str, dict] = {}        # receipt -> {world_name, date, timezone}
        self._idem: dict[tuple, tuple] = {}      # (tenant, owner, key) -> (params_json, response)
        self._outbox: dict[tuple, dict] = {}     # (owner, request_key) -> entry
        # S4: secrecy graph (choke-point store) + declaration log.
        self.secrecy = EdgeStore()
        self.declarations = DeclarationLog()
        # S3: chunk state, exposure ledgers, fixture audience override.
        self._chunks: dict[str, dict] = {}       # receipt -> {"remaining": [item_id]}
        self._ledgers: dict[tuple, object] = {}  # (tenant, owner) -> ExposureLedger
        # Fixture-only audience override (tests, simulator demo). None ->
        # belief comes from S4's declaration log through S2's fusion.
        self._fixture_audience: frozenset | None = None

    # -- S3: fixture audience channel (never a tool argument) ----------------

    def set_fixture_audience(self, listeners) -> None:
        """Fixture-only audience override (tests, simulator demo)."""
        self._fixture_audience = frozenset(listeners)

    def clear_fixture_audience(self) -> None:
        """Drop the fixture override: belief comes from the declaration log."""
        self._fixture_audience = None

    # -- internal helpers --

    def _world(self) -> FixtureWorld:
        return self._world_factory()

    def _check_idem(self, tenant: str, owner: str, key: str, params: dict):
        slot = (tenant, owner, key)
        canon = json.dumps(params, sort_keys=True, default=str)
        if slot in self._idem:
            prev_canon, prev_resp = self._idem[slot]
            if prev_canon != canon:
                raise BrokerError(INVALID_PARAMS,
                                  "conflicting request_key reuse: key already used with different parameters")
            return dict(prev_resp)
        return None

    def _store_idem(self, tenant: str, owner: str, key: str, params: dict, resp: dict):
        self._idem[(tenant, owner, key)] = (json.dumps(params, sort_keys=True, default=str), dict(resp))

    def _capsule_facts(self, receipt: str, tenant: str, owner: str) -> tuple:
        try:
            return self.kernel.open_private(receipt, tenant, owner,
                                            authenticated=True, now=time.time())
        except PermissionError:
            # Unknown and forbidden are indistinguishable — no existence oracle.
            # The continuation pointer is identical for both (J4-C3).
            raise _unavailable()

    # -- Seam 3: constant-shape planning + response construction (S3) --------

    def _signals_for(self, owner: str, now: float) -> tuple:
        """Belief signals for S2's fusion -> (signals, unknown_logit).

        Live path: S4's declaration log mapped to S2 signal kinds (the real
        flow — `room` declarations drive belief). Fixture path: the
        set_fixture_audience override, mapped to DECLARE_PRESENT signals;
        the fixture audience is exhaustive, so unknown is truly absent.
        """
        if self._fixture_audience is not None:
            signals = []
            for p in sorted(self._fixture_audience):
                if p == owner:
                    continue
                # Fixture sensing mapping: the demo's unnamed "guest" label
                # IS the guest role (no named guests exist in the fixture).
                person = "role:guest" if p == "guest" else p
                signals.append(Signal(DECLARE_PRESENT, person=person, at=now))
            return signals, logit(0.001)
        signals = []
        for d in self.declarations.since(0):
            person = owner if d.person in ("owner", owner) else d.person
            if d.kind == "present":
                signals.append(Signal(DECLARE_PRESENT, person=person,
                                      at=d.timestamp))
            elif person == owner:
                # Voice "I'm alone" / "private now" (S4 trust class at ingest).
                signals.append(Signal(ALONE, person=person, at=d.timestamp))
            else:
                signals.append(Signal(DECLARE_ABSENT, person=person,
                                      at=d.timestamp))
        return signals, None  # planner default unknown logit

    def _hotlane_rows(self, owner: str, now: float) -> tuple:
        """Fixture world -> S1-shape rows -> S2 TableRows with the S4
        keep_secret overlay applied (min-only, immediate).

        Returns (hotlane_rows, fixture_by_id): the planner reads the former;
        the S3 adapter reads rendition text from the latter.
        """
        fixture_rows = tables_for_world(self._world(), owner)
        out = []
        for fr in fixture_rows:
            clearance = effective_clearance(fr.item_id, dict(fr.clearance),
                                            self.secrecy, now)
            out.append(TableRow(
                item_id=fr.item_id, sensitivity=fr.sensitivity,
                clearance=clearance,
                chain=GeneralizationChain(depths=fr.chain, renditions={}),
                version=fr.version))
        return tuple(out), {fr.item_id: fr for fr in fixture_rows}

    def _plan_brief(self, tenant: str, owner: str, now: float) -> tuple:
        """Run S2's planner. Returns (planned, mode, screen_depth, plan).

        Pure w.r.t. the response: the SAME inputs always produce the SAME
        plan — the byte-identity property the paired-world tests pin.
        """
        rows, fixture_by_id = self._hotlane_rows(owner, now)
        signals, unknown_logit = self._signals_for(owner, now)
        ledger = self._ledgers.get((tenant, owner), initial_ledger())
        plan = plan_briefing(
            signals=signals, priors={owner: logit(0.99)}, rows=rows,
            owner=owner, ledger=ledger, unknown_logit=unknown_logit, now=now)
        planned, mode, screen_depth = planned_from_briefing(plan, fixture_by_id)
        return planned, mode, screen_depth, plan

    def _commit_exposures(self, tenant: str, owner: str, plan,
                          spoken_ids: frozenset, now: float) -> None:
        """Commit pending exposures for items ACTUALLY spoken (S2: commit
        AFTER speaking). Unchunked items consume no budget yet."""
        ledger = self._ledgers.get((tenant, owner), initial_ledger())
        due = tuple(e for e in plan.pending_exposures
                    if e.secret in spoken_ids)
        self._ledgers[(tenant, owner)] = ledger.record(due)

    def _cover_mode(self, owner: str) -> bool:
        """Room-known mode for non-brief tools: a non-owner listener has been
        declared (live) or fixture-set (tests/demo)."""
        if self._fixture_audience is not None:
            return any(p != owner for p in self._fixture_audience)
        return any(d.kind == "present" and d.person not in ("owner", owner)
                   for d in self.declarations.since(0))

    def _mode(self, owner: str) -> str:
        return "cover" if self._cover_mode(owner) else "open"

    def _simple_contract(self, speak: str, receipt: str, owner: str,
                         followups: tuple = ("continue_on_personal_device",),
                         screen_depth: int = 0) -> dict:
        """Sealed-speech response contract for non-brief tools. The speak
        texts are constant by construction — no counts, no secret tokens."""
        return shape_mod._contract(
            speak, self._mode(owner), followups, screen_depth,
            receipt, "accepted", new_plan_id(), FIXTURE_TABLE_VERSION)

    def _queue_digest(self, owner: str, key: str, receipt: str) -> None:
        """The phone digest is ALWAYS queued, silently, for every brief.

        The wire response never varies with it (followups are constant
        affordances), so the digest's presence carries no signal.
        """
        self._outbox[(owner, key)] = {"receipt": receipt, "state": "queued",
                                      "kind": "digest",
                                      "enqueued_at": time.time()}

    # -- the 6 tools (4 sealed-task + 2 user-control) --

    def room(self, tenant: str, owner: str, params: dict) -> dict:
        """Declaration -> belief update. The declaration is recorded with its
        trust class (asymmetric: voice can add listeners freely; "I'm alone"
        only loosens low-sensitivity items). The response is constant-shape:
        identical whether parsed or not, known person or not — it never
        confirms or denies secrets."""
        declaration = params.get("declaration")
        _check(isinstance(declaration, str)
               and 1 <= len(declaration) <= 200, "declaration")
        validate_request_key(params.get("request_key"))
        key = params["request_key"]

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        parsed = parse_declaration(declaration)
        if parsed is not None:
            person, kind = parsed
            # Voice declarations are unauthenticated by construction: the MCP
            # transport carries no speaker-verification claim. The trust class
            # is tagged here; S2's fusion consumes it.
            self.declarations.declare(person, kind, source="voice",
                                      authenticated=False)

        ref = "room-" + secrets.token_urlsafe(16)
        # S3: uniform sealed-speech contract on every tool. "Noted." is the
        # entire vocabulary — constant whether parsed or not, known or not.
        resp = self._simple_contract("Noted.", ref, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def keep_secret(self, tenant: str, owner: str, params: dict) -> dict:
        """One sentence -> instant TIGHTEN edge (global scope). Parse, gate,
        store — all in one call, so clearance drops immediately via the
        min-only overlay. No confirmation needed: tightening is always safe.
        The response never echoes topic nouns (Seam 3 discipline)."""
        instruction = params.get("instruction")
        _check(isinstance(instruction, str)
               and 1 <= len(instruction) <= 500, "instruction")
        validate_request_key(params.get("request_key"))
        key = params["request_key"]

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        for proposal in parse_keep_secret(instruction):
            # claimed_source="declared" comes from the parser: an explicit
            # user act. The gate still enforces TIGHTEN ∧ conf >= 0.6; the
            # parser's output vocabulary is TIGHTEN-only anyway.
            self.secrecy.add(GLOBAL_SCOPE, proposal, owner=owner)

        ref = "ks-" + secrets.token_urlsafe(16)
        # S3: uniform sealed-speech contract. Constant speak — the response
        # never echoes topic nouns (Seam 3 discipline, per S4's docstring).
        resp = self._simple_contract(
            "Noted. I'll keep that private from the people you named.",
            ref, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def prepare_day_brief(self, tenant: str, owner: str, params: dict) -> dict:
        validate_date(params.get("date"))
        validate_timezone(params.get("timezone"))
        validate_request_key(params.get("request_key"))
        key = params["request_key"]
        continuation = params.get("continuation_ref")
        if continuation is not None:
            validate_request_ref(continuation)

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        # "next": continue a chunked brief. Ownership is validated first
        # (unknown/forbidden -> identical "unavailable", no oracle).
        if continuation is not None:
            return self._next_chunk(tenant, owner, continuation, params, key)

        world = self._world()
        facts = _facts_for_world(world)
        # Receipt created BEFORE private lookup; shape independent of contents.
        now = time.time()
        accepted = self.kernel.accept(tenant, owner, key, facts, now)
        receipt = accepted["receipt"]
        self._tasks[receipt] = {"world": world.name, "date": params["date"],
                                "timezone": params["timezone"]}

        # Seam 3: S2 plans against fused belief; S3 assembles constant-shape.
        # Private computation stays inside the boundary; only the planned
        # rendition at the planned depth crosses it.
        #
        # Chunking runs over SPOKEN items only: absorbed/deferred rows are
        # invisible and must not shift chunk boundaries (else a hidden row's
        # presence would be measurable in the turn structure).
        planned, mode, screen_depth, plan = self._plan_brief(tenant, owner, now)
        spoken = tuple(p for p in planned
                       if p.action == "SPEAK" and p.depth > 0 and p.text)
        chunk, remaining = take_chunk(spoken, CHUNK_SIZE)
        if remaining:
            self._chunks[receipt] = {
                "remaining": [p.item_id for p in remaining]}
            followups = ("next", "continue_on_personal_device")
        else:
            followups = ("continue_on_personal_device",)
        resp = assemble(AssemblyInput(
            items=chunk, mode=mode, plan_id=new_plan_id(),
            table_version=FIXTURE_TABLE_VERSION, screen_depth=screen_depth,
            followups=followups, continuation_ref=receipt))
        # S2: commit exposures AFTER speaking — only for items actually spoken.
        self._commit_exposures(tenant, owner, plan,
                               frozenset(p.item_id for p in chunk), now)
        self._queue_digest(owner, key, receipt)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def _next_chunk(self, tenant: str, owner: str, receipt: str,
                    params: dict, key: str) -> dict:
        """Return the next chunk of a chunked brief.

        Belief is re-read structurally: the world is recompiled and the
        remaining items are RE-PLANNED against fresh belief through S2's
        planner. An audience change between turns collapses the disclosure
        at the turn boundary — the honest version of "mid-stream collapse".
        Idempotent: replaying the same key returns the stored chunk without
        advancing (the idem check precedes the advance).
        """
        self._capsule_facts(receipt, tenant, owner)  # ownership; no oracle
        now = time.time()
        state = self._chunks.get(receipt)
        planned, mode, screen_depth, plan = self._plan_brief(tenant, owner, now)
        if not state:
            resp = terminal_assembly(new_plan_id(), FIXTURE_TABLE_VERSION,
                                     mode, receipt)
            self._store_idem(tenant, owner, key, params, resp)
            return resp
        remaining_ids = set(state["remaining"])
        replanned = tuple(p for p in planned if p.item_id in remaining_ids)
        # Only spoken items chunk (see prepare_day_brief); the re-plan may
        # have absorbed an item the earlier turn spoke — it simply drops out.
        respoken = tuple(p for p in replanned
                         if p.action == "SPEAK" and p.depth > 0 and p.text)
        chunk, rest = take_chunk(respoken, CHUNK_SIZE)
        if rest:
            state["remaining"] = [p.item_id for p in rest]
            followups = ("next", "continue_on_personal_device")
        else:
            self._chunks.pop(receipt, None)
            followups = ("continue_on_personal_device",)
        resp = assemble(AssemblyInput(
            items=chunk, mode=mode, plan_id=new_plan_id(),
            table_version=FIXTURE_TABLE_VERSION, screen_depth=screen_depth,
            followups=followups, continuation_ref=receipt))
        self._commit_exposures(tenant, owner, plan,
                               frozenset(p.item_id for p in chunk), now)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def resolve_day_change(self, tenant: str, owner: str, params: dict) -> dict:
        validate_request_ref(params.get("request_ref"))
        change = validate_change(params.get("change"))
        validate_request_key(params.get("request_key"))
        key = params["request_key"]
        receipt = params["request_ref"]

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        self._capsule_facts(receipt, tenant, owner)  # ownership check; facts unused publicly
        world = self._world()
        busy = _busy_minutes(world)

        if change["kind"] == "find_alternative_window":
            # Strict fixtures carry private content: generic answer only — a
            # window/no-window answer would be secret-dependent. The lenient
            # fixture resolves a single verdict inside the boundary; only the
            # verdict crosses, never candidates or counts.
            if world.public_derived_schedule:
                ws = change["window_start"]
                we = change["window_end"]
                # Fixture day is synthetic; map the requested window onto
                # fixture minutes for the demo solver (documented).
                start_m = ws.hour * 60 + ws.minute
                end_m = we.hour * 60 + we.minute
                slot = find_window(busy, change["duration_minutes"], start_m, end_m)
                if slot is not None:
                    speak = (f"A {change['duration_minutes']}-minute window is "
                             f"available at {_fmt_time(slot)}.")
                else:
                    speak = "No suitable window found in that range."
            else:
                speak = "No suitable window found in that range."
        else:  # add_flexible_block: draft only, no external mutation
            speak = "Draft prepared. Approve it on your personal device."

        # S3: uniform sealed-speech contract (replaces public_facts).
        resp = self._simple_contract(speak, receipt, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def personal_facts(self, receipt: str, tenant: str, owner: str) -> list:
        """Owner-authenticated personal surface (the phone panel).

        Raises BrokerError("unavailable") for unknown/forbidden — the panel
        maps it to a generic locked state, never an oracle.
        """
        facts = self._capsule_facts(receipt, tenant, owner)
        return [{"key": f.key, "value": f.value,
                 "readers": sorted(f.label.readers),
                 "topics": sorted(f.label.topics)} for f in facts]

    def day_card(self, receipt: str, tenant: str, owner: str) -> dict:
        """Public-safe card for the ui:// resource. Sealed-speech contract.

        Re-plans against current belief and assembles the full planned set
        (cards don't chunk — they are a static projection, not a turn).
        Exposure accounting attaches to speech acts (the brief's tool calls,
        which are idempotent and keyed); the card is a read-only view and
        does not commit — a deployment serving cards to rooms without speech
        should route through prepare_day_brief. (S2's lane owns the budget
        semantics; S3 owns the shape: no counts, no ordinals, fixed suffix.)
        """
        self._capsule_facts(receipt, tenant, owner)  # ownership; no oracle
        now = time.time()
        planned, mode, screen_depth, _plan = self._plan_brief(tenant, owner, now)
        card = assemble(AssemblyInput(
            items=planned, mode=mode, plan_id=new_plan_id(),
            table_version=FIXTURE_TABLE_VERSION, screen_depth=screen_depth,
            followups=("continue_on_personal_device",),
            continuation_ref=receipt))
        card["uri"] = "ui://earshot/day-card"
        return card

    def continue_on_personal_device(self, tenant: str, owner: str, params: dict) -> dict:
        validate_request_ref(params.get("request_ref"))
        validate_request_key(params.get("request_key"))
        key = params["request_key"]
        receipt = params["request_ref"]

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        self._capsule_facts(receipt, tenant, owner)
        slot = (owner, key)
        if slot not in self._outbox:
            self._outbox[slot] = {"receipt": receipt, "state": "queued",
                                 "enqueued_at": time.time()}
        # "accepted" means queued — never delivered (dossier §12.4).
        # S3: uniform sealed-speech contract.
        resp = self._simple_contract("Continuing on your personal device.",
                                     receipt, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def withdraw_request(self, tenant: str, owner: str, params: dict) -> dict:
        validate_request_ref(params.get("request_ref"))
        validate_request_key(params.get("request_key"))
        key = params["request_key"]
        receipt = params["request_ref"]

        hit = self._check_idem(tenant, owner, key, params)
        if hit is not None:
            return hit

        try:
            self.kernel.revoke(receipt, tenant, owner)
        except PermissionError:
            raise _unavailable()
        self._tasks.pop(receipt, None)
        # S3: withdrawing a brief also drops its chunk state — a withdrawn
        # brief has no "next".
        self._chunks.pop(receipt, None)

        # J4-C4 substance: a queued personal-device continuation is an
        # in-flight external effect. Revoking the capsule does not un-queue
        # it, so mark every outbox entry for this receipt withdrawn — it can
        # never be acted on. The public surface never claims "undone"; the
        # exact reconciliation state stays private.
        #
        # The auto-queued brief digest is infrastructure, not an explicit
        # continuation: only explicit continuations trigger the reconciling
        # variant of the speak text.
        had_inflight = False
        for slot, entry in self._outbox.items():
            if slot[0] == owner and entry.get("receipt") == receipt \
                    and entry.get("state") == "queued":
                entry["state"] = "withdrawn"
                if entry.get("kind") != "digest":
                    had_inflight = True

        # S3: uniform sealed-speech contract. Two constant speak texts (the
        # reconciling variant is a function of call history, not secrets).
        if had_inflight:
            speak = ("Request withdrawn. A queued continuation is "
                     "reconciling — already emitted output can't be unsent.")
        else:
            speak = ("Request withdrawn. Already emitted output can't be "
                     "unsent.")
        resp = self._simple_contract(speak, receipt, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp
