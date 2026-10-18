# Impact — would this ship to 100M devices? Who pays for it?

J1 verdict: the broker pivot is the right product shape; Profile A is the only
shippable profile; the impact story the dossier ships with is incomplete. This
doc completes it with numbers. Every figure traces to `evidence/j01-cost.txt`
(base case) or is labeled an assumption. The model is parameterized
(`services/gateway/config/analysis/cost_model.py`) — reprice inputs, don't
argue with the point estimate.

## The one-line pitch (dossier §15.5, kept)

"Data access, task execution, and room disclosure are different permissions.
EARSHOT demonstrates how to separate them without abandoning the task."

## Who pays: the math

Base case (stated assumptions: 20 requests/device/day, 30% need the bounded
planner, $0.002/planner call):

| Component | $/device/year | Share |
|---|---|---|
| Model inference (planner) | $4.38 | **99.4%** |
| Request infra (API + DB) | $0.01 | 0.3% |
| Encrypted storage | $0.01 | 0.3% |
| **Total COGS** | **$4.41** | |

Scenarios: low $0.24/yr → high $70.16/yr. Sensitivity ranking: the three
multiplicative planner-cost drivers (requests/day, planner fraction,
$/call) dominate; infra and storage never move the answer.

At 100M devices: **~$441M/year COGS** (base). Break-even at 50% gross margin
requires **$0.73/month** per device.

## Who pays: the options, ranked

1. **Amazon bundle subsidy (recommended).** Privacy-as-a-Prime/Alexa+ benefit.
   The product's value is retention and attach, not direct revenue — the same
   logic that funds Alexa's losses. $441M/yr is ~the cost of a mid-size Alexa
   feature team plus inference; it buys a differentiated trust story competitors
   can't copy without the same architecture. This is the VP's pick: the margin
   comes from Prime retention, measured in churn basis points, not from the
   feature's own P&L.
2. **Consumer subscription attach ($0.99/mo tier).** Break-even needs $0.73/mo
   at 50% margin, so $0.99/mo clears it with headroom — *if* attach rates hold.
   Risk: privacy features have historically weak willingness-to-pay; the buyer
   is the household's most privacy-sensitive adult, not the account holder.
   Viable as an Alexa+ premium tier, weak as a standalone SKU.
3. **Skill-developer B2B2C.** Rejected for v1: no skill developer will pay
   $4.41/user/year to *reduce* their own data access. The incentive points the
   wrong way.

**The lever that matters:** planner-call gating. Every request served by a
deterministic path (receipt, precomputed plan, cached projection) instead of
the planner is $0.002 saved. Cutting the planner fraction from 30% to 15%
halves COGS. This — not infra optimization — is the engineering roadmap's
economic center.

## Distribution (execution doctrine: distribution second, idea third)

- **First-party feature (18-month horizon).** Needs the dossier's three
  critical Amazon asks (§15.4): signed requester/surface/audience context,
  an ephemeral no-memory channel, output-lease validation. These are real,
  carry-able asks — the most undervalued asset in the dossier.
- **Alexa+ add-on (partner-gated).** The dossier admits builder tools are
  partner-gated; the competition explicitly permits the independent simulator.
  Viable for the hackathon, not a distribution plan.
- **Open-source self-host.** Not distribution — no moat, no support, no
  revenue. The §12 trace-harness is a good mini-challenge contribution, not a
  go-to-market.

Pick lane 1. Everything else is demo or community.

## Design critique: lead with the shippable profile

The video outline's hero beat (0:40–1:05: Mom walks in, lease invalidated) is
Profile B — the profile that *cannot ship* (no sensing exists; §11.3 admits
undetected entry has no finite stop bound). A Devices VP's first question
will be about the sensing, and the answer ("simulated") will taint the
shippable Profile A by association.

**Reorder the story:** open with the sealed-task utility (0:15–0:40: "organize
my afternoon" → useful plan, private reasons never leave the boundary), keep
the walk-in beat clearly labeled as a controlled-host research demo, and close
on the Amazon asks. The interruption is the sizzle; the sealed task is the
steak. Ship the steak.

## What would make me sign the PRD

1. Measured full-path p50/p95/p99 over a network (J3) — kernel time is
   necessary, not sufficient.
2. Planner-call gating design with a target planner fraction and a measurement
   plan (the economic center of the roadmap).
3. Tenant-isolation adversarial suite green (J6) — the #1 Sev-1 vector at scale.
4. The three Amazon asks filed as product feedback with owner names attached.
5. A 5-household usability study: can owners state a disclosure preference and
   complete a plan faster than the phone-only baseline? (dossier §15.5 —
   validate impact with studies, not adoption statistics.)

## Residual risks (honest)

- Model pricing moves: at $0.008/call (high scenario), COGS hits $70/yr and
  the subscription math breaks. Hedge: planner-call gating + small-model
  distillation are roadmap items, not solved problems.
- The coercive-household exclusion (§5.2) is honest but shrinks the safety
  narrative; the commercial story must be *utility with discretion*, never
  safety.
- 100M-device request volume (~23k rps avg) needs real load engineering;
  nothing in this build has seen a network.
