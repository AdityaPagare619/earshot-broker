# SEAT VERDICT — J5, Developer Evangelist / DX

**Lens:** first-time user, lowest-capability device, 90 seconds to value.
**Scoring:** Design, Idea. **Confidence:** 80.

## What I judged

The kernel (24/24 green), the contracts JSON, blueprint §4.1, and the dossier's
product-experience section — against one question: can a developer go from
`git clone` to trusting this system with a real secret in 90 seconds, on the
weakest device they own?

## What's strong

1. **The kernel is stdlib-only.** This is a DX superpower nobody is bragging
   about: zero install, zero build, runs on a Raspberry Pi, a Chromebook, a
   borrowed laptop. The 90-second clock is winnable *because* of this.
2. **`accept()` / `open_private()` are real primitives** with the right shape —
   stable public receipts, owner-bound sealed capsules, one generic error. I can
   build an honest personal surface directly on them.
3. **The dossier names the 7 onboarding steps** (§4.1) and the NL-rule landmine
   (speaking a secret rule to a shared speaker leaks it). Naming the landmine is
   good. Leaving it without a safe path is not.

## What's weak — what would fail my review

1. **Onboarding is prose, not a path.** §4.1 is seven numbered sentences. There
   is no implementation, no owner, no timer. I cannot demo a checklist. A
   developer evangelist with no runnable onboarding has no story.
2. **The 90-second promise has no artifact and no owner.** "Lowest-capability
   device" appears nowhere in the build plan; the blueprint's TypeScript web
   client points the *opposite* way (build step, browser, npm — the 90 seconds
   die at `npm install`).
3. **The NL-rule landmine has no safe alternative.** The dossier warns: don't
   speak secret rules to the shared speaker. Fine — *where do I write them
   instead?* There is no personal surface. The warning without a path is a
   trap with a signpost.
4. **Auth is a hole.** `open_private` needs `authenticated=True` + tenant/owner
   binding. Nothing mints the owner session, nothing explains it. Without it,
   the "authenticated personal surface" is a fiction the demo can't run.
5. **No "what will the room see" preview exists.** The entire product promise is
   *trust the boundary* — and trust is built by showing, not telling. The
   dossier's demo story needs the owner to *see* the three projections side by
   side. Nobody built the viewer.
6. **Counterfactual privacy is a concept, not a button.** The dossier's
   strongest test (swap prenatal→therapy→nothing; public output must not move)
   has no runnable artifact. An evangelist would ship this as the "prove it"
   moment of every demo.
7. **No one-command setup.** After `git clone`, the next step is "read 57
   pages." The first 90 seconds of every developer's experience are currently
   documentation.

## Verdict

The foundation is honest and testable; the DX surface is vapor. Nothing here is
a reason to redesign the kernel — it's a reason to build the missing surface
with the same honesty: fixture-grade auth labeled as such, a real onboarding
state machine, a per-audience preview, a runnable counterfactual proof, and one
command that does it all in under 90 seconds on stock Python.

**What I'm building (my area):** `apps/personal/` — onboarding that runs,
personal surface that shows, preview that proves, quickstart that times itself.
