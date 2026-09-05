"""Tests for Phase 3D calibration pipeline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration import load_experiment, run_calibration_from_path
from squeeze_core.calibration.detection_ablation import apply_detection_policy, detection_policy_from_spec
from squeeze_core.calibration.models import DetectionVariantSpec
from squeeze_core.research.models import DetectionStatus, ResearchCaseClassification
from squeeze_core.research.serialization import deserialize_research_dataset


FIXTURES = ROOT / "tests" / "fixtures"
EXPERIMENT = FIXTURES / "calibration" / "detection_ablation_baseline.json"
PREDICATE_SYNTHETIC = FIXTURES / "calibration" / "detection_predicate_candidates_synthetic.json"
PREDICATE_HISTORICAL = FIXTURES / "calibration" / "detection_predicate_candidates_historical.json"
DATASET = FIXTURES / "research" / "phase_3b_research_dataset.json"


class DetectionAblationTests(unittest.TestCase):
    def test_baseline_matches_stored_synthetic_true_positive(self) -> None:
        dataset = deserialize_research_dataset(DATASET.read_bytes())
        row = next(row for row in dataset.rows if row.case_id == "SYN_TRUE_POSITIVE")
        policy = detection_policy_from_spec(
            DetectionVariantSpec(
                policy_version="phase_3b_research_detection_policy.v1",
                required_rule_ids=(
                    "PRICE_RANGE",
                    "MARKET_DATA_AVAILABLE",
                    "COMPLETED_BAR_AVAILABLE",
                ),
                rationale_code="STRUCTURAL_MOMENTUM_DISCOVERY_PREDICATE",
            )
        )
        updated = apply_detection_policy(row, policy)
        self.assertEqual(updated.research_detection_status, DetectionStatus.DETECTED)
        self.assertEqual(updated.research_classification, ResearchCaseClassification.TRUE_POSITIVE)

    def test_momentum_full_flips_false_positive_to_not_detected(self) -> None:
        dataset = deserialize_research_dataset(DATASET.read_bytes())
        row = next(row for row in dataset.rows if row.case_id == "SYN_FALSE_POSITIVE")
        policy = detection_policy_from_spec(
            DetectionVariantSpec(
                policy_version="calibration.detection.momentum_full.v1",
                required_rule_ids=(
                    "PRICE_RANGE",
                    "MARKET_DATA_AVAILABLE",
                    "COMPLETED_BAR_AVAILABLE",
                    "PERCENTAGE_CHANGE_MINIMUM",
                    "RELATIVE_VOLUME_MINIMUM",
                    "FLOAT_MAXIMUM",
                ),
                rationale_code="CALIBRATION_MOMENTUM_FULL_ABLATION",
            )
        )
        updated = apply_detection_policy(row, policy)
        self.assertEqual(updated.research_detection_status, DetectionStatus.NOT_DETECTED)
        self.assertEqual(updated.research_classification, ResearchCaseClassification.TRUE_NEGATIVE)


class CalibrationExperimentTests(unittest.TestCase):
    def test_load_experiment_fixture(self) -> None:
        experiment = load_experiment(EXPERIMENT)
        self.assertEqual(experiment.experiment_version, "detection_ablation_baseline.v1")
        self.assertEqual(len(experiment.variants), 3)

    def test_run_synthetic_detection_ablation(self) -> None:
        report = run_calibration_from_path(EXPERIMENT)
        self.assertEqual(report.experiment_type.value, "DETECTION_ABLATION")
        self.assertEqual(len(report.variant_results), 3)
        baseline = next(
            item for item in report.variant_results if item.variant_id == "baseline"
        )
        momentum_full = next(
            item for item in report.variant_results if item.variant_id == "momentum_full"
        )
        self.assertEqual(baseline.case_count, 11)
        self.assertGreaterEqual(len(momentum_full.flips_from_baseline), 1)
        flip_ids = {flip.case_id for flip in momentum_full.flips_from_baseline}
        self.assertIn("SYN_FALSE_POSITIVE", flip_ids)

    def test_two_rule_minimal_negative_control(self) -> None:
        report = run_calibration_from_path(PREDICATE_SYNTHETIC)
        two_rule = next(
            item for item in report.variant_results if item.variant_id == "two_rule_minimal"
        )
        flip_ids = {flip.case_id for flip in two_rule.flips_from_baseline}
        self.assertIn("SYN_TRUE_NEGATIVE", flip_ids)
        self.assertIn("SYN_FALSE_NEGATIVE", flip_ids)

    def test_momentum_full_filters_false_positive(self) -> None:
        report = run_calibration_from_path(PREDICATE_SYNTHETIC)
        momentum_full = next(
            item for item in report.variant_results if item.variant_id == "momentum_full"
        )
        self.assertEqual(len(momentum_full.flips_from_baseline), 1)
        flip = momentum_full.flips_from_baseline[0]
        self.assertEqual(flip.case_id, "SYN_FALSE_POSITIVE")
        self.assertEqual(flip.baseline, ResearchCaseClassification.FALSE_POSITIVE)
        self.assertEqual(flip.variant, ResearchCaseClassification.TRUE_NEGATIVE)

    def test_historical_baseline_detects_biya(self) -> None:
        report = run_calibration_from_path(PREDICATE_HISTORICAL)
        baseline = next(
            item for item in report.variant_results if item.variant_id == "baseline"
        )
        self.assertEqual(baseline.case_count, 31)

    def test_historical_momentum_full_blocks_on_relative_volume_fail(self) -> None:
        report = run_calibration_from_path(PREDICATE_HISTORICAL)
        momentum_full = next(
            item for item in report.variant_results if item.variant_id == "momentum_full"
        )
        flip_ids = {flip.case_id for flip in momentum_full.flips_from_baseline}
        self.assertEqual(
            flip_ids,
            {
                "BIYA_EARLIEST_BOUNDARY",
                "BIYA_LATEST_BOUNDARY",
                "APVO_ARTIFACT_DISCOVERY",
                "ATAI_ARTIFACT_DISCOVERY",
                "AVTX_ARTIFACT_DISCOVERY",
                "BHVN_ARTIFACT_DISCOVERY",
                "CADL_ARTIFACT_DISCOVERY",
                "CELZ_ARTIFACT_DISCOVERY",
                "CGEM_ARTIFACT_DISCOVERY",
                "GDC_ARTIFACT_DISCOVERY",
                "GPRE_ARTIFACT_DISCOVERY",
                "IOVA_ARTIFACT_DISCOVERY",
                "KLRS_ARTIFACT_DISCOVERY",
                "LMNX_ARTIFACT_DISCOVERY",
                "MGNX_ARTIFACT_DISCOVERY",
                "OBE_ARTIFACT_DISCOVERY",
                "SG_ARTIFACT_DISCOVERY",
                "ZNTL_ARTIFACT_DISCOVERY",
            },
        )
        for flip in momentum_full.flips_from_baseline:
            self.assertEqual(flip.variant_detection, DetectionStatus.NOT_DETECTED)


if __name__ == "__main__":
    unittest.main()
