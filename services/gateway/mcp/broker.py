"""Sealed-task broker: the 4 MCP tools against the real kernel (J3).

Every tool binds (tenant, owner) from the verified auth context — never from
arguments. Private computation happens inside the boundary; only explicitly
authorized public facts cross it. All error messages are secret-free.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from datetime import date as date_cls
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import fixtures
from fixtures import FixtureWorld

import shape as shape_mod
from shape import (AssemblyInput, FixturePlanner, assemble, new_plan_id,
                   tables_for_world, take_chunk, terminal_assembly,
                   FIXED_SUFFIX, FIXTURE_TABLE_VERSION, CHUNK_SIZE)

# --- kernel loading (single source of truth: packages/kernel/kernel.py) ---
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_KERNEL_PATH = os.path.join(_REPO_ROOT, "packages", "kernel", "kernel.py")


def _load_kernel():
    spec = importlib.util.spec_from_file_location("earshot_kernel", _KERNEL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_k = _load_kernel()
Kernel, Fact, Label, Context = _k.Kernel, _k.Fact, _k.Label, _k.Context
PUB = _k.PUBLIC  # '*'


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
        self._chunks: dict[str, dict] = {}       # receipt -> {"remaining": [item_id]}
        # Fixture belief (S3): the gateway's audience for the fixture planner.
        # None -> {owner} (owner alone). Set via set_fixture_audience() — a
        # FIXTURE-ONLY channel, never a tool argument. S2's real planner owns
        # live belief; S4's `room` tool will drive it.
        self._fixture_audience: frozenset | None = None

    def set_fixture_audience(self, listeners) -> None:
        """Fixture-only audience override (tests, simulator demo)."""
        self._fixture_audience = frozenset(listeners)

    def _audience(self, owner: str) -> frozenset:
        if self._fixture_audience is not None:
            return self._fixture_audience | {owner}
        return frozenset({owner})

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

    # -- Seam 3: constant-shape response construction ----------------------

    def _simple_contract(self, speak: str, receipt: str, owner: str,
                         followups: tuple = ("continue_on_personal_device",),
                         screen_depth: int = 0) -> dict:
        """Response contract for non-brief tools (already constant by
        construction — short status texts, no counts, no secret tokens)."""
        return shape_mod._contract(
            speak, self._mode(owner), followups, screen_depth,
            receipt, "accepted", new_plan_id(), FIXTURE_TABLE_VERSION)

    def _mode(self, owner: str) -> str:
        """Mode is room-known, not secret: the room knows who's there.

        The planner's own mode and this one always agree — both are
        "cover" iff a non-owner is in the fixture audience.
        """
        return "cover" if any(p != owner for p in self._audience(owner)) else "open"

    def _queue_digest(self, owner: str, key: str, receipt: str) -> None:
        """The phone digest is ALWAYS queued, silently, for every brief.

        The wire response never varies with it (followups are constant
        affordances), so the digest's presence carries no signal.
        """
        self._outbox[(owner, key)] = {"receipt": receipt, "state": "queued",
                                      "kind": "digest",
                                      "enqueued_at": time.time()}

    # -- the 4 tools --

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

        # "next": continue a chunked brief. The continuation ref is validated
        # for ownership first (unknown/forbidden -> identical "unavailable").
        if continuation is not None:
            return self._next_chunk(tenant, owner, continuation, params, key)

        world = self._world()
        facts = _facts_for_world(world)
        # Receipt created BEFORE private lookup; shape independent of contents.
        accepted = self.kernel.accept(tenant, owner, key, facts, time.time())
        receipt = accepted["receipt"]
        self._tasks[receipt] = {"world": world.name, "date": params["date"],
                                "timezone": params["timezone"]}

        # Seam 3: plan against fixture belief, assemble constant-shape.
        # Private computation stays inside the boundary; only the leased
        # public projection crosses (Profile A: durable-public facts only).
        tables = tables_for_world(world, owner)
        planned, mode, screen_depth = FixturePlanner.plan(
            tables, self._audience(owner), owner)
        chunk, remaining = take_chunk(planned, CHUNK_SIZE)
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
        self._queue_digest(owner, key, receipt)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def _next_chunk(self, tenant: str, owner: str, receipt: str,
                    params: dict, key: str) -> dict:
        """Return the next chunk of a chunked brief.

        Belief is re-read structurally: the world is rebuilt fresh and the
        remaining items are re-planned. An audience change between turns
        collapses the disclosure at the turn boundary — the honest version
        of "mid-stream collapse".
        """
        self._capsule_facts(receipt, tenant, owner)  # ownership; no oracle
        state = self._chunks.get(receipt)
        audience = self._audience(owner)
        mode = "cover" if any(p != owner for p in audience) else "open"
        if not state:
            resp = terminal_assembly(new_plan_id(), FIXTURE_TABLE_VERSION,
                                     mode, receipt)
            self._store_idem(tenant, owner, key, params, resp)
            return resp
        world = self._world()
        tables = tables_for_world(world, owner)
        planned, _, screen_depth = FixturePlanner.plan(tables, audience, owner)
        remaining_ids = set(state["remaining"])
        replanned = tuple(p for p in planned if p.item_id in remaining_ids)
        chunk, rest = take_chunk(replanned, CHUNK_SIZE)
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

        resp = self._simple_contract(speak, receipt, owner)
        self._store_idem(tenant, owner, key, params, resp)
        return resp

    def day_card(self, receipt: str, tenant: str, owner: str) -> dict:
        """Public-safe card for the ui:// resource. Only public facts cross."""
        facts = self._capsule_facts(receipt, tenant, owner)
        public = [p for p in Kernel.public_projection(facts) if len(p) <= 300][:12]
        return {"uri": "ui://earshot/day-card",
                "request_ref": receipt,
                "request_state": "accepted",
                "public_facts": list(public),
                "note": "Public facts only. Full plan is in the owner inbox."}

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
        resp = {"request_ref": receipt, "request_state": "accepted",
                "public_facts": ["Continuation queued in the owner inbox."]}
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

        # J4-C4 substance: a queued personal-device continuation is an
        # in-flight external effect. Revoking the capsule does not un-queue
        # it, so mark every outbox entry for this receipt withdrawn — it can
        # never be acted on. The public surface never claims "undone"; the
        # exact reconciliation state stays private.
        had_inflight = False
        for slot, entry in self._outbox.items():
            if slot[0] == owner and entry.get("receipt") == receipt \
                    and entry.get("state") == "queued":
                entry["state"] = "withdrawn"
                had_inflight = True

        if had_inflight:
            public_facts = ["Request withdrawn. A queued personal-device "
                            "continuation is reconciling — already emitted "
                            "output cannot be retracted."]
        else:
            public_facts = ["Request withdrawn. Already emitted output cannot "
                            "be retracted."]
        resp = {"request_ref": receipt, "request_state": "accepted",
                "public_facts": public_facts}
        self._store_idem(tenant, owner, key, params, resp)
        return resp
