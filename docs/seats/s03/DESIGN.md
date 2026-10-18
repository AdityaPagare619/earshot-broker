# DESIGN — S3: Constant Shape (Seam 3)

**Seat:** S3 · **Date:** 18 Oct 2026 · **Status:** written before code, per protocol.

## D1 — New module `services/gateway/mcp/shape.py`: the assembler is a pure function
All constant-shape logic lives in one stdlib-only module: `assemble()`,
`probe_response()`, `Chunker`, and the fixture planner. Pure functions, frozen
dataclass inputs. The gateway (broker) and the simulator (gateway_port) BOTH
import it — one assembly implementation, two call sites. No forked logic.

**Why:** the seam must be single-sourced. Two assemblers (one for the wire, one
for the UI) would drift, and drift is where shape leaks are born.

## D2 — REPLACE `public_facts`, don't layer alongside it
Tool results become the sealed-speech response contract:
`speak`, `speak_policy="verbatim_no_elaboration"`, `mode`, `followups`,
`screen_depth`, `request_ref`, `request_state`, `_meta{plan_id, table_version}`.
`content[0].text` becomes the speak text (verbatim), not a JSON dump.
`API_CONTRACTS.json` outputSchemas are updated to match; J3's tests are updated
to assert the new shape (intent preserved: auth, idempotency, C1–C5, error shapes).

**Rejected:** layering the contract next to `public_facts`. The variable-length
list IS the leak; keeping it would be security theater with better stationery.

## D3 — `request_ref` IS the continuation ref (no rename)
The contract table says `continuation_ref`; the wire already has an opaque,
owner-bound `request_ref` (the kernel receipt). Renaming would churn the server's
`latest_ref` wiring, every test, and the simulator for zero security gain.
Documented: `request_ref` is the opaque owner-bound continuation reference.

## D4 — Fixed suffix in BOTH modes, always
"The rest of your day is on your phone." appended to every brief-family speak
text — cover AND open, withheld-something AND withheld-nothing. Rationale: even
in open mode, quarantined items may be withheld (Seam 1), so the suffix must not
be a signal in either mode. Phone digest ALWAYS queued silently (outbox), in both
modes — the buzz carries no signal because it never varies.

**Rejected:** suffix-only-in-cover. Within cover mode the suffix must not signal
withholding; across modes the mode field already differs (the room knows who's
there — mode is not secret), so suffixing both modes costs nothing and buys
uniformity.

## D5 — The assembler takes planned depths, never raw text
Input: `PlannedItem(item_id, depth:int, text:str, action, table_version)` —
the planner (S2's, or my fixture) puts ONLY planned-depth rendition text in.
The assembler emits exactly what it's given, in canonical item_id order, with no
counts, no ordinals, no depths, no sensitivities, no item IDs in the output.
"Nothing above planned depth in any field" is structural: the assembler has no
code path that can reach above-depth text, and a test asserts every emitted
string is a member of the input set.

**Rejected:** letting the assembler re-derive depths from text (would require the
assembler to understand content — a second planner, and a leak vector).

## D6 — Fixture planner, frozen interface, S2 replaces it
`FixturePlanner` implements the frozen-contract math minimally: credible set from
fixture listeners, ε(s)=0.5−0.45·s, d*=min clearance over credible set,
cover = any non-owner listener credible. It consumes `TableRow`s built by
`tables_for_world()` (fixture compiler: BusyBlock → chain + clearance +
sensitivity). The assembler's input types are frozen; S2's real planner
implements the same interface. The fixture is labeled FIXTURE everywhere.

## D7 — Chunking: `continuation_ref` re-enters `prepare_day_brief`
`prepare_day_brief` gains OPTIONAL `continuation_ref` (additive inputSchema
change, validated like `request_ref`). Semantics: "give me the next chunk of
this brief." Broker holds chunk state keyed by receipt (opaque, owner-bound);
each "next" re-runs the fixture planner on remaining items (belief re-read is
structural — the broker rebuilds the world per call). Chunk size 2. `followups`
is `["next", "continue_on_personal_device"]` until the last chunk, then
`["continue_on_personal_device"]`. Idempotent replay of a "next" returns the
same chunk (idem check precedes state advance).

**Rejected:** a separate `next_chunk` tool. Six tools is the surface budget;
chunking is a mode of the brief, not a seventh verb.

## D8 — Probe resistance without a probe tool
`probe_response(query)` returns the identical response contract for ANY query
text: speak = "I'll put anything about that on your phone." + fixed suffix,
mode=cover, same shape. Unit tests assert byte-identity across existing-item /
nonexistent-item / secret-topic queries. The simulator's `utter()` probe branch
routes through it. A dedicated probe tool is future surface (S4/S6) — the
STYLE (any probe-shaped query → identical response) is covered now.

## D9 — Paired-world suite: 7 tests, 1 negative control
Extend `test_paired_world.py` (new file `test_constant_shape.py` to avoid
churn in J3's file): prenatal↔therapy, strict↔empty, mom↔mom+guest (proves
listener counts don't leak), open↔cover DIFFERS (anti-vacuity), negative
control (mislabeled-public secret → bodies differ AND contain the token),
no-secret-tokens sweep, ref/plan_id shape-constant. Normalize `request_ref`
AND `_meta.earshot/plan_id` (both random-by-design, secret-independent).

## D10 — Simulator UI speaks the contract
`gateway_port.kernel_direct` returns the response contract via the shared
assembler. `host.utter()` uses `res["speak"]`; briefing segments come from the
speak text (sentence-split), still arbiter-gated per segment. The leaky
FIXTURES briefing lines ("3 flexible tasks", "One private item") are deleted;
`fixture_mode` config remains for nudge behavior but both modes are now
constant-shape. Probe branch → `probe_response()`.

## Rejected alternatives (summary)
- R1: Layering contract beside `public_facts` → preserves the leak. Killed.
- R2: Renaming `request_ref` → churn without security gain. Killed.
- R3: Suffix only in cover mode → cross-mode signal for zero benefit. Killed.
- R4: Separate `next_chunk` tool → seventh verb, surface budget exceeded. Killed.
- R5: Assembler deriving depths from text → second planner, leak vector. Killed.
- R6: Building S2's planner here → lane violation; fixture + frozen interface instead.

## Kill conditions (what would invalidate this design)
- K1: A paired-world test fails after the fixture planner is replaced by S2's
  real planner → the assembler interface leaked planner internals; redesign the
  interface, not the tests.
- K2: Any wire field is found to vary with secret content (fuzz the worlds) →
  the field moves behind the seam or dies.
- K3: The "next" flow is unusable in the 3-minute demo → chunking becomes
  UI-only (simulator), gateway keeps single-shot; the seam doesn't depend on it.

## Interface registry (for other seats)
- S2: implement `plan(tables, belief) -> AssemblyInput`-shaped output; see
  `shape.py::AssemblyInput` / `PlannedItem` (frozen). Replace `FixturePlanner`.
- S4: `room` / `keep_secret` tools return `shape.assemble(...)` output. Reuse,
  don't rebuild.
- S5: `test_constant_shape.py` is yours to extend with the adversarial listener;
  the paired-world harness (`_paired_bodies`) is reusable.
- S6: `tables_for_world()` is the fixture compiler; your pack work replaces the
  fixture chains/lexicons with pack data. `table_version` is currently a fixture
  constant — your compiler should use a monotonic epoch counter (NOT a content
  hash; content-derived versions are metadata leaks).

## Post-merge amendments (18 Oct ~18:40–19:00 IST — S1/S2/S4/S5/S6 all landed)

The wave moved while S3 built. The design adapted; the decisions held.

**A1 — S2 landed: the fixture planner is DELETED, not replaced.** S2's
`plan_briefing` (minimax + exposure budgets + log-odds fusion) is now the
single planner. `shape.planned_from_briefing` adapts `BriefingPlan` →
`(planned, mode, screen_depth)`; rendition text comes from the row's chain at
the planned depth. K1 resolved empirically: all 9 paired-world tests pass
against the REAL planner, byte-identical. `shape.py` itself imports NOTHING
(stdlib-only, zero dependencies) — the S2 integration lives in `broker.py`.

**A2 — S4 landed: `room`/`keep_secret` return the sealed-speech contract.**
Uniform wire shape is Seam 3's mandate, so S4's two tools were converted
(`speak` "Noted." / "Noted. I'll keep that private from the people you
named.") and S4's tests updated. The declaration log feeds S2's fusion on
the live path (`_signals_for`: present→DECLARE_PRESENT, owner-absent→ALONE,
other-absent→DECLARE_ABSENT). The day-card resource also returns the
contract (F1 count-leak closed on the resource path).

**A3 — Chunking runs over SPOKEN items only.** Absorbed/deferred rows are
invisible and must not shift chunk boundaries — otherwise a hidden row's
presence would be measurable in the turn structure (found while writing the
strict↔empty paired test; fixed before it could ship).

**A4 — Exposure budgets are chunk-aware.** S2's pending exposures are
committed AFTER speaking, only for items ACTUALLY spoken in the chunk
(`secret == item_id` attribution). Unchunked items consume no budget yet.

**A5 — `gateway_port.kernel_direct` is the REAL in-process Broker.**
Better than D10's plan: zero second implementation to drift. The simulator
host speaks `res["speak"]` verbatim, sentence-split into arbiter-gated
segments; probe-shaped utterances never reach a data path (fixture regex,
labeled; the RESPONSE is the guarantee). Audience changes sync the fixture
sensing channel before every tool call; a new utterance resumes the arbiter
for new grants (designed mechanism, not autoplay).

**A6 — keep_secret applies via the min-only overlay BEFORE planning.**
`effective_clearance` is applied per row in `_hotlane_rows`, so a TIGHTEN
edge drops clearance on the very next brief.

**A7 — S6's ShapePort noted, not chased.** S6 shipped `integration/ports.py`
with a `FixtureShape` stand-in behind their own port design. `shape.py`'s
`AssemblyInput`/`PlannedItem`/`planned_from_briefing` is the frozen S3
interface (this doc); converging the two ports is a parent-level
integration step. The EN fixture strings in `shape.py` are labeled
constants; the pack (S6) owns localization.

## Final interface registry (as merged)
- S1 → S3: `tables_for_world()` is the fixture Disclosure Table compiler;
  S1's real compiler produces `TableRow`s the broker maps the same way.
- S2 → S3: `planned_from_briefing(plan, rows_by_id)` — the ONLY adapter.
- S3 → S4/S5/S6: `assemble(AssemblyInput) -> dict` (the contract),
  `probe_speak() -> str`, `take_chunk()`, `terminal_assembly()`.
- S4 → S3: declaration log → `_signals_for` → S2 fusion (live path).
