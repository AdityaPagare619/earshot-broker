# pro-examples — DESIGN.md

## Goal
`examples/` is the first thing a judge or developer runs after `pip install -e .`.
Three single-file, copy-paste scripts. Each one PROVES a load-bearing claim of
the architecture — not narrates it. Every example runs in seconds, exits 0 with
a one-line verdict, and works on Windows/macOS/Linux (pathlib, UTF-8 stdout,
no POSIX calls, stdlib only).

## The three examples (one claim each)

### 1. `mcp_tool_call.py` — "the MCP server is real"
Claim: the gateway speaks MCP 2025-11-25 over Streamable HTTP and the sealed
response contract holds on the wire.
- Spins up the REAL gateway (`earshot.gateway.mcp.server`) in a thread on
  127.0.0.1 with an ephemeral port (no fixed-port assumption → parallel-safe).
- Performs the spec handshake (`initialize` → `notifications/initialized`),
  then `tools/call prepare_day_brief` with a real `request_key`/`date`/`timezone`.
- Asserts the sealed-speech contract on the wire response: `speak_policy ==
  "verbatim_no_elaboration"`, `request_state == "accepted"`, a `request_ref`
  in the 20–128 char band. Prints the spoken text.
- Proof line: the actual `speak` string returned by the server.
- Risk: port conflicts if another lane's suite runs concurrently — mitigated with
  port 0 (ephemeral) + `getsockname()`.

### 2. `sealed_pipeline.py` — "one secret, three seams, computed"
Claim: a private item survives quarantine → belief → constant-shape planning
without its content ever appearing in the room-facing output.
- Drives `SealedSpeechPipeline` directly (fixture stages behind the frozen ports):
  ingest a therapy note (sensitivity high) + a standup (public).
- Declares "mom's here" via `room()`, then `brief()`s.
- Asserts: therapy item COMPILED (not stuck in quarantine), planned depth for
  the therapy item is BELOW its full detail (d<4) while the room is non-empty,
  the spoken text does NOT contain the therapy title, and the phone digest
  EXISTS (the private content went to the personal channel, not the room).
- Proof line: `speak` text + the therapy item's planned depth.
- Honest label: `[FIXTURE]` stages are deterministic stand-ins — printed.

### 3. `custom_pack.py` — "the household pack is data, and data decides depth"
Claim: disclosure depth is governed by pack data, not code — change the pack,
change what the room hears, without touching a line of Python.
- Loads the shipped `en` pack; renders a health-topic note at mom's (elder)
  clearance → d3 ("a note about health").
- Copies the pack tree to a temp dir, edits ONE value in `base/roles.yaml`
  (elder/health: 3 → 0), reloads, renders again → d0 (absorbed, not spoken).
- Asserts the two renditions differ and the custom one is the absorbed form.
- Proof line: both renditions printed side by side.
- Risk: hand-editing YAML could break schema validation — the example asserts
  the reload SUCCEEDS (validation is the point: bad packs fail loudly).

## Shared conventions
- `from __future__ import annotations`; module docstring states the claim;
  `main()` returning int; `if __name__ == "__main__": raise SystemExit(main())`.
- `ensure_utf8_stdout()` first (Windows console safety).
- Pack data located via `importlib.resources` with repo-root fallback (same
  pattern as `demo/five_beats.py` — proven on installed AND source layouts).
- Each <80 lines of code (docstrings/comments excluded from the count).
  Deliberate exception: `mcp_tool_call.py` runs ~95 — the MCP client is inline
  on purpose. A judge reading the example should SEE the 2025-11-25 handshake
  (initialize → notifications/initialized → tools/call); hiding it in a test
  helper would defeat the example's pedagogical job.
- `examples/README.md`: claim → run command → what to look for, for each.
