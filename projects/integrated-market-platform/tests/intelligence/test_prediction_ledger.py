"""BUILD 15 prediction ledger unit tests."""

from __future__ import annotations

import dataclasses
import unittest
from unittest import mock

from market_platform_foundation.intelligence.outcomes import (
    DIRECTION_UP_DOWN_5M_POLICY,
    PredictionLedgerService,
    SettlementMode,
    SettlementStatus,
    UnlabelableReason,
    build_prediction_ledger_entry,
    derive_ledger_entry_id,
    freeze_anchor_observation,
)
from market_platform_foundation.intelligence.outcomes.policy import derive_settlement_policy_identity
from market_platform_foundation.intelligence.outcomes.errors import OutcomeRegistrationError
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    ONE_MIN,
    T,
    baseline_control_forecast,
    cutoff_for,
    seed_anchor_trade,
    target_time_for,
)
from tests.intelligence.test_signal_fixtures import trade_event


class PredictionLedgerTests(unittest.TestCase):
    def test_ledger_entry_identity_is_deterministic(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry_a = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        entry_b = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        self.assertEqual(entry_a.ledger_entry_id, entry_b.ledger_entry_id)
        expected = derive_ledger_entry_id(
            forecast_id=forecast.forecast_id,
            settlement_policy_identity=entry_a.settlement_policy_identity,
            anchor_observation=entry_a.anchor_observation,
            target_time_ns=entry_a.target_time_ns,
            target_window_start_ns=entry_a.target_window_start_ns,
            target_window_end_ns=entry_a.target_window_end_ns,
            availability_cutoff_ns=entry_a.availability_cutoff_ns,
            mode=SettlementMode.ACTUAL_LIVE,
        )
        self.assertEqual(entry_a.ledger_entry_id, expected)

    def test_anchor_observation_is_frozen_at_registration(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        first = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        seed_anchor_trade(
            repo,
            price=50.0,
            event_time_ns=T - ONE_MIN,
            event_id="older-anchor",
        )
        second = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        self.assertEqual(first.anchor_observation["price"], 100.0)
        self.assertEqual(second.anchor_observation["price"], 100.0)
        self.assertEqual(first.anchor_observation["event_id"], second.anchor_observation["event_id"])

    def test_late_registration_is_rejected_for_actual_live(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        target_time = target_time_for(forecast)
        service = PredictionLedgerService(repo)
        result = service.register_forecast(
            forecast,
            now_ns=target_time + 1,
            mode=SettlementMode.ACTUAL_LIVE,
        )
        self.assertEqual(result.status, SettlementStatus.LATE_REGISTRATION)
        self.assertEqual(result.forecast_id, forecast.forecast_id)
        self.assertEqual(repo.get_prediction_ledger_entries_by_forecast(forecast.forecast_id), ())

    def test_settlement_policy_identity_matches_versioned_policy(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        self.assertEqual(
            entry.settlement_policy_identity,
            DIRECTION_UP_DOWN_5M_POLICY.policy_id,
        )
        self.assertEqual(
            entry.settlement_policy_identity,
            derive_settlement_policy_identity(DIRECTION_UP_DOWN_5M_POLICY),
        )
        self.assertEqual(entry.horizon_ns, HORIZON_5M)

    def test_ledger_persistence_idempotency_and_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = build_prediction_ledger_entry(forecast, repo, registered_at_ns=T)
        self.assertEqual(repo.put_prediction_ledger_entry(entry), RepositoryPutResult.INSERTED)
        self.assertEqual(repo.put_prediction_ledger_entry(entry), RepositoryPutResult.ALREADY_PRESENT)
        conflict = dataclasses.replace(entry, metadata={**entry.metadata, "tampered": True})
        with self.assertRaises(RepositoryConflictError):
            repo.put_prediction_ledger_entry(conflict)

    def test_anchor_temporal_rejection(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        late_anchor = trade_event(
            "late-anchor",
            event_time_ns=T,
            price=100.0,
            quantity=10,
            available_time_ns=T + ONE_MIN,
        )
        with mock.patch(
            "market_platform_foundation.intelligence.outcomes.anchor._events_for_forecast_context",
            return_value=(late_anchor,),
        ):
            with mock.patch(
                "market_platform_foundation.intelligence.outcomes.anchor._eligible_anchor_events",
                return_value=(late_anchor,),
            ):
                with mock.patch(
                    "market_platform_foundation.intelligence.outcomes.anchor.p6_reference_price",
                    return_value={
                        "trade_id": "late-anchor",
                        "price": 100.0,
                        "event_time_ns": T,
                    },
                ):
                    with self.assertRaises(OutcomeRegistrationError) as ctx:
                        freeze_anchor_observation(
                            forecast,
                            repo,
                            policy=DIRECTION_UP_DOWN_5M_POLICY,
                        )
        self.assertEqual(
            ctx.exception.code,
            UnlabelableReason.ANCHOR_TEMPORALLY_INVALID.value,
        )


if __name__ == "__main__":
    unittest.main()
