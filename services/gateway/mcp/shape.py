"""Seam 3 — constant-shape assembly (S3 seat).

The ONLY module that turns planned disclosure into spoken text. Pure functions,
stdlib only, no I/O, no model. It is imported by both the MCP gateway
(services/gateway/mcp/broker.py — the wire path) and the simulator
(apps/simulator/gateway_port.py — the UI path): one assembly implementation,
two call sites. If these ever drift, shape leaks are born.

The guarantee, stated as code: the assembler emits ONLY text it was given, in
canonical order, with no counts, no ordinals, no depths, no sensitivities, no
item IDs, and the fixed suffix ALWAYS appended (even when nothing was withheld).
"Nothing above planned depth in any field" is structural — the planner (S2's
real planner, or the fixture planner below) puts only planned-depth rendition
text into PlannedItem; the assembler has no code path that can reach any other
text.

Cover-mode shape is a function of the credible set only — never of hidden data.
"""
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Constants (the shape itself — changing these changes what the room hears)

SPEAK_POLICY = "verbatim_no_elaboration"

#: Appended to EVERY brief-family speak text, in both modes, whether or not
#: anything was withheld. Its presence must never be a signal. (Even in open
#: mode, quarantined items may be withheld — Seam 1 — so the suffix is not a
#: signal there either.)
FIXED_SUFFIX = "The rest of your day is on your phone."

#: The entire probe vocabulary. One sentence, no variants: a probe answered any
#: other way becomes a probe-distinguishable oracle.
PROBE_SPEAK = "I'll put anything about that on your phone."

#: Terminal chunk: the "next" after the last chunk. Constant, like everything.
TERMINAL_SPEAK = "That's everything I can share out loud."

#: Chunk size for the honest mid-conversation collapse (A2 §8.4).
CHUNK_SIZE = 2

#: Fixture table version. Constant BY DESIGN: a content-derived version would be
#: a metadata leak across paired worlds. S1's real compiler must use a monotonic
#: epoch counter, never a content hash (see docs/seats/s03/DESIGN.md D6/D10).
FIXTURE_TABLE_VERSION = 1

_LEAD_IN = "Here's today: "
_NOTHING_LOUD = "Nothing I can share out loud right now. "

#: Words the assembler must never emit (it never does — structural — but the
#: tests pin this so a future edit can't silently add them).
_BANNED_WRAPPER_WORDS = ("first", "second", "third", "one private",
                         "private item", "withheld", "hidden")


# --------------------------------------------------------------------------
# Frozen input types (S2 implements against these; the fixture planner below
# is the stand-in until S2 lands)

@dataclass(frozen=True)
class PlannedItem:
    """One item's plan. `text` is the rendition at EXACTLY `depth`.

    The planner guarantees: text came from the item's generalization chain at
    `depth`, and `depth` is the minimax result over the credible set. The
    assembler trusts this the way a renderer trusts a display list.
    """
    item_id: str
    depth: int            # d* — planned spoken depth, 0..4 (0 = absorbed, d0)
    text: str             # rendition at `depth`; "" when depth == 0
    action: str           # SPEAK | PHONE | DEFER
    table_version: int


@dataclass(frozen=True)
class AssemblyInput:
    """Everything the assembler needs. Nothing it doesn't."""
    items: tuple          # PlannedItem — planner-ordered; re-sorted canonically
    mode: str             # "cover" | "open"  (mode is room-known, not secret)
    plan_id: str          # opaque, random, secret-independent ("pln_"+hex)
    table_version: int
    screen_depth: int
    followups: tuple      # e.g. ("next", "continue_on_personal_device")
    continuation_ref: str  # opaque owner-bound ref (the kernel receipt)
    request_state: str = "accepted"


# --------------------------------------------------------------------------
# Assembly

def _check_item(it: PlannedItem) -> None:
    if not isinstance(it.item_id, str) or not it.item_id:
        raise ValueError("PlannedItem.item_id must be a non-empty string")
    if it.depth not in (0, 1, 2, 3, 4):
        raise ValueError(f"PlannedItem.depth out of range: {it.depth}")
    if it.action not in ("SPEAK", "PHONE", "DEFER"):
        raise ValueError(f"PlannedItem.action unknown: {it.action}")
    if it.depth == 0 and it.text:
        raise ValueError("depth-0 (absorbed) items must carry no text")
    if it.action != "SPEAK" and it.text and it.depth > 0:
        # Non-spoken items must not smuggle text into the assembly input.
        raise ValueError("non-SPEAK items must carry no text")


def _join_spoken(texts: list[str]) -> str:
    """Join without counts, without ordinals. Oxford comma; constant template."""
    if len(texts) == 1:
        return texts[0]
    if len(texts) == 2:
        return f"{texts[0]}, and {texts[1]}"
    return ", ".join(texts[:-1]) + f", and {texts[-1]}"


def assemble(inp: AssemblyInput) -> dict:
    """Build the sealed-speech response contract. Pure and total.

    Output shape depends only on (mode, planned items at planned depths) —
    never on hidden content. In particular: no counts ("3 tasks"), no ordinals
    ("first"), no depths, no sensitivities, no item IDs anywhere in the output.
    """
    if inp.mode not in ("cover", "open"):
        raise ValueError(f"mode must be 'cover'|'open', got {inp.mode!r}")
    for it in inp.items:
        _check_item(it)

    # Canonical order, structural: item_id sort is independent of secrets.
    items = tuple(sorted(inp.items, key=lambda p: p.item_id))
    spoken = [p.text for p in items
              if p.action == "SPEAK" and p.depth > 0 and p.text]

    # Depth guard, structural: every emitted string is a member of the planned
    # set. There is no code path that can emit anything else.
    planned_texts = {p.text for p in items if p.text}
    for t in spoken:
        if t not in planned_texts:
            raise AssertionError("assembler emitted unplanned text")

    if spoken:
        speak = f"{_LEAD_IN}{_join_spoken(spoken)}. {FIXED_SUFFIX}"
    else:
        speak = f"{_NOTHING_LOUD}{FIXED_SUFFIX}"

    _assert_wrapper_clean(speak, spoken)

    return _contract(speak, inp.mode, inp.followups, inp.screen_depth,
                     inp.continuation_ref, inp.request_state,
                     inp.plan_id, inp.table_version)


def _contract(speak: str, mode: str, followups: tuple, screen_depth: int,
              continuation_ref: str, request_state: str,
              plan_id: str, table_version: int) -> dict:
    """The sealed-speech response contract. Single construction site."""
    return {
        "speak": speak,
        "speak_policy": SPEAK_POLICY,
        "mode": mode,
        "followups": list(followups),
        "screen_depth": screen_depth,
        "request_ref": continuation_ref,
        "request_state": request_state,
        "_meta": {"earshot/plan_id": plan_id,
                  "earshot/table_version": table_version},
    }


def _assert_wrapper_clean(speak: str, spoken: list[str]) -> None:
    """The assembler's own template adds no digits, ordinals, or leak words.

    Digits may only arrive inside item texts (e.g. "3:40") — never from the
    wrapper. Runs on every assembly; cheap, and it makes the invariant
    fail-fast instead of test-only.
    """
    low = speak.lower()
    for w in _BANNED_WRAPPER_WORDS:
        if w in low:
            # Allow the word only if it came from an item text, not the wrapper.
            if not any(w in t.lower() for t in spoken):
                raise AssertionError(f"wrapper leaked banned word: {w!r}")
    # Digits in the wrapper (outside item texts) would be counts.
    stripped = speak
    for t in spoken:
        stripped = stripped.replace(t, "", 1)
    if any(ch.isdigit() for ch in stripped):
        raise AssertionError("wrapper introduced digits (possible count leak)")


# --------------------------------------------------------------------------
# Probe resistance

def probe_speak() -> str:
    """The entire probe vocabulary: one constant string.

    Argless BY DESIGN: the response is computed without consulting the query,
    the world, or any data — so it is identical whether the probed item exists,
    doesn't exist, or is secret. Callers that detect a probe-shaped query route
    here instead of to any data path.
    """
    return PROBE_SPEAK


# --------------------------------------------------------------------------
# Chunked turns — the honest mid-conversation collapse

def take_chunk(items: tuple, n: int = CHUNK_SIZE) -> tuple[tuple, tuple]:
    """Split planned items into (chunk, remaining). Pure.

    Each "next" is a new tool call: the caller re-plans `remaining` against
    FRESH belief (the broker rebuilds the world per call — re-read is
    structural), then calls take_chunk again. Collapse happens at the turn
    boundary, which the platform physically allows.
    """
    if n <= 0:
        raise ValueError("chunk size must be positive")
    items = tuple(sorted(items, key=lambda p: p.item_id))
    return items[:n], items[n:]


def terminal_assembly(plan_id: str, table_version: int, mode: str,
                      continuation_ref: str) -> dict:
    """The 'next' after the last chunk. Constant, terminal, honest."""
    speak = f"{TERMINAL_SPEAK} {FIXED_SUFFIX}"
    _assert_wrapper_clean(speak, [])
    return _contract(speak, mode, ("continue_on_personal_device",), 0,
                     continuation_ref, "accepted", plan_id, table_version)


# --------------------------------------------------------------------------
# Fixture planner (STAND-IN for S2 — labeled FIXTURE throughout)
#
# Implements the frozen-contract math minimally: credible set from fixture
# listeners, ε(s) = 0.5 − 0.45·s, d* = min clearance over the credible set,
# cover = any non-owner listener credible. S2's real planner implements the
# AssemblyInput/PlannedItem interface above; the assembler never changes.

@dataclass(frozen=True)
class FixtureRow:
    """Mirrors the brief's TableRow field-for-field (named FixtureRow so S1's
    future TableRow never collides)."""
    item_id: str
    sensitivity: float          # 0..1
    clearance: dict             # {person_or_role: depth_int}
    chain: tuple                # (d4, d3, d2, d1) texts; d0 = absorbed
    version: int = FIXTURE_TABLE_VERSION


def _epsilon(sensitivity: float) -> float:
    return 0.5 - 0.45 * sensitivity


def _clearance_for(row: FixtureRow, person: str) -> int:
    if person in row.clearance:
        return row.clearance[person]
    if person == "unknown":
        return row.clearance.get("unknown", 0)
    # Named-but-unlisted listeners are guests of the household.
    return row.clearance.get("role:guest", 0)


class FixturePlanner:
    """Minimal planner over fixture rows. Deterministic. NOT the S2 planner."""

    # Fixture belief: listed listeners are P=0.95 present; the "unknown"
    # pseudo-person is P=0.05 (joins only at ε ≤ 0.05, i.e. sensitivity ≥ 1.0 —
    # mechanism present, dormant in fixture).
    _P_LISTED = 0.95
    _P_UNKNOWN = 0.05

    @classmethod
    def plan(cls, rows: tuple, audience: frozenset, owner: str) -> tuple:
        """-> tuple[PlannedItem], canonical order. Plus (mode, screen_depth)."""
        planned = []
        for row in rows:
            eps = _epsilon(row.sensitivity)
            credible = {p for p in audience if cls._P_LISTED >= eps}
            if cls._P_UNKNOWN >= eps:
                credible.add("unknown")
            if not credible:
                credible = {owner}
            dstar = min(_clearance_for(row, p) for p in credible)
            if dstar > 0:
                text = row.chain[4 - dstar]
                action = "SPEAK"
            else:
                text = ""
                action = "DEFER"  # absorbed (d0): silent digest covers it
            planned.append(PlannedItem(row.item_id, dstar, text, action,
                                       row.version))
        planned.sort(key=lambda p: p.item_id)
        cover = any(p != owner for p in audience)
        mode = "cover" if cover else "open"
        spoken_depths = [p.depth for p in planned if p.action == "SPEAK"]
        screen_depth = min(spoken_depths) if spoken_depths else 0
        return tuple(planned), mode, screen_depth


# --------------------------------------------------------------------------
# Fixture table compiler (STAND-IN for S1 — labeled FIXTURE throughout)

_HEALTH_HINTS = ("checkup", "therapy", "clinic", "prenatal", "doctor",
                 "ob-gyn", "dental", "hospital")
_FIXTURE_HOUSEHOLD = ("ravi", "mom")


def _fmt_min(m: int) -> str:
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{mm:02d} {suffix}"


def _sensitivity_for(title: str, public_title: bool) -> float:
    low = title.lower()
    if any(h in low for h in _HEALTH_HINTS):
        return 0.95
    if public_title:
        return 0.2
    return 0.5


def _chain_for(title: str, location: str, tstr: str,
               sensitivity: float, public_title: bool) -> tuple:
    if sensitivity >= 0.9:
        return (f"{title} at {tstr} at {location}",
                f"doctor's appointment at {tstr}",
                f"an appointment at {tstr}",
                "something on your calendar this afternoon")
    if public_title:
        return (f"{title} at {tstr} at {location}",
                f"{title} at {tstr}",
                title,
                "something on your calendar")
    return (f"{title} at {tstr}",
            f"{title} at {tstr}",
            f"a work block at {tstr}",
            "something on your calendar")


def _clearance_for_block(owner: str, readers: frozenset,
                         public_title: bool) -> dict:
    c = {owner: 4}
    for p in readers:
        c[p] = 4
    for p in _FIXTURE_HOUSEHOLD:
        if p not in c:
            c[p] = 2 if public_title else 0
    c["role:guest"] = 2 if public_title else 0
    c["role:child"] = 1 if public_title else 0
    c["unknown"] = 0
    return c


def tables_for_world(world, owner: str = "priya") -> tuple:
    """Compile a fixture world into FixtureRows. Deterministic.

    `world` is a services/gateway/mcp/fixtures.py FixtureWorld. Canonical
    item_id order. Every string the hot path may speak is produced HERE —
    the assembler only arranges them.
    """
    rows = []
    for b in world.busy:
        tstr = _fmt_min(b.start_min)
        sens = _sensitivity_for(b.title, b.public_title)
        rows.append(FixtureRow(
            item_id=f"busy:{b.start_min}-{b.end_min}",
            sensitivity=sens,
            clearance=_clearance_for_block(owner, b.readers, b.public_title),
            chain=_chain_for(b.title, b.location, tstr, sens, b.public_title)))
    for f in world.flex:
        rows.append(FixtureRow(
            item_id=f"flex:{f.name}",
            sensitivity=0.3,
            clearance={owner: 4, "ravi": 4, "mom": 4,
                       "role:guest": 2, "role:child": 2, "unknown": 0},
            chain=(f.name, f.name, "a flexible task",
                   "something on your list")))
    for i, text in enumerate(world.public_facts):
        rows.append(FixtureRow(
            item_id=f"pub:{i}",
            sensitivity=0.1,
            clearance={owner: 4, "ravi": 4, "mom": 4,
                       "role:guest": 4, "role:child": 4, "unknown": 4},
            chain=(text, text, text, text)))
    rows.sort(key=lambda r: r.item_id)
    return tuple(rows)


def new_plan_id() -> str:
    """Opaque, random, secret-independent. Normalized in paired-world tests."""
    return "pln_" + secrets.token_hex(8)
