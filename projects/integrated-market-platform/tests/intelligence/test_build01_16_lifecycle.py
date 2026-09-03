"""BUILD 01–16 integrated lifecycle test."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts.prediction_ledger import PredictionLedgerEntryV1
from market_platform_foundation.intelligence.evaluation import (
    EvaluationService,
    EvaluationSpec,
    ProbabilityView,
)
from market_platform_foundation.intelligence.evaluation.types import AggregateStatus
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    SettlementStatus,
    register_control_forecast_for_settlement,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    T,
    baseline_control_forecast,
    cutoff_for,
    seed_terminal_trade,
    target_time_for,
)


class Build01To16LifecycleTests(unittest.TestCase):
    def test_control_forecast_settlement_and_evaluation(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        registration = register_control_forecast_for_settlement(forecast, repo, now_ns=T)
        self.assertIsInstance(registration, PredictionLedgerEntryV1)
        entry = registration
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        settlement = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        self.assertEqual(settlement.status, SettlementStatus.SETTLED)

        spec = EvaluationSpec(
            evaluation_as_of_ns=cutoff,
            decision_start_ns=T - 1,
            decision_end_ns=T + 1,
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
            probability_view=ProbabilityView.RAW,
        )
        report = EvaluationService(repo).evaluate(spec, persist=True)
        self.assertEqual(report.aggregate_metrics.status, AggregateStatus.OK)
        self.assertIsNotNone(report.aggregate_metrics.brier_score)
        self.assertIsNotNone(repo.get_evaluation_report(report.report_id))


if __name__ == "__main__":
    unittest.main()
