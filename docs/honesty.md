# EARSHOT — Honesty Ledger

*What is real, what is simulated, what we don't claim, and what would kill the
story. If any row in the first table is wrong, the project is misrepresenting
itself — file it as a bug.*

## 1. Real vs simulated

| Component | Status | What that means |
|---|---|---|
| MCP server (`earshot-server`) | **Real** | Hand-rolled stdlib Streamable HTTP, MCP spec 2025-11-25 pinned. Real `initialize` handshake, real `tools/list`, real `tools/call` over TCP. No SDK. |
| The 6 tools | **Real** | `prepare_day_brief`, `resolve_day_change`, `continue_on_personal_device`, `withdraw_request`, `room`, `keep_secret` — all execute the real sealed pipeline, not stubs. |
| Sealed pipeline (quarantine → secrecy graph → belief → constant shape) | **Real** | Deterministic code over frozen contracts. 640 tests, one `pytest` invocation. |
| Wire-level paired-world byte-identity | **Real** | Secret-swaps under fixed cover audiences produce byte-identical HTTP response bodies (modulo opaque refs). `evidence/constant-shape-results.txt`. |
| Latency (p99 2.54ms HTTP round trip) | **Real, measured** | Client-measured, N=200, on this machine. Under the 500ms budget with headroom — but it is *our* measurement, not a device measurement. `services/gateway/mcp/evidence/latency.json`. |
| Privacy SLO (existence AUC 0.497) | **Real, measured — on synthetic households** | Seeded synthetic households (EN/HI/Hinglish), 200 AUC triples, reproducible. The *number* is real; the *households* are not. `packages/trace-harness/evidence/slo/`. The keyword listener is explicitly a lower bound, not a strong adversary. |
| Web simulator (`earshot-sim`) | **Simulated — labeled** | An independent web simulator, **not** an Echo, not a live Alexa+ device. Says so in an unmissable banner. It drives the *real* in-process broker, but the room, the sensors, and the speaker are theater. |
| Calendar / tasks adapters | **Fixtures** | `services/gateway/adapters/` implements the adapter contract against fixture data, not your real Google Calendar. Real adapters are integration work. |
| Auth (bearer dev tokens) | **Dev stand-in** | In-memory tokens, restart reseeds, printed for the operator. Explicitly non-production. Production needs OAuth 2.1 / PKCE. |
| Sensor input ("Mom walks in") | **Simulated** | Scripted declarations and fixture audiences, not microphones or presence sensors. The belief-fusion math is real; the evidence feed is not. |
| Demo video | **Real output, narrated** | The terminal frames are real demo output; the voiceover is TTS. Labeled `[SIMULATOR] [FIXTURE]` where it matters. |

## 2. What we don't claim (retired claims stay retired)

- **No "0% leak" benchmark.** An earlier prototype reported "42.4% → 0 leaks"
  over 3,000 synthetic personas. The broker dossier declined to reuse those
  numbers and so do we — they are not cited anywhere as verified.
- **No "zero privacy leaks," no "universal," no "military-grade."** The claim
  is narrow: existence AUC ≈ 0.5 against the tested listener class, on the
  tested corpus, with the listed residual risks open.
- **The 4-level disclosure lattice (FULL > ABSTRACT > EXISTENCE > SILENT) is
  UX labels, not the security model.** The real model governs field contents,
  existence, derived info, action effects, recipients, purpose, channel, and
  persistence. Anyone describing the lattice as the mechanism is wrong.
- **No "works with your Alexa today."** There is no partner-gated Alexa+
  integration here; the track rules bless the simulated path and we took it
  honestly.
- **No performance claim beyond our measurements.** The latency and AUC numbers
  are measured on our hardware, on synthetic data. A device measurement would
  be a different number.

## 3. Kill conditions

If any of these happen, the privacy story as told is invalid — not "needs a
patch," invalid:

1. **A paired-world byte-identity test fails.** The constant-shape claim rests
   on wire-level byte-identity. One failing pair means the room can distinguish
   secrets, and every downstream claim falls.
2. **Existence AUC moves clearly above 0.5 against a stronger listener.**
   The SLO is release-blocking by architecture law. A 0.65 against a real
   listener class is not "close enough" — it's a failed SLO.
3. **A residual risk is demonstrated inside the defended adversary class.**
   The register (threat-model §5) is the boundary of the promise. A casual-
   overhearing break with no fix is a kill, not a footnote.
4. **Adapter mislabeling in a real deployment.** Boundary 1 has no technical
   control — only the adapter contract and review. A production adapter that
   labels secrets PUBLIC voids G1 silently. This is the deepest trust root and
   the least technical one.
5. **The dev auth layer ships as production auth.** Bearer dev tokens are a
   stand-in with a printed warning. If they ever guard real data without
   replacement, the auth boundary (threat-model §3) is fiction.
6. **The simulator is presented as a device.** The banner is load-bearing. Any
   screenshot, video, or demo that crops it out is misrepresentation.
