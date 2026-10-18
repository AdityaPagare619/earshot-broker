# Trace-harness report

Mode: fixture MCP server over Streamable HTTP (http://127.0.0.1:8896/mcp); fixture, not the product server

## Paired worlds

### no_private_vs_one_private — PASS
World B has one private health fact; world A has none. The public trace must be identical.
Randomness independence: ok

### prenatal_vs_therapy — PASS
The secret's *content* changes (prenatal vs therapy) with identical shape. Public trace must not distinguish them.
Randomness independence: ok

### reordered_private_records — PASS
Same secrets, different record order. Public trace must be order-independent.
Randomness independence: ok

### source_error_vs_no_match — PASS
World A has a private fact flagged as a source error; world B has no such fact. The error must not surface.
Randomness independence: ok
- timing note (weak signal): step 1 resolve_day_change: <1ms vs <10ms

### one_vs_several_private — PASS
World B has three private facts; world A has one. The public trace must not reveal the count.
Randomness independence: ok

## Adversarial fixtures

- cross_tenant_reference_replay: PASS — replay error=(-32001, 'Unavailable'), garbage error=(-32001, 'Unavailable'), identical=True
- double_withdraw_no_oracle: PASS — world A: (None, (-32001, 'Unavailable'), 'ok', 'error'); world B: (None, (-32001, 'Unavailable'), 'ok', 'error')

## What this does NOT prove

No production security, no timing-channel absence, no real listener detection. A PASS is a necessary condition, not a certificate. See the package README.
