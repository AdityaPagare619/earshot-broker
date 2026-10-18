# Product feedback — EARSHOT (Alexa+ track)

Feedback on the tools we actually used, from a team that built a real
spec-pinned MCP server and an independent simulator against them.

## 1. MCP specification (2025-11-25, Streamable HTTP)

**What worked.** The spec is precise enough to hand-roll. We implemented the
full Streamable HTTP transport in stdlib Python with no SDK — initialize
handshake, session IDs, tools/list, tools/call, JSON-RPC error codes — and it
interoperates cleanly. The protocol-version negotiation header is the right
call: it caught a real bug for us (see friction log).

**What hurt.**
- The official Python SDK negotiates a *newer* protocol version (2026-07-28)
  than the track pins (2025-11-25). A team that trusts the SDK silently
  violates the track's version pin. Either the SDK should let callers pin a
  max protocol version, or the track should bless the SDK's negotiated
  version explicitly.
- Elicitation (server-initiated) is effectively unavailable on the modern
  protocol, which is fine — but the docs bury this. A one-line "design for
  out-of-band confirmation instead" note would save teams a day.

## 2. Alexa+ track tooling (gated partner access)

**What worked.** The FAQ is honest: gated Alexa+ tooling is not available to
participants, and the independent-simulator path is explicitly blessed. That
honesty let us design *for* the constraint instead of around it — our
simulator is labeled on every screen and every demo beat.

**What hurt.**
- There is no real Alexa+ to develop against, so "works with Alexa+" is
  unverifiable by participants. A read-only sandbox — even a mock that only
  echoes tool calls — would let teams validate integration shape instead of
  asserting it.
- The judging criterion "repo must call the track tech in code" is the right
  bar, but it sits in the FAQ, not the rules page. We nearly missed it.

## 3. Devpost submission flow

**What worked.** The under-3-minute video cap forces concision; the friction
log bonus rewards honesty — both shaped our build for the better.

**Ask.** Let submitters attach the friction log as a file, not just a text
field. Ours has structure (timestamps, severities) that plain text mangles.

---
*EARSHOT — private task broker for Alexa+. github.com/AdityaPagare619/earshot-broker*
