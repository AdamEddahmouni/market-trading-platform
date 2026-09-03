"""BUILD 15 outcome settlement unit tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    Direction,
    ForecastEstimate,
    ForecastV1,
    OutcomeResolutionStatus,
    QualityState,
    QualitySummary,
    SnapshotV1,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.baselines import direction_up_down_target
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    P6_DIRECTION_POLICY,
    PredictionLedgerService,
    SettlementMode,
    SettlementStatus,
    UnlabelableReason,
    derive_outcome_id,
    p6_reference_price,
)
from market_platform_foundation.intelligence.outcomes.p6_compat import p6_terminal_candidate
from market_platform_foundation.intelligence.outcomes.types import SettlementResult
from market_platform_foundation.intelligence.outcomes.observations import event_to_tape_row
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.codec import RECORD_CODECS
from market_platform_foundation.intelligence.persistence.mongo.schema import COLLECTION_SPECS
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    INSTRUMENT,
    ONE_MIN,
    QUALITY,
    SCOPE,
    T,
    baseline_control_forecast,
    cutoff_for,
    seed_anchor_trade,
    seed_terminal_trade,
    target_time_for,
)
from tests.intelligence.test_signal_fixtures import trade_event


HORIZON_30M = 1800 * 1_000_000_000
P6_TOLERANCE = 300 * 1_000_000_000


class OutcomeSettlementTests(unittest.TestCase):
    def _register(
        self,
        repo: InMemoryIntelligenceRepository,
        forecast: ForecastV1,
        *,
        mode: SettlementMode = SettlementMode.ACTUAL_LIVE,
        scenario_id: str | None = None,
        now_ns: int = T,
    ):
        service = PredictionLedgerService(repo)
        result = service.register_forecast(
            forecast,
            now_ns=now_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        if isinstance(result, SettlementResult):
            self.fail(f"ledger registration failed: {result.status}")
        return result

    def test_not_due_before_availability_cutoff(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = self._register(repo, forecast)
        cutoff = cutoff_for(forecast)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff - 1)
        self.assertEqual(result.status, SettlementStatus.NOT_DUE)
        self.assertIsNone(result.outcome)

    def test_settles_at_exact_availability_cutoff(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.resolution_status, OutcomeResolutionStatus.SETTLED)

    def test_up_outcome_when_terminal_price_rises(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.realized_direction, Direction.LONG)
        self.assertGreater(result.realized_return, 0.0)

    def test_down_outcome_when_terminal_price_falls(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=90.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.realized_direction, Direction.SHORT)
        self.assertLess(result.realized_return, 0.0)

    def test_zero_return_is_unlabelable(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=100.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.status, SettlementStatus.UNLABELABLE)
        assert result.outcome is not None
        self.assertEqual(result.outcome.resolution_status, OutcomeResolutionStatus.UNLABELABLE)
        self.assertEqual(result.unlabelable_reason, UnlabelableReason.ZERO_RETURN.value)

    def test_no_target_observation_is_unlabelable(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = self._register(repo, forecast)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.status, SettlementStatus.UNLABELABLE)
        assert result.outcome is not None
        self.assertEqual(
            result.unlabelable_reason,
            UnlabelableReason.NO_TARGET_OBSERVATION.value,
        )

    def test_late_data_does_not_change_settled_outcome(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        service = OutcomeSettlementService(repo)
        first = service.settle(entry, now_ns=cutoff)
        repo.put_event(
            trade_event(
                "late-arrival",
                event_time_ns=target + ONE_MIN,
                price=999.0,
                quantity=10,
                available_time_ns=cutoff + ONE_MIN,
            )
        )
        second = service.settle(entry, now_ns=cutoff + ONE_MIN)
        self.assertEqual(second.status, SettlementStatus.ALREADY_SETTLED)
        assert first.outcome is not None and second.outcome is not None
        self.assertEqual(first.outcome_id, second.outcome_id)
        self.assertEqual(
            first.outcome.end_observation["observation"]["price"],
            second.outcome.end_observation["observation"]["price"],
        )
        self.assertEqual(first.outcome.end_observation["observation"]["price"], 110.0)

    def test_out_of_order_legal_arrival_settles_correctly(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        target = target_time_for(forecast)
        repo.put_event(
            trade_event(
                "terminal-first",
                event_time_ns=target,
                price=105.0,
                quantity=10,
                available_time_ns=target,
            )
        )
        entry = self._register(repo, forecast)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.end_observation["observation"]["price"], 105.0)

    def test_observations_available_after_cutoff_are_ignored(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        entry = self._register(repo, forecast)
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target, event_id="legal-terminal")
        repo.put_event(
            trade_event(
                "late-available",
                event_time_ns=target,
                price=50.0,
                quantity=10,
                available_time_ns=cutoff + 1,
            )
        )
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.end_observation["observation"]["price"], 110.0)

    def test_outcome_identity_is_deterministic(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = self._register(repo, forecast)
        expected = derive_outcome_id(
            forecast_id=forecast.forecast_id,
            ledger_entry_id=entry.ledger_entry_id,
            settlement_policy_identity=entry.settlement_policy_identity,
            mode=SettlementMode.ACTUAL_LIVE,
        )
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff_for(forecast))
        self.assertEqual(result.outcome_id, expected)

    def test_input_order_independence(self) -> None:
        target = T + HORIZON_5M
        cutoff = target + ONE_MIN
        events = (
            trade_event("anchor-trade", event_time_ns=T, price=100.0, quantity=10),
            trade_event("terminal-trade", event_time_ns=target, price=110.0, quantity=10),
        )

        def settle_with_order(order: tuple[int, int]) -> str:
            repo = InMemoryIntelligenceRepository()
            for index in order:
                repo.put_event(events[index])
            forecast = baseline_control_forecast(repo)
            entry = self._register(repo, forecast)
            result = OutcomeSettlementService(repo).settle(
                entry,
                now_ns=cutoff,
            )
            assert result.outcome_id is not None
            return result.outcome_id

        first_id = settle_with_order((0, 1))
        second_id = settle_with_order((1, 0))
        self.assertEqual(first_id, second_id)

    def test_actual_and_counterfactual_outcomes_are_separated(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo, anchor_price=100.0)
        actual_entry = self._register(repo, forecast, mode=SettlementMode.ACTUAL_LIVE)
        cf_entry = self._register(
            repo,
            forecast,
            mode=SettlementMode.COUNTERFACTUAL,
            scenario_id="scenario-a",
        )
        self.assertNotEqual(actual_entry.ledger_entry_id, cf_entry.ledger_entry_id)
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(
            repo,
            price=110.0,
            event_time_ns=target + ONE_MIN,
            event_id="actual-terminal",
        )
        service = OutcomeSettlementService(repo)
        actual_result = service.settle(actual_entry, now_ns=cutoff)
        repo.put_event(
            trade_event(
                "cf-terminal",
                event_time_ns=target + 30 * 1_000_000_000,
                price=90.0,
                quantity=10,
                available_time_ns=cutoff,
            )
        )
        cf_result = service.settle(cf_entry, now_ns=cutoff + 1)
        assert actual_result.outcome is not None and cf_result.outcome is not None
        self.assertNotEqual(actual_result.outcome_id, cf_result.outcome_id)
        self.assertEqual(actual_result.outcome.realized_direction, Direction.LONG)
        self.assertEqual(cf_result.outcome.realized_direction, Direction.SHORT)

    def test_counterfactual_separation_across_repositories(self) -> None:
        target = T + HORIZON_5M
        cutoff = target + ONE_MIN

        repo_up = InMemoryIntelligenceRepository()
        forecast_up = baseline_control_forecast(repo_up, anchor_price=100.0)
        entry_up = self._register(repo_up, forecast_up, mode=SettlementMode.ACTUAL_LIVE)
        seed_terminal_trade(repo_up, price=110.0, event_time_ns=target)
        up_result = OutcomeSettlementService(repo_up).settle(entry_up, now_ns=cutoff)

        repo_down = InMemoryIntelligenceRepository()
        forecast_down = baseline_control_forecast(repo_down, anchor_price=100.0)
        entry_down = self._register(
            repo_down,
            forecast_down,
            mode=SettlementMode.COUNTERFACTUAL,
            scenario_id="scenario-b",
        )
        seed_terminal_trade(repo_down, price=90.0, event_time_ns=target)
        down_result = OutcomeSettlementService(repo_down).settle(entry_down, now_ns=cutoff)
        assert up_result.outcome is not None and down_result.outcome is not None
        self.assertNotEqual(up_result.outcome_id, down_result.outcome_id)
        self.assertEqual(up_result.outcome.realized_direction, Direction.LONG)
        self.assertEqual(down_result.outcome.realized_direction, Direction.SHORT)

    def test_p6_compatibility_uses_reference_and_terminal_helpers(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = SnapshotV1(
            snapshot_id="snap-p6",
            schema_version="1",
            decision_time_ns=T,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id="p6-anchor"),),
        )
        anchor_event = trade_event("p6-anchor", event_time_ns=T, price=100.0, quantity=10)
        repo.put_event(anchor_event)
        repo.put_snapshot(snapshot)
        forecast = ForecastV1(
            forecast_id="fc-p6",
            schema_version="1",
            scope=SCOPE,
            decision_time_ns=T,
            snapshot_id=snapshot.snapshot_id,
            target=direction_up_down_target(INSTRUMENT),
            horizon=TimeHorizonNs(duration_ns=HORIZON_30M),
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.6,
                calibrated_probability=0.6,
            ),
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={
                "contributor_role": "CONTROL",
                "forecast_stage": "CONTROL_BASELINE",
            },
        )
        repo.put_forecast(forecast)
        entry = self._register(repo, forecast)
        self.assertEqual(entry.settlement_policy_identity, P6_DIRECTION_POLICY.policy_id)
        cutoff = entry.availability_cutoff_ns
        tape = [event_to_tape_row(anchor_event)]
        assert tape[0] is not None
        ref = p6_reference_price(tape, decision_time_ns=T)
        self.assertIsNotNone(ref)
        assert ref is not None
        self.assertEqual(ref["price"], entry.anchor_observation["price"])
        target = target_time_for(forecast)
        terminal_event = trade_event(
            "p6-terminal",
            event_time_ns=target + 60 * 1_000_000_000,
            price=105.0,
            quantity=10,
            available_time_ns=target + 60 * 1_000_000_000,
        )
        repo.put_event(terminal_event)
        terminal_receipt = event_to_tape_row(terminal_event)
        assert terminal_receipt is not None
        ticks = [
            (
                int(terminal_receipt["event_time_ns"]),
                float(terminal_receipt["price"]),
                int(terminal_receipt["available_time_ns"]),
            )
        ]
        candidate = p6_terminal_candidate(
            ticks,
            target_ns=target,
            tolerance_ns=P6_TOLERANCE,
        )
        self.assertIsNotNone(candidate)
        result = OutcomeSettlementService(repo).settle(
            entry,
            now_ns=cutoff,
        )
        self.assertEqual(result.status, SettlementStatus.SETTLED)
        assert result.outcome is not None
        self.assertEqual(result.outcome.end_observation["observation"]["price"], 105.0)

    def test_prediction_ledger_mongo_schema_has_no_ttl_indexes(self) -> None:
        codec_names = {codec.collection_name for codec in RECORD_CODECS}
        self.assertIn("prediction_ledger", codec_names)
        spec = next(
            spec for spec in COLLECTION_SPECS if spec.codec.collection_name == "prediction_ledger"
        )
        for index in spec.indexes:
            self.assertFalse(hasattr(index, "expire_after_seconds"))
        validator_props = spec.validator.get("properties", {})
        self.assertNotIn("ttl", validator_props)
        self.assertNotIn("expires_at_ns", validator_props)


if __name__ == "__main__":
    unittest.main()
