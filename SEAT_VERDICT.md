# SEAT VERDICT — J10: Principal Engineer / adversarial red team

**Lens:** Technical Implementation. Signature question: *"Where does this break?
Give me the concrete failure path."*
**Confidence:** 85/100 that every finding below reproduces against the current
kernel. Each will be a test before this seat is done.

## What's strong (credit where due)

1. The kernel's *static* checks are genuinely tight: label join is correct
   (public ⨝ private = private), `UNKNOWN` poisons stale/unevidenced audiences,
   `redeem` re-checks epoch + audience + policy + label at commit time, receipts
   are 192-bit and idempotent, `open_private` raises one generic error (no
   existence oracle). The 24 tests cover the single-threaded contract well.
2. The dossier is honest about what it doesn't claim (§5.2, §11.3, G1–G5 narrowly
   stated). That honesty is the only reason this verdict is about *mechanisms*,
   not *marketing*.
3. Bearer leases are crash-safe by construction: no server-side grant state means
   a renderer crash between prepare and redeem leaves nothing half-committed.

## What's weak — the concrete failure paths

**F1. The kernel has no serialization boundary; epoch-vs-commit races are
untested and, as specified, uncloseable.**
`prepare`/`redeem` are pure static functions. There is no grant store, no lock,
no authoritative epoch. Invalidation works *only if the redeemer honestly
re-reads the current epoch* — i.e., the party being constrained supplies the
constraint. Blueprint §6 mandates "acquire room/renderer serialization boundary;
re-read grant, epoch, policy, data versions." That boundary does not exist in the
kernel. Concrete path: thread A prepares lease L at epoch 1; thread B processes
audience_changed (epoch → 2); thread A's renderer calls `redeem(L, ctx_at_epoch_1)`
— the kernel compares against the *supplied* ctx, sees epoch 1 == 1, and releases
the value. The invalidation never fired because nothing authoritative was
consulted. **This is the single most important race in the system and the kernel
cannot express it.**

**F2. The renderer controls the clock, so TTL and lease expiry are advisory.**
`now` is a caller argument to `prepare`, `redeem`, `effective_audience`, `accept`,
`open_private`. A renderer that freezes `now` at lease-issue time defeats the
1.0s sensor TTL and the 0.25s lease expiry simultaneously. Concrete path: lease
prepared at t=100, expires 100.25; renderer replays `redeem(L, ctx, now=100.1)`
forever — every call succeeds. The kernel cannot distinguish "sensor said 0.5s
ago" from "renderer lied about sensor time." Freshness is a property of whoever
mints the Context, and the threat model must say so.

**F3. `accept`'s idempotency key lacks the revision component the blueprint
mandates.**
Blueprint §7: outbox dedupe key is `unique(owner, request, revision,
destination)`. Kernel `accept` keys on `(tenant, owner, request_key)` only.
Concrete path: owner calls `resolve_day_change` (plan v2) reusing request_key
"day-brief"; the capsule still holds plan v1's facts; the continuation opens v1.
A retried request after a plan revision silently serves the *old* plan's private
facts. Stale-data-on-idempotent-retry — the exact failure the blueprint's
revision component exists to prevent.

**F4. Leases have no sequence number and no candidate digest.**
Blueprint §6: "Bind each segment to `epoch + sequence + candidate_digest`. After
advancing the local epoch, reject any buffered or late segment from an older
epoch." The kernel `Lease` carries (tenant, principal, audience, epoch,
policy_version, expires_at, fact) — no sequence, no digest. Concrete path: two
leases L1, L2 for the same fact at the same epoch; a renderer replays L1's value
as a "new" segment after L2 was superseded — indistinguishable. Worse: a value
redeemed legitimately at epoch 1, buffered by the renderer, played after the
epoch advanced to 2. The kernel denied the *redeem*; nothing stops the *playback*.
"Already emitted sound remains disclosed" (§11.5) is honest, but the window
between redeem and playback is unmodeled and untested.

**F5. No lease revocation primitive.**
Capsules have `revoke()`; leases don't. The only invalidation path is epoch bump
(which invalidates *everything* pending — a sledgehammer) or waiting 0.25s.
Concrete path: owner calls `withdraw_request` for one specific pending release
while another legitimate release is mid-flight — the kernel cannot express
"cancel grant G but keep grant H." Either you nuke the epoch (denying H too) or
you wait out the TTL. The dossier's "cancellation and execution are different"
(§11.5) is correct about emitted audio; it under-specifies pending grants.

**F6. Empty audience releases everything.**
`Label.allows(frozenset())` → `frozenset().issubset(readers)` → **True for any
label**. With valid evidence of an empty room, `room_projection` returns secret
values to the renderer. Physically harmless (nobody's listening), but in Profile
B the value *crosses into the renderer process* on the word of whoever minted
the Context — and per F2, that party may be lying about the room. The
empty-room fast path deserves an explicit test pinning the intended behavior,
because "nobody present" is exactly what a compromised sensor claims.

**F7. Stale-sensor race at the minting boundary.**
`Context(observed_at=...)` is caller-supplied. Concrete path: sensor thread
updates `observed_at` at t=100.0, then stalls (GC pause, IPC backlog); the
arbiter mints Context at t=100.9 with the *last* observed_at=100.0 — fresh by
TTL, dead in reality. The kernel's TTL check measures the age of the *timestamp*,
not the liveness of the *sensor*. Heartbeat liveness (§11.2: "if sensing stops
heartbeating, expire the lease") is a system property the kernel cannot see.

**F8. `derive` trusts its caller about dependencies.**
`Kernel.derive` *requires* explicit dependencies (good — refuses
dependency-free derivation), but nothing stops a caller from passing an
incomplete dependency list. Concrete path: planner derives "leave at 15:00"
from (PUBLIC_FACT,) while the value was actually computed from SECRET too —
label stays PUBLIC, secret-derived content crosses. Label propagation is only as
complete as the dependency declaration, and the declaration is unaudited.
(Counterexample generator §7.4 is supposed to catch this at review time; at
runtime nothing does.)

**F9. Cross-tenant principal-name collision is tested for `open_private` but the
lease path has no tenant check against the *renderer*.**
`redeem` checks `(lease.tenant, lease.principal, ...) == (ctx.tenant,
ctx.principal, ...)` — but ctx is renderer-supplied (F1 again). A renderer
serving two tenants that mixes up contexts fails open by construction. The
kernel is correct *given honest inputs*; the system must ensure the renderer
can't be confused. Untested.

**F10. The 0.25s lease TTL vs. the 1.0s sensor TTL vs. no audio-chunk checks.**
The dossier says "local checks for each audio chunk" (kernel.py comment) and
"smaller audio chunks reduce queued exposure" (§11.3). The kernel has no chunk
concept at all. Concrete path: a 30-second spoken brief is one lease; the room
changes at second 5; the renderer has no per-chunk revalidation point to consult.
Chunking is entirely the (unwritten) renderer's job — the security property
"stop future chunks after invalidation" (G3) has no kernel-side hook.

## What would fail in my review

- Any claim that the kernel *alone* closes the epoch-vs-commit race. It doesn't;
  the closure lives in the unwritten arbiter layer. My tests will demonstrate
  the race against naive usage and the closure with a serialization boundary.
- Any latency number that measures only kernel functions and presents it as
  "stop latency." §11.3's sum has five terms; I can measure one (arbiter
  response). The other four get labeled, not hand-waved.
- Shipping `accept`'s revision-less idempotency into the outbox path without the
  blueprint's revision component.

## The anti-theater check (principal-mindset §11)

This seat's decay mode would be "race tests that pass because the harness is
rigged" — sleeps tuned so the interleaving always hits. Mitigation: every race
test uses a deterministic scheduler (explicit turn-taking via events/barriers),
not timing; each test also runs a *control* showing the naive path fails and the
guarded path passes. A race test that can't show both is theater.

## Verdict on the current state: PROMOTE the kernel as a reference, BANK the
system claims.

The kernel is a correct, well-tested *decision function*. It is not a
concurrency-safe release mechanism — and it doesn't pretend to be (the comments
say so). My job: build the adversarial evidence that keeps those two statements
from being confused, and name every residual risk with its mechanism.
