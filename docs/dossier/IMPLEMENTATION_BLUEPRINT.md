# EARSHOT — implementation blueprint

Companion to `EARSHOT_REDESIGN.md`. These are proposed production semantics, not claims that the reference prototype implements them.

## 1. Repository layout for the actual competition build

```text
earshot/
  apps/
    simulator/             # real MCP client, controlled output arbiter
    personal/              # separate authenticated owner experience
  services/
    gateway/
      mcp/                 # initialize/list/call, auth, public response projection
      private_api/         # owner-only policy, plan, approval, audit endpoints
      context/             # authenticated sensor events, epochs, freshness
      release/             # labels, declassifiers, grants, commit checks
      adapters/            # explicit schema/ownership/source contracts
    worker/
      planners/            # bounded AI proposer + deterministic solver
      outbox/              # idempotent delivery and retries
      reconciliation/      # ambiguous provider mutations
  packages/
    contracts/             # JSON Schemas and typed models
    policy/                # parser, validator, interpreter, versioned artifacts
    fixtures/              # synthetic paired worlds
    app-ui/                # public-safe MCP App bundle
  tests/
    unit/
    property/
    integration/
    paired_world/
    races/
    audio_device/
  evidence/                # actual results, versions, measurement instructions
  docs/
    threat-model.md
    integration-boundaries.md
    friction-log.md
```

Prefer Python for the gateway/kernel/solver and a small TypeScript web client. Do not adopt two incompatible MCP protocol revisions by independently installing each language’s latest SDK. Resolve exact versions together, commit lockfiles, and test the negotiated wire version.

## 2. Private task state machine

```text
ACCEPTED
   -> NEEDS_OWNER_INPUT
   -> COMPUTING
        -> VALIDATED_DRAFT
             -> AWAITING_PRIVATE_APPROVAL
                  -> EXECUTING
                       -> COMPLETED
                       -> RECONCILING -> COMPLETED / PARTIAL / FAILED
        -> FAILED
   -> CANCELED
```

Transitions are private by default. The public surface can remain at request-level `accepted` where deeper status would disclose protected existence or outcomes. This does not authorize lying about completion: never map `accepted` to “done.”

A controlled renderer has a separate state machine:

```text
PREPARED -> LEASED -> COMMITTING -> EMITTING -> FINISHED
                \       \            \
                 -> REVOKED / EXPIRED  -> STOPPED
```

Task completion and presentation completion are not the same event. The task can remain ready even after its room presentation is stopped.

## 3. Source adapter contract

Every adapter declares:

```text
provider identity and fixed endpoint allowlist
permitted OAuth scopes
record and field schemas
owner and other data subjects
version / ETag / recurrence semantics
field labels and private defaults
bounded supported transformations
possible external recipients of each mutation
idempotency / conflict / retry behavior
provider notification side effects
freshness and deletion semantics
```

Do not use arbitrary upstream MCP descriptions as security declarations. A malicious source could say its clinical records are public. Ownership and default labels come from the connected account and confirmed source configuration.

Minimum calendar handling:

- Expand recurrence for a bounded day/time range using a tested library.
- Preserve time zone and original instant; handle all-day events separately.
- Treat declined/canceled/transparent events according to the provider semantics.
- Never infer that an external appointment is movable because a local record is editable.
- Use busy intervals if they suffice; fetch details only for an explicitly authorized purpose.
- Use source versions in plans; stale plans must be regenerated before mutation.
- Do not overwrite attendees or notification flags during a time-only change.

## 4. Typed plan, not arbitrary executable model code

Example private plan AST:

```json
{
  "plan_type": "day_revision",
  "input_snapshot": "server_owned_snapshot_ref",
  "nodes": [
    {"id": "n1", "op": "load_busy_intervals", "source": "bound_calendar"},
    {"id": "n2", "op": "load_flexible_tasks", "source": "bound_tasks"},
    {"id": "n3", "op": "find_slot", "duration_minutes": 20,
      "depends_on": ["n1", "n2"]},
    {"id": "n4", "op": "draft_owner_task_change", "depends_on": ["n3"]},
    {"id": "n5", "op": "publish_personal_plan", "depends_on": ["n4"]}
  ]
}
```

A validator rejects unknown operators, source IDs not supplied by the server, unbounded ranges, dependency cycles and writes outside the allowed scope. No `eval`, arbitrary Python, arbitrary SQL or arbitrary URL execution.

The AST is private. Even revealing the existence of `load_busy_intervals` after a carefully chosen query could aid inference. Public discovery exposes stable generic task tools, not per-secret generated tools.

### Control-flow taint

Suppose the planner produces:

```text
if private_busy_at_3:
    recommend_4pm
else:
    recommend_3pm
```

Both outputs depend on the private condition. The program-counter label joins into the result even if no private string appears in the output. A simple “scan for the clinic name” test misses this.

For arbitrary model-generated plans, dependency inference is not reliably complete. Conservatively label the whole plan with all private inputs it observed, then release only independently verified transformations. This sacrifices some public expressiveness for a meaningful boundary.

## 5. Candidate selection

For each task, build a bounded candidate set:

1. Public independent facts only.
2. A user-approved coarse schedule projection.
3. Personal exact plan.
4. Owner-only draft action.
5. Defer without public private-result status.

Reject invalid candidates first. Rank remaining candidates using user preferences and expected task utility. The model does not select an unauthorized candidate by assigning it a large utility score.

If the plan needs a new kind of disclosure, ask privately. Do not invent a convenient permission at runtime.

## 6. Precise commit ordering

A conceptual implementation for the controlled host:

```text
prepare(candidate):
    authenticate caller
    read current task, data, policy and audience versions
    validate candidate and all dependencies
    persist grant tied to those versions, owner and output channel

commit(grant):
    acquire room/renderer serialization boundary
    re-read grant, current epoch, policy and data versions
    if missing / revoked / expired / version mismatch:
        deny
    else:
        append COMMITTED event and release a bounded segment
    release serialization boundary

audience_changed(event):
    stop local output first
    validate issuer, timestamp and sequence
    serialize with commit boundary
    increment epoch and invalidate prior pending grants
    keep private task state intact
```

This is not globally atomic with the physical room. The linearization point orders **observed software events**. A person may have entered before the sensor noticed. The renderer also needs a local rule to prevent a late segment arriving after stop from playing.

Bind each segment to `epoch + sequence + candidate_digest`. After advancing the local epoch, reject any buffered or late segment from an older epoch. Do not rely only on the server refusing the next request.

## 7. Delivery semantics

Use a transactional outbox:

```text
BEGIN
  persist validated plan revision
  insert outbox row with unique(owner, request, revision, destination)
COMMIT
```

Worker attempts delivery at least once. The destination inbox upserts by the same key. This yields idempotent observable delivery in the supported destination, not magical exactly-once delivery across all providers.

For quiet mode, background synchronization changes private app state without a secret-dependent notification sound or public badge. If the operating system cannot guarantee that behavior, disable push for strict fixtures and use owner-initiated fetch.

For haptic mode, the owner must explicitly allow existence signaling. A vibration visible on the counter can still disclose an event occurred.

## 8. External writes

Each action proposal includes:

```text
source record/version
exact fields to change
all recipients and notification effects
permitted purpose
owner approval binding
idempotency key
expected outcome and reconciliation strategy
```

A personal approval is bound to a particular plan digest, recipients and version; “yes” in a later unrelated voice turn does not approve a changed plan.

Provider write flow:

1. Revalidate ownership, permission and current source version.
2. Record operation attempt before sending.
3. Send with provider idempotency/concurrency controls where supported.
4. Record success if the provider confirms it.
5. On timeout, query the provider or reconcile by stable operation identity.
6. Never blindly retry a potentially completed mutation.
7. Return accurate personal status; only release permitted public status.

## 9. Concrete request trace

### Normal public-safe path

| Sequence | Event | Information boundary |
|---|---|---|
| 1 | Host initializes MCP 2025-11-25 | Stable capability schema, no personal data |
| 2 | `tools/list` | Four generic tools, independent of private records |
| 3 | `prepare_day_brief` | Public date/timezone intent, owner from verified token |
| 4 | Server creates request reference | Independent of private-match count |
| 5 | Public projection returned | Only authorized durable-public facts |
| 6 | Private worker computes plan | Private input never sent to room host |
| 7 | Personal outbox update | Owner-bound registered destination |
| 8 | Owner opens plan | Separate personal token and recent authentication |

### Audience change, controlled profile

| Sequence | Event | Result |
|---|---|---|
| 1 | Candidate prepared at epoch 31 | Not yet emitted |
| 2 | Lease granted for segment 2, policy 7 | Restricted to owned renderer |
| 3 | Entry observed locally | Output stop triggered |
| 4 | Epoch becomes 32 | Old segment cannot commit or resume |
| 5 | Late epoch-31 segment arrives | Local arbiter rejects it |
| 6 | Task remains ready privately | No repetition of private goal needed |
| 7 | Listener leaves | No automatic sensitive replay |

### Guest queries a continuation

A guest obtains the public reference and asks for its contents. Public MCP has no private-reveal tool. Calling the private API with the public token fails its audience/scope checks. Calling with the guest’s personal token fails owner binding. Error response does not distinguish unknown reference from forbidden reference.

## 10. Deployment profiles and switches

```text
PROFILE=public_persistent_host
  audience_sensitive_content_to_mcp = false
  private_reveal_via_mcp = false
  public_result_status = permission-dependent
  personal_api = independently_authenticated

PROFILE=controlled_host_demo
  audience_sensitive_output = explicit_consent_and_assumptions
  local_arbiter = required
  sensor_heartbeat = required
  fresh_context_after_epoch_change = required
  autoplay_after_retrust = false
```

These are deployment controls owned by the service/operator, not tool arguments a model can set.

## 11. Production readiness gates

Do not connect real sensitive records until:

- authentication and authorization are implemented and reviewed;
- cross-tenant tests cover every store/cache/API;
- private data is absent from observability pipelines;
- all public response channels use a common release assembler;
- source updates invalidate dependent data;
- tasks and delivery survive crashes without duplicated effects;
- secret-dependent errors/status are contained;
- owner disclosure settings are comprehensible in usability testing;
- supported transformations have explicit tests;
- renderer/sensor claims have actual device measurements;
- certification questions about private handoff and silence are resolved for the target integration.

## 12. A useful additional open-source artifact

A possible separate contribution is a **public-trace privacy test harness** for MCP servers:

- run paired synthetic worlds;
- execute the same initialized MCP request sequence;
- capture text, structured content, resources and metadata;
- normalize independent random request IDs;
- compare allowed public projections;
- report secret-dependent shape/status/content differences;
- include adversarial reference-replay fixtures.

This is a proposed contribution, not a repository already created or a qualification already earned. Amazon’s Open Source rules require an additional project/contribution and associated URLs during the window; see `SOURCE_AUDIT.md`.

## 13. Problem-solving method used for this redesign

This is the reusable design method, not a claim of an unprecedented invention:

1. **Start with irreversible harm.** Identify what cannot be taken back: spoken words, visible pixels, sent notifications and facts retained by an uncontrolled host.
2. **Find the actual authority boundary.** Enumerate APIs we control and reject guarantees that require unverified host powers.
3. **Define the user outcome before the data request.** “Prepare a workable afternoon” is not equivalent to “read every calendar record.”
4. **Build counterexamples before features.** Mom alone at the Echo, a secret-dependent absence, an expired audience sample, a late audio segment, and a private title in an error must all shape the architecture.
5. **Model all information recipients.** Include the room, assistant memory, provider APIs, personal device, shared calendar and operational logs.
6. **Separate uncertain interpretation from authorization.** Let AI propose meaning and plans; require typed permissions and deterministic enforcement for release.
7. **Choose the smallest workflow that demonstrates the whole boundary.** One private calendar plan is stronger evidence than twelve shallow integrations.
8. **Test both preservation and utility.** Compare against the safe but unhelpful “always use your phone” baseline as well as unsafe assistants.
9. **Expose deployment assumptions.** A controlled renderer and a stock Alexa host are different systems; label them separately.
10. **Promote only measured claims.** Ship test artifacts and observed friction, not benchmark numbers inherited from a pitch.

### Alternatives considered and rejected as the foundation

| Approach | Strength | Why it is not the selected foundation |
|---|---|---|
| Post-generation privacy-checking LLM | Flexible natural language | Secret already entered host context; checker fallibility; does not own output sink |
| Generic upstream MCP redactor | Easy to demonstrate | Incomplete source semantics; bypass paths; weak action/inference handling |
| Camera-first trusted-room detector | Strong visual demo | Absence detection does not prove acoustic privacy; enrollment and bystander risks |
| Always mute / phone-only relay | Simple containment | Little task utility; cannot justify the agentic workflow claim |
| Fully local voice assistant | Owns more of the stack | Different distribution/integration target; local computation alone does not stop room disclosure |
| Cryptographic multi-party computation / homomorphic private planner | Potentially smaller trust boundary for limited computations | Overkill for this deadline; arbitrary semantic planning and speaker control remain unsolved by encryption alone |
| Sealed private task broker | Preserves utility while minimizing public data | Requires explicit adapters, owner authentication and honest host boundaries; selected because those can be built and tested |

The chosen design is not the most complicated. It is the smallest design that addresses useful task completion, irreversible disclosure and the documented integration boundary together.
