# pro-api-docs — DESIGN.md

## What this lane owns
`docs/api.md` exclusively. The single reference a stranger (judge, developer,
integrator) reads to call the EARSHOT MCP gateway correctly. Nothing else in the
repo is touched.

## Doc structure
1. **Header**: what this is (MCP spec 2025-11-25, Streamable HTTP), base URL,
   auth model (dev bearer token → server-side (tenant, owner) binding; tool args
   never carry identity), protocol versions pinned.
2. **Session handshake**: `initialize` → `notifications/initialized` → `tools/list`.
   Real captured request/response.
3. **The constant-shape envelope**: every tool response is `content[0].text`
   (`speak`, verbatim) + `structuredContent` (full contract). Envelope fields
   documented once: `speak`, `speak_policy: "verbatim_no_elaboration"`,
   `spoken_depths`, `verbatim_no_elaboration`, `request_ref`, `_meta`
   (plan id + table version), fixed suffix. Why the shape is constant
   (paired-world guarantee) — one paragraph, pointer to docs/architecture.md.
4. **Six tools**, one section each, identical template:
   - One-line purpose (from the contract description).
   - Parameters table: name, type, required?, constraints (min/max length,
     enums, formats), verbatim constraint text from the schema.
   - Auth: which principal the example token maps to; what a wrong/other-tenant
     token sees.
   - Real `curl` request (copy-pasteable) + real captured response (trimmed only
     for length, never edited).
   - Success semantics: what "accepted" means (e.g. continue = queued not
     delivered; withdraw = cannot undo emitted speech).
   - Error cases: real captured error responses (bad params, unknown ref,
     auth failures), with codes.
5. **Day-card resource**: `ui://earshot/day-card` — when it appears
   (only after `prepare_day_brief` in the session), `resources/list` +
   `resources/read` captured examples, public-safe guarantee.
6. **Error catalog**: transport errors (401 missing/malformed bearer, 400 bad
   session), JSON-RPC errors (`-32602` invalid params, broker error codes),
   all captured live.
7. **Capture provenance**: exactly how every example was produced (server
   command, port, token, fixture data), so anyone can re-capture.

## Accuracy method (kemiljk lens: accuracy > beauty)
- Every schema constraint copied from `packages/contracts/API_CONTRACTS.json`
  (the file the server asserts against at startup — `assert protocolVersion`
  pin).
- Every request/response example captured from a REAL running server on this
  box (`earshot-server --port 8899`), via the same curl form shown. No
  hand-written JSON. Capture script kept at `/tmp` during the lane; provenance
  recorded in the doc.
- Every envelope field name verified against `services/gateway/mcp/shape.py`
  and `broker.py` before writing.
- Discrepancies between contract/code/doc found during capture are listed in
  the final report (not silently papered over).

## Risks
- Fixture data: examples use the fixture tenant/owner (`dev-owner-token` →
  tenant `house-a`, owner `owner-1`). The doc labels this explicitly — examples
  are reproducible, not production data.
- Response bodies contain opaque `request_ref` values that differ per run;
  the doc notes they are opaque and shows the shape, not a stable value.
- `room`/`keep_secret` responses are constant-shape by design ("Noted.") —
  the doc explains WHY the response is boring (it is the feature).
