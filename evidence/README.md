# S6 Evidence — measurements, not claims

## Test counts (2026-10-18)
- `packs/tests`: 33 tests, OK (27 pack conformance + 6 language-blind)
- `integration/tests`: 14 tests, OK (8 pipeline incl. 3 seam counterfactuals
  + 1 negative control; 6 demo-beat properties)
- Total: **47 tests, all green**, stdlib only (`unittest`).

## Demo runs
- `evidence/demo_en.log`: 5-beat demo, `--lang en` → ALL 5 BEATS PASSED
- `evidence/demo_hi.log`: 5-beat demo, `--lang hi` → ALL 5 BEATS PASSED
- Both runs compute through the same `SealedSpeechPipeline`; every beat
  asserts (exit non-zero on any failure). Honest `[SIMULATOR]`/`[FIXTURE]`
  labels throughout; not a live Alexa+ device.

## Key measured properties
- Beat 4 (counterfactual): therapy-day vs no-therapy-day briefings are
  byte-identical in both languages (mom present).
- Language-blind: identical depth/action decisions en vs hi across three
  room states (alone / mom / maya); spoken strings differ (Devanagari
  present in hi, absent in en).
- Verifier catches: the pack's own leak verifier fired twice during
  development (a `{category}` placeholder in d3 templates leaking
  "therapy"; a Latin-only gift regex) — both fixed in data, not code.
- Exposure budget observed live: a turn-1 d4 disclosure correctly
  tightened a turn-2 re-disclosure to d2 (Law 5 working as designed).
