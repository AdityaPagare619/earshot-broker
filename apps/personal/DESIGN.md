# DESIGN — J5: personal surface + onboarding + quickstart

**Owner:** J5 (single-threaded). **Type:** 2 (reversible UX surface; CLI command
names treated as Type-1-stable — minimal, frozen early).

## Problem

Turn dossier §4.1's seven onboarding sentences into a runnable path, and give the
owner a personal surface that *shows* the privacy boundary instead of describing
it — all in under 90 seconds, on stock Python, zero install.

## Decisions

1. **CLI-first personal surface, stdlib only.** Lowest-capability device = anything
   running Python 3.10+. No build step, no browser, no npm. The 90-second clock
   starts at `git clone`. A generated `--html` report covers the phone-view case
   without requiring a client.
2. **One command: `python3 apps/personal/quickstart.py`.** Seeds fixtures, runs
   all 7 onboarding steps with safe guided defaults, mints the owner session,
   prepares a day brief through the real kernel, renders the per-audience
   preview, runs the counterfactual proof, prints elapsed time. Deterministic
   seed → reproducible demo.
3. **Onboarding as a real state machine** (`profile.py`), persisted to
   `./.earshot-profile.json` (local, portable, deletable — no home-dir writes).
   Steps map 1:1 to §4.1: connect source → private-by-default → public-ack
   choice → per-field declassification (existence / busy / leave-by / reminders /
   sounds — separate choices) → register personal destination → scope
   explanation → profile explanation. Schema versioned (`profile_version: 1`).
4. **Fixture calendar adapter implements the §3 adapter contract for real:**
   provider identity, fixed scopes, record/field schemas, owner/subjects, field
   labels with private defaults, freshness semantics. It's a fixture *source*,
   not a mock — the contract is the point.
5. **Personal surface = inbox over the kernel** (`inbox.py`): `inbox` lists
   sealed requests (receipt refs only — never private content in listings);
   `open` requires the owner session and calls `open_private`; `preview` shows
   three projections side-by-side (public / controlled-room-under-assumptions /
   personal-full); `approve` binds to a sha256 plan digest and refuses stale
   plans; `prove` runs the counterfactual (swap hidden fact → public projection
   byte-identical).
6. **Demo-grade auth, labeled honestly** (`auth.py`): the owner session is a
   locally generated token in the profile. Every surface that uses it says
   `auth: demo-token (fixture-grade — production needs OAuth/PKCE)`. The kernel
   gets `authenticated=True` only through this session; wrong owner/tenant →
   the kernel's generic `PermissionError('Unavailable')`, never an oracle.
7. **Rules are authored on the personal surface, never spoken.** The CLI prompts
   for sensitive rules privately — this is the safe path the dossier's landmine
   warning was missing.

## Rejected alternatives

1. **TypeScript web client for the personal surface** (blueprint §1 suggests a
   TS web client). Rejected: build step + browser + npm violates
   lowest-capability and blows the 90-second budget at install time. The web
   client remains right for J2's simulator; onboarding must not wait for it.
2. **Real OAuth/PKCE in the quickstart.** Rejected: needs network, client
   registration, and interactive user steps — incompatible with a deterministic
   90-second path. Fixture-grade auth, loudly labeled, with the production
   requirement documented in `docs/quickstart.md`.
3. **Interactive-only wizard, no defaults.** Rejected: pure interactivity taxes
   the first run and makes the 90-second path unreproducible. Guided defaults
   (safe: private-by-default, minimal declassification) with a later
   `personal settings` path to change them. Interactivity is a feature of the
   *second* run, not the first.

## Frozen contracts

- CLI verbs: `quickstart | onboard [--interactive] | inbox | open <ref> |
  preview <ref> [--html] | approve <ref> | prove <ref> | settings`. No new
  top-level verbs without a design note.
- Profile JSON: `{profile_version, tenant, owner, sources[], defaults{},
  declassify{}, destination{}, session{}}`. v1 frozen; v2 migrates.
- Preview output: `{ref, public[], room_assumed[], personal_full[], assumptions[],
  counterfactual_ok}` — the `--html` report renders exactly this.

## Failure modes

- Kernel `PermissionError` → print `Unavailable` (never distinguish unknown from
  forbidden — the CLI must not become an existence oracle).
- Expired/revoked receipt → `Unavailable`, with a private hint to re-run
  quickstart.
- Missing fixture source → onboarding step 1 fails loudly; nothing downstream
  runs on an unconnected source.
- Stale plan digest on approve → refuse with the expected vs actual digest
  prefix; the owner re-opens the current plan.

## Honest boundaries

- Fixture calendar, fixture planner (deterministic slot-finder, NOT the
  dossier's bounded-AI planner), fixture auth. Each labeled at every surface.
- No real sensors, no OAuth, no network. `docs/quickstart.md` carries the
  production-requirements list (from blueprint §11, trimmed to onboarding).
- Timings are wall-clock on this machine, reported as observed, not promised.

## Pre-mortem (top 3)

1. **The quickstart becomes a demo script that rots** — fixture data drifts from
   kernel semantics. Mitigation: the quickstart *is* the test (`test_quickstart`
   runs it end-to-end and asserts the 90s budget and all projections).
2. **Someone mistakes demo auth for real auth** and connects a real calendar.
   Mitigation: the fixture adapter refuses non-fixture sources by construction;
   `connect` only accepts `fixture:` URIs; docs say so in caps.
3. **The preview teaches users the room projection is a guarantee.** Mitigation:
   every preview prints its assumptions (controlled renderer, epoch, policy
   version) and the Profile-A/Profile-B distinction from the dossier.
