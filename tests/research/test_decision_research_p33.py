"""P3.3 decision research tests.

Includes the current P3.3 `evaluate_experiment` behavior lock
(:class:`EvaluateExperimentLegacyBaselineP33`). DECISION-RESEARCH-001 Task 6
replaces the hard-coded 5/20 thresholds with card-driven ``min_sample_oos``
statuses; when it lands, update that class to the new contract explicitly
instead of letting it break unnoticed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.research.decision_research import (
    SHORT_SQUEEZE_EXPERIMENTS,
    reject_historical_finviz_screen_without_capture,
    run_short_squeeze_family,
    validate_temporal_example,
)
from market_platform_foundation.research.decision_research.experiments import evaluate_experiment
from market_platform_foundation.research.decision_research.pit_gate import chronological_split


def _valid_example(*, decision_time_ns: int, positive: bool) -> dict:
    """Build a PIT-valid example: features before decision, outcome after."""
    return {
        "decision_time_ns": decision_time_ns,
        "features": [
            {
                "available_time_ns": decision_time_ns - 100,
                "evidence_family": "SQUEEZE_STATE",
            }
        ],
        "outcome_time_ns": decision_time_ns + 5000,
        "outcome": {"positive": positive},
    }


def _make_examples(n: int, *, positive_from: int = 0) -> list[dict]:
    """``n`` PIT-valid examples; examples[i] is positive when ``i >= positive_from``."""
    return [
        _valid_example(decision_time_ns=(i + 1) * 1000, positive=i >= positive_from)
        for i in range(n)
    ]


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


class EvaluateExperimentLegacyBaselineP33(unittest.TestCase):
    """Legacy lock on P3.3 ``evaluate_experiment`` (hard-coded 5/20 thresholds, in-sample).

    Every assertion here documents behavior Task 6 of DECISION-RESEARCH-001 will
    intentionally change to card-driven ``min_sample_oos`` with OOS-only metrics.
    The runner's current in-sample (TRAIN split) evaluation is also pinned so the
    switch to OOS-only reporting is an explicit, reviewable diff.
    """

    SS_BASE = SHORT_SQUEEZE_EXPERIMENTS["SS-BASE"]
    SS_CAT = SHORT_SQUEEZE_EXPERIMENTS["SS-CAT"]

    # -- status thresholds ---------------------------------------------------
    def test_legacy_threshold_insufficient_below_5(self) -> None:
        for n in (0, 1, 4):
            result = evaluate_experiment(self.SS_BASE, _make_examples(n))
            self.assertEqual(result["status"], "INSUFFICIENT_DATA", f"n={n}")
            self.assertEqual(result["sample_count"], n)

    def test_legacy_threshold_prospective_5_to_19(self) -> None:
        for n in (5, 19):
            result = evaluate_experiment(self.SS_BASE, _make_examples(n))
            self.assertEqual(result["status"], "NEEDS_PROSPECTIVE_VALIDATION", f"n={n}")
            self.assertEqual(result["sample_count"], n)

    def test_legacy_threshold_inconclusive_at_20_and_above(self) -> None:
        for n in (20, 24, 30):
            result = evaluate_experiment(self.SS_BASE, _make_examples(n))
            self.assertEqual(result["status"], "INCONCLUSIVE", f"n={n}")
            self.assertEqual(result["sample_count"], n)

    def test_legacy_never_reports_supported(self) -> None:
        # Current code has no SUPPORTED / NOT_SUPPORTED path at any sample count.
        result = evaluate_experiment(self.SS_BASE, _make_examples(30))
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertNotIn(result["status"], {"SUPPORTED", "NOT_SUPPORTED"})

    # -- PIT filtering --------------------------------------------------------
    def test_legacy_pit_invalid_excluded_from_sample_count(self) -> None:
        examples = _make_examples(5)
        examples[0]["features"][0]["available_time_ns"] = examples[0]["decision_time_ns"] + 1
        result = evaluate_experiment(self.SS_BASE, examples)
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")

    # -- metrics --------------------------------------------------------------
    def test_legacy_precision_and_false_positive_rate(self) -> None:
        examples = _make_examples(6, positive_from=4)  # 2/6 positive
        result = evaluate_experiment(self.SS_BASE, examples)
        self.assertAlmostEqual(result["metrics"]["precision"], 2.0 / 6.0)
        self.assertAlmostEqual(result["metrics"]["false_positive_rate"], 4.0 / 6.0)

    def test_legacy_false_positive_rate_is_none_at_zero_precision(self) -> None:
        # Subtle legacy behavior: fpr short-circuits to None when precision == 0,
        # rather than reporting 1.0.
        examples = _make_examples(6, positive_from=999)  # all negative
        result = evaluate_experiment(self.SS_BASE, examples)
        self.assertEqual(result["metrics"]["precision"], 0.0)
        self.assertIsNone(result["metrics"]["false_positive_rate"])

    def test_legacy_identity_and_promotion_fields(self) -> None:
        result = evaluate_experiment(self.SS_CAT, _make_examples(5))
        self.assertEqual(result["experiment_id"], "SS-CAT")
        self.assertEqual(result["baseline_id"], "SS-BASE")
        self.assertEqual(result["added_evidence"], ["CATALYST"])
        self.assertEqual(result["strategy_promotion"], "NONE")

    # -- family runner (in-sample TRAIN split) --------------------------------
    def test_legacy_runner_evaluates_on_train_split_in_sample(self) -> None:
        # 24 PIT-valid examples -> chronological_split train = int(24*0.6) = 14,
        # so every family member is evaluated on 14 in-sample examples (not OOS).
        result = run_short_squeeze_family(_make_examples(24))
        self.assertEqual(result["splits"]["train"], 14)
        for row in result["experiments"]:
            self.assertEqual(row["sample_count"], 14)
            self.assertEqual(row["status"], "NEEDS_PROSPECTIVE_VALIDATION")

    def test_legacy_runner_statuses_follow_train_size(self) -> None:
        # 8 total PIT-valid examples, but the runner evaluates on the TRAIN split
        # only (int(8*0.6) = 4) — below the n<5 threshold despite 8 valid inputs.
        # Pins the in-sample train-split semantics Task 6 replaces with OOS.
        result = run_short_squeeze_family(_make_examples(8))
        self.assertEqual(result["splits"]["train"], 4)
        for row in result["experiments"]:
            self.assertEqual(row["sample_count"], 4)
            self.assertEqual(row["status"], "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
