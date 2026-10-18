# SEAT VERDICT — J8: Sr Manager, Device Appstore (product quality bar)

Lens: Design, Impact. Signature question: "Store listing, ratings, support
burden, obvious-vs-creative line." Confidence: 78.

## What I reviewed

Seed README, `evidence/VALIDATION_SUMMARY.md`, dossier §1–3 + §15.4–15.5 + §16,
the 4 tool contracts, the 24-test kernel (all passing), and the honest-boundaries
language across the dossier. I am judging the **public surface** — what a judge,
a store reviewer, or a user sees first — not the kernel internals (J3/J6's job).

## Verdict: the engineering is unusually honest; the public surface is not yet shippable

The dossier's honesty is the project's moat — §2.2's evidence corrections, the
refusal to reuse unverified benchmarks, the explicit "we do not claim to
intercept all Alexa output" line. That honesty is rare and it is exactly what
survives an Appstore review. But the current README does not yet convert that
honesty into a **listing**. It reads as a research repo that happens to mention
a hackathon. A store listing must do three jobs in 30 seconds: *what is it, why
should I care, why should I trust it.* The seed README does job 1, fumbles job
2 (the Priya moment is buried under operating principles), and does job 3
backwards (it leads with architecture, not with the trust evidence).

## Strengths (keep, amplify)

1. **Honest-claims discipline is Appstore-grade.** The "Status (honest)" section
   and the traceability rule ("every claim must trace to evidence/") are the
   single strongest listing asset. Most hackathon repos die at review because
   they overclaim; this one is structurally incapable of it. Amplify: make the
   honesty *visible* in the first screen, not a section header.
2. **The one-liner works.** "EARSHOT keeps helping when the room stops being
   private" is a listing headline, not a README subtitle. It names the user
   outcome, not the mechanism. Keep it; promote it.
3. **§15.5's defensible pitch is quotable.** "Data access, task execution and
   room disclosure are different permissions" — that is the store-listing
   sub-headline. It survives a hostile reading, which is the only kind that
   matters.
4. **The 70 decisions (§16) are a trust artifact.** Appstore reviewers and
   judges both scan for "did someone think about the edges." Decisions 5–10
   (explicit non-goals, no medical scope, label the simulator) are listing
   copy waiting to happen.

## Weaknesses (each would cost us in my review)

1. **No obvious-vs-creative argument anywhere in the public surface.** The rules
   explicitly name "basic MCP wrapper" as the obvious line and this project
   clears it by a mile (sealed tasks, counterfactual privacy, lease
   invalidation) — but the README never says so. A judge skimming for the
   obvious/creative line will not find the sentence that places us. This is
   the highest-leverage missing paragraph in the repo.
2. **No support surface at all.** No FAQ, no troubleshooting, no "what to do
   when it doesn't work," no support contact path. Appstore lens: support
   burden is a ship-blocker. For a hackathon the analog is judge friction —
   every unanswered "but what about X?" is a point lost. `docs/support.md`
   must exist and must answer the 8 questions a skeptical user asks.
3. **The demo moment is buried.** The Priya walk-in (dossier §4) is the
   emotional core and it appears nowhere in the README's first screen. Store
   listings lead with the human moment, then the mechanism. Current order is
   inverted.
4. **Claims lack inline traceability.** "24-test reference kernel" is stated;
   the evidence file is not linked at the point of claim. A reviewer should be
   able to click from any number to its artifact in one hop. Fix: every
   measured claim gets its `evidence/` link inline.
5. **Non-goals are present but soft.** "No device connection, no production
   OAuth" is listed — good — but it reads as an apology. Reframe: boundaries
   are a *feature of the listing* (what we don't claim is why you can trust
   what we do). The Appstore rejects apps that overclaim; state the boundary
   as a positive.
6. **No ratings/reviews thinking.** Hackathon analog: the friction log and
   product feedback are the "reviews." The README should point at them the
   way a listing points at reviews — social proof of honesty. Currently
   unlinked from the public surface.
7. **Accessibility and multi-adult households (§15.5) are unaddressed in
   public copy.** The dossier flags the mother-in-law stereotype risk; the
   README should show the product serves multi-adult households generally,
   not one anecdote.

## What would fail in my review (ship-blockers)

- **S1.** Public surface never argues the obvious-vs-creative line → judge
  cannot place us above "basic MCP wrapper" on a skim. **Fix: dedicated
  section, explicit.**
- **S2.** Zero support surface → support-burden question unanswered. **Fix:
  docs/support.md with FAQ + troubleshooting + contact path.**
- **S3.** Any claim without a one-hop evidence link → trust failure. **Fix:
  inline evidence links on every number.**

## What I am building (this seat)

1. `README.md` rewritten to store-listing quality: headline → human moment →
   the creative-line argument → how it works (brief) → honest boundaries as
   trust → evidence-linked claims → layout → run instructions.
2. `docs/support.md`: FAQ (8 skeptical questions answered), troubleshooting
   table (symptom → cause → fix), support contact path, known limitations.
3. `docs/why-not-obvious.md` — or the argument inline in README: the
   obvious-vs-creative case, explicitly mapped to the rules' language.
4. Every claim traceable: inline links to `evidence/`.

## Residual risks I am NOT covering (flagged for other seats)

- J2 owns the simulator's human feel; I will not duplicate demo mechanics.
- J4 owns failure-path tests; my troubleshooting table references their docs
  where they exist and marks gaps honestly where they don't.
- J7 owns the ask-amazon/product-feedback doc; my README links to it rather
  than restating it.
- The kernel has no cryptography or real identity (evidence says so); my copy
  must never imply otherwise — I will police my own adjectives.

## Scores (my lens, current state → after my build)

- Design (public surface): 55 → 80 (target)
- Impact (listing persuasiveness): 50 → 78 (target)

The gap is all in the public surface, not the engineering. That is exactly
what this seat exists to close.
