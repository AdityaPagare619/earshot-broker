# Friction log — EARSHOT build (18 Oct 2026)

Honest record of what slowed us down, what we got wrong, and what we changed.
Timestamps in IST. Severity: P0 = blocked the build, P1 = cost hours,
P2 = papercut.

## P0

- **The SDK trap (16:45).** The installed official MCP Python SDK negotiates
  protocol version 2026-07-28. The track pins 2025-11-25. A team using the SDK
  as documented would silently violate the pin and never know — the handshake
  succeeds. We caught it only because we hand-rolled the transport in stdlib
  and asserted the version bytes on the wire. **Fix:** hand-rolled stdlib
  server; version asserted in tests. **Ask of the platform:** let the SDK pin
  a maximum protocol version.

## P1

- **Stale test server held port 8899 (17:55).** A backgrounded gateway from an
  earlier verification run kept the port; the trace-harness suite failed to
  bind and the failure looked like a code bug. Cost ~20 minutes before we
  checked PIDs instead of code. **Fix:** kill-by-PID discipline; the harness
  now fails loudly with "port in use by PID n".
- **pkill matched our own shell (18:05).** `pkill -f` with a pattern present
  in our own command line killed our own shell (exit signal 15) — twice.
  **Fix:** bracket patterns (`[s]erver.py`) that can't match the invoker.
- **Arbiter/kernel audience TTL mismatch (J2, ~17:30).** The output arbiter's
  grant TTL and the kernel's audience TTL disagreed, so every commit
  self-denied in the simulator. Looked like a kernel bug; was a contract
  drift between two seats. **Fix:** single source of truth for TTLs,
  cross-seat contract test.

## P2

- **tests/README.md invocation gap (18:50).** The documented test command
  predated the failure-paths suite and missed its harness dir on PYTHONPATH —
  6 import errors that looked like regressions. **Fix:** README corrected,
  37/37 green.
- **Unittest discovery vs per-package imports.** Four packages, four import
  styles (`from hotlane import`, `from edges import`, self-resolving
  sys.path). Every seat's "all green" claim initially failed under a naive
  `discover` until the right PYTHONPATH was found. **Fix:** each suite now
  documents its exact invocation; orchestrator verifies with it.
- **Devpost FAQ vs rules page.** "Repo must call the track tech in code" and
  "Kiro Crew qualifies alone" live in the FAQ, not the rules. Nearly missed
  both.

## What we'd tell the next team

1. Assert the protocol version on the wire, not in your dependency list.
2. A privacy test that can't fail is theater — every suite needs a negative
   control. (Ours caught two real leaks in *data*, not code.)
3. Label the simulator on every screen. The rules bless it; hiding it would
   be the actual foul.
