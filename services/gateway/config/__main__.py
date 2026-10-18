"""Operator entrypoint: validate the deployment configuration.

Usage:
    EARSHOT_PROFILE=public_persistent_host python3 -m services.gateway.config --check
    EARSHOT_PROFILE=controlled_host_demo python3 -m services.gateway.config --check --signoffs signoffs.json

--check loads the profile (fail-closed), runs the readiness gates, prints the
measured latency and cost summaries, and exits non-zero when the deploy is
blocked. This is the command a deploy pipeline runs before rollout.
"""
from __future__ import annotations

import argparse
import json
import sys

from .analysis.cost_model import CostInputs, report as cost_report
from .analysis.latency import budget_table, measure_kernel_latency
from .analysis.latency import report as latency_report
from .profiles import ProfileError, load_profile
from .readiness import deploy_blocked, run_readiness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate EARSHOT gateway deployment configuration.")
    parser.add_argument("--check", action="store_true",
                        help="run profile load + readiness gates")
    parser.add_argument("--signoffs", default=None,
                        help="JSON file of MANUAL-gate sign-offs")
    parser.add_argument("--latency-iters", type=int, default=10000)
    args = parser.parse_args(argv)

    if not args.check:
        parser.print_help()
        return 2

    try:
        profile = load_profile()
    except ProfileError as exc:
        print(f"PROFILE ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"profile: {profile.name}")
    print(f"flags: {profile.describe()}")

    signoffs = None
    if args.signoffs:
        with open(args.signoffs) as fh:
            signoffs = json.load(fh)

    results = run_readiness(signoffs)
    print("\nreadiness gates:")
    for r in results:
        mark = {"PASS": "ok", "FAIL": "FAIL", "MANUAL": "manual"}[r.status]
        signed = " (signed)" if r.signoff else ""
        print(f"  [{mark}] {r.name}{signed}")
    blocked = deploy_blocked(results)
    if blocked:
        print(f"\nDEPLOY BLOCKED by {len(blocked)} gate(s):")
        for name in blocked:
            print(f"  - {name}")
    else:
        print("\nreadiness: no blocking gates")

    print("\n" + latency_report(measure_kernel_latency(
        iterations=args.latency_iters)))
    print("\n" + cost_report(CostInputs()))

    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
