# EARSHOT MCP Gateway — API Reference

The EARSHOT gateway is a **self-hosted MCP server** implementing
**[MCP spec 2025-11-25](https://spec.modelcontextprotocol.io/)** over
**Streamable HTTP**. It exposes the sealed-speech pipeline as 6 tools plus one
public-safe resource.

> **Every request/response example in this document was captured from a real
> running server** (`earshot-server --port 8899` on 2026-10-18). Capture
> provenance is at the bottom — re-run the capture to verify any example.
> Opaque values (`request_ref`, `plan_id`, session ids) differ per run; their
> *shape* is what matters.

## Base URL & transport

```
POST http://127.0.0.1:8899/mcp
```

- Default port is `8000` (`earshot-server --port 8000`); the examples use `8899`.
- Every POST carries `Content-Type: application/json` and
  `Accept: application/json, text/event-stream`.
- `GET /` returns `404` — the server only serves the `/mcp` endpoint.

## Authentication (development)

```
Authorization: Bearer <dev-token>
```

- **Required on every request**, including `initialize`. Missing header →
  HTTP `401` `{"error": "missing Authorization header: expected 'Bearer <dev-token>'"}`.
  Unknown token → HTTP `401` `{"error": "unknown or revoked token"}`.
  (Transport-level errors are plain JSON, not JSON-RPC envelopes.)
- The token is bound **server-side** to a `(tenant, owner)` pair. Tool arguments
  **never** carry identity — it comes only from the verified token.
- Dev tokens are printed to **stderr at server startup** and **reseed on every
  restart**:
  ```
  EARSHOT dev tokens (non-production, restart reseeds):
    tenant=house-a owner=priya token=esh_dev_...
    tenant=house-a owner=ravi  token=esh_dev_...
    tenant=house-b owner=meera token=esh_dev_...
  ```
- This is explicitly **non-production auth**. Production would use the Alexa
  QuickStart OAuth 2.1 + PKCE profile; no identity provider exists in
  competition scope, and a mock OAuth flow would be security theater. The
  fixture principals exist so cross-tenant tests are real: `priya` is the
  household owner, `ravi` a non-owner member, `meera` a different tenant.

## Session handshake

```bash
# 1. initialize — server pins protocolVersion 2025-11-25
curl -s -D headers.txt -X POST http://127.0.0.1:8899/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2025-11-25","capabilities":{},
                 "clientInfo":{"name":"my-client","version":"1"}}}'
```

```jsonc
// 200 OK — note the Mcp-Session-Id response header (captured in headers.txt)
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {"tools": {}, "resources": {}},
    "serverInfo": {"name": "earshot-broker", "version": "0.1.0"}
  }
}
```

```bash
# 2. notifications/initialized — required before any other call → 202, empty body
SESSION=$(grep -i "^Mcp-Session-Id:" headers.txt | awk '{print $2}' | tr -d '\r')
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8899/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
# → 202

# 3. tools/list
curl -s -X POST http://127.0.0.1:8899/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| python3 -c "import json,sys; print([t['name'] for t in json.load(sys.stdin)['result']['tools']])"
# → ['prepare_day_brief', 'resolve_day_change', 'continue_on_personal_device',
#    'withdraw_request', 'room', 'keep_secret']
```

> From here on, every example assumes `Authorization: Bearer $TOKEN`,
> `Mcp-Session-Id: $SESSION`, and `MCP-Protocol-Version: 2025-11-25` headers,
> and shows only the `-d` payload plus the captured response body. The examples
> use a bash array for the repeated headers — define it once:
>
> ```bash
> H=(-H "Content-Type: application/json"
>    -H "Accept: application/json, text/event-stream"
>    -H "Authorization: Bearer $TOKEN"
>    -H "Mcp-Session-Id: $SESSION"
>    -H "MCP-Protocol-Version: 2025-11-25")
> ```

## The constant-shape envelope

Every `tools/call` returns HTTP `200` with this envelope — the **same fields in
the same order for every tool, every audience, every secret**:

```jsonc
{
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [
      {"type": "text", "text": "<speak — the ONLY text the room may hear>"}
    ],
    "isError": false,
    "structuredContent": {
      "speak": "<identical to content[0].text>",
      "speak_policy": "verbatim_no_elaboration",
      "mode": "cover",              // "cover" | "open"
      "screen_depth": 4,             // deepest spoken depth this turn
      "followups": ["next", "continue_on_personal_device"],
      "request_ref": "<opaque, owner-bound — NOT authorization>",
      "request_state": "accepted",  // observed value on tool responses
      "_meta": {
        "earshot/plan_id": "pln_5cf87e1d141837e7",
        "earshot/table_version": 1
      }
    }
  }
}
```

**What "constant shape" means:** the response to a probe (`room` → `"Noted."`)
is structurally identical to a full brief. Cover-mode shape is a function of
the *credible audience set* only — never of hidden data. A listener comparing
two responses learns nothing about which secrets exist. `content[0].text` is
the verbatim speech; hosts must render it **without elaboration**
(`speak_policy`). The fixed suffix *"The rest of your day is on your phone."*
is appended to every brief-family utterance **even when nothing was withheld**
— its presence is never a signal.

---

## Tools

### `prepare_day_brief`

Prepare a day plan using sources the owner connected to EARSHOT. Returns only
explicitly public facts. The full plan and private processing status remain in
the authenticated owner inbox.

**Parameters** (`inputSchema`, `additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `date` | string | ✅ | `format: date` (`YYYY-MM-DD`) |
| `timezone` | string | ✅ | 1–80 chars; validated IANA timezone, not a guessed numeric offset |
| `request_key` | string | ✅ | 16–128 chars; retry-stable. Server binds dedupe to the authenticated owner and rejects conflicting reuse |
| `continuation_ref` | string | — | 20–128 chars; the `request_ref` of an in-progress chunked brief → returns the next chunk (`"next"` followup). Re-plans remaining items against fresh belief |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"prepare_day_brief",
                 "arguments":{"date":"2026-10-19","timezone":"Asia/Kolkata",
                              "request_key":"my-app-brief-key-0001"}}}'
```

```jsonc
// 200 OK — captured from the real server (fixture tenant house-a)
{
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [{"type": "text",
      "text": "Here's today: School pickup at 7:00 PM at school gate, and Focus block at 10:00 AM. The rest of your day is on your phone."}],
    "isError": false,
    "structuredContent": {
      "speak": "Here's today: School pickup at 7:00 PM at school gate, and Focus block at 10:00 AM. The rest of your day is on your phone.",
      "speak_policy": "verbatim_no_elaboration",
      "mode": "cover",
      "screen_depth": 4,
      "followups": ["next", "continue_on_personal_device"],
      "request_ref": "7moNLk_ixxChTqm951htUfecwIbl_Wkg",
      "request_state": "accepted",
      "_meta": {"earshot/plan_id": "pln_5cf87e1d141837e7", "earshot/table_version": 1}
    }
  }
}
```

Calling it **again after** `room("Mom's here")` + `keep_secret("Never mention
the clinic in front of Mom")` re-plans against fresh belief — same envelope,
reshaped speech:

```jsonc
{"text": "Nothing I can share out loud right now. The rest of your day is on your phone."}
```

The room hears less; the *shape* of the answer never changes. A successful call
also publishes the [`ui://earshot/day-card`](#uinearshotday-card) resource for
this session.

**Errors:** missing/invalid params → `-32602` (see [error catalog](#error-catalog)).

---

### `resolve_day_change`

Prepare a revision to an existing sealed day plan, using private constraints
**without returning them**. Draft only: external calendar changes require
personal approval. Never reveals why a slot is unavailable.

**Parameters** (`additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `request_ref` | string | ✅ | 20–128 chars; opaque EARSHOT reference from an earlier call. Identifies the request — **not authorization** (identity comes from the bearer token) |
| `change` | object | ✅ | `kind` ∈ `add_flexible_block` \| `find_alternative_window`; `duration_minutes` 5–240; `window_start`, `window_end` `format: date-time`; `additionalProperties: false` |
| `request_key` | string | ✅ | 16–128 chars; retry-stable, owner-bound dedupe |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call",
       "params":{"name":"resolve_day_change",
                 "arguments":{"request_ref":"7moNLk_ixxChTqm951htUfecwIbl_Wkg",
                   "change":{"kind":"find_alternative_window","duration_minutes":30,
                             "window_start":"2026-10-19T14:00:00+05:30",
                             "window_end":"2026-10-19T18:00:00+05:30"},
                   "request_key":"my-app-change-key-0001"}}}'
```

```jsonc
// 200 OK — captured. No window fit the private constraints; the reason stays sealed.
{
  "jsonrpc": "2.0", "id": 4,
  "result": {
    "content": [{"type": "text", "text": "No suitable window found in that range."}],
    "isError": false,
    "structuredContent": {
      "speak": "No suitable window found in that range.",
      "speak_policy": "verbatim_no_elaboration",
      "mode": "cover",
      "screen_depth": 0,
      "followups": ["continue_on_personal_device"],
      "request_ref": "7moNLk_ixxChTqm951htUfecwIbl_Wkg",
      "request_state": "accepted",
      "_meta": {"earshot/plan_id": "pln_520a65a75d25b07c", "earshot/table_version": 1}
    }
  }
}
```

**Errors:** unknown `request_ref` → `-32603` `"Unavailable"` (deliberately vague —
see [error catalog](#error-catalog)).

---

### `continue_on_personal_device`

Queue continuation of this EARSHOT request in the registered owner inbox. Does
**not** accept an arbitrary destination. *Accepted means queued, not delivered
or read*; no private item count is returned.

**Parameters** (`additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `request_ref` | string | ✅ | 20–128 chars; opaque reference, not authorization |
| `request_key` | string | ✅ | 16–128 chars; retry-stable, owner-bound dedupe |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call",
       "params":{"name":"continue_on_personal_device",
                 "arguments":{"request_ref":"7moNLk_ixxChTqm951htUfecwIbl_Wkg",
                              "request_key":"my-app-cont-key-0001"}}}'
```

```jsonc
// 200 OK — captured
{"text": "Continuing on your personal device.",
 "structuredContent": {
   "speak": "Continuing on your personal device.",
   "speak_policy": "verbatim_no_elaboration",
   "mode": "cover", "screen_depth": 0,
   "followups": ["continue_on_personal_device"],
   "request_ref": "7moNLk_ixxChTqm951htUfecwIbl_Wkg",
   "request_state": "accepted",
   "_meta": {"earshot/plan_id": "pln_4cc2a39995c50800", "earshot/table_version": 1}}}
```

---

### `withdraw_request`

Withdraw pending work and unreleased EARSHOT output. **Cannot undo already
emitted speech or completed external effects.** Exact partial-completion state
remains in the owner inbox.

**Parameters** (`additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `request_ref` | string | ✅ | 20–128 chars; opaque reference, not authorization |
| `request_key` | string | ✅ | 16–128 chars; retry-stable, owner-bound dedupe |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call",
       "params":{"name":"withdraw_request",
                 "arguments":{"request_ref":"7moNLk_ixxChTqm951htUfecwIbl_Wkg",
                              "request_key":"my-app-wd-key-0001"}}}'
```

```jsonc
// 200 OK — captured. A queued continuation was reconciling at withdraw time.
{"text": "Request withdrawn. A queued continuation is reconciling — already emitted output can't be unsent.",
 "structuredContent": {
   "speak": "Request withdrawn. A queued continuation is reconciling — already emitted output can't be unsent.",
   "speak_policy": "verbatim_no_elaboration",
   "mode": "cover", "screen_depth": 0,
   "followups": ["continue_on_personal_device"],
   "request_ref": "7moNLk_ixxChTqm951htUfecwIbl_Wkg",
   "request_state": "accepted",
   "_meta": {"earshot/plan_id": "pln_2c599f2d6a1bbae4", "earshot/table_version": 1}}}
```

---

### `room`

Declare room state in plain words (`"Mom's here"`, `"I'm alone"`). Updates
presence belief with **asymmetric trust**: declarations can add listeners
freely, but `"alone"` only loosens low-sensitivity items. **Never confirms or
denies secrets** — the response is constant by design.

**Parameters** (`additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `declaration` | string | ✅ | 1–200 chars; spoken declaration, e.g. `"Mom's here"` |
| `request_key` | string | ✅ | 16–128 chars; retry-stable, owner-bound dedupe |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call",
       "params":{"name":"room",
                 "arguments":{"declaration":"Mom'\''s here",
                              "request_key":"my-app-room-key-0001"}}}'
```

```jsonc
// 200 OK — captured. The boring response IS the feature: a probe answered any
// other way becomes a probe-distinguishable oracle.
{"text": "Noted.",
 "structuredContent": {
   "speak": "Noted.",
   "speak_policy": "verbatim_no_elaboration",
   "mode": "cover", "screen_depth": 0,
   "followups": ["continue_on_personal_device"],
   "request_ref": "room-UoG9jiMRik9_xRYkbWF3EQ",
   "request_state": "accepted",
   "_meta": {"earshot/plan_id": "pln_aed0d83028ed9f8d", "earshot/table_version": 1}}}
```

The effect is visible on the *next* `prepare_day_brief`, which re-plans against
the updated belief (see the before/after example under
[`prepare_day_brief`](#prepare_day_brief)).

---

### `keep_secret`

Say in one sentence what to keep private from whom
(`"Never mention the clinic in front of Mom"`). Creates an **immediate
TIGHTEN edge**: clearance drops at once, no confirmation needed. Tightening is
always safe — the model may make you more private, never less.

**Parameters** (`additionalProperties: false`):

| Name | Type | Required | Constraints |
|---|---|---|---|
| `instruction` | string | ✅ | 1–500 chars; one spoken sentence naming what to keep from whom |
| `request_key` | string | ✅ | 16–128 chars; retry-stable, owner-bound dedupe |

```bash
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call",
       "params":{"name":"keep_secret",
                 "arguments":{"instruction":"Never mention the clinic in front of Mom",
                              "request_key":"my-app-ks-key-0001"}}}'
```

```jsonc
// 200 OK — captured
{"text": "Noted. I'll keep that private from the people you named.",
 "structuredContent": {
   "speak": "Noted. I'll keep that private from the people you named.",
   "speak_policy": "verbatim_no_elaboration",
   "mode": "cover", "screen_depth": 0,
   "followups": ["continue_on_personal_device"],
   "request_ref": "ks-6cNnVKAfmcreEX9tEwrsvQ",
   "request_state": "accepted",
   "_meta": {"earshot/plan_id": "pln_cd69155acaea4222", "earshot/table_version": 1}}}
```

---

## Resources

### `ui://earshot/day-card`

A public-safe card for the session's latest accepted day brief. Contains only
explicitly public facts — no secrets cross, ever. The card is richer than
speech (full public depth) but still sealed: compare the spoken brief (2 items)
with the card below (6 public items) from the same session.

The resource **only appears in `resources/list` after a `prepare_day_brief`
has been accepted in that session**. A session with no brief lists zero
resources; reading the URI in such a session returns `-32602`.

```bash
# resources/list — after prepare_day_brief
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":9,"method":"resources/list","params":{}}'
```

```jsonc
// 200 OK — captured
{"jsonrpc": "2.0", "id": 9, "result": {"resources": [{
  "uri": "ui://earshot/day-card",
  "name": "Earshot day card",
  "description": "Public-safe card for the session's latest accepted day brief. Contains only explicitly public facts.",
  "mimeType": "application/json"
}]}}
```

```bash
# resources/read
curl -s -X POST http://127.0.0.1:8899/mcp "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":10,"method":"resources/read",
       "params":{"uri":"ui://earshot/day-card"}}'
```

```jsonc
// 200 OK — captured (contents[0].text is a JSON string, mimeType application/json)
{"jsonrpc": "2.0", "id": 10, "result": {"contents": [{
  "uri": "ui://earshot/day-card",
  "mimeType": "application/json",
  "text": "{\"speak\": \"Here's today: School pickup at 7:00 PM at school gate, Focus block at 10:00 AM, Call the bank, Water the plants, Collect groceries after 6, and Dinner prep at 7 PM. The rest of your day is on your phone.\", \"speak_policy\": \"verbatim_no_elaboration\", \"mode\": \"cover\", \"followups\": [\"continue_on_personal_device\"], \"screen_depth\": 4, \"request_ref\": \"7moNLk_ixxChTqm951htUfecwIbl_Wkg\", \"request_state\": \"accepted\", \"_meta\": {\"earshot/plan_id\": \"pln_1c656788560ffe8a\", \"earshot/table_version\": 1}, \"uri\": \"ui://earshot/day-card\"}"
}]}}
```

---

## Error catalog

Transport errors (HTTP status, plain-JSON body — **not** JSON-RPC):

| Case | HTTP | Body (captured) |
|---|---|---|
| Missing `Authorization` header | 401 | `{"error": "missing Authorization header: expected 'Bearer <dev-token>'"}` |
| Unknown/revoked token | 401 | `{"error": "unknown or revoked token"}` |

JSON-RPC errors (HTTP 200, `{"jsonrpc":"2.0","id":…,"error":{…}}`):

| Code | Meaning | Captured example |
|---|---|---|
| `-32700` | Parse error — body isn't JSON | `{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}` (from `rpc_error` in `server.py`) |
| `-32601` | Method/tool not found | `{"code": -32601, "message": "Unknown tool: delete_everything"}` |
| `-32602` | Invalid params — schema violation | `{"code": -32602, "message": "invalid params: 'arguments.timezone'"}` (missing required field); `{"code": -32602, "message": "invalid params: 'arguments.request_key'"}` (`request_key` shorter than 16 chars) |
| `-32603` | Unavailable — **deliberately vague** | `{"code": -32603, "message": "Unavailable", "data": {"continuation": "personal_inbox"}}` (unknown `request_ref`) |

**Why `-32603` says so little:** the error oracle is part of the privacy
contract. Distinguishing "unknown ref" from "ref belongs to another owner"
from "ref expired" would let a caller probe which requests exist. All
unavailable states collapse to one message plus a recovery pointer
(`personal_inbox`). This indistinguishability is pinned by tests
(`tests/failure_paths/`).

**Idempotency:** re-sending a call with the same `request_key` returns the
original receipt (dedupe is keyed by `(tenant, owner, request_key)` — a
guessed key from another principal cannot retrieve someone else's receipt).

---

## Capture provenance

Every example above was produced on **2026-10-18** by:

```bash
git checkout c422bae                       # pro-api-docs worktree base
python3 -m venv /tmp/apidocs-venv
/tmp/apidocs-venv/bin/pip install -e ".[test]"
/tmp/apidocs-venv/bin/earshot-server --port 8899   # dev tokens printed to stderr
/tmp/apidocs-venv/bin/python /tmp/apidocs-capture.py
```

- Server: the real stdlib Streamable HTTP gateway (no mocks), fixture tenant
  `house-a` / owner `priya` via the startup-printed dev token.
- Client: raw `urllib` JSON-RPC/HTTP — the same wire shape as the `curl`
  commands shown (headers: `Content-Type`, `Accept`,
  `Authorization: Bearer $TOKEN`, `Mcp-Session-Id`, `MCP-Protocol-Version`).
- Raw captures: 20 request/response pairs (kept as the lane's working record;
  the doc shows the 14 that teach something).
- Re-run any example by substituting your own startup-printed token for
  `$TOKEN` and the `Mcp-Session-Id` from your own `initialize` call.
