# EARSHOT MCP gateway (J3)

Real MCP server — **Streamable HTTP, MCP spec 2025-11-25 pinned** — exposing the
4 sealed-task tools against the real kernel. Stdlib only, zero dependencies.

## Run

```bash
# from the repo root
python3 services/gateway/mcp/server.py --port 8000
```

Dev bearer tokens print to stderr at startup (non-production; restart reseeds).
Fixture principals: `priya` (owner, house-a), `ravi` (member, house-a),
`meera` (owner, house-b). To pin known tokens for integration:

```bash
EARSHOT_DEV_TOKENS='{"tok123": ["house-a", "priya"]}' python3 services/gateway/mcp/server.py
```

## Wire contract (frozen)

- `POST /mcp` — the single MCP endpoint. `GET`/`DELETE` → 405 (spec-legal).
- `Authorization: Bearer <dev-token>` required on **every** request → 401 otherwise.
- `initialize` negotiates `2025-11-25` (a newer client version negotiates down).
- `MCP-Session-Id` assigned at initialize; required afterwards (400 missing,
  404 unknown/expired after 30 min idle).
- `MCP-Protocol-Version` must equal `2025-11-25` on later requests → 400.
- `Origin`, when present, must be localhost → 403 (DNS-rebinding protection).
- Rate limit: 100 req/min per credential → 429.
- Tools: `prepare_day_brief`, `resolve_day_change`, `continue_on_personal_device`,
  `withdraw_request` — schemas verbatim from `packages/contracts/API_CONTRACTS.json`.
- Resources: `ui://earshot/day-card` (public facts only, latest brief in session).
- Identity is **never** a tool argument: (tenant, owner) binds from the token.
  Unknown vs forbidden `request_ref` → identical `-32603 "Unavailable"`.

## For J2's simulator client

Point at `http://127.0.0.1:8000/mcp`, send `Authorization: Bearer <token>` on
every request including `initialize`, then the standard flow:
`initialize` → `notifications/initialized` → `tools/list` → `tools/call`.
The token for the demo owner is printed at server startup, or pin one via
`EARSHOT_DEV_TOKENS` (above) so both sides share it without scraping logs.

## Tests

```bash
cd services/gateway/mcp/tests
python3 test_protocol.py   # 25: spec compliance, sessions, auth, limits
python3 test_tools.py      # 19: tool behavior, validation, J6-R1 regression
python3 test_paired_world.py  # 5: wire-level counterfactual invariance
python3 test_latency.py    # 1:  N=200 client-measured round trips -> evidence/latency.json
```

Kernel tests (untouched): `cd packages/kernel && python3 test_kernel.py` → 24/24.

## Honest boundaries

Localhost only, no TLS. In-memory sessions/capsules/outbox (restart loses
state). Dev bearer auth — **not** production OAuth (see `docs/seats/j03/DESIGN.md`
D3 and the J6-F1 gate note). Fixture data, labeled. No real Alexa, no
certification. Latency measured on loopback; see `evidence/latency.json` for
methodology.
