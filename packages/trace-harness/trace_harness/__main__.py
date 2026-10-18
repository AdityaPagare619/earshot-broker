"""CLI: python -m trace_harness run [--selftest | --fixture-port P] [--out DIR]

Two honest modes:
  selftest      drive the reference kernel in-process (proves the harness
                itself; NOT evidence about any server).
  fixture (default)  start the bundled fixture MCP server, load the paired
                worlds, run everything over Streamable HTTP, write the
                evidence report.

Pointing at an external server is a Python-API operation (see README):
load the five world pairs' facts under their tenant names, then drive
MCPHttpAdapter yourself. The harness never silently invents server state.
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent / "kernel"))
sys.path.insert(0, str(_HERE.parent.parent.parent))  # repo root: wincompat

from wincompat import ensure_utf8_stdout  # noqa: E402

from trace_harness import (  # noqa: E402
    builtin_pairs, MCPHttpAdapter, KernelDirectAdapter, run_sequence,
    normalize_trace, diff_traces, adversarial_suite,
)
from trace_harness.normalize import assert_randomness_independent  # noqa: E402


def _run_all(make_adapter, setup_world=None, teardown=None):
    """Run every pair + adversarial suite. Returns the report dict."""
    pair_results = []
    for pair in builtin_pairs():
        if setup_world:
            setup_world(pair.world_a)
        trace_a = run_sequence(make_adapter(pair.world_a), pair.world_a)
        if setup_world:
            setup_world(pair.world_b)
        trace_b = run_sequence(make_adapter(pair.world_b), pair.world_b)
        if teardown:
            teardown()
        na, nb = normalize_trace(trace_a), normalize_trace(trace_b)
        try:
            assert_randomness_independent(na, nb)
            independence = "ok"
        except AssertionError as e:
            independence = f"FAILED: {e}"
        verdict = diff_traces(na, nb)
        pair_results.append({
            "pair": pair.name,
            "description": pair.description,
            "verdict": "PASS" if verdict.passed else "FAIL",
            "randomness_independence": independence,
            "differences": [
                {"step": d.step_index, "tool": d.tool,
                 "channel": d.channel, "detail": d.detail}
                for d in verdict.differences
            ],
            "timing_notes": [
                {"step": d.step_index, "tool": d.tool, "detail": d.detail}
                for d in verdict.timing_notes
            ],
            "steps_run": len(trace_a),
        })

    adv_results = []
    pair = builtin_pairs()[1]
    if setup_world:
        setup_world(pair.world_a)
        setup_world(pair.world_b)
    for r in adversarial_suite(make_adapter, pair.world_a, pair.world_b):
        adv_results.append({"name": r.name, "passed": r.passed,
                            "detail": r.detail})
    if teardown:
        teardown()
    return {"pairs": pair_results, "adversarial": adv_results}


def _to_fact(d):
    from kernel import Fact, Label  # kernel dir on sys.path at module top
    return Fact(d["key"], d["value"],
                Label(frozenset(d["readers"]), frozenset(d.get("topics", ()))))


def main(argv=None):
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description="Public-trace privacy harness")
    ap.add_argument("command", choices=["run", "slo"],
                    help="run: paired-world wire harness; slo: privacy SLO lab")
    ap.add_argument("--selftest", action="store_true",
                    help="drive the kernel in-process (harness self-check)")
    ap.add_argument("--fixture-port", type=int, default=8899)
    ap.add_argument("--out", default="evidence",
                    help="directory for the Markdown + JSON report")
    ap.add_argument("--seed", type=int, default=7,
                    help="SLO lab seed (deterministic)")
    ap.add_argument("--households", type=int, default=4,
                    help="SLO lab household count")
    args = ap.parse_args(argv)

    if args.command == "slo":
        from trace_harness.slo import run_slo_lab
        report = run_slo_lab(seed=args.seed, n_households=args.households,
                             out_dir=args.out)
        pts = report["pareto"]["points"]
        for pname, pt in pts.items():
            print(f"{pname}: AUC={pt['leakage_auc']:.3f} "
                  f"utility={pt['owner_utility']:.3f} "
                  f"friction={pt['friction']:.3f}")
        print(f"counterfactuals: {report['counterfactuals']['passed']}")
        print(f"report: {args.out}/slo-report.md")
        return 0

    if args.selftest:
        from kernel import Kernel

        def make_adapter(world):
            facts = tuple(_to_fact(d) for d in world.facts)
            return KernelDirectAdapter(Kernel(), world.tenant, world.owner, facts)

        report = _run_all(make_adapter)
        report["mode"] = "selftest (in-process kernel; NOT server evidence)"
    else:
        sys.path.insert(0, str(_HERE.parent / "tests"))
        import fixtureserver

        server = fixtureserver.start(args.fixture_port)
        base = f"http://127.0.0.1:{args.fixture_port}/mcp"

        def setup_world(world):
            server.state.world_facts[world.tenant] = tuple(
                _to_fact(d) for d in world.facts)
            _reset(args.fixture_port)

        def make_adapter(world):
            return MCPHttpAdapter(base, world.tenant, world.owner)

        report = _run_all(make_adapter, setup_world=setup_world)
        report["mode"] = (f"fixture MCP server over Streamable HTTP "
                          f"({base}); fixture, not the product server")
        server.shutdown()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    _write_markdown(report, str(outdir / "trace-harness-report.md"))
    with open(outdir / "trace-harness-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    npass = sum(1 for p in report["pairs"] if p["verdict"] == "PASS")
    nadv = sum(1 for a in report["adversarial"] if a["passed"])
    print(f"pairs: {npass}/{len(report['pairs'])} PASS; "
          f"adversarial: {nadv}/{len(report['adversarial'])} PASS")
    print(f"report: {args.out}/trace-harness-report.md")
    return 0 if (npass == len(report["pairs"])
                 and nadv == len(report["adversarial"])) else 1


def _reset(port):
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/__reset", b"{}",
                 {"Content-Type": "application/json"})
    conn.getresponse().read()
    conn.close()


def _write_markdown(report, path):
    lines = ["# Trace-harness report", "",
             f"Mode: {report['mode']}", "",
             "## Paired worlds", ""]
    for p in report["pairs"]:
        lines.append(f"### {p['pair']} — {p['verdict']}")
        lines.append(f"{p['description']}")
        lines.append(f"Randomness independence: {p['randomness_independence']}")
        for d in p["differences"]:
            lines.append(f"- step {d['step']} {d['tool']} [{d['channel']}] {d['detail']}")
        for t in p["timing_notes"]:
            lines.append(f"- timing note (weak signal): step {t['step']} "
                         f"{t['tool']}: {t['detail']}")
        lines.append("")
    lines.append("## Adversarial fixtures")
    lines.append("")
    for a in report["adversarial"]:
        lines.append(f"- {a['name']}: {'PASS' if a['passed'] else 'FAIL'} — {a['detail']}")
    lines.append("")
    lines.append("## What this does NOT prove")
    lines.append("")
    lines.append("No production security, no timing-channel absence, no real "
                 "listener detection. A PASS is a necessary condition, not a "
                 "certificate. See the package README.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
