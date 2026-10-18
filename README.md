# EARSHOT — private task broker

**"EARSHOT keeps helping when the room stops being private."**

A smart speaker broadcasts to a room. EARSHOT is a room-aware **private task
broker** for Alexa+: instead of filtering how much of a private record Alexa may
read aloud, it accomplishes the user's task **without giving the room-facing
assistant the private record at all**.

Old question: *"How much of this private record may Alexa read aloud?"*
New question: *"Can the assistant accomplish the user's task without giving the
room-facing assistant the private record at all?"*

## Operating principle

1. **Sealed tasks.** Private facts stay inside EARSHOT's processing boundary.
   The room-facing host receives only explicitly releasable facts plus an
   opaque, owner-bound request reference — never the underlying records.
2. **Deterministic security boundary, useful AI inside it.** AI interprets
   private preferences and proposes plans; deterministic code validates
   permissions, schedule constraints, dependencies, and external effects.
   The model never authorizes its own disclosures.
3. **Two honest deployment profiles.** *Persistent public host:* protected facts
   never enter that host's context through EARSHOT. *EARSHOT-controlled host:*
   audience changes invalidate pending disclosure leases and stop future
   output (stated sensing limits; not an Echo-interruption API).
4. **Counterfactual privacy.** Change the hidden appointment — or remove it —
   and the public response must not reveal the difference through text, counts,
   status, metadata, or notification behavior.

## The four MCP tools (spec 2025-11-25, Streamable HTTP)

`prepare_day_brief` · `resolve_day_change` · `continue_on_personal_device` ·
`withdraw_request` — see `packages/contracts/API_CONTRACTS.json`.

## Status (honest)

This repo starts from a 57-page architecture dossier (`docs/dossier/`) and a
24-test reference kernel (`packages/kernel/`). It is **not** a completed Alexa+
integration: no device connection, no production OAuth, no real sensors, no
certification. Every claim in this repo must trace to an artifact in
`evidence/`. The old answer-filter prototype lives on separately; this is a
redesign, not a rename.

## Layout

- `docs/dossier/` — the architecture dossier (md/html/pdf), blueprint, source audit
- `packages/kernel/` — reference kernel: labels, sealed tasks, leases (24 tests)
- `packages/contracts/` — the four proposed MCP tool schemas
- `evidence/` — validation summary, test outputs, traces
- `apps/` `services/` — the competition build (in progress)

## Run the kernel tests

```bash
python3 -m unittest discover -s packages/kernel
```
