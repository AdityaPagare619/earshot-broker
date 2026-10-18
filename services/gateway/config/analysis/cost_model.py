"""Cost model: who pays for EARSHOT at 100M-device scale.

This module computes; it does not assert. Every default is a STATED
ASSUMPTION (October 2026 public-pricing knowledge), documented alongside the
number it produces. The deliverable is the sensitivity ranking — which input
moves the answer — not the point estimate.

Headline finding (base case): the bounded-AI planner call dominates COGS
(~99% of per-device cost). Storage and request infra are rounding errors.
That single fact answers "who pays": this cannot be a free-tier feature at
planner-call rates — it needs a subscription attach, an Amazon bundle
subsidy, or aggressive planner-call gating/caching. See docs/impact.md.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class CostInputs:
    """All inputs are annualizable rates. Defaults are stated assumptions."""

    requests_per_device_per_day: float = 20.0
    # Fraction of requests that need the bounded AI planner (dossier §7.2).
    # The rest are served by deterministic paths (precomputed plans, receipts).
    private_task_fraction: float = 0.30
    # Cost of one bounded planner call (small model, short context).
    # ASSUMPTION — reprice by editing this field, not the code.
    model_cost_per_call_usd: float = 0.002
    # Encrypted private records retained per user.
    storage_gb_per_user: float = 0.05
    storage_cost_per_gb_month_usd: float = 0.023
    # Gateway API + database, per million requests. ASSUMPTION.
    infra_cost_per_million_requests_usd: float = 2.0

    def assumptions(self) -> dict[str, str]:
        return {
            "requests_per_device_per_day":
                "ASSUMPTION — 20 task initiations/day/device; sensitivity-tested",
            "private_task_fraction":
                "ASSUMPTION — 30% need the planner; the lever that matters most",
            "model_cost_per_call_usd":
                "ASSUMPTION (Oct 2026) — small-model short-context call; reprice as needed",
            "storage_gb_per_user":
                "ASSUMPTION — 50 MB encrypted private records per user",
            "storage_cost_per_gb_month_usd":
                "Public object-storage pricing knowledge, Oct 2026",
            "infra_cost_per_million_requests_usd":
                "ASSUMPTION — API + managed DB amortized; excludes model calls",
        }


@dataclass(frozen=True)
class CostBreakdown:
    model_usd_per_year: float
    infra_usd_per_year: float
    storage_usd_per_year: float

    @property
    def total_usd_per_year(self) -> float:
        return (self.model_usd_per_year + self.infra_usd_per_year
                + self.storage_usd_per_year)

    @property
    def model_share(self) -> float:
        total = self.total_usd_per_year
        return self.model_usd_per_year / total if total else 0.0


def cost_per_device_year(inp: CostInputs) -> CostBreakdown:
    requests_per_year = inp.requests_per_device_per_day * 365.0
    model = (requests_per_year * inp.private_task_fraction
             * inp.model_cost_per_call_usd)
    infra = requests_per_year / 1e6 * inp.infra_cost_per_million_requests_usd
    storage = inp.storage_gb_per_user * inp.storage_cost_per_gb_month_usd * 12.0
    return CostBreakdown(model, infra, storage)


def scenarios() -> dict[str, CostBreakdown]:
    """Low / base / high. Ranges are the honest unit, not the point."""
    base = CostInputs()
    low = CostInputs(
        requests_per_device_per_day=8.0,
        private_task_fraction=0.15,
        model_cost_per_call_usd=0.0005,
    )
    high = CostInputs(
        requests_per_device_per_day=40.0,
        private_task_fraction=0.60,
        model_cost_per_call_usd=0.008,
        storage_gb_per_user=0.20,
    )
    return {
        "low": cost_per_device_year(low),
        "base": cost_per_device_year(base),
        "high": cost_per_device_year(high),
    }


def sensitivity(inp: CostInputs) -> list[tuple[str, float, float]]:
    """Vary each input ±50%; rank by absolute change in $/device/year.

    Returns (input_name, cost_at_minus_50pct, cost_at_plus_50pct), ranked by
    spread descending. This is the VP's question: 'what breaks the model?'
    """
    base_total = cost_per_device_year(inp).total_usd_per_year
    rows = []
    for f in fields(inp):
        name = f.name
        lo_kwargs = {name: getattr(inp, name) * 0.5}
        hi_kwargs = {name: getattr(inp, name) * 1.5}
        from dataclasses import replace
        lo = cost_per_device_year(replace(inp, **lo_kwargs)).total_usd_per_year
        hi = cost_per_device_year(replace(inp, **hi_kwargs)).total_usd_per_year
        rows.append((name, lo, hi, hi - lo))
    rows.sort(key=lambda r: r[3], reverse=True)
    return [(name, lo, hi) for name, lo, hi, _ in rows]


def break_even_monthly_price(inp: CostInputs, target_margin: float = 0.5) -> float:
    """Subscription price/month needed for target gross margin on COGS."""
    total = cost_per_device_year(inp).total_usd_per_year
    return (total / (1.0 - target_margin)) / 12.0


def report(inp: CostInputs | None = None) -> str:
    inp = inp or CostInputs()
    b = cost_per_device_year(inp)
    lines = [
        "COST PER DEVICE-YEAR (base case; every input is a stated assumption):",
        f"  model inference : ${b.model_usd_per_year:8.2f}  ({b.model_share*100:.1f}% of COGS)",
        f"  request infra   : ${b.infra_usd_per_year:8.2f}",
        f"  storage         : ${b.storage_usd_per_year:8.2f}",
        f"  TOTAL           : ${b.total_usd_per_year:8.2f} / device / year",
        "",
        "scenarios:",
    ]
    for name, cb in scenarios().items():
        lines.append(f"  {name:<6} ${cb.total_usd_per_year:7.2f}/yr "
                     f"(model share {cb.model_share*100:.0f}%)")
    lines.append("")
    lines.append("sensitivity (±50% per input, ranked by spread):")
    for name, lo, hi in sensitivity(inp):
        lines.append(f"  {name:<42} ${lo:6.2f} .. ${hi:6.2f}")
    lines.append("")
    lines.append(
        f"break-even at 50% gross margin: "
        f"${break_even_monthly_price(inp):.2f}/month subscription")
    lines.append("")
    lines.append("READ: model inference dominates. The business question is "
                 "planner-call gating/caching, not infra optimization.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
