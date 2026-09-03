"""Calibration dataset and calibrator tests (BUILD 14)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.fusion import (
    CalibrationDatasetBuilder,
    CalibrationExample,
    CalibrationMethod,
    CalibrationTrainer,
    apply_calibration,
)
from market_platform_foundation.intelligence.fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES
from tests.intelligence.fusion_fixtures import SCOPE, default_horizon, default_target


class CalibrationDatasetTests(unittest.TestCase):
    def _example(self, index: int, *, label: int = 1, probability: float = 0.6) -> CalibrationExample:
        decision = 1_000_000_000_000
        horizon = default_horizon()
        return CalibrationExample(
            raw_fusion_id=f"RFF-{index}",
            raw_probability=probability,
            target=default_target(),
            horizon=horizon,
            scope=SCOPE,
            forecast_decision_time_ns=decision,
            label=label,
            label_available_time_ns=decision + horizon.duration_ns + 1,
            fusion_policy_identity="FPOL-TEST",
        )

    def test_dataset_identity_order_independent(self) -> None:
        builder = CalibrationDatasetBuilder()
        examples = [self._example(index, label=index % 2) for index in range(MINIMUM_CALIBRATION_SAMPLES)]
        dataset_a = builder.build(
            examples,
            target=default_target(),
            horizon=default_horizon(),
            fusion_policy_identity="FPOL-TEST",
            calibration_cutoff_ns=9_000_000_000_000,
        )
        dataset_b = builder.build(
            list(reversed(examples)),
            target=default_target(),
            horizon=default_horizon(),
            fusion_policy_identity="FPOL-TEST",
            calibration_cutoff_ns=9_000_000_000_000,
        )
        self.assertEqual(dataset_a.dataset_id, dataset_b.dataset_id)

    def test_future_label_rejected(self) -> None:
        builder = CalibrationDatasetBuilder()
        example = self._example(1)
        with self.assertRaises(Exception):
            builder.build(
                [example],
                target=default_target(),
                horizon=default_horizon(),
                fusion_policy_identity="FPOL-TEST",
                calibration_cutoff_ns=example.label_available_time_ns - 1,
            )

    def test_logistic_calibrator_deterministic(self) -> None:
        builder = CalibrationDatasetBuilder()
        examples = [self._example(index, label=index % 2, probability=0.2 + (index % 7) * 0.1) for index in range(MINIMUM_CALIBRATION_SAMPLES)]
        dataset = builder.build(
            examples,
            target=default_target(),
            horizon=default_horizon(),
            fusion_policy_identity="FPOL-TEST",
            calibration_cutoff_ns=9_000_000_000_000,
        )
        trainer = CalibrationTrainer()
        artifact_a = trainer.fit(dataset, method=CalibrationMethod.LOGISTIC_PROBABILITY, available_time_ns=8_000_000_000_000)
        artifact_b = trainer.fit(dataset, method=CalibrationMethod.LOGISTIC_PROBABILITY, available_time_ns=8_000_000_000_000)
        assert artifact_a is not None and artifact_b is not None
        self.assertEqual(artifact_a.calibration_model_id, artifact_b.calibration_model_id)
        self.assertEqual(artifact_a.parameter_fingerprint, artifact_b.parameter_fingerprint)
        self.assertAlmostEqual(
            apply_calibration(artifact_a, 0.55),
            apply_calibration(artifact_b, 0.55),
        )

    def test_identity_control_status(self) -> None:
        builder = CalibrationDatasetBuilder()
        examples = [self._example(index, label=index % 2) for index in range(MINIMUM_CALIBRATION_SAMPLES)]
        dataset = builder.build(
            examples,
            target=default_target(),
            horizon=default_horizon(),
            fusion_policy_identity="FPOL-TEST",
            calibration_cutoff_ns=9_000_000_000_000,
        )
        artifact = CalibrationTrainer().fit(
            dataset,
            method=CalibrationMethod.IDENTITY_CONTROL,
            available_time_ns=8_000_000_000_000,
        )
        assert artifact is not None
        self.assertAlmostEqual(apply_calibration(artifact, 0.42), 0.42)


if __name__ == "__main__":
    unittest.main()
