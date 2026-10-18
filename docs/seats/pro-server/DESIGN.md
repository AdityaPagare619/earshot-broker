# pro-server — DESIGN.md

**Lane:** MCP gateway hardening (`services/gateway/mcp/server.py`), additive only.
**Base:** main @ c422bae. **Status:** design first, then build.

## What this lane changes (and only this)

1. **`--host` flag** on `earshot-server` (default `127.0.0.1`). `run()` gains a
   keyword `host="127.0.0.1"` — backward compatible, no test touches `run()`
   (tests construct `ThreadedMCPServer` directly; verified by grep).
2. **Graceful shutdown.** Today `run()` catches `KeyboardInterrupt` and `pass`es —
   the listening socket is never closed and no shutdown line is printed.
   New: `finally:` prints `EARSHOT MCP gateway: shutting down` and calls
   `server.server_close()`. SIGTERM → treated as KeyboardInterrupt via a handler
   installed in `main()` only (never in `run()`: tests run `run()` on worker
   threads, and `signal.signal` outside the main thread raises `ValueError`).
   Windows: the SIGTERM handler is installed only when `sys.platform != "win32"`;
   Ctrl-C path (KeyboardInterrupt) is platform-neutral. No `signal.SIGKILL`
   assumptions anywhere.
3. **Structured startup line.** One stable line on stderr:
   `EARSHOT MCP gateway listening on http://{host}:{port}/mcp protocol=2025-11-25 auth=dev-bearer`
   The existing `describe_for_operator()` token listing is kept verbatim —
   it is the dev token discovery mechanism.
4. **`--dev-token` flag** (dev-only, documented). Accepts the same JSON the
   `EARSHOT_DEV_TOKENS` env var takes: `'{"mytok": ["house-a", "priya"]}'`.
   Implemented by seeding `os.environ["EARSHOT_DEV_TOKENS"]` before the
   `AuthRegistry()` is constructed — uses auth's existing extension point,
   **zero changes to auth.py or the auth binding**.
5. **Request log format: frozen and documented** (not changed):
   `[HH:MM:SS] POST {method} tool={tool} tenant={tenant} status={status} {ms}ms`
   on stderr; never params, never values. `EARSHOT_QUIET=1` silences it.

## What this lane will NOT change

- Protocol behavior (spec 2025-11-25 pin), auth binding logic, tool
  implementations, `shape.py`, broker, session lifecycle, rate limits,
  Origin policy. `packages/kernel/` untouched (frozen by brief law).
- The `run(port, world_factory=None)` positional contract: `host` and
  `dev_token_json` are keyword-only additions.
- No new dependencies (stdlib only: `signal` is stdlib).

## Error contract (documented here; behavior unchanged)

**Transport-level** — plain JSON `{"error": "<message>"}`, no JSON-RPC envelope:

| HTTP | Trigger |
| ---- | ------- |
| 400 | missing `MCP-Session-Id` header; `MCP-Protocol-Version` mismatch |
| 401 | missing / malformed / unknown bearer token |
| 403 | `Origin` header present but not localhost |
| 404 | wrong path; unknown or expired session id |
| 405 | GET or DELETE on `/mcp` (no SSE streams / no client termination — spec-legal) |
| 413 | request body > 1 MiB |
| 429 | > 100 requests/min per credential |

**JSON-RPC** — HTTP 200 with `{"jsonrpc":"2.0","id":…,"error":{"code","message"}}`:

| Code | Name | Trigger |
| ---- | ---- | ------- |
| -32700 | Parse error | body is not JSON |
| -32600 | Invalid Request | non-object message; batch (unsupported) |
| -32601 | Method not found | unknown method or unknown tool name |
| -32602 | Invalid params | schema validation fails — **field name only, never the value** |
| -32603 | Internal error | unexpected exception — redacted; traceback to stderr only |

**Tool success** — HTTP 200, constant-shape envelope:
`{"content":[{"type":"text","text": <speak verbatim>}], "structuredContent": {...}, "isError": false}`.
`isError` is always `false`: tool-level failures are JSON-RPC errors, never
half-shaped successes.

## Risks

- **R1 — tests construct the server directly**, so `run()` changes are invisible
  to the 91 wire tests. Mitigation: live verification (start real server,
  handshake, tools/call, SIGINT → clean exit line, `--help`).
- **R2 — `--host 0.0.0.0` vs Origin policy.** Non-loopback binds still hit the
  localhost-only `Origin` check for browser clients. Documented in `--host`
  help text; not changed (out of scope).
- **R3 — env-var seeding for `--dev-token`.** Contained: only read by
  `AuthRegistry.__init__` in this process. Flag overrides env (documented).
- **R4 — `server_close()` in `finally` after `serve_forever`.** Safe: `shutdown()`
  is not needed (we're past the loop); `server_close()` releases the socket so
  rapid restart doesn't hit `EADDRINUSE` even with `allow_reuse_address`.

## Verification plan

1. `python -m pytest services/gateway/mcp` — 91 wire tests green.
2. Live: `earshot-server --port 8899 --dev-token '{"demo":["house-a","priya"]}'`
   → startup line sane → curl initialize (expect session id) → tools/call
   prepare_day_brief with `Bearer demo` → 200 + constant shape → SIGINT →
   `shutting down` line, exit 0, port released (immediate rebind works).
3. `earshot-server --help` — flags documented, dev-only warnings present.
4. Full `python -m pytest` if time permits (foundation already proved 640 green).

## kemiljk critic notes (filled after build)

- **Caught:** `latency.json` + `evidence/j06-*.json` regenerated by my test runs —
  restored before commit (generated evidence is not my lane's diff).
- **Caught:** first SIGINT test signaled the bash wrapper PID, not the server
  (`$!` inside a backgrounded exec session). Re-ran against the real server
  PID: shutdown line prints, process exits, port immediately rebindable.
- **Caught:** `test_replay_epoch` shared one broker across tests — the
  keep_secret edge polluted the room test. Fixed with per-test servers.
- **Caught:** request_key "rr11-ks-000002" was 14 chars (min 16) — the schema
  rejected it; renamed.
- Judged the `--dev-token` env-seeding: contained (only read by
  `AuthRegistry.__init__` in this process), documented as dev-only. Kept.
- Judged the startup-line rewording: no test or script parses the old text
  (tests construct the server directly). Kept.

## RR-11 (pro-threat follow-up, folded into this lane)

**Finding:** `_check_idem` returned the cached sealed response BEFORE
audience/belief evaluation — replaying a request_key from a permissive
audience state returned the permissive speech after the room tightened
(needs victim's bearer token + the key).

**Fix (in `broker.py`, additive):** the idempotency slot now binds an
audience epoch — `(declaration count, secrecy edge count, fixture audience)`.
`_check_idem` misses after any `room` declaration, fixture-audience swap, or
`keep_secret` edge, so the replay re-plans against current belief; the
param-conflict check still spans epochs (client bug regardless of room
changes); `_store_idem` evicts stale epochs for the key. No double exposure
commit on true retries (same epoch still hits the cache).

**Regression tests** (`services/gateway/mcp/tests/test_replay_epoch.py`, 3 tests):
replay-after-room-tightens (live `room` tool path), replay-after-keep_secret,
conflicting-params-across-epochs. Negative control proven: the two replay
tests FAIL on the unfixed broker, pass with the fix.

**Residuals:** wall-clock decay of ALONE signals (10-min half-life) is not in
the epoch — replays are retries seconds apart; binding time would defeat
legitimate retry idempotency. Concurrent mutation between `_check_idem` and
`_store_idem` is a microscopic window; the next replay self-corrects.
