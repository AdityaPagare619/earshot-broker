# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- New changes go here under Added / Changed / Fixed / Security.
     Every claim needs evidence under evidence/ — see the 1.0.0 entry. -->

## [1.0.0] — 2026-10-18

The sealed-speech release: EARSHOT as a **private task broker**, not an answer
filter. The operating question is "can the assistant accomplish the user's task
*without giving the room-facing assistant the private record at all?*" Private
facts stay inside EARSHOT's boundary; the room-facing host receives only
releasable facts plus an opaque, owner-bound request reference.

### Added

- **Sealed-speech pipeline** — three seams, each eliminating a problem class:
  - **Seam 1, Quarantine** (`packages/slowlane/`): every ingested item is
    quarantined by default; a deterministic 4-check verifier (entity leak,
    multilingual topic leak, quasi-identifier repetition, monotonicity) must
    pass before anything compiles. 68 tests, including a counterfactual with
    an adversarial email arriving 5s before the briefing → byte-identical
    public projection.
  - **Seam 2, Seal** (`packages/secrecy/`): secrecy edges are minted only by the
    MonotoneGate choke point — accept = (TIGHTEN ∧ confidence ≥ 0.6) ∨
    (LOOSEN ∧ valid owner confirmation). Voice claims like "I'm alone" are
    capped at sensitivity 0.7 at ingest (asymmetric trust). 57 tests + a
    2000-case adversarial property suite with negative control.
  - **Seam 3, Constant shape** (`services/gateway/mcp/shape.py`): every tool
    response carries the same envelope (`speak`, `verbatim_no_elaboration`,
    spoken-depth fields, `_meta` plan id + table version); wire-level
    paired-world tests prove secret-swaps under fixed cover audiences are
    byte-identical modulo opaque references.
- **Hot lane** (`packages/hotlane/`): log-odds belief fusion with asymmetric
  trust (ALEXA_HINT can only tighten disclosure; authenticated PRIVATE_NOW is a
  hard override), credible sets, minimax planner against the worst credible
  listener, immutable exposure ledger. 89 tests; planner p99 9.86ms (50 items).
- **MCP gateway** (`services/gateway/mcp/`): hand-rolled stdlib Streamable HTTP
  server, MCP spec **2025-11-25 pinned**. 6 tools: `prepare_day_brief`,
  `resolve_day_change`, `continue_on_personal_device`, `withdraw_request`,
  `room`, `keep_secret`. 91 wire tests over real HTTP; measured round trip
  p99 **2.54ms** against the 500ms budget (`evidence/latency.json`).
- **Controlled web host** (`apps/simulator/`): real MCP client, output arbiter
  with epoch-bound single-use playback grants, Echo-class UI with an explicit
  honesty banner. 35 tests.
- **Household Packs** (`packs/`): taxonomy, role defaults, templates, and
  EN/HI lexicons as inert data — the kernel is universal, customization is
  data. Hot path is language-blind: identical depth decisions in English and
  Hindi. 33 tests including 6 language-blindness proofs.
- **Privacy SLO lab** (`packages/trace-harness/slo/`): seeded synthetic
  households, 4 baseline speaker policies, Mann-Whitney existence AUC,
  counterfactual suites, negative controls. Headline (seed 7, 200 AUC
  triples): sealed-speech **0.497** vs native 0.928 / keyword-filter 0.921 /
  v1-lattice 0.875 — the SLO target is existence AUC ≈ 0.5. `evidence/`
  carries the charts.
- **Trace harness** (`packages/trace-harness/`): paired-world differential
  testing over real HTTP, public-trace only — the project's open-source
  artifact. 16 tests.
- **5-beat demo** (`demo/five_beats.py`, `--lang en|hi`): scripted end-to-end
  run of one evening — the leak, the sealed replay, the "Mom walks in" turn.
- **Professional packaging**: `pip install -e .` → `earshot-demo`,
  `earshot-server`, `earshot-sim`, `earshot`. Zero dependencies (stdlib only).
  One invocation runs everything: `python -m pytest` → **640 passed +
  64 subtests** (~30s). CI on ubuntu/windows/macos × Python 3.10–3.12.
- **Docs**: architecture, API reference (all 6 tools, captured from live
  runs), threat model, pack authoring guide, quickstart.

### Changed

- The v1 answer-filter design (4-level disclosure lattice as the enforcement
  model) is superseded: the lattice survives only as UX labels. The real model
  governs field contents, existence, derived information, action effects,
  recipients, purpose, channel, and persistence.
- The frozen reference kernel (`packages/kernel/`, 24 tests) is re-exposed
  through the `earshot` package but never modified — it is the trust anchor,
  not a work in progress.

### Fixed

- R1 (critical, found by adversarial review): kernel `accept()` idempotency
  returned the victim's receipt to anyone guessing the request key, and
  `open_private` trusted caller-supplied `authenticated=True`. Closed by the
  server-side auth wrapper: idempotency keyed by (tenant, owner, key),
  authentication bound from the Authorization header.
- Arbiter/kernel audience TTL mismatch that made every commit self-deny.
- Port collisions between the trace-harness fixture server and the MCP test
  server in the unified test run.
- Stale hardcoded worktree paths in test helpers; phantom `tests/__init__.py`
  packages shadowing the root suite under pytest.
- Unicode `print()` crashes (Devanagari demo output) on cp1252/cp936/cp932
  consoles — `earshot.wincompat.ensure_utf8_stdout()` wired into all entry
  points.

### Security

- See [SECURITY.md](SECURITY.md) for reporting and scope. Trust boundaries are
  stated narrowly in [docs/threat-model.md](docs/threat-model.md): the kernel
  trusts label assignment (adapters), audience evidence (sensors), and the
  `authenticated` flag — all three are currently **assumptions, not
  verifications**. Residual risks that cannot be fixed in this codebase are
  tracked openly in [docs/residual-risks.md](docs/residual-risks.md) — including
  the redeem-to-playback window and renderer-controlled clock defeating TTLs.

### What this release does NOT claim

- The simulator is an **independent simulator, not a live Alexa+ device**.
  No Amazon device, cloud, or certification is involved.
- The privacy SLO numbers come from **seeded synthetic households**, not real
  homes. The keyword adversarial listener is explicitly a *lower bound* —
  a stronger listener would do better.
- The dev bearer-token auth is a **development stand-in**, not production
  authentication. Profile A (EARSHOT-controlled host) is the only shippable
  deployment profile; the persistent room-facing host profile is documented
  but not recommended.
- Latency figures (kernel ≤17.1µs p99, HTTP p99 2.54ms) were measured on the
  development machine; other terms in the 500ms budget are unmeasurable here
  and labeled as such.

[1.0.0]: https://github.com/AdityaPagare619/earshot-broker/releases/tag/v1.0.0
