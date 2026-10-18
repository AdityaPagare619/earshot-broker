"""Tests for analysis/ — latency measurement and cost model."""
import unittest

from ..analysis.cost_model import (CostInputs, break_even_monthly_price,
                                   cost_per_device_year, scenarios,
                                   sensitivity)
from ..analysis.latency import budget_table, measure_kernel_latency


class TestLatency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = measure_kernel_latency(iterations=2000)

    def test_all_kernel_ops_measured(self):
        ops = {s.operation for s in self.samples}
        self.assertTrue(
            {"accept", "open_private", "public_projection", "room_projection",
             "derive", "prepare", "redeem"}.issubset(ops))

    def test_percentiles_sane(self):
        for s in self.samples:
            self.assertGreater(s.p50_ms, 0, s.operation)
            self.assertGreaterEqual(s.p95_ms, s.p50_ms, s.operation)
            self.assertGreaterEqual(s.p99_ms, s.p95_ms, s.operation)
            # kernel ops must be far below the 500ms budget individually
            self.assertLess(s.p99_ms, 50.0, s.operation)

    def test_budget_table_labels_basis(self):
        rows = budget_table(self.samples)
        measured = [r for r in rows if r["basis"].startswith("MEASURED")]
        assumed = [r for r in rows if r["basis"].startswith("ASSUMED")]
        mixed = [r for r in rows if r["basis"].startswith("MIXED")]
        self.assertTrue(measured, "no measured rows")
        self.assertTrue(assumed, "no assumed rows")
        self.assertEqual(len(mixed), 1, "exactly one labeled total row")
        self.assertIn("NOT a claim", mixed[0]["basis"])


class TestCostModel(unittest.TestCase):
    def test_base_breakdown(self):
        b = cost_per_device_year(CostInputs())
        self.assertGreater(b.total_usd_per_year, 0)
        # the planner call dominates COGS — the model's headline finding
        self.assertGreater(b.model_share, 0.90)

    def test_scenarios_ordered(self):
        s = scenarios()
        self.assertLess(s["low"].total_usd_per_year,
                        s["base"].total_usd_per_year)
        self.assertLess(s["base"].total_usd_per_year,
                        s["high"].total_usd_per_year)

    def test_sensitivity_ranks_planner_inputs_first(self):
        ranked = [name for name, _, _ in sensitivity(CostInputs())]
        # the three multiplicative drivers of planner cost dominate; infra and
        # storage are rounding errors. (requests_per_device_per_day scales the
        # model term too, so it belongs in the top three.)
        self.assertEqual(
            set(ranked[:3]),
            {"model_cost_per_call_usd", "private_task_fraction",
             "requests_per_device_per_day"})
        self.assertNotIn("storage_gb_per_user", ranked[:3])
        self.assertNotIn("infra_cost_per_million_requests_usd", ranked[:3])

    def test_break_even_positive(self):
        price = break_even_monthly_price(CostInputs())
        self.assertGreater(price, 0)
        # base COGS ~$4.4/yr -> 50% margin needs ~$0.73/mo; sanity bound
        self.assertLess(price, 5.0)

    def test_zero_planner_fraction_kills_model_cost(self):
        b = cost_per_device_year(CostInputs(private_task_fraction=0.0))
        self.assertEqual(b.model_usd_per_year, 0.0)


if __name__ == "__main__":
    unittest.main()
