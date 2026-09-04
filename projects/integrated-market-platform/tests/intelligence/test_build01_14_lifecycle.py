"""Full BUILD 01–14 lifecycle tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.baselines import BaselinePredictionEngine, BaselinePredictionRequest, default_control_suite
from market_platform_foundation.intelligence.fusion import (
    ForecastDecisionStatus,
    ForecastFusionManifest,
    ForecastFusionService,
    FusionPolicy,
    build_contributor_ref,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.fusion_fixtures import sample_snapshot
from tests.intelligence.test_baseline_fixtures import default_horizon, default_target, momentum_signal


class Build01To14LifecycleTests(unittest.TestCase):
    def test_production_pipeline_abstains_without_production_contributors(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = sample_snapshot("snap-build14-prod")
        repo.put_snapshot(snapshot)
        signal = momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.02)
        repo.put_signal(signal)
        engine = BaselinePredictionEngine()
        request = BaselinePredictionRequest(
            snapshot=snapshot,
            signals=(signal,),
            target=default_target(),
            horizon=default_horizon(),
        )
        controls = []
        for model in default_control_suite(target=default_target()).models:
            result = engine.predict(request, model)
            assert result.forecast is not None
            repo.put_forecast(result.forecast)
            controls.append(build_contributor_ref(result.forecast))
        manifest = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=controls,
            fusion_policy=FusionPolicy(),
        )
        service = ForecastFusionService(repo)
        result = service.evaluate(manifest, persist=True)
        self.assertIsNone(result.forecast)
        self.assertEqual(result.status, ForecastDecisionStatus.ABSTAINED_CONTROL_ONLY)
        final_forecasts = [
            row
            for row in repo.get_forecasts_by_instrument(snapshot.scope.instrument_ids[0])
            if row.metadata.get("forecast_stage") == "FINAL_FUSED_CALIBRATED"
        ]
        self.assertEqual(final_forecasts, [])


if __name__ == "__main__":
    unittest.main()
