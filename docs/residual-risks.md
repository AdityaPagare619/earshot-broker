# Residual risk register — J10

Every break that cannot be fixed inside this seat's scope, with its mechanism,
why it is unfixable *here*, the fix shape, and the suggested owner. A risk
leaves this register only when a test proves the fix — never by rewording.

## RR-1 — Redeem-to-playback window (F4)

**Mechanism:** `redeem` returns the plaintext value; a renderer that buffers it
can play it after the epoch advanced. `authorize_playback` refuses stale
segments, but the arbiter cannot reach into the speaker — the check is
voluntary. Demonstrated: `test_buffered_value_plays_after_epoch_advance_naive`.
**Why unfixable here:** the kernel has no audio pipeline and no per-chunk hook;
"already emitted sound remains disclosed" (§11.5) is a physical fact.
**Fix shape:** controlled audio pipeline with per-chunk epoch checks *in the
renderer process*, small chunk sizes, no prebuffering of future sentences.
**Suggested owner:** J2 (simulator/renderer).

## RR-2 — Renderer-controlled clock defeats TTLs (F2)

**Mechanism:** `now` is a caller argument everywhere; a renderer that freezes
`now` defeats the 0.25s lease TTL and the 1.0s sensor TTL simultaneously.
Demonstrated: `test_frozen_clock_defeats_lease_expiry`,
`test_frozen_clock_defeats_sensor_ttl`.
**Why unfixable here:** the kernel has no trusted time source; freshness is a
property of whoever mints the Context.
**Fix shape:** arbiter mints all Contexts with its own monotonic clock;
renderer never supplies time (the test arbiter already does this — production
must too). NTP/clock-sync is then the next trust layer.
**Suggested owner:** J3 (gateway/server).

## RR-3 — Forged sensor timestamps (F7)

**Mechanism:** `observed_at` is caller-supplied; a forged-fresh timestamp is
indistinguishable from a true-fresh one. Demonstrated:
`test_forged_fresh_timestamp_indistinguishable`,
`test_heartbeat_gap_vs_timestamp_age`.
**Why unfixable here:** the kernel sees timestamps, not sensors. TTL measures
timestamp age, never sensor liveness.
**Fix shape:** authenticated sensor channel (signed heartbeats with sequence
numbers, §11.2); heartbeat-loss → expire leases. Liveness must be a *signal*,
not a timestamp.
**Suggested owner:** J2 (sensor/arbiter integration).

## RR-4 — `accept` serves stale facts on revision (F3)

**Mechanism:** idempotency key `(tenant, owner, request_key)` lacks the
blueprint's revision component (§7: `unique(owner, request, revision,
destination)`). Re-accepting a revised plan under the same key returns the old
capsule. Demonstrated: `test_timeout_after_accept_serves_stale_facts`.
**Why unfixable here:** changing the key shape alters the frozen kernel
contract shared with J3/J6.
**Fix shape:** include plan revision in the dedupe key, or version capsules and
return the newest on re-accept (with the receipt remaining stable per revision).
**Suggested owner:** J3 (contracts), J6 (paired-world regression).

## RR-5 — No per-lease revocation (F5)

**Mechanism:** leases have no `revoke()` counterpart; withdrawing one pending
grant forces an epoch bump that denies all pending grants. Demonstrated:
`test_withdraw_one_grant_kills_all_pending`, `test_kernel_has_no_lease_revoke`.
**Why unfixable here:** adding revocation needs a grant registry — the missing
production layer (same as F1).
**Fix shape:** grant registry with per-grant state (pending/committed/
withdrawn); `withdraw_request` marks the grant withdrawn; commit checks the
mark under the serialization boundary.
**Suggested owner:** J3.

## RR-6 — Incomplete dependency declarations launder labels (F8)

**Mechanism:** `Kernel.derive` trusts the caller's dependency list; omitting a
secret dependency yields a PUBLIC-labeled derivative. Demonstrated:
`test_incomplete_derive_launders_label`.
**Why unfixable here:** the kernel cannot observe the planner's true inputs —
only the declared ones.
**Fix shape:** taint tracking at the planner boundary (every value entering the
planner carries its label; the planner API requires labeled inputs), plus the
counterexample generator (§7.4) at review time. Defense in depth, not a kernel
fix.
**Suggested owner:** whoever owns the planner (cross-seat; flag for Petu).

## RR-7 — Empty-audience release (F6)

**Mechanism:** `Label.allows(frozenset())` is True for any label; valid evidence
of an empty room releases secrets into the renderer. Pinned:
`test_empty_audience_releases_everything`.
**Why unfixable here:** it is arguably intended ("nobody listening") — but the
claim "nobody is present" comes from the Context minter (see RR-2/RR-3).
**Fix shape:** policy decision, not code: either keep empty-room release as an
explicit, auditable policy choice, or require a second factor (owner presence
proof) for HIGH-sensitivity facts even in empty rooms.
**Suggested owner:** product/policy (flag for Petu).

## RR-8 — UNKNOWN in label readers (policy footgun)

**Mechanism:** a label with `UNKNOWN` in readers defeats stale-evidence
protection by construction. Demonstrated:
`test_unknown_in_label_readers_is_a_footgun`.
**Why unfixable here:** the kernel is correct per the label; the vulnerability
is in label authoring.
**Fix shape:** label linter: reject `UNKNOWN` (and empty-reader subtleties) in
private labels at policy-compile time; property-test all compiled policies
against the stale-evidence adversary.
**Suggested owner:** J6 (policy/adversarial suite).

## RR-9 — Distributed serialization boundary doesn't exist yet

**Mechanism:** the test arbiter is single-process + `threading.Lock`. Blueprint
§6/§11.1 require one logical sequencer per room in a distributed deployment.
Demonstrated: the arbiter module docstring states the gap explicitly.
**Why unfixable here:** no distributed infrastructure in scope; GIL means even
the tests exercise interleavings, not true parallelism.
**Fix shape:** per-room sequencer (single-writer partition, Raft/Paxos, or
sticky routing to one arbiter instance); linearizable epoch increments.
**Suggested owner:** J1 (deployment profiles), J3.

## RR-10 — Context contamination via renderer memory (§11.4)

**Mechanism:** a renderer that legitimately received a value (empty room,
then occupant enters) retains it in memory/caches. Deleting the transcript
doesn't prove erasure. No test can prove a negative here — documented, not
demonstrated.
**Why unfixable here:** requires renderer-process memory discipline outside any
kernel contract.
**Fix shape:** Profile A (never return revocable secrets to persistent hosts);
Profile B: fresh public context from authorized structured state after audience
changes, never "sanitized" summaries; renderer memory hygiene requirements.
**Suggested owner:** J2, J4 (certification boundary labels).

## Closed or controlled (kept for the record)

- **C-1** Tenant confusion at redeem/open: kernel denies (tests
  `test_tenant_confusion_at_redeem_denied`,
  `test_same_principal_name_across_tenants_isolated`). Residual: a confused
  *renderer* is RR-9's problem, not the kernel's.
- **C-2** Receipt oracle: one generic `PermissionError('Unavailable')` for all
  failure modes (tests `test_receipt_guessing_gives_no_oracle`,
  `test_revoked_capsule...`). Timing oracles out of scope, noted.
- **C-3** Crash between prepare and commit: bearer leases leave no
  half-committed state; arbiter sweeps expired grants
  (`test_crash_between_prepare_and_commit_leaves_nothing`).
- **C-4** Clock regression (`now < observed_at`): denied
  (`test_clock_regression_denied`).
