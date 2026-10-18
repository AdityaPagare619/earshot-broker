# pro-readme — DESIGN.md

## Audience analysis

**Primary: the Devpost judge.** They have ~90 seconds, a Windows laptop, have
never heard of MCP, and are scoring four criteria: Tech Implementation, Design,
Potential Impact, Quality of the Idea. They will skim the README top-to-bottom
once. If the quickstart doesn't look copy-pasteable in the first screen, we've
lost them. They also check the "obvious" line — the rules explicitly demote
"basic MCP wrapper" work — so the README must make the non-obviousness concrete
in one table, not in prose.

**Secondary: the curious developer.** Clones, runs `pip install -e .`, wants the
demo in under 2 minutes and the test suite green in one command. They read
deeper: tools table, architecture summary, evidence links.

**Tertiary: the future contributor.** Needs layout, docs map, contributing path,
license — bottom of the page is fine.

## Information architecture (top → bottom, 90-second scan)

1. **Title + one-liner + badges** — identity in 5 seconds. Badges: CI
   (ubuntu/windows/macos), tests (640, one command), Python 3.10–3.12, MIT,
   stdlib-only. Badges are promises; every one must be true in CI.
2. **The hook** — Dec 2019 Instax Christmas surprise, 3 sentences. Felt, not
   explained. (Community evidence file exists; the README tells the story.)
3. **What it is** — one paragraph + the one-liner *"Secrets have audiences.
   Rooms have beliefs. Speech has memory."* The stronger question
   ("can the assistant finish the task without giving the room host the
   private record at all?") in bold — this is the Quality-of-Idea payload.
4. **2-minute quickstart** — the money section. Four copy-paste blocks:
   install → demo → server → tests. Nothing else competes for attention here.
5. **Six tools table** — what the MCP server exposes, one line each. Proves
   "repo calls the track tech in code."
6. **Why not a basic wrapper** — 4-row table, concrete mechanisms
   (sealed tasks, counterfactual privacy, lease invalidation, deterministic
   boundary). Answers the "obvious" demotion directly.
7. **Three seams** — 3 tight bullets, each naming the problem class it kills.
   Depth lives in docs/architecture.md (pro-architecture's lane).
8. **Proof** — AUC table (0.497 vs 0.928, n=200, chance 0.50) + evidence links.
   Every number one hop from a file.
9. **Track compliance** — 3 bullets: real self-hosted MCP server, spec
   2025-11-25 pinned over Streamable HTTP, simulated-Alexa+ path is the
   rules-blessed route (gated tooling unavailable to participants).
10. **What we don't claim** — the honesty section (brief non-negotiable #6).
    Non-negotiable, kept tight.
11. **Layout + docs map + contributing + license** — bottom matter.

## What gets cut from the current README

- **docs/dossier/ links** — the dossier stays in the private archive; the public
  repo must not link to files that won't exist. (Migration exclusion.)
- **The ASCII pipeline diagram** — depth belongs in docs/architecture.md.
- **"Run the kernel tests" appendix** — folded into the quickstart.
- **Stale invocations** — `python3 demo/five_beats.py`, `python3 -m trace_harness
  slo` from the package dir: replaced by entry points (`earshot-demo`,
  `earshot-server`, `earshot-sim`) and `pip install -e ".[test]"`.
- **"400+ tests"** — now 640, one `python -m pytest`.
- **"Four task-oriented tools"** — there are six; fixed everywhere.

## URL policy

All in-repo links are relative (migration-safe). Absolute GitHub URLs appear
exactly twice (clone URL, CI badge) and are flagged in my final report for
rewrite when the public repo name is decided — the org/user segment is stable
(`AdityaPagare619`), only the repo slug changes.

## Risks

- **pro-legal hasn't landed** (CHANGELOG/CONTRIBUTING/SECURITY): README references
  CONTRIBUTING.md per the target layout. If pro-legal fails, that's a dangling
  link — flagged in report; Petu's merge verification is the backstop.
- **pro-evidence hasn't landed**: I link to `evidence/` paths that exist today
  (VALIDATION_SUMMARY.md, constant-shape-results.txt, kernel-tests.txt) and the
  SLO dir under packages/trace-harness/evidence/slo/. If pro-evidence moves them,
  links need a sweep — flagged.
- **AUC numbers** are from seed 7 (n=200); README states the n. Seeds 8/9 confirm
  stability (per S5 report) but the README cites the primary run only.

## Critic lenses applied

- **kemiljk_ai-output-judgement**: README is scaffolding until judged — concrete
  failures to hunt: every claim needs a link (semantics), no invented numbers
  (tokens→facts), no template residue ("built with ❤️"), hierarchy must survive
  a 90-second skim (layout).
- **mrstev3n_balise-ux-writing**: mode = Rewrite/Generate for a stranger;
  protect meaning (never soften the honesty section into marketing), one term
  per object ("sealed task", "constant shape", "lease" used consistently),
  actions describe real commands, no usability claims without evidence.
