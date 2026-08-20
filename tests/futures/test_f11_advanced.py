"""Tests for Futures F11 advanced modeling baseline."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures_quality import FuturesQualityFlag  # noqa: E402
from market_platform_foundation.futures.advanced_baseline import (  # noqa: E402
    FUTURES_ENGINEERED_METHOD,
    compute_family_engineered_baseline,
    compute_futures_forecast_from_inputs,
)
from market_platform_foundation.futures.advanced_features import (  # noqa: E402
    build_futures_feature_vector,
)
from market_platform_foundation.futures.research.baseline_harness import (  # noqa: E402
    load_es_f11_baseline_dataset,
    run_f11_baseline_gate_validation,
    run_f11_baseline_walk_forward_harness,
)
from market_platform_foundation.futures.research.gates import (  # noqa: E402
    GATE_MILESTONE_F11_S1,
    GATE_MILESTONE_FQ8,
    evaluate_f11_s1_gate,
    evaluate_fq8_gate,
)
from market_platform_foundation.features.institutional import configure_institutional_ledger  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.composition import configure_fixture_provider_composition  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_futures_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402


class F11FeatureTests(unittest.TestCase):
    def test_unimplemented_family_fail_closed(self) -> None:
        vector = build_futures_feature_vector(
            instrument_family="CL",
            trend_3m=1.2,
            cot_available=True,
            net_percentile=0.9,
        )
        self.assertFalse(vector.family_supported)
        self.assertIn("FAMILY_MODEL_UNIMPLEMENTED", vector.quality_flags)
        forecast = compute_family_engineered_baseline(vector)
        self.assertEqual(forecast.model_confidence, 0.0)
        self.assertEqual(forecast.outright_up_probability, 0.5)

    def test_stale_cot_omits_crowding(self) -> None:
        vector = build_futures_feature_vector(
            instrument_family="ES",
            trend_3m=1.0,
            cot_available=False,
            net_percentile=None,
        )
        self.assertFalse(vector.cot_available)
        self.assertEqual(vector.crowding_signal, 0.0)
        self.assertIn(FuturesQualityFlag.POSITIONING_UNKNOWN.value, vector.quality_flags)


class F11GateUnitTests(unittest.TestCase):
    def test_insufficient_sample_when_empty(self) -> None:
        result = evaluate_f11_s1_gate([], [], [])
        self.assertEqual(result["gate_milestone"], GATE_MILESTONE_F11_S1)
        self.assertEqual(result["gate_status"], "INSUFFICIENT_SAMPLE")

    def test_fq8_fail_when_probability_unchanged(self) -> None:
        result = evaluate_fq8_gate(0.6, 0.6, cot_available=True)
        self.assertEqual(result["gate_milestone"], GATE_MILESTONE_FQ8)
        self.assertEqual(result["gate_status"], "FAIL")

    def test_fq8_pass_when_crowding_changes_probability(self) -> None:
        result = evaluate_fq8_gate(0.4, 0.62, cot_available=True)
        self.assertEqual(result["gate_status"], "PASS")


class F11HarnessTests(unittest.TestCase):
    def test_walk_forward_gate_pass(self) -> None:
        dataset = load_es_f11_baseline_dataset()
        harness = run_f11_baseline_walk_forward_harness(dataset)
        self.assertTrue(harness.get("available"))
        evaluation = harness.get("f11_s1_evaluation", {})
        self.assertEqual(evaluation.get("gate_status"), "PASS")

    def test_engineered_method_on_inputs(self) -> None:
        result = compute_futures_forecast_from_inputs(
            instrument_family="ES",
            trend_3m=1.5,
            annualized_carry=0.04,
            curve_slope_change=0.0003,
            net_percentile=1.0,
            crowding_regime="CROWDED_LONG",
            stress_score=0.2,
            cot_available=True,
        )
        self.assertEqual(result.futures_model_version, FUTURES_ENGINEERED_METHOD)
        self.assertEqual(result.baseline_tier, "M8")
        self.assertEqual(result.direction_bias, "UP")


class F11GoldenFixtureTests(unittest.TestCase):
    def test_es_f11_baseline_expected_matches_computed(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_f11_baseline_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        report = run_f11_baseline_gate_validation()
        self.assertEqual(report["aggregate_status"], expected["aggregate_status"])
        self.assertEqual(report["gate_summary"], expected["gate_summary"])
        latest = expected["latest_futures_forecast"]
        self.assertEqual(latest["futures_model_version"], FUTURES_ENGINEERED_METHOD)
        self.assertEqual(latest["baseline_tier"], "M8")


class F11WorkspaceTests(unittest.TestCase):
    def test_workspace_exposes_latest_futures_forecast(self) -> None:
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        configure_fixture_provider_composition()
        configure_institutional_ledger(build_combined_fixture_ledger(as_of_time_ns=cutoff))
        payload = build_workspace_futures_payload(
            "ES",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        configure_institutional_ledger(None)
        forecast = payload.get("latest_futures_forecast")
        self.assertIsInstance(forecast, dict)
        assert isinstance(forecast, dict)
        self.assertEqual(forecast.get("futures_model_version"), FUTURES_ENGINEERED_METHOD)
        self.assertTrue(forecast.get("research_only"))
        self.assertTrue(payload.get("futures_advanced_forecast_available"))


if __name__ == "__main__":
    unittest.main()
