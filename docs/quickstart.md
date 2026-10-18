# Quickstart — from `git clone` to a private day brief in 90 seconds

**You need:** Python 3.10+, this repo, 90 seconds. No installs, no builds, no
browser, no network. Everything below runs on the weakest device you own.

## The one command

```bash
git clone <this-repo> && cd <this-repo>
python3 apps/personal/quickstart.py
```

That's the whole setup. In well under 90 seconds (measured: <1s on a laptop)
you get:

1. **Onboarding, all 7 steps** — source connected with explicit scopes, private
   by default, public-acknowledgement choice, per-field declassification
   (existence / busy / leave-by / reminders / sounds — separate choices),
   personal destination registered, scope + runtime profiles acknowledged.
2. **An owner session** — demo-grade token, labeled as such everywhere.
3. **A sealed day brief** through the real kernel — receipt, stable public
   message, plan digest.
4. **The per-audience preview** — public vs. controlled-room vs. personal, side
   by side, with stated assumptions.
5. **The counterfactual proof** — the hidden appointment changes
   (prenatal → therapy → removed) and the public output does not move. Byte for
   byte.
6. **`preview.html`** — a single-file report you can open on your phone.

Re-run any time; it reuses your profile (`--fresh` starts over).

## The personal surface

From `apps/personal/`:

```bash
python3 -m personal.cli onboard --interactive   # guided setup, your answers
python3 -m personal.cli inbox                   # sealed requests (refs only)
python3 -m personal.cli open <ref>              # exact plan + labeled facts
python3 -m personal.cli preview <ref>           # what each recipient sees
python3 -m personal.cli preview <ref> --html r.html
python3 -m personal.cli approve <ref>           # approval bound to plan digest
python3 -m personal.cli prove <ref>             # counterfactual proof
python3 -m personal.cli settings                # view declassification choices
python3 -m personal.cli settings --set busy_times=no
```

Write sensitive rules here, on the personal surface — **never speak a rule that
contains a secret to the shared speaker**. A spoken rule leaks through the
room and through host context; no downstream gateway can undo that.

## What each recipient sees (the trust model in one table)

| Recipient | Sees | Why |
|---|---|---|
| Anyone, any host (Profile A) | Weather, team lunch | Only durable-public facts cross |
| Room, controlled host, "alone" assumed (Profile B demo) | + the private appointment | Explicit stated assumption, lease-bound |
| Owner, personal surface | Everything + exact plan + approvals | Owner session, tenant/owner binding |

Listings never contain private content. Unknown/forbidden requests answer
`Unavailable` — the surface is not an existence oracle.

## Honest boundaries (read before demoing)

- **Fixture everything:** fixture calendar, fixture deterministic planner (NOT
  the dossier's bounded-AI planner), fixture-grade auth. Each is labeled at
  every surface that uses it.
- **No real sensors, no OAuth, no network, no audio.** The "controlled host"
  is a stated assumption in this demo, not a measured device.
- **Profile A vs B is load-bearing:** never imply Profile B's controls exist
  in Profile A. The preview prints its assumptions every time.
- Timings are wall-clock observations on the machine that ran them.

## To production (what's missing, no hand-waving)

From the blueprint's readiness gates, the onboarding-relevant subset:

1. Real OAuth/PKCE owner sessions replacing the demo token (kernel already
   takes `authenticated` + tenant/owner binding — the seam exists).
2. A real source adapter implementing the §3 contract (the fixture adapter
   declares the contract; a production adapter fills it).
3. The bounded-AI planner + deterministic solver replacing the fixture
   slot-finder (the plan digest / approval binding already assumes a real
   planner — the interface doesn't change).
4. Cross-tenant tests over every store, private data out of observability,
   secret-independent error shapes (partially demonstrated; not complete).
5. Usability testing that owners actually understand the declassification
   choices (step 4 is the highest-risk UX in this flow).
