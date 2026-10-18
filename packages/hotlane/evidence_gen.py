"""Evidence generator for S2: latency + planner-level counterfactuals.

Writes:
  evidence/hotlane/latency.txt         — plan_briefing over 50 items (K3: <15ms)
  evidence/hotlane/counterfactuals.txt — planner-level counterfactual checks
  evidence/hotlane/test-run.txt        — full suite output (captured by runner)

Run (after `pip install -e .`):
  python -m earshot.hotlane.evidence_gen
"""

import os
import statistics
import sys
import time

from earshot.hotlane import (
    ALONE,
    BEACON_PRESENT,
    DECLARE_PRESENT,
    UNKNOWN,
    Exposure,
    GeneralizationChain,
    Signal,
    TableRow,
    initial_ledger,
    logit,
    plan_briefing,
)


def make_row(item_id, sensitivity, clearance, version=1):
    chain = GeneralizationChain(
        depths=("d4", "d3", "d2", "d1"),
        renditions={"en": ("d4", "d3", "d2", "d1")},
    )
    return TableRow(item_id=item_id, sensitivity=sensitivity,
                    clearance=dict(clearance), chain=chain, version=version)


NOW = 1_000_000.0


def latency_evidence():
    rows = [
        make_row(f"itm_{i:02d}", sensitivity=(i % 10) / 10,
                 clearance={"priya": 4, "mom": i % 5, "maya": (i + 1) % 5},
                 version=i)
        for i in range(50)
    ]
    signals = [
        Signal(BEACON_PRESENT, "priya", NOW - 100),
        Signal(DECLARE_PRESENT, "mom", NOW - 200),
    ]
    priors = {"priya": logit(0.9), "mom": logit(0.6), "maya": logit(0.3)}
    kw = dict(signals=signals, priors=priors, rows=rows, owner="priya",
              ledger=initial_ledger(), unknown_logit=logit(0.02), now=NOW)
    # Warmup.
    plan_briefing(**kw)
    samples = []
    for _ in range(200):
        t0 = time.perf_counter()
        plan_briefing(**kw)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(0.95 * len(samples))]
    p99 = samples[int(0.99 * len(samples))]
    mx = samples[-1]
    verdict = "PASS" if p99 < 15.0 else "FAIL"
    return (
        "hot-lane latency evidence (S2, K3: plan_briefing < 15ms compute)\n"
        f"method: 50 items, 200 samples, perf_counter, this box\n"
        f"p50={p50:.3f}ms p95={p95:.3f}ms p99={p99:.3f}ms max={mx:.3f}ms\n"
        f"budget: 15.0ms  verdict: {verdict}\n"
    )


def counterfactual_evidence():
    out = ["planner-level counterfactual checks (S2)",
           "Note: the planner never sees content — only (sensitivity, clearance,",
           "beliefs, ledger). These checks pin that the *decision-relevant*",
           "inputs are labels/ints, and that audience changes only quieten.",
           ""]
    priors = {"priya": logit(0.95), "mom": logit(0.5)}
    base_signals = [Signal(BEACON_PRESENT, "mom", NOW - 60)]

    def plan_for(rows, signals, ledger=None):
        plan = plan_briefing(
            signals=signals, priors=priors, rows=rows, owner="priya",
            ledger=ledger or initial_ledger(),
            hidden_from={r.item_id: frozenset({"mom"}) for r in rows},
            unknown_logit=logit(0.01), now=NOW)
        return [(p.item_id, p.decision, p.depth) for p in plan.items]

    # CF1: prenatal -> therapy. Same sensitivity/clearance, different secret
    # label. Decisions must be identical: the planner cannot tell secrets apart
    # by content (it never sees any).
    prenatal = make_row("prenatal_visit", 0.9, {"priya": 4, "mom": 1})
    therapy = make_row("therapy_session", 0.9, {"priya": 4, "mom": 1})
    r1 = plan_for([prenatal], base_signals)
    r2 = plan_for([therapy], base_signals)
    same = [(d, z) for (_, d, z) in r1] == [(d, z) for (_, d, z) in r2]
    out.append(f"CF1 prenatal->therapy (label swap): decisions identical: {same}")

    # CF2: remove the item. Remaining items' plans must be unchanged
    # (no cross-item interference in the planner).
    a = make_row("a", 0.8, {"priya": 4, "mom": 2})
    b = make_row("b", 0.4, {"priya": 4, "mom": 4})
    both = plan_for([a, b], base_signals)
    just_b = plan_for([b], base_signals)
    b_in_both = [x for x in both if x[0] == "b"]
    out.append(f"CF2 remove-item: b unchanged: {b_in_both == just_b}")

    # CF3: add a guest. Depths must not rise (K3 at planner level).
    guest_row = make_row("g", 0.7, {"priya": 4, "mom": 3})
    before = plan_for([guest_row], base_signals)[0][2]
    guest_signals = base_signals + [Signal(DECLARE_PRESENT, "guest_anna", NOW - 10)]
    priors2 = dict(priors, guest_anna=logit(0.5))
    plan = plan_briefing(
        signals=guest_signals, priors=priors2, rows=[guest_row], owner="priya",
        ledger=initial_ledger(),
        hidden_from={"g": frozenset({"mom", "guest_anna"})},
        unknown_logit=logit(0.01), now=NOW)
    after = plan.items[0].depth
    out.append(f"CF3 add-guest: depth {before} -> {after} (never rises: {after <= before})")

    # CF4: replay yesterday's ALONE. Same signals + same now -> bit-identical.
    alone = [Signal(ALONE, "priya", NOW - 3600)]
    r_a = plan_for([make_row("x", 0.5, {"priya": 4, "mom": 4})], alone)
    r_b = plan_for([make_row("x", 0.5, {"priya": 4, "mom": 4})], alone)
    out.append(f"CF4 replay-alone: deterministic replay identical: {r_a == r_b}")

    # CF5: ALONE ignored for high-sensitivity (the D3 gate, end to end).
    hi = make_row("hi", 0.9, {"priya": 4, "mom": 0})
    plan_hi = plan_briefing(
        signals=[Signal(ALONE, "priya", NOW - 60)], priors=priors, rows=[hi],
        owner="priya", ledger=initial_ledger(), unknown_logit=logit(0.01), now=NOW)
    mom_credible = "mom" in plan_hi.items[0].credible
    out.append(f"CF5 alone-vs-high-sensitivity: mom still credible: {mom_credible} "
               f"(decision={plan_hi.items[0].decision})")

    return "\n".join(out) + "\n"


def main():
    import os
    evdir = os.path.join("evidence", "hotlane")
    os.makedirs(evdir, exist_ok=True)
    lat = latency_evidence()
    cf = counterfactual_evidence()
    with open(os.path.join(evdir, "latency.txt"), "w") as f:
        f.write(lat)
    with open(os.path.join(evdir, "counterfactuals.txt"), "w") as f:
        f.write(cf)
    print(lat)
    print(cf)


if __name__ == "__main__":
    main()
