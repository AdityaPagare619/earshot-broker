# J5 evidence — personal surface + onboarding

**Measured 2026-10-18, worktree seat/j05, Python 3.12, stdlib only.**

## Test results

`python3 -m unittest tests.test_personal` (from `apps/personal/`): **15/15 pass**
(0.1s). Kernel suite untouched and still green: 24/24
(`packages/kernel`, `python3 -m unittest test_kernel`).

| Test | What it proves |
|---|---|
| seven_steps_logged_and_profile_v1 | Onboarding runs all 7 dossier steps; profile schema v1 |
| private_by_default_and_separate_declassification | New data defaults private; 5 declassification fields are independent choices |
| non_fixture_source_refused | `connect` rejects non-`fixture:` URIs by construction |
| adapter_contract_declares_private_defaults | Fixture adapter declares the §3 contract with private defaults |
| listings_expose_no_private_content | Inbox JSON contains no private strings |
| open_requires_valid_session | Bogus token → `PermissionError` |
| open_returns_exact_plan_and_labeled_facts | Owner sees exact plan + per-fact labels |
| wrong_owner_cannot_open | Tenant/owner binding enforced; generic error |
| approve_binds_digest_and_detects_tamper | Approval bound to sha256 plan digest; tampered plan invalidates |
| public_projection_excludes_private | Public sees weather + lunch, not the appointment |
| uncontrolled_host_matches_public | Profile A: room projection == public projection |
| room_assumed_lists_assumptions | ≥3 stated assumptions on every preview |
| counterfactual_public_projection_stable | prenatal → therapy → removed: public output byte-identical |
| counterfactual_variant_actually_changed_private_content | Non-vacuity guard: variants really changed the secret |
| end_to_end_within_budget | Full quickstart < 90s; profile + HTML report written |

## Timed quickstart

`python3 apps/personal/quickstart.py`: **<1s wall clock** (budget 90s) —
onboarding, session, sealed day brief, 3-way preview, counterfactual proof,
HTML report. Deterministic; re-runnable with `--fresh`.

## Claims and their traces

- "Zero-install, lowest-capability" → stdlib only; `python3 -c "import sys"` is
  the only prerequisite. Trace: no requirements.txt exists under apps/personal/.
- "Private by default" → `test_private_by_default_and_separate_declassification`.
- "Listings never leak" → `test_listings_expose_no_private_content`.
- "Counterfactual boundary holds" → `test_counterfactual_public_projection_stable`
  + non-vacuity guard.
- "90 seconds" → `test_end_to_end_within_budget` (measured <1s on this machine;
  reported as observed, not promised for all machines).

## Not claimed

Real OAuth, real sensors, real calendar, the dossier's AI planner, production
security, device integration, certification. See `docs/quickstart.md` § "Honest
boundaries".
