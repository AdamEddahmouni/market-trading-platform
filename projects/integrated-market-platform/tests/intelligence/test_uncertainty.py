"""Uncertainty and final forecast tests (BUILD 14)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.fusion import (
    CalibrationApplicator,
    CalibrationExample,
    CalibrationMethod,
    CalibrationTrainer,
    CalibrationDatasetBuilder,
    FinalForecastPolicy,
    ForecastDecisionStatus,
    ForecastFusionManifest,
    ForecastFusionService,
    FusionPolicy,
    predictive_entropy,
)
from market_platform_foundation.intelligence.fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.fusion_fixtures import (
    baseline_control_forecast,
    control_contributor,
    production_contributor,
    sample_snapshot,
    synthetic_production_forecast,
)
from tests.intelligence.fusion_fixtures import SCOPE, default_horizon, default_target


class UncertaintyTests(unittest.TestCase):
    def test_predictive_entropy(self) -> None:
        self.assertAlmostEqual(predictive_entropy(0.5), 1.0)
        self.assertAlmostEqual(predictive_entropy(0.0), 0.0)
        self.assertAlmostEqual(predictive_entropy(1.0), 0.0)


class FinalForecastTests(unittest.TestCase):
    def test_control_only_production_abstains(self) -> None:
        snapshot = sample_snapshot()
        control = baseline_control_forecast(snapshot)
        manifest = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[control_contributor(control)],
            fusion_policy=FusionPolicy(),
        )
        service = ForecastFusionService(InMemoryIntelligenceRepository())
        result = service.evaluate(manifest, persist=True)
        self.assertIsNone(result.forecast)
        self.assertEqual(result.status, ForecastDecisionStatus.ABSTAINED_CONTROL_ONLY)

    def test_synthetic_operational_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = sample_snapshot()
        f1 = synthetic_production_forecast(
            forecast_id="FCST-P1",
            snapshot=snapshot,
            probability=0.8,
            signal_ids=("SIG-1",),
            forecast_family_key="family-a",
        )
        f2 = synthetic_production_forecast(
            forecast_id="FCST-P2",
            snapshot=snapshot,
            probability=0.6,
            signal_ids=("SIG-2",),
            forecast_family_key="family-b",
        )
        policy = FusionPolicy()
        manifest = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[production_contributor(f1), production_contributor(f2)],
            fusion_policy=policy,
        )
        builder = CalibrationDatasetBuilder()
        horizon = default_horizon()
        examples = []
        for index in range(MINIMUM_CALIBRATION_SAMPLES):
            label = index % 2
            examples.append(
                CalibrationExample(
                    raw_fusion_id=f"RFF-{index}",
                    raw_probability=0.2 + (index % 8) * 0.1,
                    target=default_target(),
                    horizon=horizon,
                    scope=SCOPE,
                    forecast_decision_time_ns=snapshot.decision_time_ns,
                    label=label,
                    label_available_time_ns=snapshot.decision_time_ns + horizon.duration_ns + 1,
                    fusion_policy_identity=policy.policy_identity,
                )
            )
        dataset = builder.build(
            examples,
            target=default_target(),
            horizon=horizon,
            fusion_policy_identity=policy.policy_identity,
            calibration_cutoff_ns=snapshot.decision_time_ns + horizon.duration_ns + 100,
        )
        artifact = CalibrationTrainer().fit(
            dataset,
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=snapshot.decision_time_ns,
        )
        assert artifact is not None
        service = ForecastFusionService(repo)
        result = service.evaluate(manifest, calibration_artifact=artifact, persist=True)
        self.assertEqual(result.status, ForecastDecisionStatus.EMITTED_CALIBRATED)
        assert result.forecast is not None
        self.assertIsNotNone(result.forecast.estimate.calibrated_probability)
        loaded = repo.get_forecast(result.forecast.forecast_id)
        assert loaded is not None
        second = repo.put_forecast(result.forecast)
        self.assertEqual(second.value, "ALREADY_PRESENT")

    def test_calibration_unavailable_abstains(self) -> None:
        snapshot = sample_snapshot()
        forecast = synthetic_production_forecast(
            forecast_id="FCST-P1",
            snapshot=snapshot,
            probability=0.7,
            signal_ids=("SIG-1",),
            forecast_family_key="family-a",
        )
        manifest = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[production_contributor(forecast)],
            fusion_policy=FusionPolicy(),
        )
        service = ForecastFusionService(InMemoryIntelligenceRepository(), final_policy=FinalForecastPolicy(require_calibration=True))
        result = service.evaluate(manifest)
        self.assertEqual(result.status, ForecastDecisionStatus.ABSTAINED_CALIBRATION_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
