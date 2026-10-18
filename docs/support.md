# Support — EARSHOT private task broker

How to get help, what to do when something doesn't work, and what we openly
don't cover yet. If you're evaluating this for the hackathon, start with the
[README](../README.md) — this page is the support-burden answer: everything a
skeptical user would ask, answered honestly.

## FAQ

**1. Does this work on my Echo?**
No. The competition's Alexa+ builder tooling is gated and unavailable to
participants, so the demo runs on a clearly labeled independent simulator.
EARSHOT is an MCP server (spec 2025-11-25, Streamable HTTP) plus that
simulator — not a device integration. See "What we don't claim" in the README.

**2. Can it stop Alexa from announcing my packages / reading my messages?**
No — and anyone who claims their add-on can is overclaiming. An MCP add-on is
invoked when Alexa routes a request to it; it is not a mandatory interception
layer around built-in announcements, other integrations, or retained history.
EARSHOT protects *its own* workflows (day planning through its four tools).
It does not gag Alexa.

**3. What happens when someone walks in mid-task?**
On the EARSHOT-controlled host profile, the audience change invalidates
pending disclosure leases and stops future output — the task itself stays
ready privately, so nobody has to start over. On a persistent public host,
protected facts never entered that host's context in the first place, so
there is nothing to retract. What already left the boundary as speech or a
completed external effect cannot be un-said — `withdraw_request` is explicit
about this limit.

**4. Can another household member pull up my private plan?**
No. Continuations are owner-bound: a guest holding the public reference gets
nothing (the public MCP surface has no private-reveal tool), and the private
API rejects mismatched audience, scope, and owner binding. The error response
deliberately does not distinguish "unknown reference" from "forbidden
reference."

**5. Why only four tools? Where are the settings / admin / audience controls?**
Deliberate. Audience manipulation, trust changes, and private retrieval are
*not* exposed as room-facing model tools — that's the security boundary, not
a missing feature. Owner controls live on the authenticated personal surface,
not in the voice channel.

**6. Does it use AI? Is the AI deciding what's private?**
AI interprets intent, resolves ambiguous goals, and proposes plans — inside
the sealed boundary. Deterministic code validates permissions, schedule
arithmetic, dependencies, and external effects. The model never authorizes
its own disclosures. Randomizing a privacy decision would not make the
product more intelligent.

**7. What data does the demo use?**
Synthetic fixtures only — no real calendars, no real personal data. The
reference kernel (`packages/kernel/`) runs on stdlib Python with fixture
labels.

**8. Is this certified / production-ready / secure?**
No. This is a competition entry demonstrating an architecture. The kernel
has no cryptography and no real identity verification
(`evidence/VALIDATION_SUMMARY.md`, "Limits"). Treat every security property
as demonstrated against the reference kernel and synthetic scenarios — not
as a production guarantee.

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `python3 -m unittest discover -s packages/kernel` fails | Wrong working directory, or a non-stdlib Python | Run from the repo root with system `python3`; the kernel needs no dependencies |
| MCP client can't reach the server | Server not running, or wrong URL/port | Start the gateway server (`earshot-server`) per the quickstart; confirm `POST /mcp` answers `initialize` (see `evidence/VALIDATION_SUMMARY.md` for the expected handshake) |
| Inspector shows tools but calls fail | Schema mismatch or stale server | Restart the server; schemas are frozen in `packages/contracts/API_CONTRACTS.json` — extra input properties are forbidden by contract |
| `continue_on_personal_device` says "accepted" but nothing arrived | Accepted means **queued**, not delivered | Check the personal outbox; delivery is acknowledged separately — "never say delivered on enqueue alone" is a design rule, not a bug |
| A plan change didn't apply to my calendar | `resolve_day_change` is draft-only by design | External writes require explicit owner approval on the personal surface, then reconciliation |
| Public output looks "thin" / missing detail | The release policy withheld it | That is the product working: only explicitly released facts leave the boundary. Check the personal continuation for the full plan |

## Known limitations (stated, not hidden)

- Simulator only; no Echo/device integration.
- No production OAuth, no real sensors, no real identity — owner binding in
  the demo is modeled, not cryptographic.
- No latency, audio, or cloud benchmarks have been run.
- Medical, emergency, and financial-advice uses are out of scope.
- Withdrawing a request cannot retract already-emitted speech or completed
  external effects.

## Contact / feedback

- **Hackathon judges:** product feedback and friction log live with the
  submission (Devpost). `docs/ask-amazon.md` lists the product feedback we
  believe Amazon could act on — filed as requests, not invented APIs.
- **Contributors:** open an issue on the repo with the observed behavior,
  expected behavior, and the evidence artifact it traces to. Reports without
  a reproducible trace will be asked for one — that's the honesty rule
  working as intended.
- **Security concerns:** do not file public issues for suspected
  vulnerabilities; use the contact listed on the Devpost submission.

## Support-burden note (for reviewers)

This page exists because support burden is a ship-blocker. Every answer above
traces to the architecture doc, the kernel, or `evidence/` — no invented behavior, no
"coming soon" promises. Where we don't know yet, we say so and point at the
open question instead of inventing an answer.
