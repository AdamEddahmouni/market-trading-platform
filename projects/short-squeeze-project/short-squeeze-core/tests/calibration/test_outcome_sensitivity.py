"""Tests for OUTCOME_SENSITIVITY calibration experiments."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration import run_calibration_from_path
from squeeze_core.calibration.models import OutcomeVariantSpec
from squeeze_core.calibration.outcome_sensitivity import apply_outcome_policy, outcome_policy_from_spec
from squeeze_core.research.models import OutcomeLabel, ResearchCaseClassification
from squeeze_core.research.serialization import deserialize_research_dataset


FIXTURES = ROOT / "tests" / "fixtures"
SYNTHETIC_EXPERIMENT = FIXTURES / "calibration" / "outcome_sensitivity_synthetic.json"
HISTORICAL_EXPERIMENT = FIXTURES / "calibration" / "outcome_sensitivity_historical.json"
DATASET = FIXTURES / "research" / "phase_3b_research_dataset.json"


class OutcomeSensitivityUnitTests(unittest.TestCase):
    def test_baseline_matches_stored_true_positive(self) -> None:
        dataset = deserialize_research_dataset(DATASET.read_bytes())
        row = next(row for row in dataset.rows if row.case_id == "SYN_TRUE_POSITIVE")
        policy = outcome_policy_from_spec(
            OutcomeVariantSpec(
                policy_version="phase_3b_outcome_label_policy.v1",
                upward_threshold_percent=Decimal("25"),
                downward_threshold_percent=Decimal("-25"),
                rationale_code="FIXED_UNOPTIMIZED_24_HOUR_RESEARCH_OUTCOME",
            )
        )
        updated = apply_outcome_policy(row, policy)
        self.assertEqual(updated.outcome_label, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE)
        self.assertEqual(updated.research_classification, ResearchCaseClassification.TRUE_POSITIVE)

    def test_symmetric_30_flips_boundary_cases(self) -> None:
        dataset = deserialize_research_dataset(DATASET.read_bytes())
        row = next(row for row in dataset.rows if row.case_id == "SYN_TRUE_POSITIVE")
        policy = outcome_policy_from_spec(
            OutcomeVariantSpec(
                policy_version="calibration.outcome.symmetric_30.v1",
                upward_threshold_percent=Decimal("30"),
                downward_threshold_percent=Decimal("-30"),
                rationale_code="CALIBRATION_OUTCOME_SYMMETRIC_30",
            )
        )
        updated = apply_outcome_policy(row, policy)
        self.assertEqual(updated.outcome_label, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE)
        self.assertEqual(updated.research_classification, ResearchCaseClassification.FALSE_POSITIVE)

    def test_upward_30_flips_biya_earliest_only(self) -> None:
        dataset = deserialize_research_dataset(DATASET.read_bytes())
        policy = outcome_policy_from_spec(
            OutcomeVariantSpec(
                policy_version="calibration.outcome.upward_30.v1",
                upward_threshold_percent=Decimal("30"),
                downward_threshold_percent=Decimal("-25"),
                rationale_code="CALIBRATION_OUTCOME_UPWARD_30",
            )
        )
        earliest = next(row for row in dataset.rows if row.case_id == "BIYA_EARLIEST_BOUNDARY")
        latest = next(row for row in dataset.rows if row.case_id == "BIYA_LATEST_BOUNDARY")
        updated_earliest = apply_outcome_policy(earliest, policy)
        updated_latest = apply_outcome_policy(latest, policy)
        self.assertEqual(updated_earliest.outcome_label, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE)
        self.assertEqual(updated_latest.outcome_label, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE)


class OutcomeSensitivityExperimentTests(unittest.TestCase):
    def test_synthetic_threshold_sweep(self) -> None:
        report = run_calibration_from_path(SYNTHETIC_EXPERIMENT)
        self.assertEqual(report.experiment_type.value, "OUTCOME_SENSITIVITY")
        symmetric_30 = next(
            item for item in report.variant_results if item.variant_id == "symmetric_30"
        )
        self.assertGreaterEqual(len(symmetric_30.flips_from_baseline), 1)
        flip_ids = {flip.case_id for flip in symmetric_30.flips_from_baseline}
        self.assertIn("SYN_TRUE_POSITIVE", flip_ids)
        self.assertIn("SYN_FALSE_NEGATIVE", flip_ids)

    def test_historical_upward_30_flips_earliest_boundary(self) -> None:
        report = run_calibration_from_path(HISTORICAL_EXPERIMENT)
        upward_30 = next(
            item for item in report.variant_results if item.variant_id == "upward_30"
        )
        flip_ids = {flip.case_id for flip in upward_30.flips_from_baseline}
        self.assertIn("BIYA_EARLIEST_BOUNDARY", flip_ids)
        self.assertNotIn("BIYA_LATEST_BOUNDARY", flip_ids)


if __name__ == "__main__":
    unittest.main()
