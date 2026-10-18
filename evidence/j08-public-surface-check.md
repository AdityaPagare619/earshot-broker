# J8 public-surface verification — 18 October 2026

Seat: J8 (Sr Manager, Device Appstore). Area: README + docs/support.md +
obvious-vs-creative argument.

## Checks performed

1. Kernel: `python3 -m unittest discover -s packages/kernel` → **24 tests, OK**
   (stdlib only; confirms the "24 unit tests" README claim on this branch).
2. Link audit: all **13 relative links** across README.md and docs/support.md
   resolve to real files in the tree (script-checked, none missing).
3. Banned-word scan: no superlatives in public copy ("guarantee", "proven",
   "revolutionary", "first-ever", "best-in-class", "military-grade" —
   the only hits are explicit negations or meta-discussion in DESIGN.md).
4. Claim traceability: every number in the README links one hop to evidence/
   (kernel-tests.txt, synthetic-scenario-trace.json, VALIDATION_SUMMARY.md).
5. No new factual claims invented: all copy derives from docs/dossier/,
   packages/contracts/API_CONTRACTS.json, or evidence/.

## Honesty notes

- The Inspector/handshake evidence cited in the README was produced by the
  dossier author and recorded in evidence/VALIDATION_SUMMARY.md; the README
  links to that summary rather than implying J8 re-ran it.
- Troubleshooting rows depending on the J3 gateway server are marked as
  landing on that seat's branch.
- No latency, device, OAuth, or production-security claims are made anywhere
  in J8 copy (dossier §17: none measured).
