# Validation summary — 18 October 2026

## What the suite proves (reproduce: `python -m pytest` from repo root)

- **Frozen reference kernel:** 24/24 unit tests (`evidence/kernel-tests.txt`).
  The kernel is never modified by design; the suite pins that.
- **Real Streamable HTTP MCP server** (spec 2025-11-25, stdlib-only, no SDK):
  91 gateway tests green over live HTTP — initialize handshake negotiates
  2025-11-25, `tools/list` exposes 6 tools, `tools/call` round-trips real
  sealed-speech responses, dev bearer-token auth binds tenant/owner server-side
  (unauthenticated → 401). Client-measured p99 < 500ms budget asserted in-suite
  (`services/gateway/mcp/tests/test_latency.py`).
- **Constant-shape speech at the wire:** secret-swaps under fixed cover audiences
  are byte-identical (modulo shape-pinned opaque refs); the negative control
  proves the suite detects real leaks (`evidence/constant-shape-results.txt`).
- **Privacy SLO:** sealed-speech existence AUC 0.497 vs native 0.928
  (200 triples/policy, seed 7) — policy layer, fixture listener as lower-bound
  adversary (`packages/trace-harness/evidence/slo/`).
- **Failure paths:** 37 tests — error-oracle indistinguishability, deny→recovery
  matrix, lease lifecycle, withdraw-vs-reconcile (`evidence/failure-path-results.txt`).
- **Races:** 8 documented races (RR-1..RR-8); the honest finding is that the kernel alone
  closes none — per-chunk `authorize_playback` exists as test scaffolding
  (`tests/races/arbiter.py`), not production code; the production simulator
  ships epoch-bound single-use grants + stop-output-first. Closing the gap is
  documented future work (`evidence/race-matrix.md`).
- **Packs:** 33 tests incl. 6 language-blind (identical depth decisions en vs hi);
  the pack leak-verifier fired twice during development and both leaks were
  fixed in *data* (`evidence/demo_en.log`, `evidence/demo_hi.log`).

## Honest limits — what was NOT proven

- No real Alexa+ device, skill, or account was used: there is no participant-facing
  Alexa+ environment (partner-gated per the competition FAQ). The simulator is
  independent and labeled as such everywhere; the MCP server is real software
  speaking the real protocol.
- No performance benchmark beyond the in-suite latency assertions; no sensor,
  audio, OAuth, or cloud-provider integration testing.
- The fixture adversarial listener is a *lower bound* — a smarter adversary
  could do better than AUC 0.497 suggests.
- Synthetic households are not real households; belief noise is a fixture model.
- No production security audit; no full MCP conformance certification claimed.
- The synthetic kernel contains no cryptography or real identity verification;
  the dev bearer token is a development stand-in, not a security boundary.

## Reading this directory

Start at `evidence/README.md` — it indexes every artifact, traces every public
number one hop to its file, and gives the reproduction command.
