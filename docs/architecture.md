# EARSHOT Architecture — Sealed Speech

> **"Secrets have audiences. Rooms have beliefs. Speech has memory."**

## The stronger question

Every AI assistant whispers to a private screen. A smart speaker **broadcasts to a
room** — it answers the person, but everyone hears.

The old question was: *"How much of this private record may Alexa read aloud?"*
The stronger question is: **"Can the assistant accomplish the user's task without
giving the room-facing assistant the private record at all?"**

EARSHOT is a **private task broker** for Alexa+. Private facts stay inside EARSHOT's
processing boundary. The room-facing assistant receives only explicitly releasable
information plus an opaque, owner-bound request reference. The plan, the private
reasons, and the approvals live in an authenticated personal continuation — the
owner's phone. **The assistant keeps helping even when the room stops being private.**

The one invariant the whole system hangs from:

> **Alexa can't leak what it was never told — and the room can't learn what it
> can't tell apart.**

---

## The Three Seams

A submarine has bulkheads, not one thick hull. Each seam is independently enforced
and independently testable by counterfactual. A mechanism that can't name the
problem class it eliminates doesn't ship.

| Seam | Enforces | Eliminates | Modules |
|---|---|---|---|
| **1 · QUARANTINE** | Nothing uncompiled reaches the hot path. Every new item enters `QUARANTINED`; until the slow lane understands, verifies, and compiles it, the hot path sees only d0 (silence). | Unparsed-data leaks · prompt injection via new arrivals · "the model hadn't finished reading it yet" | `earshot.slowlane` (quarantine, verifier, compiler) |
| **2 · SEAL** | Private facts never cross the broker boundary. Sealed tasks compute inside; the room-facing host gets releasable facts + an opaque request reference — never the private record. You can't be forced to make a host forget what it was never given. | Retained-context re-disclosure · host-memory leaks · "the model was told and later asked" | `earshot.gateway.mcp.broker`, `earshot.secrecy` |
| **3 · CONSTANT SHAPE** | Speech reveals nothing about what was withheld. In cover mode, output shape is a function of the credible set only — never of hidden data. No counts, no ordinals; the fixed suffix is appended even when nothing was withheld; the phone digest is always sent silently. | Existence inference ("one private item" IS the leak) · traffic analysis on speech · cumulative pattern leaks | `earshot.gateway.mcp.shape`, `earshot.hotlane` |

**The invariant across all three:** model-derived or unauthenticated inputs may only
*tighten* disclosure. Loosening requires an authenticated act by the owner.

---

## The seven laws (compressed)

1. **Every secret has a non-audience.** A secret is kept *from someone specific*.
   The secrecy graph infers `about` / `for` / `hidden_from(until)` / `cleared_to`
   edges from content itself. → `earshot.secrecy.edges`, `earshot.secrecy.inference`
2. **The room is a belief, not a fact.** Per-person presence probabilities from
   fused signals; decide against the **credible set** — everyone above a threshold
   that scales with sensitivity: **ε(s) = 0.5 − 0.45·s**. A grocery list tolerates
   uncertainty; a pregnancy does not. → `earshot.hotlane.credible`
3. **Speak to the worst credible listener.** Minimax: the most specific rendition
   every credible listener is cleared for. Deterministic, explainable, fail-closed.
   → `earshot.hotlane.planner`
4. **The room must not be able to tell.** Constant-shape output — spoken text is
   conditionally independent of hidden items given the credible set.
   → `earshot.gateway.mcp.shape`
5. **Disclosure is cumulative.** Per-listener exposure ledgers with decayed budgets;
   the ninth Tuesday "appointment at 3:40" doesn't get spoken.
   → `earshot.hotlane.budgets` (`ExposureLedger`)
6. **The model may make you more private, never less.** AI lives in the slow lane
   behind the monotone acceptance rule: `(TIGHTEN ∧ conf ≥ 0.6) ∨ (LOOSEN ∧ valid
   confirmation)` — nothing else mints a secrecy edge. → `earshot.secrecy.gate`
   (`MonotoneGate`, the only edge minter)
7. **Learn slowly, decide instantly.** The slow lane compiles a Disclosure Table
   (generalization chains, per-person clearance, pre-verified multilingual
   renditions). The hot path fuses belief, takes a minimum, checks budgets,
   assembles text. **No model in the hot path.** → `earshot.slowlane.compiler`,
   `earshot.hotlane`

**Language-blind by construction.** The hot path operates on
`(item_id, depth:int, clearance:int)` — integers, never strings. All language lives
in compiled rendition tables built in the slow lane. A new language is a data task,
never a code change.

---

## The pipeline

```
 OWNER CONSENT + SCOPED SOURCES
 (calendar, reminders, deliveries, notes — each explicitly connected)
        │
        ▼
 ┌─ STAGE 1 · INGEST ──────────────────── SLOW LANE (AI allowed) ─────────┐
 │  normalize → understand → render → verify → compile                    │
 │  AI infers topics, subjects, non-audiences (tighten-only, gated)        │
 │  AI drafts per-item generalization chains d4→d0, per household language  │
 │  DETERMINISTIC verifier: entity / topic / quasi-identifier / monotonicity│
 │  Fallback: boring templates — nicer than template, never leakier        │
 │  Output: Disclosure Table row (versioned)                                │
 │  Modules: earshot.slowlane.{quarantine,understand,verifier,compiler}     │
 └────────────────────────────┬────────────────────────────────────────────┘
                       SEAM 1 · QUARANTINE
        ▼
 ┌─ STAGE 2 · BROKER ─────────────────── SEALED BOUNDARY ─────────────────┐
 │  Sealed tasks computed inside; typed declassifiers with label           │
 │  propagation; release leases bound to (data, policy, audience epoch)    │
 │  Modules: earshot.gateway.mcp.broker, earshot.secrecy.{store,gate}      │
 └────────────────────────────┬────────────────────────────────────────────┘
                       SEAM 2 · SEAL
        ▼
 ┌─ STAGE 3 · SPEAK ──────────────────── HOT LANE (deterministic) ─────────┐
 │  belief fusion → credible set → minimax plan → exposure budgets          │
 │  → constant-shape assembly → verbatim response → hash-chained ledger     │
 │  Modules: earshot.hotlane.{belief,credible,planner,budgets},             │
 │           earshot.gateway.mcp.shape                                     │
 └────────────────────────────┬────────────────────────────────────────────┘
                       SEAM 3 · CONSTANT SHAPE
        ▼
 ┌─ STAGE 4 · CONTINUE ──────────────── PERSONAL CHANNEL ─────────────────┐
 │  Authenticated personal continuation on the owner's phone: full content, │
 │  confirm cards, defer queue, approvals, reconciliation.                  │
 │  Public projection and personal continuation are SEPARATE outputs of     │
 │  the same sealed computation — never two views of one leak.              │
 └──────────────────────────────────────────────────────────────────────────┘
```

The data model, in six lines: an **Item** moves
`QUARANTINED → COMPILED → RELEASED → EXPIRED`; a **SecrecyEdge** records who it's
hidden from and until when; a **GeneralizationChain** holds renditions d4 (full)
→ d0 (absorbed, nothing spoken); the hot lane reads only the **DisclosureTable**
row `(item, sensitivity, clearance per person, version)`; speech happens under a
**Lease** bound to `(data_version, policy_version, audience_epoch)`.

---

## The room-facing surface: 6 tools

Six verbs the calling assistant can distinguish; the intelligence lives behind them.
All implemented in `earshot.gateway.mcp.broker`, served over Streamable HTTP
(MCP spec 2025-11-25) by `earshot.gateway.mcp.server`.

| Tool | The caller says | What it really does |
|---|---|---|
| `prepare_day_brief` | "What's my day?" | Sealed day computation → public projection + personal continuation |
| `resolve_day_change` | "Move my call; Mom's coming" | Re-solve inside the seal; adapt without naming private reasons |
| `continue_on_personal_device` | "Send that to my phone" | Authenticated handoff of the sealed remainder |
| `withdraw_request` | "Forget I asked" | Withdraw in-flight continuations; the public message says "reconciling" — never "undone," never "delivered" |
| `room` | "Mom's here" / "I'm alone" | Declaration → belief update. Asymmetric: adding listeners is free; "alone" loosens only low-sensitivity items within a half-life |
| `keep_secret` | "Never mention the clinic in front of Mom" | One sentence → instant TIGHTEN edge (clearance 0 immediately, re-rendered async). No confirmation needed — tightening is always safe |

**Deliberately NOT voice verbs:** audience manipulation, trust changes, private
retrieval, owner approval. Loosening (`release`) never happens by voice — only on
the authenticated phone.

**The response contract:** every tool returns `speak` text with
`verbatim_no_elaboration` policy, a minimal payload containing only spoken-depth
fields, and `_meta` with plan id + table version. **Absent by design:** no
`hidden_count`, no `withheld: true`, no sealed item IDs. A hallucinating caller can
only rearrange text that is already safe.

---

## Deployment: two honest profiles

| Profile | Claim |
|---|---|
| **A — Persistent room-facing host** (the shippable profile) | Protected facts never enter that host's context through EARSHOT. The seal is the product. |
| **B — EARSHOT-controlled host** (the demo profile) | Audience changes invalidate pending disclosure leases and stop future output — subject to stated sensing and playback limits. **Not presented as an existing Echo-interruption API.** |

The profile is an immutable runtime switch (`earshot.gateway.config.ProfileGate`) —
the server refuses to start without one. Profile A is what transfers to a real
Alexa+ integration; Profile B is what makes the walk-in demonstration possible,
honestly labeled via the independent simulator (`earshot-sim`).

---

## Kernel vs Household Pack

**The kernel is universal. The pack is data.** (The IAM lesson: nobody forks IAM
for a use case.)

- **Kernel** — identical in Ohio, Jaipur, Nairobi: the three seams, lease/epoch
  machinery, belief math, exposure budgets, constant-shape assembly, the 6-tool
  surface, the response contract. Frozen: `packages/kernel/` is never modified.
- **Household Pack** — per culture/language/household: topic taxonomy, multilingual
  lexicons for the leak verifier, role defaults, generalization templates
  (`packs/base`, `packs/en`, `packs/hi`).

Customizing EARSHOT for a new household, language, or culture = editing the pack.
Use cases are data, not code — which is why the design survives infinite use cases.
See `docs/packs.md`.

---

## Evaluation: privacy as an SLO

**The privacy SLO: existence AUC ≈ 0.5 against an adversarial listener —
release-blocking.**

Method: seeded synthetic households (4–6 people, EN/HI/Hinglish, 30 simulated
days); an adversarial listener hears only what was spoken in each listener's
presence and tries to infer secrets. Measured (seed 7, n=200 triples,
`packages/trace-harness/evidence/slo/slo-report.md`):

| Policy | Existence AUC | Inference rate | Utility | Friction |
|---|---|---|---|---|
| Native (says everything) | 0.928 | 0.545 (base 0.25) | 1.000 | 0.000 |
| Keyword filter | 0.921 | 0.273 (base 0.25) | 0.954 | 0.250 |
| EARSHOT v1 (4-level lattice) | 0.875 | 0.273 (base 0.25) | 1.000 | 0.000 |
| **EARSHOT sealed-speech** | **0.497** | 0.273 (base 0.25) | 1.000 | 0.060 |

**Counterfactuals are the test grammar.** Every seam has canonical counterfactuals
(change prenatal→therapy; remove the item; add a guest; replay yesterday's
"alone") — public output must be byte-invariant across the counterfactual. **A
privacy test that can't fail is theater:** the suite ships a negative control
(mislabel a secret public → the harness must FAIL). 4/4 counterfactual suites pass
for sealed-speech; the adversarial listener is explicitly labeled a *lower bound*.

---

## Threat model (summary)

The defended adversary is the **casual overhearer** — guest, relative, kid — plus
the concealment target probing passively ("any packages?") or actively ("I'm
alone…": voice can't loosen target-linked edges or sensitivity ≥ 0.7; only the
authenticated phone can). Prompt injection via data is property-tested to never
raise a clearance. The misbehaving host LLM never receives withheld data, so it
has nothing to hallucinate *from*. Out of scope, stated: native announcements of
non-routed data, and the account holder interrogating their own assistant in
private (legitimate use, not an attack). Full model: `docs/threat-model.md`.

---

## What we don't claim

Production security · real listener detection · Echo audio interruption ·
universal interception of native announcements · any benchmark without shown
evidence. **Kill conditions:** existence AUC materially above 0.5 after budgets →
constant shape needs rework, not tuning; a real Alexa+ integration path opens →
Profile B's sensing assumptions get replaced by measured ones. A design that can't
name its kill conditions is a pitch. This one can.

---

*Entry points: `earshot-demo` (5-beat demo) · `earshot-server` (MCP gateway) ·
`earshot-sim` (independent simulator) · `pip install -e .`, then
`python -m pytest` runs all 640 tests. Companion: `docs/api.md` (tool reference),
`docs/threat-model.md`, `docs/packs.md`, `docs/quickstart.md`.*
