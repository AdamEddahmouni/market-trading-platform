"""SS P7 advanced model tests — pain, magnitude, ensemble."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.research.squeeze_models import (  # noqa: E402
    estimate_short_pain_distribution,
    predict_squeeze_ensemble,
    predict_squeeze_magnitude,
    precision_at_k,
    run_squeeze_walk_forward_harness,
)

_PAIN_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "short_pain_proxy_slice.json"
_MAGNITUDE_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "magnitude_scenario.json"


class SqueezeP7ModelTests(unittest.TestCase):
    def test_pain_distribution_fail_closed_without_proxy(self) -> None:
        dist = estimate_short_pain_distribution(
            symbol="NVDA",
            spot_price=128.5,
            entry_price_proxy=None,
            observation_time="2026-07-21T20:30:10.000000000Z",
            available_time="2026-07-21T20:30:10.000000000Z",
        )
        self.assertEqual(dist.status, "UNAVAILABLE")
        self.assertIsNone(dist.underwater_pct)

    def test_pain_proxy_fixture_estimates_research_proxy(self) -> None:
        scenario = json.loads(_PAIN_FIXTURE.read_text(encoding="utf-8"))
        dist = estimate_short_pain_distribution(
            symbol=scenario["symbol"],
            spot_price=scenario["spot_price"],
            entry_price_proxy=scenario["entry_price_proxy"],
            observation_time=scenario["observation_time"],
            available_time=scenario["available_time"],
        )
        self.assertEqual(dist.status, "RESEARCH_PROXY")
        assert dist.underwater_pct is not None
        self.assertGreaterEqual(dist.underwater_pct, scenario["expected"]["min_underwater_pct"])
        self.assertEqual(len(dist.pain_percentiles or ()), 3)

    def test_magnitude_fail_closed_without_physical_forecast(self) -> None:
        result = predict_squeeze_magnitude([0.5, 0.3, 0.2])
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["expected_move_pct"])

    def test_magnitude_scenario_fixture(self) -> None:
        scenario = json.loads(_MAGNITUDE_FIXTURE.read_text(encoding="utf-8"))
        result = predict_squeeze_magnitude(
            scenario["features"],
            squeeze_context=scenario["squeeze_context"],
            physical_forecast=scenario["physical_forecast"],
        )
        self.assertEqual(result["status"], "RESEARCH_ONLY")
        assert result["expected_move_pct"] is not None
        self.assertGreaterEqual(
            result["expected_move_pct"],
            scenario["expected"]["min_expected_move_pct"],
        )

    def test_rare_event_ensemble_returns_hazard_by_horizon(self) -> None:
        result = predict_squeeze_ensemble([0.6, 0.4, 0.3], horizon_days=5)
        self.assertIn("occurrence_probability", result)
        self.assertIn("hazard_by_horizon", result)
        self.assertIn(5, result["hazard_by_horizon"])
        self.assertEqual(len(result["head_probabilities"]), 3)

    def test_walk_forward_harness_reports_ensemble_and_precision(self) -> None:
        report = run_squeeze_walk_forward_harness()
        self.assertEqual(report["pit_status"], "PASS")
        self.assertIn("ensemble_calibration", report)
        self.assertIn("precision_at_k", report["calibration"])
        self.assertIn("precision_at_k", report["ensemble_calibration"])

    def test_precision_at_k(self) -> None:
        preds = [0.9, 0.8, 0.2, 0.1]
        labels = [True, False, True, False]
        score = precision_at_k(preds, labels, k=2)
        self.assertEqual(score, 0.5)


if __name__ == "__main__":
    unittest.main()
