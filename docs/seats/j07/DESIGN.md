# DESIGN.md — J7: ask-amazon.md + trace-harness + commercial roadmap

**Owner:** J7 (single-threaded). **Type:** Type-2 (docs + test tooling; reversible),
except the harness's *wire protocol assertions* which are Type-1-adjacent — they
must match the frozen MCP 2025-11-25 contract, verified against the spec I read
today, not the dossier's summary.

## Problem

Two gaps block the commercial story: (1) §15.4's product feedback is a bullet
list with no trade framing — Amazon can't act on a wishlist; (2) §12's trace
harness is a paragraph — an open-source contribution that doesn't exist can't
earn distribution or mini-challenge consideration. I build both, plus the
beyond-hackathon roadmap that names who pays.

## Decisions

### D1. ask-amazon.md is a partnership proposal, not a support ticket
Structure per ask: **The request** (concrete semantics, not "clarify X") →
**Who it unblocks** (partner class, not just EARSHOT) → **What we offer in
return** (the trade) → **Evidence** (source-audit ID). The six §15.4 asks are
reordered by ecosystem leverage: (1) certification guidance for intentional
non-disclosure — unblocks every privacy add-on; (2) signed requester/audience
context; (3) ephemeral no-memory channel with enforcement semantics;
(4) output-lease validation at the host renderer; (5) personal-channel
continuation; (6) elicitation/version/scope clarifications. Each framed as a
*request with proposed semantics*, never an invented API.

### D2. The trace harness speaks MCP over Streamable HTTP
`packages/trace-harness/` tests a *target server's public trace*, not the
kernel's internals. Architecture:
- `worlds.py` — paired synthetic world fixtures (no-secret vs secret variants:
  no private event / one private event; prenatal vs therapy vs oncology titles;
  reordered records; source error vs no-match).
- `adapters.py` — two adapters behind one interface: `MCPHttpAdapter` (stdlib
  `http.client`, Streamable HTTP: initialize → session header → tools/call,
  per spec §session-management verified today) and `KernelDirectAdapter`
  (in-process, self-test only, labeled as such).
- `capture.py` — runs the same initialized request sequence against both
  worlds; captures text, structured content, resources, metadata (status,
  byte size, timing bucket).
- `normalize.py` — replaces independent random IDs (receipts, session IDs)
  with stable tokens; buckets timestamps. Per dossier §14.3: random refs must
  be *independent*, not identical — normalization asserts shape-independence,
  never byte-equality of secrets-derived randomness.
- `differ.py` — difference taxonomy: TEXT / STRUCTURED / METADATA /
  STATUS / ABSENT; verdict PASS (no secret-dependent difference in the public
  trace) or FAIL naming the channel. Reports to `evidence/`.
- `adversarial.py` — reference-replay fixtures: replay another tenant's
  receipt, cross-tenant `open_private`, stale-lease redeem, revoked-receipt
  redeem — expecting uniform `PermissionError('Unavailable')` (no existence
  oracle).
- A minimal fixture MCP server (`fixtureserver.py`, stdlib only) implementing
  the 4 proposed tools against the real kernel, used *only* by the harness's
  own tests to prove the HTTP path end-to-end. Labeled fixture, never presented
  as the product server (J3 owns that).

### D3. The roadmap names beachheads, not studies
Beyond-hackathon roadmap (inside ask-amazon.md): Phase 0 validation (paired
developer interviews, not "user studies" vapor — named questions), Phase 1
pilot (Alexa+ add-on store submission track + certification discussion as the
gating conversation), Phase 2 partner (named Amazon teams: Alexa+ add-ons
platform, Alexa Smart Home — as *conversation targets*, not commitments).
Commercial vehicle options compared: add-on store listing (distribution,
Amazon's cut), AWS reference architecture (the real bill: Bedrock bounded
planner + KMS + SQS + DynamoDB, cost sketch labeled estimate), open-source
harness as the standards play. Unit economics: per-request cost decomposed
from the §13.3-style latency allocation, labeled illustrative.

### D4. Honest-boundary labels are part of the deliverable, not an appendix
Every doc and the harness README carry: what was actually run (kernel 24
tests, harness N tests, fixture server), what was NOT (no real device, no
certification, no production security, no AWS spend — ₹0 budget). The harness
never claims to prove security; it *detects public-trace variance*, a
necessary-but-insufficient condition.

## Rejected alternatives (with reasons)

1. **Kernel-in-process-only harness.** Rejected: it tests the reference
   implementation's internals, not the attack surface. The privacy property
   lives or dies on the *wire trace* — what a room-facing host actually
   receives. An in-process harness is a unit-test suite in a trench coat; the
   verdict (R2) kills it.
2. **Byte-for-byte response comparison.** Rejected: dossier §14.3 is explicit —
   byte-for-byte invariance is only valid for deterministic projections.
   Receipts and session IDs are *supposed* to be independent random values;
   demanding equality would fail correct implementations and pass broken ones
   that reuse IDs (which is itself a vulnerability — ID reuse across worlds
   would be flagged by the *independence* check). Normalize-then-compare on
   shape, plus an explicit randomness-independence assertion.
3. **Harness as an MCP SDK-dependent client package.** Rejected: stdlib only.
   ₹0 budget, zero install friction, and the artifact must be adoptable by any
   MCP server builder in one file-copy. A pip dependency (even `mcp`) would
   tie the *test tool* to the thing being tested and add version-pinning
   failure modes. The Streamable HTTP client is ~60 lines of `http.client` —
   small enough to audit, which is itself a selling point.

## Frozen contracts (I consume, not change)

- MCP 2025-11-25 Streamable HTTP: POST JSON-RPC, `Accept:
  application/json, text/event-stream`, `Mcp-Session-Id` header round-trip,
  `MCP-Protocol-Version` header (verified from the spec today).
- Kernel API: `accept / open_private / revoke / room_projection /
  public_projection / prepare / redeem` (frozen in `packages/kernel/`).
- The 4 proposed tools in `API_CONTRACTS.json` (proposed, not all
  implemented — the fixture server implements the subset the harness needs:
  `prepare_day_brief`, `continue_on_personal_device`, `withdraw_request`).

## Failure modes

- **F1:** Target server's session handling differs (no `Mcp-Session-Id`
  returned — legal per spec, session optional). Mitigation: adapter works
  sessionless; session ID treated as optional.
- **F2:** Timing-channel assertions flake on loaded machines. Mitigation:
  timing is *bucketed* (order-of-magnitude), never asserted exactly; the
  harness reports timing distributions, and the verdict only fails on
  *systematic* secret-dependent skew across N runs (documented as statistical,
  not a proof — the kernel itself notes it has no constant-time transport).
- **F3:** A target that echoes secrets in error messages fails LOUD — the
  differ's TEXT channel catches it, and the report quotes the leak. That's the
  harness working as intended.
- **F4:** Someone runs the harness against a production server with real
  data. Mitigation: worlds are synthetic-only by construction; README states
  it; the fixture server refuses non-`tenant` prefixed tenants... (kept
  simple: synthetic fixtures only, documented).

## Pre-mortem (one year later, this failed)

1. The harness became a checkbox ("we ran the harness, we're private") and a
   partner shipped a timing leak it couldn't detect — because I oversold it.
   Guard: D4 — the README's first section after the title is "What this does
   NOT prove."
2. ask-amazon.md read as a demand letter and got filed under "enthusiastic
   builder." Guard: D1 — every ask leads with the partner class it unblocks
   and the trade we offer; the tone is "here's a conformance tool you can
   use," not "give us APIs."
3. The fixture server got mistaken for the product server in a demo.
   Guard: it's named `fixtureserver`, lives under `trace-harness/tests/`,
   and its docstring says so in the first line.

## Kill conditions (dated)

- If the HTTP adapter cannot complete initialize→tools/call against the
  fixture server by end of build session → report BLOCKED with mechanism, do
  not fake the wire path.
- If paired-world runs show nondeterminism I can't attribute (not timing,
  not randomness) → the differ is unsound; kill the verdict feature, keep the
  capture/normalize tooling, report honestly.
