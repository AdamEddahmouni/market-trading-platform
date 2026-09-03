"""Tests for O10 distributional baseline research milestones."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.research.distributional_baseline import (  # noqa: E402
    GATE_MILESTONE_R_O5,
    evaluate_p_baseline_oos,
    forecast_distributional_baseline,
    option_return_linear_factors,
)
from market_platform_foundation.options.research.harness import (  # noqa: E402
    load_options_baseline_dataset,
    run_options_baseline_walk_forward_harness,
)


class OptionsO10DistributionalBaselineTests(unittest.TestCase):
    def test_forecast_distributional_baseline_from_bars(self) -> None:
        dataset = load_options_baseline_dataset()
        closes = [float(bar["close"]) for bar in dataset["bars"]]
        result = forecast_distributional_baseline(
            closes,
            symbol="NVDA",
            as_of_time="2026-07-21T20:30:00.000000000Z",
        )
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("gate_milestone"), GATE_MILESTONE_R_O5)
        self.assertIn("vol_forecast_annualized", result)

    def test_evaluate_p_baseline_oos_qlike_gate(self) -> None:
        predictions = [0.25, 0.26, 0.27, 0.28]
        realized = [0.24, 0.25, 0.26, 0.27]
        naive = [0.30, 0.30, 0.30, 0.30]
        result = evaluate_p_baseline_oos(predictions, realized, naive_predictions=naive)
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("gate_status"), "PASS")
        self.assertIsNotNone(result.get("mean_qlike"))

    def test_option_return_linear_factors_research_only(self) -> None:
        result = option_return_linear_factors(delta=0.5, vega=0.2, vol_exposure=0.15)
        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("target_id"), "T-OPT")
        self.assertTrue(result.get("not_trade_signal"))

    def test_walk_forward_harness_smoke(self) -> None:
        result = run_options_baseline_walk_forward_harness()
        self.assertTrue(result.get("available"))
        self.assertIn("r_o5_evaluation", result)
        self.assertIn("r_o10_surf_evaluation", result)
        self.assertGreater(result.get("fold_count", 0), 0)


if __name__ == "__main__":
    unittest.main()
