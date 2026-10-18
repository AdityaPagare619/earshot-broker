# DESIGN.md — J2 · apps/simulator/ (controlled web host)

Owner: J2 (single-threaded). Type-2 decisions throughout except the MCP wire
contract (Type-1: pinned 2025-11-25, frozen once written).

## Problem
Build the controlled web host: a REAL MCP client speaking to the gateway,
audience-change events, a local output arbiter implementing blueprint §6
(prepare/commit/audience_changed ordering with lease invalidation), and the
walk-in demo path — as an Echo-class experience, honestly labeled as a
simulator. This is the surface every judge watches; it must feel like an Echo,
read in 10 seconds, and never claim what it isn't.

## Architecture

```
apps/simulator/
  mcp_client.py      # real MCP client: initialize/list/call over Streamable HTTP
                     # stdlib only (urllib); pinned protocol 2025-11-25
  arbiter.py         # local output arbiter: prepare/commit/audience_changed
                     # blueprint §6 ordering; epoch-bound segment gate
  audience.py        # audience event source: manual guest toggle + scripted
                     # sensor events; seq nos, freshness TTL; UNKNOWN on stale
  gateway_port.py    # GatewayPort: call_tool() with two backends —
                     #   mcp (default, real client -> gateway URL from env)
                     #   kernel_direct (real kernel in-process, LABELED demo mode)
  host.py            # controlled web host: stdlib http.server; Echo-styled UI;
                     # JSON API for UI; drives client + arbiter + audience
  ui/index.html      # single self-contained page: Echo device, room strip,
                     # phone panel, dev drawer, honest labels
  demo.py            # scripted walk-in scenario runner (real path, not theater)
  tests/             # test_arbiter.py, test_mcp_client.py, test_walkin.py,
                     # protocol_conformance_harness.py (test-only mini MCP server)
```

**Data flow (the walk-in beat):** UI voice request → `GatewayPort.call_tool(
"prepare_day_brief", ...)` → public projection returned → arbiter
`prepare(candidate)` mints epoch-bound grant → host releases **segments**;
each segment re-validates via `commit(grant)` under the serialization lock →
audience event ("Mom enters") → arbiter `audience_changed`: **stop output
first**, epoch++, invalidate pending grants, task state kept → speaker shows
discreet "moved to your phone" (strict fixture: no count, no buzz) → phone
panel quietly syncs exact plan (demo unlock = authenticated session) →
`resolve_day_change` adapts using private constraints → private approval.

## Decisions

1. **stdlib MCP client, no SDK.** Full control of `MCP-Protocol-Version`,
   session headers, SSE framing, `notifications/initialized`. No dependency pin
   risk across seats (J3 pins the server side), no httpx-class env bugs. The
   client is protocol-tested against a conformance harness in tests/.
2. **GatewayPort with two backends, active backend always displayed.** `mcp`
   is the primary citizen (real HTTP to the gateway URL from env/config);
   `kernel_direct` is the labeled local-demo fallback that exercises the REAL
   kernel in-process — never a mock of the security boundary. One env var
   (`EARSHOT_GATEWAY_URL`) switches; J3's server plugs in with zero code change.
3. **Arbiter owns the stop path, synchronously.** `audience_changed` stops
   output before touching versions — no awaits, no LLM, no network in the stop
   path (blueprint §11.2). A single `threading.Lock` serializes commit vs
   invalidation (the linearization point J10 will probe). Every emitted segment
   carries `(epoch, seq, digest)`; the renderer rejects older-epoch segments
   even if they arrive late (blueprint §6: don't rely on the server refusing).
4. **Segments, not speeches.** The speaker releases small approved segments;
   each segment is a separate commit check. This is what makes the walk-in
   interruption real: revocation lands between segments, not "after the TTS
   finishes." Browser speechSynthesis may voice segments for feel — labeled
   presentation only, never the enforcement (§11.3).
5. **Single self-contained page, no framework.** One HTML file, inline CSS/JS.
   One-command run (`python3 host.py`), zero install, reproducible — dossier
   §13.3. The dense dashboard lives ONLY in the dev drawer (§4.4); the customer
   surface is discreet: light ring, transcript, room pills, phone panel.
6. **Honest labels as UI elements, not footnotes.** Persistent banner:
   "Independent simulator — not a live Alexa+ device · Profile B: controlled
   host". Audience events labeled "simulated sensor / manual". Strict fixture
   shows quiet sync; relaxed fixture shows the nudge — the difference is the
   lesson.

## Rejected alternatives

1. **React/Next.js frontend.** Rejected: build toolchain, node_modules, and a
   second language runtime for a demo host the dossier demands be one-command
   and reproducible. A crafted single page beats a generic framework scaffold
   (no AI-slop dashboard).
2. **MCP Python SDK for the client.** Rejected: cross-seat pin risk (J3 owns
   server deps; two SDKs must negotiate one protocol revision — blueprint §1
   warns exactly against this), plus observed httpx env bugs in the prior wave.
   stdlib gives exact wire control and zero install.
3. **A `DemoGatewayStub` implementing the 4 tools with canned answers.**
   Rejected: a stub as the demo backbone is theater. The security boundary is
   exercised against the real kernel; the wire path is exercised against a
   protocol harness. No canned "AI" anywhere.

## Frozen contracts
- MCP wire: 2025-11-25; `initialize` → `notifications/initialized` →
  `tools/list` → `tools/call`; `MCP-Protocol-Version` header on all
  post-init requests; session via response `Mcp-Session-Id`.
- Tool surface: `API_CONTRACTS.json` (4 tools, input schemas as specified).
- Arbiter: `prepare(candidate)->grant | None`; `commit(grant)->segment |
  None`; `audience_changed(event)` → stops output, bumps epoch, invalidates.
  Segment = `(epoch, seq, digest, text)`. Late/older-epoch segments rejected
  locally, always.
- Audience event: `{seq, observed_at, received_at, listeners, source:
  "manual"|"scripted", zone}`; stale (>TTL) or seq-regressed events →
  UNKNOWN, never upgrade.

## Failure modes (exercised, not just coded)
- Audience event arrives mid-segment → output stops before versions bump.
- Commit races invalidation → lock orders them; loser denies.
- Late segment from old epoch arrives after stop → rejected by epoch check.
- Sensor heartbeat stops → evidence stale → UNKNOWN → restricted output.
- Gateway unreachable → UI shows degraded state, kernel_direct labeled
  fallback; never silently swaps backends.
- Guest asks for private continuation → generic "Unavailable", no oracle.

## Honest boundaries
- Simulated presence (manual toggle + scripted events), labeled.
- No real Echo/Alexa+ device; no official simulator; no certification claim.
- Browser TTS is a demo voice, not a real-time cutoff; measured stop
  latency is event-to-arbiter, and physical-entry latency is unmeasured
  (dossier §11.3 — stated on screen in the dev drawer).
- Kernel-direct mode is local-demo only; the MCP path is the real
  integration surface.

## Pre-mortem (why this seat fails)
1. The walk-in "works" because the script and the arbiter share a thread and
   the race never actually happens → guard: `test_arbiter.py` forces
   commit-vs-invalidation interleavings from two threads; the UI demo uses
   the same code path as the tests.
2. The Echo feel reads as a chatbot skin → guard: light-ring states,
   segment-paced speech, room pills, and the 10-second test ("Alexa plans
   your day without telling the room why") reviewed against the UI, not
   described in a doc.
3. J3's server arrives with a different session/auth behavior and my client
   breaks at integration → guard: client strictly follows the pinned spec
   (verified URLs in SOURCE_AUDIT spirit), auth headers configurable, and
   the failure surfaces as a visible degraded state, never silent.

Kill condition: arbiter race tests red after ~3h of debugging → report
BLOCKED with the mechanism; do not weaken the ordering to make tests pass.
