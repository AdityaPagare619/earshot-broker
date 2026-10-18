"""Latency analysis: MEASURED kernel numbers + LABELED assumptions.

Dossier §13.1 gives a warm-path engineering allocation that is explicitly "not
measured results", and §14.2 demands: measure the network round trip, not the
kernel time. This module does the honest version of what is measurable here:

* measures the real kernel operations with time.perf_counter over many
  iterations -> p50/p95/p99 (MEASURED);
* composes the §13.1 budget table with a two-column layout: measured vs
  assumed, where every assumed row is labeled as an assumption with its
  source (dossier allocation), never presented as a measurement;
* REFUSES to print a single "total latency" without the assumption column
  beside it.

What this does NOT do: claim the 500ms MCP round-trip budget is met. That
needs J3's real-server measurement over a network. This module says exactly
where the measured part ends.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass


def _kernel():
    import importlib.util
    from pathlib import Path
    here = Path(__file__).resolve()
    # services/gateway/config/analysis/latency.py -> repo root is 5 levels up
    root = here.parents[4]
    path = root / "packages" / "kernel" / "kernel.py"
    spec = importlib.util.spec_from_file_location("earshot_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@dataclass(frozen=True)
class LatencySample:
    operation: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    n: int


def _percentile(data: list[float], q: float) -> float:
    if not data:
        return 0.0
    ordered = sorted(data)
    idx = min(len(ordered) - 1, int(q * len(ordered)))
    return ordered[idx]


def measure_kernel_latency(iterations: int = 10_000) -> list[LatencySample]:
    """Measure real kernel operations. Returns per-operation p50/p95/p99."""
    k = _kernel()
    kernel = k.Kernel()
    pub = k.Fact("weather", "Rain is forecast.", k.Label(frozenset({"*"})))
    # NOTE: label readers must name the audience members ("alice"), matching
    # how the kernel test suite binds Context audience to Label readers.
    pri = k.Fact("appt", "Clinic 3pm",
                 k.Label(frozenset({"alice"}), frozenset({"health"})))
    facts = (pub, pri)
    ctx_pub = k.Context("t1", "alice", frozenset({"alice"}), 1, 1000.0,
                        True, True, False, 1)
    ctx_ctrl = k.Context("t1", "alice", frozenset({"alice"}), 1, 1000.0,
                         True, True, True, 1)

    rec = kernel.accept("t1", "alice", "lat-key", facts, now=1000.0)

    def bench(fn):
        samples = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - t0) * 1000.0)
        return samples

    # accept() with a fresh request key each call (dedup path would be cheaper)
    counter = [0]

    def do_accept():
        counter[0] += 1
        kernel.accept("t1", "alice", f"lat-key-{counter[0]}", facts, now=1000.0)

    ops = {
        "accept": do_accept,
        "open_private": lambda: kernel.open_private(
            rec["receipt"], "t1", "alice", True, now=1001.0),
        "public_projection": lambda: k.Kernel.public_projection(facts),
        "room_projection": lambda: k.Kernel.room_projection(facts, ctx_ctrl, 1000.0),
        "derive": lambda: k.Kernel.derive("plan", "leave at 2", (pub, pri)),
        "prepare": lambda: k.Kernel.prepare(pri, ctx_ctrl, 1000.0),
    }
    lease = k.Kernel.prepare(pri, ctx_ctrl, 1000.0)
    ops["redeem"] = lambda: k.Kernel.redeem(lease, ctx_ctrl, 1000.0)

    results = []
    for name, fn in ops.items():
        # warmup
        for _ in range(100):
            fn()
        samples = bench(fn)
        results.append(LatencySample(
            operation=name,
            p50_ms=_percentile(samples, 0.50),
            p95_ms=_percentile(samples, 0.95),
            p99_ms=_percentile(samples, 0.99),
            n=iterations,
        ))
    return results


# Dossier §13.1 allocations, labeled as what they are: hypotheses.
_ASSUMED_ROWS = [
    ("Network and edge overhead", 120.0, "dossier §13.1 allocation (hypothesis)"),
    ("Token validation / request validation", 25.0, "dossier §13.1 allocation (hypothesis)"),
    ("Snapshot and compiled-policy lookup", 35.0, "dossier §13.1 allocation (hypothesis)"),
    ("Durable receipt + queue write", 30.0, "dossier §13.1 allocation (hypothesis)"),
    ("Headroom", 120.0, "dossier §13.1 allocation (hypothesis)"),
]


def budget_table(samples: list[LatencySample]) -> list[dict]:
    """Two-column budget: MEASURED kernel rows + ASSUMED system rows.

    The kernel rows use the measured p99 of the operations on the request
    path (accept + public_projection for Profile A). Everything else is
    labeled ASSUMED. No single total is presented as measured.
    """
    by_op = {s.operation: s for s in samples}
    rows: list[dict] = []
    for op in ("accept", "public_projection"):
        s = by_op.get(op)
        if s:
            rows.append({
                "stage": f"kernel.{op} (p99)",
                "ms": round(s.p99_ms, 4),
                "basis": f"MEASURED — {s.n} local iterations",
            })
    for stage, ms, basis in _ASSUMED_ROWS:
        rows.append({"stage": stage, "ms": ms, "basis": f"ASSUMED — {basis}"})
    rows.append({
        "stage": "TOTAL (illustrative only)",
        "ms": round(sum(r["ms"] for r in rows), 2),
        "basis": "MIXED — measured kernel + assumed system; NOT a claim",
    })
    return rows


def report(samples: list[LatencySample]) -> str:
    lines = ["kernel latency (local, ms):"]
    lines.append(f"{'operation':<20}{'p50':>10}{'p95':>10}{'p99':>10}{'n':>8}")
    for s in samples:
        lines.append(f"{s.operation:<20}{s.p50_ms:>10.4f}{s.p95_ms:>10.4f}"
                     f"{s.p99_ms:>10.4f}{s.n:>8}")
    lines.append("")
    lines.append("500ms-budget composition (measured vs assumed):")
    lines.append(f"{'stage':<42}{'ms':>10}  basis")
    for r in budget_table(samples):
        lines.append(f"{r['stage']:<42}{r['ms']:>10}  {r['basis']}")
    lines.append("")
    lines.append("NOTE: the 500ms MCP round-trip budget can only be verified by "
                 "J3's real-server measurement over a network. Kernel time is "
                 "necessary but not sufficient evidence.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(measure_kernel_latency()))
