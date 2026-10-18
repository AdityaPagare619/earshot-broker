# Race matrix — evidence

Every race: the forced interleaving, what naive kernel use does, what the
guarded (arbiter) path does. Interleavings are forced with explicit
turn-taking (threading.Event), never sleeps.

## Epoch-vs-commit (F1) — tests/races/test_epoch_commit_races.py

| # | interleaving | naive | guarded |
|---|---|---|---|
| 1 | prepare(epoch 1) → audience_changed(epoch 2) → redeem(stale ctx) | RELEASES (over-release) | commit → None (denied) |
| 2 | prepare(v1) → policy_bumped(v2) → redeem(stale ctx) | RELEASES (over-release) | commit → None (denied) |
| 3 | prepare → commit, no race (control) | n/a | releases value + bound segment |
| 4 | commit(gid) → commit(gid) again | n/a | second → None (single-use) |

## Lease invalidation (F4/F5) — tests/races/test_lease_races.py

| # | interleaving | naive | guarded |
|---|---|---|---|
| 5 | redeem(L) → redeem(L) again | RELEASES twice (bearer replay) | second commit → None |
| 6 | redeem ok (epoch 1) → buffer value → epoch 2 → play | PLAYS (unfixable; RR-1) | authorize_playback → False |
| 7 | grant A + grant B pending → withdraw A (epoch bump) | n/a | both denied (sledgehammer; RR-5) |
| 8 | — | kernel has no `revoke_lease` (pinned) | n/a |

## Sensor trust boundary (F6/F7) — tests/races/test_sensor_races.py

| # | interleaving | naive | guarded |
|---|---|---|---|
| 9 | valid evidence, empty audience → project | RELEASES all (pinned; RR-7) | same (policy question) |
| 10 | sensor dead, forged observed_at=fresh → prepare/redeem | RELEASES (indistinguishable; RR-3) | same (trust boundary) |
| 11 | prepare → sensor_died → commit | n/a | None (heartbeat path works) |
| 12 | sensor_died → sensor_recovered → prepare → commit (control) | n/a | releases |
| 13 | readers={'priya','UNKNOWN'}, evidence dead → project | RELEASES (footgun; RR-8) | same (label authoring) |
| 14 | same observed_at, live vs dead sensor → effective_audience | identical (TTL measures timestamp age) | n/a |

## Failure injection — tests/failure-injection/test_failure_injection.py

| # | fault | response |
|---|---|---|
| 15 | freeze `now` at issue time, advance reality 1h → redeem | RELEASES (TTL defeated; RR-2) |
| 16 | frozen `now`=50.5 vs 50s-old evidence → project | RELEASES (TTL defeated; RR-2) |
| 17 | skew +0.1s (inside TTL) | behaves like honest clock |
| 18 | `now` < `observed_at` | denied (control) |
| 19 | accept(v1) → accept(v2, same key) → open | v1 facts (stale; RR-4) |
| 20 | prepare → kill_sensor → redeem | denied (good) |
| 21 | forged observed_at → prepare → redeem | RELEASES (RR-3) |
| 22 | prepare → renderer crash → sweep after TTL | grant swept, nothing half-committed |
| 23 | accept → revoke → open_private | PermissionError('Unavailable') |
| 24 | derive with omitted secret dep → project | PUBLIC label crosses (RR-6) |
| 25 | derive with honest deps | tainted correctly (control) |
| 26 | redeem with wrong-tenant ctx | denied |
| 27 | open house-a capsule as house-b/priya | PermissionError |

## Adversarial inputs — tests/failure-injection/test_adversarial_inputs.py

| # | input | response |
|---|---|---|
| 28 | guessed/empty/malformed receipt | PermissionError('Unavailable'), no oracle |
| 29 | self-minted ctx with controlled_renderer=False | prepare → None; projection → () |
| 30 | audience={'UNKNOWN'} only | denied |
| 31 | Label(readers=∅) | denied except empty-audience (pinned) |
| 32 | epoch=-1, policy_version=0 | redeem → None (equality check denies) |
| 33 | audience={'priya','stranger'} | denied |
| 34 | readers={'priya','ravi'}, audience={'priya'} | allowed (exact subset; pinned) |
| 35 | tenant='' | isolated from 'house-a' (pinned) |
| 36 | redeem after audience gained 'mom' | None (label re-check at redeem) |
| 37 | PUBLIC fact, dead sensor, uncontrolled host | crosses (by design) |

## Latency — evidence/latency.json

Kernel ops p50/p99 over 20,000 iterations: all ≤ 17.1 µs p99. Bounds the
arbiter-response term of the §11.3 sum only. See docs/latency-model.md.
