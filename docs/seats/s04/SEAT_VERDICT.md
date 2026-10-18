# SEAT_VERDICT.md — S4: Secrecy Graph & Monotone Gate

**Lens:** Law 1 (every secret has a non-audience) + Law 6 (the model may make you more
private, never less). Signature question: *"Show me the choke point. If I can mint an
edge without passing your gate, your invariant is a comment."*
**Confidence: 75%** the design below is the right shape; 60% the S1/S2 interface
lands without a reconciliation round (parallel-seat risk, named in §5).

## What's strong (keep)

1. **The frozen contract is exactly right.** `SecrecyEdge(type, target, until,
   provenance, confidence, direction)` with `LOOSEN requires confirmed` is a
   capability bound expressed as data. My job is to make it executable, not to
   redesign it.
2. **The monotone rule is the cheapest strong invariant in the architecture.**
   `accept = (TIGHTEN ∧ conf ≥ 0.6) ∨ confirmed` — one line, total mediation,
   property-testable. This is the seat where "mechanism over policy" is literal.
3. **The broker's auth posture composes.** Identity comes from the verified
   credential (R1 closed); my tools inherit that — `keep_secret`/`room` never take
   identity arguments.

## What breaks (brutal, specific)

1. **Nothing exists.** Zero secrecy-graph code in the repo. S1's table compiler and
   S2's hot lane both need my interface, and it isn't written. I am a load-bearing
   dependency for two parallel seats with no contract yet — the #1 risk of this
   seat is interface, not algorithm.
2. **The gate is theater unless it's total.** The obvious naive build — a
   `check()` function called by honest code paths — dies the day someone adds a
   "fast path" for `keep_secret` that writes clearance directly. The hot-patch
   requirement ("clearance 0 immediately") is exactly the temptation that creates
   the bypass. The gate must be a **choke point in the type flow**, not a function
   people remember to call.
3. **The LLM-shaped interface is the attack surface.** Fixture backend today, real
   model tomorrow. A future model returning `LOOSEN, conf=0.99, provenance=inferred`
   must die at the gate — and the interface must make bypassing *structurally*
   awkward, not just documented-against. Python gives me convention + tests, not
   compiler enforcement; I will label that honestly.
4. **`keep_secret` parsing is the weakest link.** One spoken sentence →
   (non-audience, topic). A deterministic parser will misfire on real phrasing
   ("don't tell anyone about…", "keep this between us"). The failure mode isn't a
   crash — it's silent under-tightening, which is a privacy failure wearing a
   success message.
5. **`room` is my verb, S2's state.** I own the declaration; S2 owns belief fusion.
   If S2's fusion ignores my trust classes, "I'm alone" becomes a loosening oracle
   no matter what I do. The asymmetric-trust table must be encoded at *ingest*
   (my side) as data S2 consumes — `can_remove: bool` on the declaration — so a
   fusion that ignores it is visibly, testably wrong.

## Pre-mortem (3 ways this seat fails)

- **P1 — Interface mismatch with S1/S2.** Their compiler expects a different
  clearance shape than my overlay provides → integration break at merge.
  *Mitigation:* my `effective_clearance()` returns exactly the frozen
  `TableRow.clearance` shape (`{person_or_role: depth_int}`); the interface
  section of DESIGN.md is written as a contract, reviewed as one.
- **P2 — Gate bypass via fast path.** Someone (including future me) adds a direct
  clearance write for latency. *Mitigation:* `EdgeStore` accepts **only
  proposals**; it applies the gate internally and returns accepted edges. There
  is no public API that writes an edge. A test asserts the store has no
  edge-writing path that skips the gate.
- **P3 — Parser misfire.** `keep_secret` under-tightens on unhandled phrasing.
  *Mitigation:* unparseable target → conservative default
  (`hidden_from(role:guest), hidden_from(role:child)`) + room-safe message
  directing detailed control to the phone. Tightening is always safe; the cost
  is annoyance, never exposure. Ambiguous parses also enqueue a phone
  confirm card (tighten now, refine later).

## Verdict

**BUILD, with the choke-point design.** The mechanism is one line; the engineering
is all in total mediation and the S1/S2 interface contract. Kill conditions for
this seat: (a) any test shows a clearance *increase* from an unconfirmed input —
  kill the build, not the test; (b) the gate gains a second entry point —
  revert, no exceptions; (c) S1/S2 need a different clearance shape — reconcile
  the interface doc first, code second.
