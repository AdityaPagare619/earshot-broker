# pro-docs — DESIGN.md

**Lane:** docs/ organization for the public migration. **Base:** main @ c422bae.

## 1. Who reads this and what they need

The primary reader is a **Devpost judge with 90 seconds and a Windows laptop** who
knows nothing about EARSHOT or MCP. Secondary: a developer evaluating the repo.
Both are strangers — no insider knowledge, no seat numbers, no dossier lore.

Judge reading order (the funnel we design for):
1. README → "what is this, why should I care" (30s)
2. `docs/quickstart.md` → "can I run it" (2 min)
3. `docs/architecture.md` → "how does it work"
4. `evidence/` → "prove it's real"
5. `docs/honesty.md` + `docs/threat-model.md` + `docs/residual-risks.md` → "what don't you claim"

Everything in the public docs/ must serve that funnel or a Devpost submission
requirement (product feedback, friction log). Everything else stays private.

## 2. Audit: 51 files categorized

**PUBLIC-JUDGE-FACING (11 — keep):** `ask-amazon.md` (the commercial ask, J7),
`certification.md` (J4 audit, honest), `deployment.md` (the two profiles),
`friction-log.md` (Devpost +10% bonus requirement), `impact.md` (J1 numbers),
`latency-model.md` (J3 honesty), `product-feedback.md` (Devpost requirement),
`quickstart.md` (rewrite — mine), `residual-risks.md` (J10 honesty),
`support.md` (J8 store-listing FAQ), `threat-model.md` (J6 engineering doc).

**Specialist lanes (4 — do not touch):** `api.md`, `architecture.md`,
`honesty.md`, `packs.md`.

**INTERNAL (41 — exclude from new repo, stay in private archive):**
`docs/seats/**` (34 files: j01–j10, s01–s06, pro-ci/packaging/tests/windows
DESIGN.md + SEAT_VERDICT.md) — build process logs, meaningless to a judge;
`docs/dossier/**` (7 files: EARSHOT_REDESIGN.*, IMPLEMENTATION_BLUEPRINT.md,
SOURCE_AUDIT.md, ARCHITECTURE.svg) — the other team's internal reference
material, not ours to publish as product docs.

## 3. What I build

1. `docs/seats/pro-docs/MIGRATION_EXCLUSIONS.md` — exact path list for the
   fresh-repo creation script. Exclusions are a list, NOT deletions: nothing is
   removed from this repo.
2. `docs/README.md` — docs index, judge-first ordering, one line per doc.
3. `docs/quickstart.md` — full rewrite: the old one (`python3
   apps/personal/quickstart.py`, "no installs") is stale post-packaging. New:
   `pip install -e .` → `earshot-demo` → `earshot-server` + curl →
   `earshot-sim`, with PowerShell variants, ports, Python version, troubleshooting.

## 4. Out of scope (explicitly)

- evidence/ curation → pro-evidence lane. My exclusion list flags raw-log
  candidates only.
- The 4 specialist docs → their lanes.
- README.md (root) → pro-readme lane. My docs/README.md links to it.

## 5. Risks

- **Stale commands.** Every shell command in quickstart.md will be RUN, not
  eyeballed. A judge copy-pasting a broken command is a lost judge.
- **Windows drift.** PowerShell variants must be real (quoting, `;` vs `&&`,
  `curl.exe` vs `curl` alias). pro-windows lane is the reference.
- **Jargon leak.** "Seat", "lane", "dossier", "S3" mean nothing to a judge.
  The critic pass hunts these.

## 6. kemiljk critic plan (docs translation)

Judge the docs part-by-part: (a) every command executed; (b) every link
resolves; (c) every timing claim measured; (d) no insider terms; (e) copy
judged against mrstev3n balise-ux-writing (clarity, action, recovery, trust).
Fix, re-verify.
