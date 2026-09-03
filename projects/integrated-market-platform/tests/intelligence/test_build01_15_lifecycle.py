"""Full BUILD 01–15 lifecycle tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.baselines import (
    BaselinePredictionEngine,
    BaselinePredictionRequest,
    default_control_suite,
)
from market_platform_foundation.intelligence.contracts import Direction, OutcomeResolutionStatus
from market_platform_foundation.intelligence.contracts.prediction_ledger import PredictionLedgerEntryV1
from market_platform_foundation.intelligence.fusion import (
    ForecastDecisionStatus,
    ForecastFusionManifest,
    ForecastFusionService,
    FusionPolicy,
    build_contributor_ref,
)
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    SettlementStatus,
    register_control_forecast_for_settlement,
    register_final_forecast_for_settlement,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.fusion_fixtures import sample_snapshot
from tests.intelligence.outcome_fixtures import (
    baseline_control_forecast,
    cutoff_for,
    seed_terminal_trade,
    synthetic_final_forecast,
    target_time_for,
    T,
)
from tests.intelligence.test_baseline_fixtures import default_horizon, default_target, momentum_signal


class Build01To15LifecycleTests(unittest.TestCase):
    def test_control_forecast_full_settlement_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        registration = register_control_forecast_for_settlement(forecast, repo, now_ns=T)
        self.assertIsInstance(registration, PredictionLedgerEntryV1)
        entry = registration
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.resolution_status, OutcomeResolutionStatus.SETTLED)
        self.assertEqual(result.outcome.realized_direction, Direction.LONG)
        self.assertEqual(repo.get_outcomes_by_forecast(forecast.forecast_id), (result.outcome,))

    def test_synthetic_final_forecast_settlement_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo, probability=0.72, anchor_price=100.0)
        registration = register_final_forecast_for_settlement(forecast, repo, now_ns=T)
        self.assertIsInstance(registration, PredictionLedgerEntryV1)
        entry = registration
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=108.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.forecast_id, forecast.forecast_id)
        self.assertEqual(result.outcome.realized_direction, Direction.LONG)

    def test_production_abstain_produces_no_outcome(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = sample_snapshot("snap-build15-prod")
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
        fusion_result = ForecastFusionService(repo).evaluate(manifest, persist=True)
        self.assertIsNone(fusion_result.forecast)
        self.assertEqual(fusion_result.status, ForecastDecisionStatus.ABSTAINED_CONTROL_ONLY)
        self.assertEqual(repo.get_prediction_ledger_entries_by_forecast("missing"), ())
        self.assertEqual(repo.get_outcomes_by_forecast("missing"), ())

    def test_settlement_does_not_mutate_forecast(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        before = repo.get_forecast(forecast.forecast_id)
        assert before is not None
        registration = register_control_forecast_for_settlement(forecast, repo, now_ns=T)
        self.assertIsInstance(registration, PredictionLedgerEntryV1)
        entry = registration
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        after = repo.get_forecast(forecast.forecast_id)
        assert after is not None
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
