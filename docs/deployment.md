# Deployment guide — EARSHOT gateway profiles

## The two profiles

| | `public_persistent_host` (Profile A) | `controlled_host_demo` (Profile B) |
|---|---|---|
| Audience-sensitive content to MCP | **never** | explicit consent + stated assumptions only |
| Private reveal via MCP | **never** | **never** |
| Lease issuance | no | yes (short-lived, epoch-bound) |
| Local arbiter | not required | **required** |
| Sensor heartbeat | not required | **required** |
| Fresh context after epoch change | no | **required** |
| Autoplay after re-trust | no | **no** (never auto-resume sensitive speech) |

Profile A is the shippable design: it makes no claim on host memory, speaker
control, or sensing. Profile B is a controlled-host demonstration — label it
"EARSHOT controlled-host demonstration — not live Alexa+ device integration"
in every telling. Never imply B's controls exist in A.

## Selecting a profile

```bash
export EARSHOT_PROFILE=public_persistent_host   # or controlled_host_demo
# optional operational tuning (TTLs, quotas — never capability flags):
export EARSHOT_CONFIG_FILE=/etc/earshot/tuning.toml
```

There is **no default**. An unset or unknown `EARSHOT_PROFILE` refuses to start
— a default would be a silent choice about the trust boundary.

`tuning.toml` may set only:

```toml
[tuning]
lease_ttl_seconds = 0.25
evidence_ttl_seconds = 1.0
receipt_ttl_seconds = 300.0
max_requests_per_minute_per_tenant = 60
```

Capability flags (`allow_lease_issuance`, `private_reveal_via_mcp`, …) are
profile-defined. A file that tries to override them fails startup with
`ProfileError`. This is deliberate: the file is operator convenience, not a
privilege mechanism.

## Pre-deploy validation

```bash
EARSHOT_PROFILE=public_persistent_host \
  python3 -m services.gateway.config --check [--signoffs signoffs.json]
```

Exit 0 = no blocking gates. Exit 1 = blocked (or profile error). The command
prints the profile flags, all eleven readiness gates, measured kernel latency,
and the cost summary. Run it in the deploy pipeline before every rollout.

`signoffs.json` records human judgments for MANUAL gates:

```json
{
  "auth_implemented_and_reviewed": {
    "signed_by": "security-reviewer",
    "date": "2026-10-20",
    "evidence_ref": "evidence/auth-review.md"
  }
}
```

An unsigned MANUAL gate blocks the deploy. There is no `--force`.

## Wiring the gate into the release path

The reference pattern lives in `services/gateway/config/integration.py`
(`ReleasePath`). J3's server should follow it:

1. Construct one `ProfileGate` per process from `load_profile()`.
2. Call `gate.check("public_projection")` before serving public facts;
   `gate.check("audience_scoped_release")` before minting any lease.
3. Unknown operations deny by default — never add a permissive fallback.
4. Log `SecurityEvent`s (operation/profile/tenant/allowed only — content-free).

Profile B additionally requires: live sensor heartbeat within
`evidence_ttl_seconds`, a ready local arbiter, and epoch/version match at
commit. See `ReleasePath.audience_scoped_release`.

## Production hardening checklist (blueprint §11, as code)

Five gates run automatically (`--check`): cross-tenant rejection, generic
error messages, single release choke point, content-free observability
events, conservative label propagation. Six gates are MANUAL and need
sign-offs: authN/authZ implementation + review, source-update invalidation,
crash-safe tasks, comprehensible owner settings (usability-tested), measured
sensor/renderer claims, certification resolution (J4).

**Do not connect real sensitive records until all eleven pass.** The checklist
is enforced by exit code, not by convention.

## Scaling notes (100M devices)

- Request volume (base assumption: 20 req/device/day): 2B requests/day,
  ~23k rps average, plan for ~70k peak. The gateway is stateless per request
  except the receipt store — shard receipts by tenant.
- The kernel's measured p99 is ~0.02ms; the budget risk is network, token
  validation, and durable writes — see `evidence/j01-latency.txt`. Measure
  the full path (J3) before claiming the 500ms budget.
- Cost driver is planner inference (~99% of COGS); see `docs/impact.md` and
  `evidence/j01-cost.txt`. Gate planner calls behind the task-type classifier:
  deterministic paths (receipts, precomputed plans) must never spend a model
  call.
- Tenant isolation is the #1 Sev-1 vector at this scale. The kernel binds
  tenant/owner on every store operation (tested); the real store needs
  row-level enforcement as defense in depth (J6's adversarial suite covers it).

## What this guide does not cover

OAuth/PKCE deployment, real sensor integration, device measurements, and
certification — all explicitly out of scope for this build (dossier §17).
They are MANUAL readiness gates, not skipped steps.
