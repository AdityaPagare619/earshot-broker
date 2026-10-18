# apps/simulator — EARSHOT controlled web host (Profile B)

**Independent simulator — not a live Alexa+ device.** The Echo-class web
experience for the walk-in demo: a real MCP client, audience-change events,
and a local output arbiter implementing blueprint §6 (prepare / commit /
audience_changed ordering with lease invalidation).

## Run it (one command, zero install)

```bash
earshot-sim --port 8734
# open http://127.0.0.1:8734/
# (or: python3 host.py --port 8734 from this directory)
```

Stdlib only. No dependencies, no build step.

## What it is

| File | Job |
|---|---|
| `mcp_client.py` | Real MCP client: initialize / list / call over Streamable HTTP, pinned 2025-11-25, session headers, SSE framing. |
| `arbiter.py` | Local output arbiter: epoch-bound grants, commit-vs-invalidation serialized on one lock, stop-output-first interrupt path, late-segment rejection. |
| `audience.py` | Audience events: manual guest-mode toggle + scripted sensor events (labeled simulated), seq nos, freshness TTL, UNKNOWN on stale. |
| `gateway_port.py` | One `call_tool()` interface, two backends: `mcp` (real HTTP to `EARSHOT_GATEWAY_URL`) and `kernel_direct` (real kernel in-process, labeled). Active backend always shown in the UI. |
| `host.py` | The web host: serves the UI, drives briefing segments through the arbiter, routes utterances (labeled demo routing, not NLU). |
| `ui/index.html` | Single self-contained page: Echo device with light-ring states, voice transcript, discreet room strip, phone panel, dev evidence drawer. |

## The walk-in demo (the evangelist beat)

1. Say **"help me organize my afternoon"** → `prepare_day_brief` → the speaker
   briefs public segments under per-segment leases.
2. Press **"Mom enters"** (or run the scripted demo) mid-briefing → the arbiter
   stops output first, advances the epoch, invalidates pending grants.
3. The speaker shows "Paused — moved to your phone." — no secret content,
   no count in the strict fixture.
4. Unlock the phone panel → the exact plan is there; nothing was re-entered.
5. Say **"make room for a twenty-minute call"** → `resolve_day_change` adapts
   the sealed plan using the private 15:40 commitment without naming it.

Try the strict/relaxed fixture toggle to see the existence lesson: strict syncs
the phone silently (no buzz, no badge); relaxed permits the "one private item"
nudge.

## Tests

```bash
cd apps/simulator/tests
python3 test_mcp_client.py   # 10: protocol conformance vs a test harness
python3 test_arbiter.py      # 12: ordering, races, invalidation, UNKNOWN
python3 test_walkin.py       # 7: end-to-end walk-in on the real path
python3 test_gateway_port.py # 4: both backends, auth on personal surface
```

35/35 green. Evidence (test runs, measured latencies, walk-in trace):
`evidence/simulator-j02/`.

Measured locally: `tools/call` p50 1.1ms / p95 1.3ms (loopback; network not
included) against the 500ms QuickStart budget.

## Honest boundaries (also on screen, permanently)

- Presence is simulated (manual toggle + scripted events). No camera, no face ID.
- Browser TTS is a demo voice, never the enforcement mechanism.
- `kernel_direct` is the labeled local-demo backend; the MCP path is the real
  integration surface (set `EARSHOT_GATEWAY_URL` when J3's server lands).
- The walk-in stops *our* renderer. It does not claim to stop a real Alexa.
- Phone unlock is a demo stand-in for owner authentication; the real auth
  boundary belongs server-side (see J6 finding R1).
