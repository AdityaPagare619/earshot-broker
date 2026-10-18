# EARSHOT — a private task broker for Alexa+

**Secrets have audiences. Rooms have beliefs. Speech has memory.**

[![CI](https://github.com/AdityaPagare619/earshot-broker/actions/workflows/ci.yml/badge.svg)](https://github.com/AdityaPagare619/earshot-broker/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-643%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue)
![stdlib](https://img.shields.io/badge/dependencies-stdlib%20only-lightgrey)
![license](https://img.shields.io/badge/license-MIT-green)

December 2019: a family's Instax camera — a Christmas surprise — was spoiled
because a shared smart speaker announced the delivery where everyone could
hear it. The speaker wasn't hacked. It worked exactly as designed. That's the
problem: **a smart speaker broadcasts to a room, but it was built as if the
room were one person.**

EARSHOT asks the stronger question. Not *"how much of this private record may
Alexa read aloud?"* — any answer to that is a filter, and a recommendation can
reveal a secret without using a single one of the secret's words. Instead:
**can the assistant finish the user's task without giving the room-facing
assistant the private record at all?** Private facts stay inside a sealed
processing boundary. The room hears only explicitly released facts. The task
continues on the owner's phone — not from scratch, from where it left off.

## Try it in 2 minutes

```bash
git clone https://github.com/AdityaPagare619/earshot-broker.git
cd earshot-broker
pip install -e ".[test]"
```

```bash
earshot-demo --lang en        # the 5-beat sealed-speech story (also --lang hi)
earshot-server --port 8899    # real MCP server (spec 2025-11-25, Streamable HTTP)
earshot-sim                   # labeled independent simulator, Echo-class UI
python -m pytest              # 643 tests, one command, ~30s, zero env vars
```

Windows, macOS, Linux. Python 3.10–3.12. Zero dependencies outside the
standard library — that constraint is a feature, and CI proves it on all
three OSes.

## The six MCP tools

A real self-hosted MCP server ([spec 2025-11-25](https://spec.modelcontextprotocol.io/),
Streamable HTTP, hand-rolled on stdlib). Tool schemas:
[`packages/contracts/API_CONTRACTS.json`](packages/contracts/API_CONTRACTS.json).

| Tool | What it does |
|---|---|
| `prepare_day_brief` | Build a day plan from the owner's connected sources; return only explicitly public facts |
| `resolve_day_change` | Revise a sealed plan under new constraints without returning the private reasons |
| `continue_on_personal_device` | Hand the task to the owner's registered personal surface — accepted means *queued*, never "delivered" on enqueue |
| `withdraw_request` | Withdraw pending work and unreleased output. Cannot unsay emitted speech — stated plainly, because revoking access is not erasing knowledge |
| `room` | Declare who's present ("mom just walked in"). The answer is always the constant-shape *"Noted."* — it never confirms or denies anything |
| `keep_secret` | Instant tighten ("don't tell Maya about the gift"), effective immediately through the monotone gate |

Deliberately **not** exposed as room-facing tools: audience manipulation,
trust changes, private retrieval, owner approval. The surface is small on
purpose.

## Why this isn't a basic MCP wrapper

| A basic wrapper does | EARSHOT does |
|---|---|
| Passes records through, maybe redacted | **Sealed tasks** — the private record never enters the room host's context. There is nothing to redact because nothing private was sent |
| Filters words in an answer | **Counterfactual privacy** — change the hidden appointment (or remove it) and the public output must not reveal the difference: not through text, counts, status, metadata, or notification behavior |
| Trusts whoever is in the room | **Lease invalidation** — an audience change invalidates pending disclosure leases; a late segment from the old room state is rejected |
| Lets the model decide what's safe | **Deterministic boundary, useful AI inside it** — AI interprets intent and proposes plans; deterministic code validates permissions, schedule arithmetic, and external effects. The model never authorizes its own disclosures |

## How it works: three seams

1. **Quarantine** — nothing untrusted reaches the hot path. Every ingested
   item is quarantined and verified by a deterministic 4-check verifier
   (entity / topic / quasi-identifier / monotonicity, multilingual) before it
   can be spoken about. *Kills the problem class: untrusted input shaping
   speech.*
2. **The seal** — private facts never cross into the room-facing host. Belief
   about who's present fuses declarations with asymmetric trust (a voice
   "I'm alone" can only loosen low-sensitivity items); a minimax planner
   speaks to the worst credible listener. *Kills the problem class: the host
   knowing too much.*
3. **Constant shape** — spoken output is conditionally independent of withheld
   content. Two briefings — one with a hidden appointment, one without — come
   out byte-identical. *Kills the problem class: the shape of the answer
   leaking the secret.*

One law above all: **the model may make you more private, never less.**
Loosening requires an authenticated owner act. Full architecture:
[`docs/architecture.md`](docs/architecture.md).

## Proof, not promises

Adversarial listener, 200 paired worlds per policy, existence AUC
(chance = 0.50):

| Speaker policy | Existence AUC |
|---|---|
| Normal assistant | 0.928 |
| Keyword filter | 0.921 |
| Word-filter lattice (our retired prototype) | 0.875 |
| **EARSHOT sealed-speech** | **0.497** |

Against a keyword-counting listener (a deliberate lower bound on attacker sophistication),
an eavesdropper guessing from EARSHOT's speech does no better than chance (AUC 0.497).
Stronger attackers (topic models, LLM listeners) are future work, not a claimed result.
Utility stays 1.000, added friction 0.060. Evidence:
[`packages/trace-harness/evidence/slo/slo-report.md`](packages/trace-harness/evidence/slo/slo-report.md)
· wire-level paired-world byte-identity with negative controls:
[`evidence/constant-shape-results.txt`](evidence/constant-shape-results.txt)
· kernel suite (24/24):
[`evidence/kernel-tests.txt`](evidence/kernel-tests.txt)
· what was checked and what was not:
[`evidence/VALIDATION_SUMMARY.md`](evidence/VALIDATION_SUMMARY.md).

## Alexa+ track compliance

- **Real MCP server**, called in code — not a README mention. Hand-rolled
  Streamable HTTP server pinned to spec 2025-11-25 (we caught the SDK
  negotiating a newer version and pinned by hand; the trap is documented in
  [`docs/friction-log.md`](docs/friction-log.md)).
- **Simulated Alexa+ experience** via an independent, honestly labeled web
  simulator in-repo — the competition's gated Alexa+ tooling is unavailable
  to participants, and the rules explicitly bless the simulated path.
- **<500ms round trip**: measured client-side p99 **8.6ms** (N=200,
  `prepare_day_brief` over loopback; budget 500ms — 58× margin), kernel ops in
  microseconds —
  [`services/gateway/mcp/evidence/latency.json`](services/gateway/mcp/evidence/latency.json)
  (frozen 2026-10-18; test runs write `latency.measured.json` instead).

## What we don't claim

- **No universal Alexa interception.** An MCP add-on runs when Alexa routes a
  request to it. It is not a mandatory layer around built-in announcements,
  other integrations, or retained history. We protect EARSHOT's own
  workflows; we do not claim to gag Alexa.
- **No real device, no production OAuth, no real sensors.** Clearly labeled
  simulator, synthetic data throughout.
- **No certification claims.** A competition entry, not a certified product.
- **No inflated evidence.** Community incidents in our research are
  illustrations, not statistics. Earlier benchmark-style claims from a retired
  prototype are not reused — they weren't verifiable, so they aren't repeated.
- **No medical or emergency scope.** Day planning only.

## Layout

```
pyproject.toml            pip install -e .  →  earshot-demo / earshot-server / earshot-sim / earshot
src/earshot/              importable package (stdlib only)
packs/                    household data packs (base taxonomy, EN + HI/Hinglish)
demo/                     5-beat sealed-speech demo runner (EN + HI)
services/gateway/mcp/     real MCP server (2025-11-25, Streamable HTTP)
services/gateway/adapters/  source-adapter contract (calendar, tasks)
apps/simulator/           independent web simulator (labeled, Echo-class UI)
packages/kernel/          reference kernel — labels, sealed tasks, leases (FROZEN)
packages/slowlane/        seam 1: quarantine, verifier, Disclosure Table compiler
packages/hotlane/         seam 2: belief fusion, credible sets, minimax planner
packages/secrecy/         secrecy graph + monotone gate (the only edge mint)
packages/trace-harness/   open-source paired-world privacy testing + SLO lab
integration/              pipeline wiring S1→S2→S3→S4 through frozen ports
tests/                    unified suite — python -m pytest, 643 tests
docs/                     architecture, quickstart, API, threat model, honesty
evidence/                 validation summary, test outputs, measured numbers
examples/                 copy-paste starting points
```

## Docs

- [`docs/quickstart.md`](docs/quickstart.md) — install, demo, server, simulator
- [`docs/architecture.md`](docs/architecture.md) — the sealed-speech design
- [`docs/api.md`](docs/api.md) — the six tools, request/response
- [`docs/threat-model.md`](docs/threat-model.md) — explicit threat model and residual risks
- [`docs/honesty.md`](docs/honesty.md) — what was checked, what was not
- [`docs/support.md`](docs/support.md) — FAQ, troubleshooting, contact

## Contributing

Bug reports and pull requests welcome — see
[`CONTRIBUTING.md`](CONTRIBUTING.md). The bar: every claim needs evidence,
every new surface needs a negative control, stdlib stays stdlib.

## License

MIT — [`LICENSE`](LICENSE).

---

*Built for the Alexa+ track of the Build, Ship, Shape: Amazon Developer
Hackathon — [Devpost](https://amazonappdev2026.devpost.com/).*
