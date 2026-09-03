"""Order Flow OF12 LOB baseline tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.order_flow import (  # noqa: E402
    LOB_BASELINE_METHOD,
    build_lob_feature_vector,
    compute_lob_baseline_forecast,
    compute_m1_cvd_baseline,
)
from market_platform_foundation.order_flow.contracts import ForecastDirection  # noqa: E402
from market_platform_foundation.order_flow.research.baseline_harness import (  # noqa: E402
    load_es_lob_baseline_dataset,
    run_of12_baseline_gate_validation,
    run_of12_baseline_walk_forward_harness,
)
from market_platform_foundation.order_flow.research.gates import (  # noqa: E402
    evaluate_of12_s1_gate,
    evaluate_of_q9_gate,
)


class LobFeatureTests(unittest.TestCase):
    def test_invalid_book_fail_closed(self) -> None:
        snapshot = {"bids": [], "asks": []}
        vector = build_lob_feature_vector(snapshot, ofi_value=1.0, book_state_valid=False)
        self.assertFalse(vector.book_state_valid)
        self.assertIn("BOOK_STATE_INVALID", vector.quality_flags)

    def test_mbo_unavailable_flag_when_no_queue(self) -> None:
        snapshot = {
            "bids": [{"price": 100.0, "size": 50}],
            "asks": [{"price": 100.1, "size": 40}],
        }
        vector = build_lob_feature_vector(snapshot, ofi_value=10.0, book_state_valid=True)
        self.assertIn("MBO_UNAVAILABLE", vector.quality_flags)


class LobBaselineTests(unittest.TestCase):
    def test_m8_beats_m1_on_fixture_gate(self) -> None:
        dataset = load_es_lob_baseline_dataset()
        harness = run_of12_baseline_walk_forward_harness(dataset)
        self.assertTrue(harness.get("available"))
        evaluation = harness.get("of12_s1_evaluation", {})
        self.assertEqual(evaluation.get("gate_status"), "PASS")

    def test_m8_forecast_method(self) -> None:
        snapshot = {
            "bids": [{"price": 6000.0, "size": 50}],
            "asks": [{"price": 6002.0, "size": 10}],
        }
        result = compute_lob_baseline_forecast(
            snapshot,
            ofi_value=120.0,
            book_state_valid=True,
            fragility_score=0.2,
            resiliency_score=0.7,
            bar_delta=80.0,
        )
        self.assertEqual(result.lob_model_version, LOB_BASELINE_METHOD)
        self.assertEqual(result.baseline_tier, "M8")
        self.assertGreaterEqual(result.mid_up_probability, 0.0)
        self.assertLessEqual(result.mid_up_probability, 1.0)

    def test_m1_cvd_only_comparator(self) -> None:
        snapshot = {
            "bids": [{"price": 6000.0, "size": 50}],
            "asks": [{"price": 6002.0, "size": 10}],
        }
        result = compute_m1_cvd_baseline(snapshot, bar_delta=100.0, book_state_valid=True)
        self.assertEqual(result.baseline_tier, "M1")
        self.assertEqual(result.direction_bias, ForecastDirection.UP)


class LobGoldenFixtureTests(unittest.TestCase):
    def test_es_lob_baseline_expected_matches_computed(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "order_flow" / "es_lob_baseline_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        report = run_of12_baseline_gate_validation()
        self.assertEqual(report["aggregate_status"], expected["aggregate_status"])
        self.assertEqual(report["gate_summary"], expected["gate_summary"])
        latest = expected["latest_lob_forecast"]
        self.assertEqual(latest["lob_model_version"], LOB_BASELINE_METHOD)
        self.assertEqual(latest["baseline_tier"], "M8")


class LobGateUnitTests(unittest.TestCase):
    def test_of12_s1_pass_when_m8_accuracy_wins(self) -> None:
        result = evaluate_of12_s1_gate(
            [0.4, 0.45, 0.5],
            [0.6, 0.65, 0.7],
            [True, True, False],
        )
        self.assertEqual(result["gate_status"], "PASS")

    def test_of_q9_pass_when_queue_upgrades_fill(self) -> None:
        result = evaluate_of_q9_gate(
            0.72,
            0.55,
            l2_queue_model="none",
            mbo_queue_model="fifo_displayed_mbo_v1",
        )
        self.assertEqual(result["gate_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
