# Migration exclusion list — paths that stay in the PRIVATE archive

**Purpose:** when creating the fresh public repo, copy the merged tree MINUS
these paths. Nothing is deleted from `earshot-broker`; the exclusions are a
copy filter, applied by the migration script.

**Rule of thumb:** the public repo carries only what a judge or a new
developer needs. Build-process logs, internal dossiers, and raw per-seat
evidence stay private with full history.

## Excluded: internal build logs (35 files)

The entire `docs/seats/` tree — judge/engineer working notes from the J-wave,
S-wave, and pro-wave. They document how the code was built, not what it is.
A judge opening `docs/seats/j06/SEAT_VERDICT.md` learns our org chart, not our
product.

```
docs/seats/j01/DESIGN.md            docs/seats/j01/SEAT_VERDICT.md
docs/seats/j02/DESIGN.md            docs/seats/j02/SEAT_VERDICT.md
docs/seats/j03/DESIGN.md            docs/seats/j03/SEAT_VERDICT.md
docs/seats/j04/DESIGN.md            docs/seats/j04/SEAT_VERDICT.md
docs/seats/j06/DESIGN.md            docs/seats/j06/SEAT_VERDICT.md
docs/seats/j07/DESIGN.md            docs/seats/j07/SEAT_VERDICT.md
docs/seats/j08/DESIGN.md            docs/seats/j08/SEAT_VERDICT.md
docs/seats/j09/DESIGN.md            docs/seats/j09/SEAT_VERDICT.md
docs/seats/j10/DESIGN.md            docs/seats/j10/SEAT_VERDICT.md
docs/seats/s01/DESIGN.md            docs/seats/s01/SEAT_VERDICT.md
docs/seats/s02/DESIGN.md            docs/seats/s02/SEAT_VERDICT.md
docs/seats/s03/DESIGN.md            docs/seats/s03/SEAT_VERDICT.md
docs/seats/s04/DESIGN.md            docs/seats/s04/SEAT_VERDICT.md
docs/seats/s05/DESIGN.md            docs/seats/s05/SEAT_VERDICT.md
docs/seats/s06/DESIGN.md            docs/seats/s06/SEAT_VERDICT.md
docs/seats/pro-ci/DESIGN.md
docs/seats/pro-docs/DESIGN.md
docs/seats/pro-docs/MIGRATION_EXCLUSIONS.md   (this file — migration tooling)
docs/seats/pro-packaging/DESIGN.md
docs/seats/pro-tests/DESIGN.md
docs/seats/pro-windows/DESIGN.md
```

(35 files; j05 produced no seat docs — its deliverable was the CLI itself.)

## Excluded: internal dossier (6 files)

`docs/dossier/` — the partner team's 57-page redesign document and our source
audit of it. It is reference material for the build, not product documentation.
Publishing another team's internal dossier as our docs would misrepresent both.

```
docs/dossier/ARCHITECTURE.svg
docs/dossier/EARSHOT_REDESIGN.html
docs/dossier/EARSHOT_REDESIGN.md
docs/dossier/EARSHOT_REDESIGN.pdf
docs/dossier/IMPLEMENTATION_BLUEPRINT.md
docs/dossier/SOURCE_AUDIT.md
```

## Kept in docs/ (15 public files)

Judge-facing: `ask-amazon.md`, `certification.md`, `deployment.md`,
`friction-log.md`, `impact.md`, `latency-model.md`, `product-feedback.md`,
`quickstart.md`, `residual-risks.md`, `support.md`, `threat-model.md`.
Specialist lanes: `api.md`, `architecture.md`, `honesty.md`, `packs.md`
(do not copy until their lanes merge). Plus `README.md` (the docs index).

## evidence/ — flagged for pro-evidence lane (not excluded by this list)

`evidence/` currently mixes curated proof (AUC chart, latency measurements,
test counts) with raw per-seat logs (`j01-*.txt`, `j06-*.json`, `demo_*.log`,
`simulator-j02/`, `slowlane/`, `hotlane/`, `adapters/`, `trace-harness/`).
The pro-evidence lane curates it; the migration script should take evidence/
**as curated by that lane**, not as it stands here.

## Suggested migration command shape

```bash
rsync -a --exclude-from=<(sed 's/^ *//' MIGRATION_EXCLUSIONS.paths) \
  earshot-broker/ earshot-public/
```

where `MIGRATION_EXCLUSIONS.paths` is the machine-readable form of the two
lists above (one path per line, generated from this file — keep them in sync).
