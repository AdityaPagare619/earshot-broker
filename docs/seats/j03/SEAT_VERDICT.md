# SEAT_VERDICT.md — J3: Sr Solutions Architect, Alexa (MCP/protocol)

**Lens:** Technical Implementation. Signature question: *"Did you read the spec?
500ms round trip? auth checklist?"*
**Verdict on current state: CONDITIONAL PASS — strong foundation, three traps
that would fail my review if built naively.**

## What's strong (keep)

1. **The kernel is real.** 24/24 tests pass (`python3 test_kernel.py`, 0.003s).
   Label join semantics, sealed capsules, epoch-bound leases, owner-bound
   `open_private` — all stdlib, all testable. This is the right foundation.
2. **The dossier's protocol section is unusually honest.** It pins MCP 2025-11-25
   deliberately, admits the spec index redirects to 2026-07-28, and warns that
   latest SDKs are not automatically Alexa-compatible (§10.3). Most teams would
   have missed this.
3. **Contracts are well-bounded.** 4 task-oriented tools, `additionalProperties:
   false` everywhere, bounded strings/arrays, identity explicitly NOT a tool
   argument. The security note is correct.

## What would fail in my review (brutal, specific)

1. **THE SDK TRAP (would-fail #1).** The only MCP SDK on this box
   (`~/workspace/amazon-hackathon/resources/mcp-python-sdk`, installed editable)
   has `LATEST_PROTOCOL_VERSION = 2026-07-28` and its modern inbound ladder
   supports **only** `2026-07-28` (`MODERN_PROTOCOL_VERSIONS = {'2026-07-28'}`).
   Anyone who reaches for `pip install mcp` / `from mcp.server import ...`
   builds a server that negotiates the wrong protocol — silently
   non-compliant with the pinned 2025-11-25 and the Alexa-compatibility
   requirement. **My build uses no SDK.** Hand-rolled stdlib Streamable HTTP,
   exact 2025-11-25 wire behavior, verified against the spec text I read myself.
2. **Auth is the gaping hole.** The dossier describes the OAuth 2.1 + PKCE
   production profile (§10.4) but the repo has no auth at all. A server with no
   auth that binds owner from tool arguments would be a security failure. My
   build: dev bearer-token scheme binding (tenant, owner) server-side, **loudly
   labeled non-production**; production OAuth explicitly out of scope.
3. **Latency theater risk.** "0.006ms kernel time" style numbers would be
   meaningless. The dossier demands client-observed round trips (§13.1,
   decision #64). My evidence measures the full HTTP round trip from a real
   client, p50/p95/p99, N=200, against the 500ms budget.
4. **Wire-level leakage.** Kernel unit tests don't catch response-shape leaks:
   `request_ref` randomness, key order, timing, error strings, `_meta`.
   My paired-world test runs at the HTTP layer and compares full response
   bodies (modulo the opaque ref) across secret-swapped worlds.
5. **Error messages are a disclosure surface** (dossier §5.1). Every error path
   gets a test asserting no private values leak — including the
   unknown-vs-forbidden reference indistinguishability rule.

## Confidence: 75/100

The protocol surface is small and fully specified; the kernel is proven; the
traps are named. The remaining 25 is integration risk with other seats'
surfaces (J2's simulator client, J5's personal API) — mitigated by building
against the frozen contracts, never waiting.

## What I will not claim

No production auth, no TLS (localhost-only), no real Alexa device, no
certification, in-memory state (restart loses sessions), fixture data only.
Every number traces to `evidence/`.
