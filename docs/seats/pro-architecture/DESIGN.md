# pro-architecture — DESIGN.md

**Lane:** architecture doc · **Branch:** `pro/pro-architecture`
**Deliverable:** `docs/architecture.md` — the sealed-speech architecture for a senior
engineer who has never seen this project. Readable in 15 minutes.

## Audience

A senior backend/systems engineer (or a Devpost judge with technical depth) opening
the repo cold. They know what MCP is, roughly. They have 15 minutes, not 3 hours.
They will decide in the first 2 minutes whether the architecture is real or theater —
so the doc leads with the invariant and the mechanism-per-problem-class table, and
every structural claim names the module that enforces it.

## Structure (why this order)

1. **The stronger question** — the pivot from answer-filter to private task broker,
   in 3 sentences. If they read nothing else, they get the idea.
2. **The invariant** — "Alexa can't leak what it was never told — and the room can't
   learn what it can't tell apart." One line the whole doc hangs from.
3. **Three Seams** — each seam: what it enforces, the problem class it eliminates,
   the enforcing modules. Table form. This is the "mechanisms, not policies" proof.
4. **The 7 laws, compressed** — one line each + the enforcing mechanism. Laws without
   enforcement are slogans; each law names its code.
5. **The pipeline** — quarantine → belief → seal → constant shape → phone.
   ASCII dataflow with stage ownership (slow lane / sealed boundary / hot lane).
   Module paths per stage.
6. **The 6-tool surface** — compact table: tool, what the caller says, what it does,
   where it lives. Plus the deliberately-absent list (what is NOT a voice verb).
7. **Deployment profiles** — A (shippable) vs B (demo), honest framing, ProfileGate.
8. **Kernel vs Household Pack** — the IAM lesson; what forks and what never does.
9. **Evaluation** — the privacy SLO, the measured numbers with evidence pointers,
   counterfactuals as test grammar, negative control. No number without a file.
10. **Threat model summary** — one paragraph + pointer to docs/threat-model.md
    (owned by pro-threat lane; this doc does not duplicate it).
11. **Honest boundaries** — what we don't claim, kill conditions. Short.

## Distillation decisions

- Source is ~700 lines (FINAL-ARCHITECTURE.md); target ~300. Cut: the 5-beat demo
  script (belongs in demo docs), the build plan table (internal), the FAANG pattern
  table (keep one line — the IAM lesson — drop the rest), the full YAML data model
  (keep the 6-line essence: Item states, SecrecyEdge, GeneralizationChain d4→d0,
  DisclosureTable row, Lease).
- Keep verbatim: the one-liner, the stronger question, the invariant, ε(s) formula,
  the 6 tool names, the AUC numbers (0.497 vs 0.928, seed 7, n=200, evidence-linked).
- Every module path verified against docs/seats/pro-packaging/DESIGN.md §2 and
  spot-checked in the worktree (broker.py tool defs, credible.py ε, chain.py d4→d0,
  gate.py MonotoneGate, budgets.py ExposureLedger, config/gate.py ProfileGate,
  integration/pipeline.py SealedSpeechPipeline, slo-report.md AUC table).

## Risks

1. **Drift from code** — mitigated by the verification pass above; module names are
   the contract's, not the synthesis doc's.
2. **Duplicating sibling lanes** — docs/threat-model.md and docs/api.md belong to
   pro-threat / pro-api-docs; this doc summarizes (one paragraph / one table) and
   links, never duplicates.
3. **Over-claiming** — every metric points at evidence/; the "what we don't claim"
   section is not optional.

## kemiljk critic log

- Draft 1 risk: opening with philosophy before mechanism — critic would flag
  "theater before proof." Fixed: invariant + seam table in the first screen.
- Draft 1 risk: 7 laws as prose paragraphs — unreadable. Fixed: one line each,
  mechanism named.
- Check after writing: every `earshot.*` path in the doc resolves in the worktree
  (grep-verified); every number has an evidence pointer.
