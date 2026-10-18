# The ask of Amazon — a partnership proposal, not a wishlist

**From:** the EARSHOT team (Alexa+ track, Build/Ship/Shape hackathon)
**To:** Alexa+ add-ons platform, Alexa Smart Home, AWS BD counterparts
**Date:** 18 October 2026
**Status:** requests with proposed semantics. Not invented APIs. Not demands.

## The trade, up front

We are not asking Amazon for favors. We bring three things a platform team
can use on day one:

1. **A conformance-style test harness** (`packages/trace-harness/`) — paired
   synthetic worlds, public-trace differ, adversarial reference-replay
   fixtures. Any MCP server builder can point it at their server. Amazon's
   certification team could use it as an *input* to privacy review, the way
   test suites feed conformance programs elsewhere.
2. **A reference implementation of the sealed-task pattern** — private task
   brokering with deterministic release boundaries, against the real kernel.
3. **Developer demand signal** — 56,000 hackathon registrants building on the
   same MCP surface; the privacy questions we hit are the questions they
   will hit.

The pitch in one line (dossier §15.5): **data access, task execution, and
room disclosure are different permissions.** EARSHOT demonstrates how to
separate them without abandoning the task.

## The asks, ordered by ecosystem leverage

### 1. Certification guidance for intentional non-disclosure (highest leverage)

**Request:** publish certification guidance covering add-ons that
*deliberately withhold* — silent proactive withholding, private
continuation on a personal channel, and "no dead end" compliance when the
correct behavior is to say less. Today the guidelines (source audit S13:
no dead ends, no silent failures, full workflow) were written for
transactional add-ons; a privacy add-on that says "one private item — sent
to your phone" needs to know what "complete" means.

**Who it unblocks:** every privacy, health, family-safety, and enterprise
add-on — a partner class, not just us.

**Proposed semantics:** a `withhold` outcome is certifiable when (a) the
withholding is logged to an owner-visible surface, (b) a continuation path
exists (personal channel, follow-up intent), and (c) the user can inspect
*why* (owner-visible reason, never spoken). We propose the trace harness's
paired-world report as an acceptable evidence artifact for review.

**What we offer:** the harness + reference implementation as review inputs;
a worked certification walkthrough of our own submission.

### 2. Signed, privacy-preserving requester/audience context

**Request:** a signed context object on the MCP channel carrying:
authenticated requester identity, output surface, and audience evidence —
with an *explicit unknown state* (not an absent field). Servers must be able
to distinguish "audience verified: owner alone" from "audience unverified."

**Who it unblocks:** any add-on making disclosure decisions — without this,
every builder invents (and gets wrong) their own audience plumbing.

**Proposed semantics:** `audience: {members: [...], verified: bool,
observed_at: ts, source: "platform"|"partner"}`; `verified=false` or stale
`observed_at` MUST be treated as unknown, never as empty-and-safe. Signature
covers the tuple; servers reject replays by timestamp/nonce.

**What we offer:** our audience-state machine (kernel `Context`) as a
reference; harness fixtures for stale/replayed audience events.

### 3. Ephemeral / no-memory result channel with enforcement semantics

**Request:** a documented channel whose results the host commits *not to
retain* — with enforcement semantics, not a hint. A `sensitivity` hint that
the host may ignore is worse than nothing: it creates liability without
protection.

**Who it unblocks:** health, finance, and family add-ons whose value
evaporates if every result lands in retained history (source audit S10:
client lifecycle retains interaction history).

**Proposed semantics:** `retention: "ephemeral"` on tool results; host
acknowledges with a retention receipt; audit path lets the owner verify
deletion. If the host cannot honor it, it must *refuse the channel* rather
than silently retain.

**What we offer:** our sealed-task capsule lifecycle as the server-side
half; harness tests for retention-claim vs behavior.

### 4. Output-lease validation at the host renderer

**Request:** for dynamic room speech: lease validation, cancellation, and
played-segment acknowledgement at the renderer. A disclosure decision made
at T+0 against audience A is void if audience B walks in at T+2s and audio
is still playing.

**Who it unblocks:** any voice add-on in shared spaces — the fundamental
race of broadcast audio.

**Proposed semantics:** the server issues output leases bound to
(audience, epoch, policy version); the renderer validates the lease per
audio segment and stops on invalidation, acknowledging played segments.
(Our kernel models `prepare`/`redeem` with exactly these bindings; J10's
race analysis shows the kernel alone doesn't close the distributed race —
we disclose that, and ask for the host half.)

**What we offer:** the lease model + race-harness findings as design input.

### 5. Personal-channel continuation without shared-history pollution

**Request:** a first-class pattern for continuing a task on the owner's
personal device *without* publishing private state into shared conversation
history. Today the choice is "say it in the room" or "abandon the task."

**Who it unblocks:** every multi-device household flow.

**Proposed semantics:** opaque continuation references redeemable only by
the authenticated owner on a personal surface; no private payload in the
shared transcript. (Our `continue_on_personal_device` + capsule model.)

**What we offer:** the working pattern, demoed.

### 6. Elicitation, version, and scope clarifications

**Request:** clarify supported elicitation modes in the Alexa+ MCP profile,
publish initialization version examples that match the pinned spec
(2025-11-25), and resolve the service-scope vs user-scope table
inconsistency (source audit S16).

**Who it unblocks:** every builder — this is table stakes.

**What we offer:** our friction log entries (real ones, including the
SDK-version mismatch and Inspector setup issue we actually hit).

## The AWS production architecture (the real bill)

For the pilot beyond the hackathon, the honest production shape — and the
AWS services it naturally uses:

| Layer | Service | Why |
|---|---|---|
| Bounded private planner | **Bedrock** (private VPC endpoint) | AI interprets preferences and plans *inside* the sealed boundary; data handling documented per request |
| Capsule / receipt keys | **KMS** | envelope encryption for sealed capsules; key per tenant |
| Durable outbox (dossier §16.51) | **SQS** | personal delivery queue; never claim delivered on enqueue |
| Receipts, leases, idempotency | **DynamoDB** | conditional writes give the atomicity the kernel's in-memory maps lack (J10's race finding) |
| Tool serving | **ECS Fargate / Lambda** | Streamable HTTP endpoint, pinned spec version |

Illustrative cost sketch (labeled estimate, not a quote): at 1M sealed
requests/month, the dominant cost is Bedrock planner tokens inside the
boundary, then DynamoDB conditional writes; the deterministic release path
is sub-millisecond CPU. The architecture's cost scales with *private
planning work*, not with rooms or devices — which is the commercial point:
privacy enforcement is the cheap part; useful AI is the metered part.

## Beyond-hackathon roadmap

**Phase 0 — validation (weeks 1–4).** Paired developer interviews (n=8–12)
with Alexa+ add-on builders: can they state a disclosure preference, do
they understand public vs personal output, does the harness catch a seeded
leak in *their* server? Named questions, written up — not "user studies" vapor.

**Phase 1 — pilot (months 2–4).** Gating conversation: certification
discussion (ask #1) with the add-ons platform team. Ship the day-planning
sealed workflow as a public add-on in the Alexa+ store path; the trace
harness as the standalone open-source repo (the additional contribution for
the Open Source track — its own identity, docs, and URLs).

**Phase 2 — partner (months 4–12).** Conversation targets (not commitments):
Alexa+ add-ons platform (certification input), Alexa Smart Home (the
adjacent-device story — J9's lane), AWS (reference architecture publication).
Success looks like: the harness adopted by ≥3 external MCP server projects;
one platform guidance doc citing the sealed-task pattern; a pilot
deployment with measured task-completion vs the phone-only baseline
(dossier §14.1 baseline #4 — the bar the architecture must clear).

## Commercial vehicle options (compared honestly)

| Vehicle | Distribution | Money | Fit |
|---|---|---|---|
| Alexa+ add-on store listing | Amazon's | Amazon's rev-share; we monetize premium sealed workflows | best for reach; certification ask #1 is gating |
| AWS reference architecture | AWS channels | services bill; we monetize hosted broker or support | best for enterprise; needs the auth wrapper (J3) first |
| Open-source harness + standards play | builders | indirect (consulting, hosted) | best for leverage; slowest money |

## Known open items (disclosed, not hand-waved)

- **J6/R1 (critical):** `accept()` idempotency can return a victim's receipt
  to a caller presenting as the victim tenant; `open_private` trusts
  caller-supplied `authenticated=True`. The kernel is untouched by design;
  the fix is an auth wrapper at the API layer (J3's area). Any partner
  conversation leads with this.
- **J10:** the kernel alone closes none of the distributed races
  (prepare/redeem need a grant store, serialization, authoritative epoch).
  The DynamoDB conditional-write design above is the answer; it is not yet built.
- No device integration, no certification, no production security claimed.
  The demo is a labeled simulator; the harness tests synthetic worlds.

## Why this wins the Impact criterion

Judges score Potential Impact on: who benefits, how many, and whether it
survives contact with reality. Our answer: every Alexa+ household with more
than one person in it (the entire installed base); a test harness that makes
*other builders'* privacy claims checkable (ecosystem leverage); and an ask
list that gives Amazon concrete, shippable platform work — with the
conformance tooling to review it. Impact isn't the demo. Impact is what the
demo makes possible for everyone else.
