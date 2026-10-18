# pro-legal — DESIGN.md

**Lane:** repository governance files (CHANGELOG.md, CONTRIBUTING.md, SECURITY.md,
GitHub issue/PR templates). Written before code, per lane protocol.

## 1. Audience analysis

Three strangers will read these files, each in a different moment:

| Reader | Moment | What they need in <60s |
|---|---|---|
| Devpost judge (Windows laptop, 90s, never heard of MCP) | CHANGELOG 1.0.0 | What shipped, how big the evidence is, what's honestly simulated |
| First-time contributor | CONTRIBUTING.md | How to build, test, and get a PR merged — with the non-obvious rules up front |
| Security researcher / cautious adopter | SECURITY.md | Where to report, what the trust boundaries are, what's explicitly out of scope |

## 2. Facts gathered (all verified from the tree @ c422bae)

- **Version:** 1.0.0 (`pyproject.toml` line 7). MIT license, full standard text, 21 lines,
  copyright "Aditya Kailas Pagare" — VERIFIED complete.
- **Test count:** 640 passed + 64 subtests, one `python -m pytest` invocation (~30s).
  Source: merged foundation verification (pro-tests lane report + parent re-run).
- **Entry points:** `earshot-demo`, `earshot-server`, `earshot-sim`, `earshot` (dispatcher).
- **MCP:** spec 2025-11-25 pinned, Streamable HTTP, 6 tools
  (prepare_day_brief, resolve_day_change, continue_on_personal_device,
  withdraw_request, room, keep_secret). Source: README + pro-packaging report.
- **Privacy SLO:** sealed-speech existence AUC 0.497 vs native 0.928 / keyword-filter 0.921 /
  v1-lattice 0.875 (seed 7, 200 AUC triples). Source: S5 lane / evidence/.
- **Honesty boundaries:** independent simulator (not a live Alexa+ device); fixture data;
  dev bearer-token auth (not production auth); kernel alone closes none of the
  dossier's races (J10 RR register). Source: README, docs/threat-model.md,
  docs/residual-risks.md.
- **Trust assumptions (from docs/threat-model.md §2):** the kernel *trusts* label
  assignment (adapters), audience evidence (sensors), and the `authenticated` flag —
  all three are assumptions, not verifications.
- **Existing .github/:** only `workflows/ci.yml`. No templates exist yet.

## 3. Decisions

1. **CHANGELOG.md** follows Keep-a-Changelog shape (Added/Changed/Fixed/Security
   sections) but stays honest: every metric cites its evidence file. A "What this
   release does NOT claim" section mirrors the README honesty block — a changelog
   that only brags is median slop; the critic would flag it.
2. **CONTRIBUTING.md** leads with the three rules that will surprise contributors
   (stdlib-only, kernel frozen, DESIGN.md-first), then the mechanical path
   (install → `python -m pytest` → PR). Kernel-freeze gets its own section because
   violating it silently is the highest-cost mistake a contributor can make.
3. **SECURITY.md:** reporting via **GitHub Security Advisories** (private),
   deliberately NOT an email address — no personal contact in a public repo, and
   advisories keep the thread attached to the code. Scope section states the two
   trust boundaries that matter (dev bearer-token auth is not production auth;
   the simulator is not a security boundary). Out-of-scope list prevents
   drive-by reports against the fixture/demo surface. Response SLA stated as
   best-effort with a concrete window (acknowledge within 7 days) — an SLA we
   can't keep is worse than none.
4. **Templates:** bug report asks for repro + environment + honesty check
   ("does this involve simulated/fixture behavior?"); feature request asks for the
   problem-class framing (the project's ideology: mechanisms over instances) and a
   no-new-dependencies confirmation; PR template checklist = the merge bar
   (tests green, no new deps, kernel untouched if applicable, honesty preserved,
   docs updated). Short — long templates get deleted by contributors.

## 4. Risks

- **Overclaiming in the changelog.** Mitigation: every number traced to a file;
  the critic pass re-checks each claim against the tree.
- **CONTRIBUTING drifting from reality** (e.g. test invocation changes).
  Mitigation: only document what the foundation lanes verified; no aspirational steps.
- **SECURITY.md implying a maintained security posture we can't staff.**
  Mitigation: explicit "best effort, research/hackathon project" framing and a
  narrow scope — honesty over posture.

## 5. kemiljk critic plan (applied after drafting)

Judge each file against the rubric: Semantics (is every claim true and correctly
scoped?), Layout (does the hierarchy serve the 60-second reader?), States
(edge cases: contributor on Windows, reporter with no GitHub account, PR that
touches the kernel), Fit (do these read like they belong to *this* repo — sealed
speech, honesty-first — or any generic repo?). Name concrete failures, fix, re-verify.
