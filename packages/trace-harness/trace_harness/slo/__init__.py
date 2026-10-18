"""SLO lab public API.

run_slo_lab(seed, out_dir) -> report dict and writes evidence files:
  slo-report.md, pareto.json, pareto.svg, existence-auc.json,
  counterfactuals.json.

Everything is deterministic in `seed`. Numbers are measured, never asserted.
"""
from __future__ import annotations

import json
from pathlib import Path

from .counterfactuals import run_all as run_counterfactuals
from .pareto import pareto_markdown, pareto_svg, run_pareto
from .policies import POLICIES


def run_slo_lab(seed: int = 7, n_households: int = 4,
                out_dir: str = "evidence/slo") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pareto = run_pareto(seed=seed, n_households=n_households)
    cf_results = run_counterfactuals(POLICIES)

    cf_json = [
        {"suite": r.suite, "policy": r.policy, "passed": r.passed,
         "detail": r.detail if not r.passed else "identical public view"}
        for r in cf_results
    ]
    cf_pass = sum(1 for r in cf_results if r.passed)

    report = {
        "seed": seed,
        "n_households": n_households,
        "pareto": pareto,
        "counterfactuals": {
            "suites": ["content_swap", "remove_item", "add_guest",
                       "replay_alone"],
            "passed": f"{cf_pass}/{len(cf_results)}",
            "results": cf_json,
        },
        "does_not_prove": [
            "The fixture listener is a LOWER BOUND on adversary strength; "
            "a smarter adversary could do better.",
            "Policy-layer results are not server evidence; the wire layer is "
            "the existing trace-harness.",
            "Synthetic households are not real households; belief noise is "
            "a fixture model.",
            "No timing-channel claim: timing-shape is a structural proxy "
            "(segments, phone_sent), measured for real at the wire layer.",
        ],
    }

    with open(out / "pareto.json", "w", encoding="utf-8") as f:
        json.dump(pareto, f, indent=2)
    with open(out / "pareto.svg", "w", encoding="utf-8") as f:
        f.write(pareto_svg(pareto))
    with open(out / "existence-auc.json", "w", encoding="utf-8") as f:
        json.dump({p: {"leakage_auc": v["leakage_auc"],
                       "auc_triples": v["auc_triples"],
                       "inference_rate": v["inference_rate"],
                       "inference_base_rate": v["inference_base_rate"]}
                   for p, v in pareto["points"].items()}, f, indent=2)
    with open(out / "counterfactuals.json", "w", encoding="utf-8") as f:
        json.dump(report["counterfactuals"], f, indent=2)
    with open(out / "slo-report.md", "w", encoding="utf-8") as f:
        f.write(_markdown(report, pareto))
    return report


def _markdown(report: dict, pareto: dict) -> str:
    lines = [
        "# SLO lab report — privacy as a measurable SLO",
        "",
        f"seed={report['seed']}, households={report['n_households']}, "
        "30 days x 2 episodes each.",
        f"Listener: {pareto['listener']}",
        "",
        "## Privacy SLO: existence AUC ~= 0.5",
        "",
        "| policy | existence AUC | triples |",
        "|---|---|---|",
    ]
    for pname, pt in pareto["points"].items():
        lines.append(f"| {pname} | {pt['leakage_auc']:.3f} | {pt['auc_triples']} |")
    lines += [
        "",
        "## Pareto: leakage vs owner utility",
        "",
        pareto_markdown(pareto),
        "",
        "## Counterfactual suites",
        "",
        f"Passed: {report['counterfactuals']['passed']}",
        "",
    ]
    for r in report["counterfactuals"]["results"]:
        if not r["passed"]:
            lines.append(f"- FAIL {r['suite']} / {r['policy']}: {r['detail']}")
    lines += ["", "## What this does NOT prove", ""]
    for d in report["does_not_prove"]:
        lines.append(f"- {d}")
    lines.append("")
    return "\n".join(lines)


__all__ = ["run_slo_lab", "POLICIES"]
