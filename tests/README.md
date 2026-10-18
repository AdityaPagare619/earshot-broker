# Tests — one invocation

From the repo root:

```bash
python -m pytest
```

That's it. No `PYTHONPATH`, no per-suite incantations. The root `conftest.py`
builds `sys.path` deterministically (pathlib, cross-platform); see
`docs/seats/pro-tests/DESIGN.md` for how collisions between same-named test
helpers (`harness`, `arbiter`) are defused.

With pytest installed as the test extra:

```bash
pip install -e ".[test]"   # once
python -m pytest           # ~640 tests, one process
```

Useful variants:

```bash
python -m pytest tests/failure_paths -q        # one suite
python -m pytest -k "quarantine"               # by name
python -m pytest --collect-only -q | tail -1   # count tests
```

## Layout

| Directory | What it covers |
|---|---|
| `tests/adversarial` | Adversarial + boundary suites |
| `tests/failure_paths` | Failure-path matrix (J4): error-oracle, deny→recovery, leases, withdraw |
| `tests/failure-injection` | Fault injection vs the kernel |
| `tests/paired_world` | Paired-world invariance |
| `tests/races` | Epoch/commit/sensor races (J10) |
| `packages/kernel` | 24 reference kernel tests (FROZEN — do not touch) |
| `packages/hotlane/tests` | Belief fusion, credible sets, minimax planner, budgets |
| `packages/secrecy/tests` | Secrecy graph, monotone gate, declarations |
| `packages/slowlane/tests` | Quarantine, verifier, compiler, counterfactuals |
| `packages/trace-harness/tests` | Trace harness + privacy SLO lab |
| `packs/tests` | Household pack conformance, language-blindness |
| `services/gateway/adapters` | SourceAdapter contract + adapters |
| `services/gateway/config/tests` | Deployment profiles, readiness gates |
| `services/gateway/mcp/tests` | MCP server: protocol, tools, constant shape, latency |
| `apps/simulator/tests` | Web host: arbiter, walk-in demo, protocol conformance |
| `apps/personal/tests` | Personal surface CLI |
| `integration/tests` | End-to-end pipeline + demo beats |

## If a suite fails

1. Run just that file: `python -m pytest <path> -x`.
2. Run with `-v` (once, without the default `-q`) to see the conftest bootstrap
   header — it prints the repo root, packaged-mode flag, and the computed
   evicted-helper list on every run.
3. Networked suites (`services/gateway/mcp/tests`, `apps/simulator/tests`,
   `packages/trace-harness/tests`) bind distinct localhost ports per file; a
   stale server from a killed run can hold a port — free it and re-run.
   Do not run two networked suites at once on the same machine (e.g. two
   lanes' checkouts side by side) — the ports are a machine-global resource.
