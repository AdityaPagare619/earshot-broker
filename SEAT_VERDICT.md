# SEAT VERDICT — J1: VP, Amazon Devices (~30 yrs)

**Lens:** Impact, Design. **Signature question:** "Would this ship to 100M devices? Who pays for it?"
**Confidence:** 75% the broker pivot is the right product shape · 60% Profile A is
shippable within 18 months *if* the three critical Amazon asks land · 20% this wins
the track without a business-model slide. (Forced probabilities, per principal-mindset §7.)

## What's strong (would survive my staff review)

1. **The pivot is the product.** "Can the assistant do the task without giving the
   room-facing host the private record at all?" is a shippable question; "how much
   may Alexa read aloud" is a filter feature. Filters don't get P&L; task brokers do.
2. **Two honest profiles.** Profile A makes *no* claim on host memory, speaker
   control, or sensing — that restraint is exactly what survives a Devices security
   review. Most hackathon pitches die claiming universal interception; this one
   doesn't. Profile A is the only thing I'd let near a roadmap.
3. **The Amazon asks are real asks** (§15.4: signed requester/surface/audience
   context, ephemeral no-memory channel, output-lease validation). A VP can carry
   those into a planning meeting. This is the most undervalued asset in the dossier.
4. **Right-sized starting point.** 24-test in-memory kernel, three processes max
   (§8.2), "do not deploy as ten microservices." Execution-doctrine compliant:
   nobody built the K8s cluster before ten users wanted it.

## What's weak (would fail my review — brutal, specific)

1. **"Who pays for it?" is unanswered. This is the #1 fail.** Zero dollars in the
   dossier. At 100M devices: who runs the gateway — Amazon, the user, a skill
   developer? If Amazon runs it, where's the margin? If it's a paid add-on, who's
   the buyer and what's the ARPU? I greenlight P&L, not demos. My build must answer
   this with a parameterized cost model or the impact story is theater.
2. **Profile B cannot ship as described.** The audience-change stop depends on
   sensing that doesn't exist (no camera eval, no acoustic detection, and §11.3
   admits: undetected entry → no finite stop bound). Profile B is a research demo,
   not a roadmap. Worse: the video outline's hero beat (Mom walks in, lease
   invalidated, 0:40–1:05) demonstrates the *unshippable* profile. The impact story
   must lead with Profile A's sealed-task utility, not Profile B's interruption.
3. **The 500ms budget is unmeasured.** §13.1's allocations are explicitly labeled
   hypotheses. The dossier itself demands (§14.2): measure the network round trip,
   not kernel time. My seat owns this — I will produce measured p50/p95/p99 for the
   full local path and label every assumed component as assumed.
4. **No deployment switch exists.** Blueprint §10 defines profiles as config, but
   `services/gateway/config/` is empty. "Deployment controls owned by the
   operator, not tool arguments a model can set" is currently a sentence, not a
   mechanism. If a model can flip the profile via a tool argument, Profile A is a
   fiction. This is my build.
5. **Tenant isolation is a checklist item, not a tested property.** At 100M
   devices, cross-tenant leakage is the #1 Sev-1 vector. §11 lists it as a gate;
   there is no multi-tenant code path and no negative test. My config layer must
   be tenant-aware by design even if J6 owns the adversarial suite.
6. **No distribution story.** Execution doctrine: distribution second, idea third.
   Paths: (a) Alexa+ add-on — partner-gated, the dossier admits it; (b) first-party
   feature — needs the Amazon asks, 18-month horizon; (c) open-source self-host —
   no moat, no support, no revenue. The §12 trace-harness open-source angle is a
   nice mini-challenge play, not distribution. The impact doc must pick a lane.
7. **Threat-model/commercial tension:** §5.2 correctly excludes "protection from a
   coercive household member" — good honesty, but it also shrinks the addressable
   "safety" narrative. The commercial story can't be safety; it must be *utility
   with discretion* (the §15.5 pitch: "data access, task execution and room
   disclosure are different permissions"). My impact doc will frame it there.

## Verdict on current state

**BANK the architecture, KILL the current impact story.** The broker design and
Profile A survive; everything commercial (who pays, distribution, cost at scale,
measured latency) is missing and must be built before I'd put this in front of
anyone who owns a P&L. My 10 steps build exactly that: real profile switches,
hardening gates as code, measured latency, a parameterized cost model, and
`docs/deployment.md` + `docs/impact.md` that answer "would this ship" and "who
pays" with numbers, not adjectives.

## Pre-mortem (it is Oct 2027 and this failed — why)

1. We demoed Profile B's interruption, judges loved it, and every follow-up
   question was about sensing we don't have. The shippable Profile A never got
   its hearing. → Mitigation: impact doc and demo order lead with sealed-task
   utility; Profile B labeled "research demo" in every telling.
2. A cost model done late showed $15+/user/year in model inference and killed the
   business case in the first finance review. → Mitigation: build the cost model
   NOW (my step 7), with the planner-call as the flagged COGS driver and
   caching/precompute as the named lever.
3. Profile selection lived in docs; a misconfigured deploy ran Profile B
   semantics on a persistent host and leaked. → Mitigation: profiles as immutable
   runtime switches, fail-closed on unknown, never tool-settable (my step 6).
