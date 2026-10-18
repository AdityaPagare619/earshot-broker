# EARSHOT — documentation index

Start here if you're evaluating this project. Ordered the way a judge reads:
**run it → understand it → believe it → know its limits.**

## Run it

- [**quickstart.md**](quickstart.md) — clone → `pip install -e .` → the 5-beat
  demo, the MCP server, and the simulator, in about 2 minutes. Windows,
  macOS, and Linux covered.

## Understand it

- [**architecture.md**](architecture.md) — the sealed-speech architecture:
  three seams (quarantine → seal → constant shape), the 6 MCP tools, and why
  the model proposes but deterministic code disposes.
- [**api.md**](api.md) — every MCP tool and resource: request/response shapes,
  auth, error codes, wire examples.
- [**deployment.md**](deployment.md) — the two honest deployment profiles:
  which one ships, which one is demo-only, and the exact switch between them.
- [**packs.md**](packs.md) — the Household Pack: how regions, languages, and
  household roles customize the system without touching code.

## Believe it

- [**threat-model.md**](threat-model.md) — what we protect, from whom, and the
  narrow guarantees the kernel actually makes. Anything not listed as
  guaranteed is not guaranteed.
- [**latency-model.md**](latency-model.md) — honest latency: what we measured
  (p99 2.54ms HTTP round trip, N=200), what we can't measure here, and the
  worst-case exposure sum after a listener physically enters.
- [**impact.md**](impact.md) — would this ship to 100M devices? Who pays for
  it? The cost model with every assumption labeled.
- [**certification.md**](certification.md) — certification audit against the
  guidelines as written: what passes, what fails, and the open question only
  Amazon can settle. Not a certification claim.
- [**ask-amazon.md**](ask-amazon.md) — the partnership ask: what we'd need
  from the Alexa+ platform team, with proposed semantics. Requests, not demands.

## Know its limits

- [**honesty.md**](honesty.md) — what this is and isn't: real MCP server,
  independent labeled simulator, fixture data. Read before citing any number.
- [**residual-risks.md**](residual-risks.md) — every break we can't fix in
  this codebase, with mechanism and suggested owner. A risk leaves only when
  a test proves the fix.
- [**support.md**](support.md) — FAQ and troubleshooting, answered honestly —
  including "does this work on my Echo?" (no) and what we don't cover yet.

## Submission paperwork

- [**product-feedback.md**](product-feedback.md) — feedback on the tools we
  used (MCP spec, Alexa+ gating, Devpost flow), from a team that hand-rolled
  the transport.
- [**friction-log.md**](friction-log.md) — what slowed us down and what we got
  wrong, timestamps included. The SDK version-negotiation trap is P0.

---

**Evidence** lives in [`../evidence/`](../evidence/) — measured numbers only,
each traceable to the test or script that produced it. Raw build logs and
internal working notes stay in the project's private archive; they document
how this was built, not what it is.
