# SEAT VERDICT — J7: Principal Technical BD, AWS (commercial)

**Lens:** Impact. **Signature question:** "Business beyond the hackathon. What is the ask of Amazon?"
**Confidence scale:** 0–100, per principal-mindset §7. What was known when: dossier +
blueprint + source audit + kernel (24/24 green) + both MCP URLs verified by me
today. No device, no certification, no production security claimed anywhere —
that honesty is load-bearing for everything below.

## The brutal summary

The technology is the most honest privacy architecture I've seen in this
competition. The *business* is currently a demo with a wishlist. My job is to
close that gap: turn §15.4's six bullets into a partnership proposal Amazon
could act on, and turn §12's paragraph into a real open-source artifact that
earns distribution. Everything below is judged against one question: **does
this create a commercial relationship, or just a good submission?**

## What's strong (keep, amplify)

1. **"Requests, not invented APIs" (§15.4) is exactly right BD craft.** Lecturing
   Amazon's spec is how you get ignored; filing actionable requests with
   semantics is how you get a meeting. This instinct is rare and correct. (90)
2. **The trace harness (§12) is the smartest commercial move in the dossier.**
   A conformance-style test harness that other MCP server builders adopt is a
   distribution engine and a de-facto standard position. Standards win markets;
   features win demos. If it's real, it's the highest-leverage artifact in the
   whole program. (85)
3. **The pitch line is partner-grade:** "Data access, task execution and room
   disclosure are different permissions." That reframes EARSHOT from a feature
   into a *platform primitive* — the thing you say in the first 60 seconds of
   an Amazon partnership conversation. (85)
4. **Honest boundaries are BD credibility.** Nothing kills a partnership track
   faster than a claim that collapses in diligence. The dossier's refusal to
   reuse unverified benchmarks (source audit §G) is a commercial asset, not
   just an ethical one. (90)

## What's weak (my build must fix)

1. **There is no business model.** §15.4 is six bullets of product feedback with
   no answer to: who pays, what's the SKU, what's the commercial vehicle
   (Alexa+ add-on store? AWS Marketplace? open-source + hosted?). An Impact
   judge — and any Amazon BD counterpart — asks "who pays for it" within five
   minutes. Today the answer is silence. **This is the single biggest gap.**
   (95 that this fails a real BD review as written)
2. **The AWS story is the thinnest part of the dossier (§13.3).** "Optional
   Bedrock-backed policy/plan proposer only if there is time" is backwards. A
   Principal Tech BD brings the *production* architecture: Bedrock for the
   bounded private planner (data handling documented), KMS for capsule keys,
   SQS for the durable outbox (§16.51), DynamoDB for receipts/leases. That's a
   real AWS bill attached to a real reference architecture — which is what
   makes Amazon the natural *partner*, not just the prize-giver. (80)
3. **The trace harness is vapor today.** §12 is one paragraph of proposal. Per
   source audit S06/S39, merely open-sourcing EARSHOT does **not** qualify for
   the Open Source mini-challenge — it must be an *additional* contribution.
   The harness is that contribution, but only if it exists, runs, is
   documented, and has its own identity/URLs. A paragraph doesn't qualify.
   (90)
4. **"Small user studies" (§15.5) is honest but not commercial.** BD needs a
   named beachhead: which Amazon team (Alexa+ add-ons? Alexa Smart Home?)
   and which builder segment. The 56k hackathon participants are a developer
   *channel*, not customers. The roadmap must name the first three partner
   conversations, not "validate with studies." (75)
5. **The ask risks reading as a support ticket.** Amazon product teams receive
   thousands of feature requests. An ask lands when it (a) unblocks a *class*
   of partners, not just us, (b) proposes concrete semantics, and (c) offers a
   trade. Today's bullets do (a) weakly, (b) barely, (c) not at all. (80)
6. **The certification-guidance ask (§15.4, 5th bullet) is the highest-leverage
   item and it's buried fifth.** Per source audit S13, privacy-driven
   phone-only workflows need certification *discussion* — if Amazon publishes
   guidance for intentional non-disclosure, EARSHOT becomes certifiable and
   every privacy add-on benefits. That's a platform-level ask with ecosystem
   impact. It should lead, not trail. (85)

## What would fail in my review (red lines)

- **R1:** Shipping ask-amazon.md as a bullet list without the trade framing
  (what we offer in return). One-sided asks die in review.
- **R2:** A trace harness that only tests the kernel in-process. That's a unit
  test suite wearing a trench coat — it doesn't touch the actual attack
  surface (the MCP wire trace). Must speak MCP over Streamable HTTP to a
  target server, with a kernel-direct adapter only as self-test.
- **R3:** Any revenue or adoption number without a named source. No "TAM $X"
  slides. Unit economics sketched from the AWS architecture's real cost
  structure, labeled as estimates.
- **R4:** Claiming the harness "qualifies" for the Open Source mini-challenge.
  I build the artifact and document the qualification *argument*; the judges
  decide. (Source audit: "no mini-challenge qualification was performed in
  this research" — that stays true until someone qualifies it.)
- **R5:** Byte-for-byte comparison of full responses as the privacy test.
  Dossier §14.3 explicitly rejects this for non-deterministic projections;
  random request refs must be *independent*, not identical. Normalize, then
  compare — or the harness tests the wrong property.

## Verdict on the current state (from this seat)

**BANK the technology story; the commercial story is not yet shippable.**
The dossier gives me everything I need to build the fix: §15.4 (the asks),
§12 (the harness), §13.3 (the AWS thread to pull), §16 (the 70 decisions as
the credibility substrate). My 10 steps will produce: (1) `docs/ask-amazon.md`
— a partnership proposal, not a wishlist; (2) `packages/trace-harness/` — a
runnable, tested, documented open-source artifact; (3) the beyond-hackathon
roadmap with named beachheads and a real AWS cost sketch. Disagree-and-commit:
the sealed-task architecture stands; I'm commercializing it, not relitigating it.
