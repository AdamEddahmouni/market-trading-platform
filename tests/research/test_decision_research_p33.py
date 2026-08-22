"""P3.3 decision research tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.research.decision_research import (
    reject_historical_finviz_screen_without_capture,
    run_short_squeeze_family,
    validate_temporal_example,
)
from market_platform_foundation.research.decision_research.pit_gate import chronological_split


class DecisionResearchP33Tests(unittest.TestCase):
    def test_feature_after_decision_rejected(self) -> None:
        example = {
            "decision_time_ns": 1000,
            "features": [{"available_time_ns": 2000, "evidence_family": "CVD"}],
            "outcome_time_ns": 5000,
        }
        ok, reasons = validate_temporal_example(example)
        self.assertFalse(ok)
        self.assertTrue(any("FEATURE_AFTER_DECISION" in r for r in reasons))

    def test_outcome_must_be_after_decision(self) -> None:
        example = {
            "decision_time_ns": 5000,
            "features": [{"available_time_ns": 1000}],
            "outcome_time_ns": 1000,
        }
        ok, reasons = validate_temporal_example(example)
        self.assertFalse(ok)
        self.assertIn("OUTCOME_BEFORE_DECISION", reasons)

    def test_current_finviz_screen_cannot_be_historical(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="FINVIZ_SCREEN",
            capture_present=False,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION")

    def test_baseline_required_in_family(self) -> None:
        examples = [
            {
                "decision_time_ns": i * 1000,
                "features": [{"available_time_ns": i * 1000 - 100}],
                "outcome_time_ns": i * 1000 + 5000,
                "outcome": {"positive": i % 2 == 0},
            }
            for i in range(1, 25)
        ]
        result = run_short_squeeze_family(examples)
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertFalse(result["auto_strategy_promotion"])
        self.assertTrue(any(ex["experiment_id"] == "SS-BASE" for ex in result["experiments"]))

    def test_temporal_split(self) -> None:
        examples = [{"decision_time_ns": i} for i in range(10)]
        splits = chronological_split(examples)
        self.assertGreater(len(splits["train"]), 0)

    def test_insufficient_sample_inconclusive(self) -> None:
        examples = [
            {
                "decision_time_ns": 1000,
                "features": [{"available_time_ns": 900}],
                "outcome_time_ns": 2000,
                "outcome": {"positive": True},
            }
        ]
        result = run_short_squeeze_family(examples)
        ss_base = next(r for r in result["experiments"] if r["experiment_id"] == "SS-BASE")
        self.assertEqual(ss_base["status"], "INSUFFICIENT_DATA")

    def test_no_auto_strategy_promotion(self) -> None:
        result = run_short_squeeze_family([])
        for row in result["experiments"]:
            self.assertEqual(row.get("strategy_promotion"), "NONE")


if __name__ == "__main__":
    unittest.main()
