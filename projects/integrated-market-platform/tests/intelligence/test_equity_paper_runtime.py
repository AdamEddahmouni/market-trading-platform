"""Focused Task 4 integration coverage for the strategy Paper runtime."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    EventV1,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
    SourceReference,
    SnapshotV1,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.baselines import direction_up_down_target
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    PredictionLedgerService,
    SettlementMode,
    SettlementStatus,
)
from market_platform_foundation.intelligence.opportunity import (
    AccountActionability,
    EconomicAssumptionsV1,
    MoneyMinorUnits,
    OpportunityContext,
    OpportunityPolicyV1,
    UniversalEconomicAssessmentV1,
    build_opportunity_policy,
)
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
)
from market_platform_foundation.intelligence.promotion.types import (
    ChampionAssignmentReason,
    ChampionAssignmentV1,
    ChampionScopeV1,
)
from market_platform_foundation.intelligence.quality.models import (
    AvailabilityState,
    QualityAssessment,
)
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.portfolio.attribution import StrategyAttributionV1
from market_platform_foundation.intelligence.execution import (
    MarketQuoteV1,
    PaperExecutionOrchestrator,
    PaperPositionSnapshot,
    RiskDecisionKind,
    build_execution_policy,
    build_portfolio_snapshot,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.strategy.runtime import (
    StrategyPaperRuntime,
    StrategyRuntimeError,
)
from market_platform_foundation.intelligence.opportunity.bridge import OpportunityBridgeError
from market_platform_foundation.strategy.learning import (
    LearningEligibility,
    LearningPolicyV1,
)
from market_platform_foundation.strategy.scanning import (
    CapabilityContextSnapshot,
    PointInTimeUniverse,
    ScanBudget,
    ScanRequest,
    ScanScope,
    ScanTrigger,
    ScanTriggerType,
    StrategyEvaluationResult,
    StrategyRegistration,
    UniversalStrategyScanner,
)
from market_platform_foundation.strategy.strategy_spec import StrategyDefinition


T = 1_700_000_000_000_000_000
HORIZON = 300_000_000_000
INSTRUMENT = InstrumentIdentity("canonical", "AAPL", "EQUITY", "XNYS", "USD")
INSTRUMENT_ID = INSTRUMENT.qualified_id()
SCOPE = IntelligenceScope(
    instrument_ids=(INSTRUMENT_ID,),
    context_id="acct-paper:paper:snapshot-paper-1",
)
QUALITY = QualitySummary(state=QualityState.GOOD)


def _champion(*, target_kind: str = "direction") -> ChampionAssignmentV1:
    return ChampionAssignmentV1(
        assignment_id="champion-paper-1",
        schema_version="1",
        champion_scope=ChampionScopeV1(
            component="forecast",
            target_kind=target_kind,
            horizon_ns=HORIZON,
            mode="PAPER",
            scenario_id="paper-happy",
        ),
        candidate_id="candidate-paper-1",
        candidate_artifact_hash="artifact-paper-1",
        promotion_decision_id=None,
        previous_assignment_id=None,
        effective_from_ns=T - 1,
        assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
    )


def _forecast(champion: ChampionAssignmentV1):
    return __import__(
        "market_platform_foundation.intelligence.contracts",
        fromlist=["ForecastV1"],
    ).ForecastV1(
        forecast_id="forecast-paper-1",
        schema_version="1",
        scope=SCOPE,
        decision_time_ns=T,
        snapshot_id="snapshot-paper-1",
        target=(
            direction_up_down_target("AAPL")
            if champion.champion_scope.target_kind == "direction_up_down"
            else ForecastTarget(
                target_kind=champion.champion_scope.target_kind,
                instrument_id="AAPL",
                parameters={},
            )
        ),
        horizon=TimeHorizonNs(duration_ns=HORIZON),
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=0.8,
            calibrated_probability=0.8,
        ),
        quality=QUALITY,
        resolve_time_ns=T + HORIZON,
        metadata={
            "account_id": "acct-paper",
            "mode": "PAPER",
            "scenario_id": "paper-happy",
            "forecast_stage": "FINAL_FUSED_CALIBRATED",
            "contributor_role": "PRODUCTION",
            "champion_candidate_id": champion.candidate_id,
            "candidate_artifact_hash": champion.candidate_artifact_hash,
        },
    )


def _strategy_request() -> ScanRequest:
    definition = StrategyDefinition(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis="deterministic paper momentum",
        evidence_requirements=(),
        instrument_id="AAPL",
        asset_class="EQUITY",
        family="TREND",
        style="MOMENTUM",
        timeframe="5M",
    )
    return ScanRequest(
        universe=PointInTimeUniverse(T, (INSTRUMENT,)),
        capability_snapshot=CapabilityContextSnapshot(
            snapshot_id="snapshot-paper-1",
            as_of_time_ns=T,
            quality_assessment=QualityAssessment(decision_time_ns=T),
            context={"session": "REGULAR"},
        ),
        strategies=(
            StrategyRegistration(
                strategy_id="strategy-paper-1",
                definition=definition,
                evaluator=lambda _: StrategyEvaluationResult(
                    disposition=StrategyMatchDisposition.MATCHED,
                ),
            ),
        ),
        scope=ScanScope(account_id="acct-paper", mode="paper"),
        trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
        decision_time_ns=T,
        expires_at_ns=T + 60_000_000_000,
        budget=ScanBudget(max_evaluations=1, max_cost_units=1),
    )


def _economics() -> UniversalEconomicAssessmentV1:
    return UniversalEconomicAssessmentV1.create(
        scope=SCOPE,
        account_id="acct-paper",
        mode="PAPER",
        assessed_at_ns=T,
        expires_at_ns=T + 50_000_000_000,
        assumptions=EconomicAssumptionsV1(
            assumptions_id="economics-paper-1",
            version="1",
        ),
        expected_gross_pnl=MoneyMinorUnits(2_000, "USD", 2),
        expected_net_pnl=MoneyMinorUnits(1_500, "USD", 2),
        capital_required=MoneyMinorUnits(10_100, "USD", 2),
        buying_power_required=MoneyMinorUnits(10_100, "USD", 2),
        maximum_loss=MoneyMinorUnits(1_000, "USD", 2),
        expected_return_bps=150,
        expected_hold_ns=HORIZON,
        maximum_hold_ns=HORIZON,
        capital_lock_ns=HORIZON,
        account_actionability=AccountActionability.ACTIONABLE,
    )


def _runtime_fixture(
    *,
    forecast: ForecastV1 | None = None,
    economics: UniversalEconomicAssessmentV1 | None = None,
    cash_minor: int = 1_000_000,
    equity_minor: int = 1_000_000,
    start_of_day_equity_minor: int | None = None,
    target_kind: str = "direction",
    allocation_values: dict[str, int] | None = None,
    execution_policy=None,
    bars: list[dict[str, object]] | None = None,
    evaluator_disposition: StrategyMatchDisposition = StrategyMatchDisposition.MATCHED,
    session_id: str = "runtime-paper-task6",
) -> tuple[StrategyPaperRuntime, InMemoryIntelligenceRepository, ScanRequest, ForecastV1]:
    repository = InMemoryIntelligenceRepository()
    repository.put_event(
        EventV1(
            event_id=f"{session_id}-anchor",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=T,
            available_time_ns=T,
            payload={"price": 100.0, "quantity": 10},
            quality=QUALITY,
            source=SourceReference(
                provider_id="fixture",
                source_type="TRADE",
                source_record_id=f"{session_id}-anchor",
            ),
            instrument_id="AAPL",
        )
    )
    repository.put_snapshot(
        SnapshotV1(
            snapshot_id="snapshot-paper-1",
            schema_version="1",
            decision_time_ns=T,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=(
                ContractReference(kind="event", id=f"{session_id}-anchor"),
            ),
        )
    )
    champion = _champion(target_kind=target_kind)
    active_forecast = forecast or _forecast(champion)
    repository.put_forecast(active_forecast)
    policy: OpportunityPolicyV1 = build_opportunity_policy(
        champion_scope=champion.champion_scope,
        max_forecast_age_ns=HORIZON,
        max_opportunity_lifetime_ns=20_000_000_000,
        minimum_probability_edge=0.05,
    )
    active_economics = economics or _economics()
    active_execution_policy = execution_policy or build_execution_policy(
        trade_fraction_nav=0.02,
        max_trade_notional_minor=50_000,
        max_symbol_concentration_fraction=1.0,
        minimum_trade_notional_minor=100,
    )
    portfolio = build_portfolio_snapshot(
        captured_at_ns=T,
        cash_minor=cash_minor,
        equity_minor=equity_minor,
        currency="USD",
        price_scale=100,
        scenario_id="paper-happy",
        mode="PAPER",
        start_of_day_equity_minor=start_of_day_equity_minor,
    )
    ledger = PaperExecutionLedger.open_session(
        replay_session_id=session_id,
        instrument_id=INSTRUMENT_ID,
        symbol="AAPL",
        policy={
            "policy_version": "paper-policy-1",
            "risk_policy_identity_hash": "risk-policy-paper-1",
            "initial_cash_minor": 1_000_000,
            "currency": "USD",
            "price_scale": 100,
            "max_order_shares": 1_000,
            "max_position_shares": 1_000,
            "max_open_orders": 10,
            "commission_minor_per_share": 0,
            "fee_minor_per_order": 0,
            "participation_cap_numerator": 1,
            "participation_cap_denominator": 1,
        },
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="AUTHORIZED",
    )
    request = _strategy_request()
    if evaluator_disposition != StrategyMatchDisposition.MATCHED:
        registration = request.strategies[0]
        request = replace(
            request,
            strategies=(
                replace(
                    registration,
                    evaluator=lambda _: StrategyEvaluationResult(
                        disposition=evaluator_disposition,
                        rejection_reasons=("TASK6_REJECTED",)
                        if evaluator_disposition == StrategyMatchDisposition.REJECTED
                        else (),
                        abstention_reasons=("TASK6_ABSTAINED",)
                        if evaluator_disposition == StrategyMatchDisposition.ABSTAINED
                        else (),
                        unavailability_reasons=("TASK6_UNAVAILABLE",)
                        if evaluator_disposition == StrategyMatchDisposition.UNAVAILABLE
                        else (),
                    ),
                ),
            ),
        )
    values = {
        "scale": 2,
        "available_capital_minor": 10_100,
        "available_buying_power_minor": 10_100,
        "maximum_loss_budget_minor": 1_000,
    }
    values.update(allocation_values or {})
    runtime = StrategyPaperRuntime(
        repository=repository,
        scanner=UniversalStrategyScanner(query_planner=None, repository=repository),
        forecast_resolver=lambda _match: active_forecast,
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_policy=policy,
        opportunity_context=OpportunityContext(
            snapshot_ref=ContractReference(kind="snapshot", id="snapshot-paper-1"),
            snapshot_available_time_ns=T,
            spread_bps=5,
            spread_available_time_ns=T,
            mode="PAPER",
            scenario_id="paper-happy",
            account_id="acct-paper",
        ),
        economic_assessment=active_economics,
        comparison_constraints={"currency": "USD", "scale": 2},
        allocation_constraints=values,
        execution_policy=active_execution_policy,
        portfolio=portfolio,
        quote=MarketQuoteV1(
            instrument_id=INSTRUMENT_ID,
            bid_minor=10_000,
            ask_minor=10_100,
            available_time_ns=T,
        ),
        ledger=ledger,
        bars=bars
        or [
            {
                "available_time": T + 2_000_000_000,
                "normalized_event_id": f"{session_id}-entry-bar",
                "bar_payload": {"high": "102.00", "low": "99.00", "volume": 1},
            }
        ],
        execution_authority="AUTHORIZED",
        learning_policy=LearningPolicyV1(
            policy_id="learning-policy-task6",
            policy_version="1",
            account_id="acct-paper",
            mode="PAPER",
            minimum_samples=1,
            allowed_evidence_tiers=(EvidenceTier.OBSERVED_REPLAY,),
            allowed_evidence_modes=("PAPER",),
        ),
    )
    return runtime, repository, request, active_forecast


def _exit_opportunity(
    forecast: ForecastV1,
    *,
    valid_until_ns: int = T + 30_000_000_000,
    account_id: str = "acct-paper",
) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=f"opportunity-paper-exit-{valid_until_ns}",
        schema_version="1",
        scope=forecast.scope,
        created_at_ns=T + 3_000_000_000,
        quality=QUALITY,
        side=OpportunitySide.SHORT,
        valid_until_ns=valid_until_ns,
        source_forecast_refs=(ContractReference(kind="forecast", id=forecast.forecast_id),),
        lineage_refs=(
            ContractReference(kind="strategy_match", id="missing-until-entry"),
            ContractReference(kind="forecast", id=forecast.forecast_id),
        ),
        metadata={
            "account_id": account_id,
            "mode": "PAPER",
            "scenario_id": "paper-happy",
        },
    )


class EquityPaperRuntimeTests(unittest.TestCase):
    def test_a_profitable_round_trip_preserves_reduction_quantities(self) -> None:
        execution_policy = build_execution_policy(
            trade_fraction_nav=0.10,
            max_trade_notional_minor=20_200,
            max_symbol_concentration_fraction=1.0,
            minimum_trade_notional_minor=100,
        )
        economics = replace(
            _economics(),
            capital_required=MoneyMinorUnits(20_200, "USD", 2),
            buying_power_required=MoneyMinorUnits(20_200, "USD", 2),
        )
        runtime, repository, request, forecast = _runtime_fixture(
            economics=economics,
            allocation_values={
                "available_capital_minor": 20_200,
                "available_buying_power_minor": 20_200,
            },
            execution_policy=execution_policy,
            target_kind="direction_up_down",
            session_id="runtime-paper-task6-reduction",
        )

        entry = runtime.run_entry(request)

        self.assertEqual(entry.status, "FILLED")
        self.assertEqual(entry.quantities["allocation_desired_quantity"], 2)
        self.assertEqual(entry.quantities["proposal_requested_quantity"], 2)
        self.assertEqual(entry.quantities["risk_approved_quantity"], 2)
        self.assertEqual(entry.quantities["submitted_quantity"], 2)
        self.assertEqual(entry.quantities["filled_quantity"], 1)
        self.assertEqual(
            runtime._entry["risk_decision"].decision,
            RiskDecisionKind.APPROVE,
        )
        closed = runtime.close(
            opportunity=_exit_opportunity(forecast),
            decision_time_ns=T + 3_000_000_000,
            portfolio=build_portfolio_snapshot(
                captured_at_ns=T + 3_000_000_000,
                cash_minor=989_900,
                equity_minor=1_000_000,
                currency="USD",
                price_scale=100,
                scenario_id="paper-happy",
                mode="PAPER",
                positions=(
                    PaperPositionSnapshot(
                        instrument_id=INSTRUMENT_ID,
                        symbol="AAPL",
                        quantity=1,
                        market_value_minor=10_100,
                    ),
                ),
            ),
            quote=MarketQuoteV1(
                instrument_id=INSTRUMENT_ID,
                bid_minor=10_300,
                ask_minor=10_400,
                available_time_ns=T + 3_000_000_000,
            ),
            bars=[
                {
                    "available_time": T + 4_000_000_000,
                    "normalized_event_id": "task6-reduction-exit",
                    "bar_payload": {"high": "105.00", "low": "104.00", "volume": 1000},
                }
            ],
        )
        reconstruction = runtime.reconstruct(entry.ids["allocation_decision_id"])
        self.assertEqual(closed.status, "CLOSED")
        self.assertEqual(reconstruction.account["realized_pnl_minor"], 200)
        self.assertEqual(
            reconstruction.attribution.trading_outcome.realized_pnl_minor,
            reconstruction.account["realized_pnl_minor"],
        )
        repository.put_event(
            EventV1(
                event_id="task6-learning-terminal",
                schema_version="1",
                event_type="TRADE",
                event_time_ns=forecast.resolve_time_ns,
                available_time_ns=forecast.resolve_time_ns,
                payload={"price": 110.0, "quantity": 10},
                quality=QUALITY,
                source=SourceReference(
                    provider_id="fixture",
                    source_type="TRADE",
                    source_record_id="task6-learning-terminal",
                ),
                instrument_id="AAPL",
            )
        )
        ledger_entry = repository.get_prediction_ledger_entries_by_forecast(
            forecast.forecast_id,
        )[0]
        self.assertIsNotNone(ledger_entry)
        learning = runtime.settle_due_and_evaluate(
            now_ns=ledger_entry.availability_cutoff_ns,
        )
        self.assertEqual(learning.settlement_results[0].status, SettlementStatus.SETTLED)
        self.assertLessEqual(
            ledger_entry.registered_at_ns,
            learning.settlement_results[0].label_available_time_ns,
        )
        self.assertEqual(learning.prediction_quality, QualityState.GOOD)
        self.assertEqual(learning.trading_quality, QualityState.GOOD)
        self.assertIsNotNone(learning.prediction_outcome)
        self.assertIsNotNone(learning.trading_attribution)
        self.assertIsNotNone(learning.handoff)
        self.assertFalse(learning.handoff.promotional)
        self.assertFalse(learning.handoff.can_promote)
        self.assertFalse(learning.handoff.can_execute)
        self.assertEqual(len(repository.get_strategy_attributions_by_allocation(
            entry.ids["allocation_decision_id"],
        )), 2)

    def test_b_risk_rejection_keeps_evidence_without_paper_mutation(self) -> None:
        runtime, repository, request, _forecast_record = _runtime_fixture(
            execution_policy=build_execution_policy(
                trade_fraction_nav=0.02,
                max_trade_notional_minor=50_000,
                max_symbol_concentration_fraction=1.0,
                minimum_trade_notional_minor=100,
                daily_loss_limit_fraction=0.05,
            ),
            equity_minor=900_000,
            start_of_day_equity_minor=1_000_000,
            session_id="runtime-paper-task6-risk-rejection",
        )

        result = runtime.run_entry(request)

        self.assertEqual(result.status, "RISK_REJECTED")
        self.assertIsNotNone(repository.get_strategy_match(result.ids["strategy_match_id"]))
        self.assertIsNotNone(repository.get_opportunity(result.ids["opportunity_id"]))
        self.assertEqual(runtime.ledger.project_orders(), [])
        self.assertEqual(runtime.ledger.project_fills(), [])
        self.assertEqual(runtime.ledger.project_account()["realized_pnl_minor"], 0)
        self.assertIsNone(result.attribution_id)
        self.assertEqual(repository.get_strategy_attributions_by_allocation(
            result.ids["allocation_decision_id"],
        ), ())

    def test_c_no_allocation_persists_shared_decision_set_without_downstream_records(self) -> None:
        runtime, repository, request, _forecast_record = _runtime_fixture(
            allocation_values={
                "available_capital_minor": 0,
                "available_buying_power_minor": 0,
            },
            session_id="runtime-paper-task6-no-allocation",
        )

        result = runtime.run_entry(request)

        self.assertEqual(result.status, "NOT_ALLOCATED")
        decisions = repository.get_allocation_decisions_by_set(result.ids["decision_set_id"])
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].status.value, "NO_ALLOCATION")
        self.assertEqual(decisions[0].decision_set_id, result.ids["decision_set_id"])
        self.assertIsNone(result.ids.get("trade_proposal_id"))
        self.assertIsNone(result.ids.get("risk_decision_id"))
        self.assertEqual(runtime.ledger.project_orders(), [])
        self.assertEqual(runtime.ledger.project_fills(), [])
        self.assertEqual(runtime.ledger.project_account()["realized_pnl_minor"], 0)

    def test_d_duplicate_replay_is_idempotent_across_runtime_and_paper(self) -> None:
        runtime, repository, request, _forecast_record = _runtime_fixture(
            session_id="runtime-paper-task6-replay",
        )

        first = runtime.run_entry(request)
        repeated = runtime.run_entry(request)

        self.assertEqual(repeated.status, first.status)
        self.assertEqual(repeated.ids, first.ids)
        self.assertEqual(repeated.quantities, first.quantities)
        self.assertEqual(repeated.fill_ids, first.fill_ids)
        self.assertEqual(len(runtime.ledger.project_orders()), 1)
        self.assertEqual(len(runtime.ledger.project_fills()), 1)
        self.assertEqual(
            len(repository.get_allocation_decisions_by_set(first.ids["decision_set_id"])),
            1,
        )
        self.assertEqual(len(repository.get_strategy_attributions_by_allocation(
            first.ids["allocation_decision_id"],
        )), 1)

    def test_e_account_mismatch_fails_closed_before_cross_account_paper_mutation(self) -> None:
        champion = _champion()
        other_account_forecast = replace(
            _forecast(champion),
            forecast_id="forecast-paper-other-account",
            metadata={**_forecast(champion).metadata, "account_id": "other-account"},
        )
        runtime, repository, request, _forecast_record = _runtime_fixture(
            forecast=other_account_forecast,
            session_id="runtime-paper-task6-account-forecast",
        )
        result = runtime.run_entry(request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(runtime.ledger.project_orders(), [])
        self.assertEqual(runtime.ledger.project_fills(), [])

        mismatched_runtime, mismatched_repository, mismatched_request, _ = _runtime_fixture(
            economics=replace(_economics(), account_id="other-account"),
            session_id="runtime-paper-task6-account-economics",
        )
        with self.assertRaises(OpportunityBridgeError):
            mismatched_runtime.run_entry(mismatched_request)
        self.assertEqual(mismatched_runtime.ledger.project_orders(), [])
        self.assertEqual(mismatched_runtime.ledger.project_fills(), [])
        self.assertEqual(mismatched_repository.get_strategy_attributions_by_allocation("missing"), ())

        valid_runtime, _valid_repository, valid_request, _ = _runtime_fixture(
            session_id="runtime-paper-task6-account-reconstruct",
        )
        valid_entry = valid_runtime.run_entry(valid_request)
        before_fills = tuple(valid_runtime.ledger.project_fills())
        with self.assertRaisesRegex(StrategyRuntimeError, "RECONSTRUCTION_SCOPE_MISMATCH"):
            valid_runtime.reconstruct(valid_entry.ids["allocation_decision_id"], account_id="other-account")
        self.assertEqual(tuple(valid_runtime.ledger.project_fills()), before_fills)

    def test_f_expired_canonical_close_stops_before_downstream_mutation(self) -> None:
        runtime, repository, request, forecast = _runtime_fixture(
            session_id="runtime-paper-task6-opportunity-expiry",
        )
        entry = runtime.run_entry(request)
        with self.assertRaisesRegex(StrategyRuntimeError, "CLOSE_OPPORTUNITY_EXPIRED"):
            runtime.close(
                opportunity=_exit_opportunity(forecast, valid_until_ns=T + 3_000_000_000),
                decision_time_ns=T + 3_000_000_000,
            )
        self.assertEqual(len(runtime.ledger.project_orders()), 1)
        self.assertEqual(len(runtime.ledger.project_fills()), 1)
        self.assertEqual(len(repository.get_strategy_attributions_by_allocation(
            entry.ids["allocation_decision_id"],
        )), 1)

    def test_future_forecast_and_predecision_bars_are_rejected_without_fills(self) -> None:
        champion = _champion()
        future_forecast = replace(
            _forecast(champion),
            forecast_id="forecast-paper-future",
            decision_time_ns=T + 1,
            resolve_time_ns=T + HORIZON + 1,
        )
        runtime, _repository, request, _forecast_record = _runtime_fixture(
            forecast=future_forecast,
            session_id="runtime-paper-task6-future-forecast",
        )
        result = runtime.run_entry(request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(runtime.ledger.project_fills(), [])

        runtime, _repository, request, _forecast_record = _runtime_fixture(
            bars=[
                {
                    "available_time": T - 1,
                    "normalized_event_id": "task6-predecision-bar",
                    "bar_payload": {"high": "102.00", "low": "99.00", "volume": 1000},
                }
            ],
            session_id="runtime-paper-task6-predecision-fill",
        )
        result = runtime.run_entry(request)
        self.assertEqual(result.status, "EXECUTION_FAILED")
        self.assertEqual(runtime.ledger.project_fills(), [])
        self.assertIsNone(result.attribution_id)

    def test_profitable_round_trip_reconstructs_full_chain(self) -> None:
        repository = InMemoryIntelligenceRepository()
        repository.put_event(
            EventV1(
                event_id="anchor-paper",
                schema_version="1",
                event_type="TRADE",
                event_time_ns=T,
                available_time_ns=T,
                payload={"price": 100.0, "quantity": 10},
                quality=QUALITY,
                source=SourceReference(
                    provider_id="fixture",
                    source_type="TRADE",
                    source_record_id="anchor-paper",
                ),
                instrument_id="AAPL",
            )
        )
        repository.put_snapshot(
            SnapshotV1(
                snapshot_id="snapshot-paper-1",
                schema_version="1",
                decision_time_ns=T,
                scope=SCOPE,
                quality=QUALITY,
                source_event_refs=(ContractReference(kind="event", id="anchor-paper"),),
            )
        )
        champion = _champion()
        forecast = _forecast(champion)
        repository.put_forecast(forecast)
        policy: OpportunityPolicyV1 = build_opportunity_policy(
            champion_scope=champion.champion_scope,
            max_forecast_age_ns=HORIZON,
            max_opportunity_lifetime_ns=20_000_000_000,
            minimum_probability_edge=0.05,
        )
        economics = _economics()
        execution_policy = build_execution_policy(
            trade_fraction_nav=0.02,
            max_trade_notional_minor=50_000,
            max_symbol_concentration_fraction=1.0,
            minimum_trade_notional_minor=100,
        )
        portfolio = build_portfolio_snapshot(
            captured_at_ns=T,
            cash_minor=1_000_000,
            equity_minor=1_000_000,
            currency="USD",
            price_scale=100,
            scenario_id="paper-happy",
            mode="PAPER",
        )
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="runtime-paper-happy",
            instrument_id=INSTRUMENT_ID,
            symbol="AAPL",
            policy={
                "policy_version": "paper-policy-1",
                "risk_policy_identity_hash": "risk-policy-paper-1",
                "initial_cash_minor": 1_000_000,
                "currency": "USD",
                "price_scale": 100,
                "max_order_shares": 1_000,
                "max_position_shares": 1_000,
                "max_open_orders": 10,
                "commission_minor_per_share": 0,
                "fee_minor_per_order": 0,
                "participation_cap_numerator": 1,
                "participation_cap_denominator": 1,
            },
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        runtime = StrategyPaperRuntime(
            repository=repository,
            scanner=UniversalStrategyScanner(
                query_planner=None,
                repository=repository,
            ),
            forecast_resolver=lambda match: forecast,
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_policy=policy,
            opportunity_context=OpportunityContext(
                snapshot_ref=ContractReference(kind="snapshot", id="snapshot-paper-1"),
                snapshot_available_time_ns=T,
                spread_bps=5,
                spread_available_time_ns=T,
                mode="PAPER",
                scenario_id="paper-happy",
                account_id="acct-paper",
            ),
            economic_assessment=economics,
            comparison_constraints={
                "currency": "USD",
                "scale": 2,
            },
            allocation_constraints={
                "scale": 2,
                "available_capital_minor": 10_100,
                "available_buying_power_minor": 10_100,
                "maximum_loss_budget_minor": 1_000,
            },
            execution_policy=execution_policy,
            portfolio=portfolio,
            quote=MarketQuoteV1(
                instrument_id=INSTRUMENT_ID,
                bid_minor=10_000,
                ask_minor=10_100,
                available_time_ns=T,
            ),
            ledger=ledger,
            bars=[
                {
                    "available_time": T + 2_000_000_000,
                    "normalized_event_id": "bar-entry",
                    "bar_payload": {"high": "102.00", "low": "99.00", "volume": 1000},
                }
            ],
            execution_authority="AUTHORIZED",
        )

        entry = runtime.run_entry(_strategy_request())

        self.assertEqual(entry.status, "FILLED")
        self.assertEqual(entry.quantities["allocation_desired_quantity"], 1)
        self.assertEqual(entry.quantities["submitted_quantity"], 1)
        self.assertEqual(len(entry.fill_ids), 1)
        self.assertIn("prediction_ledger_entry_id", entry.ids)
        self.assertEqual(
            entry.ids["prediction_ledger_entry_id"],
            runtime._entry["prediction_ledger_entry"].ledger_entry_id,
        )
        self.assertIsNotNone(entry.attribution_id)
        self.assertIsNotNone(entry.ids["decision_set_id"])
        self.assertEqual(repository.get_strategy_match(entry.ids["strategy_match_id"]).disposition, StrategyMatchDisposition.MATCHED)

        exit_opportunity = __import__(
            "market_platform_foundation.intelligence.contracts",
            fromlist=["OpportunityV1"],
        ).OpportunityV1(
            opportunity_id="opportunity-paper-exit",
            schema_version="1",
            scope=SCOPE,
            created_at_ns=T + 3_000_000_000,
            quality=QUALITY,
            side=OpportunitySide.SHORT,
            valid_until_ns=T + 30_000_000_000,
            source_forecast_refs=(ContractReference(kind="forecast", id=forecast.forecast_id),),
            lineage_refs=(
                ContractReference(kind="strategy_match", id=entry.ids["strategy_match_id"]),
                ContractReference(kind="forecast", id=forecast.forecast_id),
            ),
            metadata={"account_id": "acct-paper", "mode": "PAPER", "scenario_id": "paper-happy"},
        )
        closed = runtime.close(
            opportunity=exit_opportunity,
            decision_time_ns=T + 3_000_000_000,
            portfolio=build_portfolio_snapshot(
                captured_at_ns=T + 3_000_000_000,
                cash_minor=989_900,
                equity_minor=1_000_000,
                currency="USD",
                price_scale=100,
                scenario_id="paper-happy",
                mode="PAPER",
                positions=(
                    PaperPositionSnapshot(
                        instrument_id=INSTRUMENT_ID,
                        symbol="AAPL",
                        quantity=1,
                        market_value_minor=10_100,
                    ),
                ),
            ),
            quote=MarketQuoteV1(
                instrument_id=INSTRUMENT_ID,
                bid_minor=10_300,
                ask_minor=10_400,
                available_time_ns=T + 3_000_000_000,
            ),
            bars=[
                {
                    "available_time": T + 4_000_000_000,
                    "normalized_event_id": "bar-exit",
                    "bar_payload": {"high": "105.00", "low": "104.00", "volume": 1000},
                }
            ],
        )

        self.assertEqual(closed.status, "CLOSED")
        self.assertEqual(len(closed.fill_ids), 1)
        self.assertEqual(
            runtime.reconstruct(entry.ids["allocation_decision_id"]).account["realized_pnl_minor"],
            200,
        )
        reconstruction = runtime.reconstruct(entry.ids["allocation_decision_id"])
        self.assertEqual(reconstruction.attribution.trading_outcome.realized_pnl_minor, 200)
        self.assertEqual(reconstruction.account["realized_pnl_minor"], 200)
        self.assertEqual(
            reconstruction.attribution.fill_refs,
            tuple(ContractReference(kind="fill", id=fill_id) for fill_id in sorted(entry.fill_ids + closed.fill_ids)),
        )
        replay = runtime.run_entry(_strategy_request())
        self.assertEqual(replay.status, "FILLED")
        self.assertEqual(replay.ids, entry.ids)
        self.assertEqual(replay.quantities, entry.quantities)
        self.assertEqual(replay.fill_ids, entry.fill_ids)
        self.assertEqual(len(ledger.project_fills()), 2)

    def test_closed_trade_can_remain_not_due_until_later_settlement(self) -> None:
        runtime, repository, forecast, _ = _task5_learning_runtime()
        ledger_entry = runtime._entry["prediction_ledger_entry"]

        before_due = runtime.settle_due_and_evaluate(
            now_ns=ledger_entry.availability_cutoff_ns - 1,
        )

        self.assertEqual(len(before_due.settlement_results), 1)
        self.assertEqual(
            before_due.settlement_results[0].status,
            SettlementStatus.NOT_DUE,
        )
        self.assertEqual(before_due.eligibility, LearningEligibility.INCONCLUSIVE)
        self.assertIsNone(before_due.learning_evaluation)
        self.assertEqual(repository.get_outcomes_by_forecast(forecast.forecast_id), ())

    def test_settled_prediction_and_trading_outcome_remain_separate(self) -> None:
        runtime, repository, forecast, _ = _task5_learning_runtime()
        ledger_entry = runtime._entry["prediction_ledger_entry"]
        _seed_task5_terminal_trade(
            repository,
            price=110.0,
            event_time_ns=forecast.decision_time_ns + forecast.horizon.duration_ns,
        )

        first = runtime.settle_due_and_evaluate(
            now_ns=ledger_entry.availability_cutoff_ns,
        )
        repeated = runtime.settle_due_and_evaluate(
            now_ns=ledger_entry.availability_cutoff_ns,
        )

        self.assertEqual(first.settlement_results[0].status, SettlementStatus.SETTLED)
        self.assertEqual(
            repeated.settlement_results[0].status,
            SettlementStatus.ALREADY_SETTLED,
        )
        self.assertEqual(first.eligibility, LearningEligibility.ELIGIBLE)
        self.assertEqual(first.prediction_quality, QualityState.GOOD)
        self.assertEqual(first.trading_quality, QualityState.GOOD)
        self.assertIsNotNone(first.prediction_outcome)
        self.assertIsNotNone(first.learning_evaluation)
        self.assertIsNotNone(first.handoff)
        self.assertFalse(first.handoff.promotional)
        self.assertFalse(first.handoff.can_promote)
        self.assertFalse(first.handoff.can_execute)
        self.assertFalse(first.handoff.champion_change_allowed)
        self.assertEqual(first.learning_evaluation, repeated.learning_evaluation)
        self.assertEqual(first.handoff, repeated.handoff)

    def test_learning_minimum_sample_gate_fails_closed(self) -> None:
        runtime, repository, forecast, _ = _task5_learning_runtime(minimum_samples=2)
        ledger_entry = runtime._entry["prediction_ledger_entry"]
        _seed_task5_terminal_trade(
            repository,
            price=110.0,
            event_time_ns=forecast.decision_time_ns + forecast.horizon.duration_ns,
        )

        result = runtime.settle_due_and_evaluate(
            now_ns=ledger_entry.availability_cutoff_ns,
        )

        self.assertEqual(result.eligibility, LearningEligibility.INCONCLUSIVE)
        self.assertIn("INSUFFICIENT_SAMPLES", result.learning_evaluation.reasons)
        self.assertIsNone(result.handoff)


def _seed_task5_terminal_trade(
    repository: InMemoryIntelligenceRepository,
    *,
    price: float,
    event_time_ns: int,
) -> None:
    repository.put_event(
        EventV1(
            event_id="learning-terminal",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=event_time_ns,
            available_time_ns=event_time_ns,
            payload={"price": price, "quantity": 10},
            quality=QUALITY,
            source=SourceReference(
                provider_id="fixture",
                source_type="TRADE",
                source_record_id="learning-terminal",
            ),
            instrument_id="AAPL",
        )
    )


def _task5_learning_runtime(
    *,
    minimum_samples: int = 1,
) -> tuple[StrategyPaperRuntime, InMemoryIntelligenceRepository, object, object]:
    repository = InMemoryIntelligenceRepository()
    repository.put_event(
        EventV1(
            event_id="learning-anchor",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=T,
            available_time_ns=T,
            payload={"price": 100.0, "quantity": 10},
            quality=QUALITY,
            source=SourceReference(
                provider_id="fixture",
                source_type="TRADE",
                source_record_id="learning-anchor",
            ),
            instrument_id="AAPL",
        )
    )
    repository.put_snapshot(
        SnapshotV1(
            snapshot_id="learning-snapshot",
            schema_version="1",
            decision_time_ns=T,
            scope=IntelligenceScope(instrument_ids=("AAPL",)),
            quality=QUALITY,
            source_event_refs=(
                ContractReference(kind="event", id="learning-anchor"),
            ),
        )
    )
    forecast = ForecastV1(
        forecast_id="forecast-paper-learning",
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=("AAPL",)),
        decision_time_ns=T,
        snapshot_id="learning-snapshot",
        target=direction_up_down_target("AAPL"),
        horizon=TimeHorizonNs(duration_ns=HORIZON),
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=0.8,
            calibrated_probability=0.8,
        ),
        quality=QUALITY,
        resolve_time_ns=T + HORIZON,
        metadata={"account_id": "acct-paper", "mode": "PAPER"},
    )
    repository.put_forecast(forecast)
    match = StrategyMatch.create(
        strategy_id="strategy-paper-learning",
        strategy_identity_hash="strategy-paper-learning-hash",
        scope=forecast.scope,
        decision_time_ns=forecast.decision_time_ns,
        disposition=StrategyMatchDisposition.MATCHED,
        capability_state=AvailabilityState.AVAILABLE,
        quality=QUALITY,
        source_forecast_refs=(
            ContractReference(kind="forecast", id=forecast.forecast_id),
        ),
        context={"account_id": "acct-paper", "mode": "PAPER"},
    )
    repository.put_strategy_match(match)
    prediction_ledger_entry = PredictionLedgerService(repository).register_forecast(
        forecast,
        now_ns=forecast.decision_time_ns,
        mode=SettlementMode.COUNTERFACTUAL,
        scenario_id="paper-learning",
    )
    assert hasattr(prediction_ledger_entry, "ledger_entry_id")
    allocation = SimpleNamespace(
        allocation_decision_id="allocation-paper-learning",
        account_id="acct-paper",
        mode="PAPER",
        strategy_match_ref=ContractReference(kind="strategy_match", id=match.match_id),
        forecast_refs=(
            ContractReference(kind="forecast", id=forecast.forecast_id),
        ),
        opportunity_ref=ContractReference(kind="opportunity", id="opportunity-paper-learning"),
        cluster_ref=ContractReference(kind="cluster", id="cluster-paper-learning"),
    )
    attribution = StrategyAttributionV1.create(
        schema_version="1",
        account_id="acct-paper",
        mode="PAPER",
        instrument_id=forecast.target.instrument_id,
        allocation_ref=ContractReference(
            kind="allocation_decision",
            id=allocation.allocation_decision_id,
        ),
        strategy_match_ref=ContractReference(kind="strategy_match", id=match.match_id),
        strategy_id=match.strategy_id,
        strategy_identity_hash=match.strategy_identity_hash,
        allocation_quantity=1,
        allocation_direction="LONG",
        allocation_time_ns=forecast.decision_time_ns,
        point_in_time_ns=forecast.decision_time_ns,
    )
    runtime = object.__new__(StrategyPaperRuntime)
    runtime.repository = repository
    runtime.outcome_settlement_service = OutcomeSettlementService(repository)
    runtime.learning_policy = LearningPolicyV1(
        policy_id="learning-policy-paper",
        policy_version="1",
        account_id="acct-paper",
        mode="PAPER",
        minimum_samples=minimum_samples,
        allowed_evidence_tiers=(EvidenceTier.OBSERVED_REPLAY,),
        allowed_evidence_modes=("PAPER",),
    )
    runtime._entry = {
        "forecast": forecast,
        "match": match,
        "allocation_decision": allocation,
        "attribution": attribution,
        "prediction_ledger_entry": prediction_ledger_entry,
    }
    return runtime, repository, forecast, prediction_ledger_entry


if __name__ == "__main__":
    unittest.main()
