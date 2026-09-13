"""Bounded Paper/Demo Path A scan caller: not a daemon and not Live."""

from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    EventV1,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SnapshotV1,
    SourceReference,
    StrategyMatchDisposition,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.opportunity import (
    AccountActionability,
    EconomicAssumptionsV1,
    MoneyMinorUnits,
    OpportunityContext,
    UniversalEconomicAssessmentV1,
    build_opportunity_policy,
)
from market_platform_foundation.intelligence.opportunity.engine import OpportunityEngine
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.types import OpportunityPolicyV1
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion.types import (
    ChampionAssignmentReason,
    ChampionAssignmentV1,
    ChampionScopeV1,
)
from market_platform_foundation.intelligence.quality.models import QualityAssessment
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.strategy.path_a_scan_caller import (
    STATUS_EMPTY,
    STATUS_MINTED,
    PathAScanCaller,
    PathAScanCallerError,
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
QUALITY = QualitySummary(state=QualityState.GOOD)
SCOPE = IntelligenceScope(
    instrument_ids=(INSTRUMENT_ID,),
    context_id="acct-paper:paper:snapshot-paper-1",
)


def _champion() -> ChampionAssignmentV1:
    return ChampionAssignmentV1(
        assignment_id="champion-path-a-1",
        schema_version="1",
        champion_scope=ChampionScopeV1(
            component="forecast",
            target_kind="direction",
            horizon_ns=HORIZON,
            mode="PAPER",
            scenario_id="paper-path-a",
        ),
        candidate_id="candidate-path-a-1",
        candidate_artifact_hash="artifact-path-a-1",
        promotion_decision_id=None,
        previous_assignment_id=None,
        effective_from_ns=T - 1,
        assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
    )


def _forecast(champion: ChampionAssignmentV1) -> ForecastV1:
    return ForecastV1(
        forecast_id="forecast-path-a-1",
        schema_version="1",
        scope=SCOPE,
        decision_time_ns=T,
        snapshot_id="snapshot-paper-1",
        target=ForecastTarget(target_kind="direction", instrument_id="AAPL", parameters={}),
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
            "scenario_id": "paper-path-a",
            "forecast_stage": "FINAL_FUSED_CALIBRATED",
            "contributor_role": "PRODUCTION",
            "champion_candidate_id": champion.candidate_id,
            "candidate_artifact_hash": champion.candidate_artifact_hash,
        },
    )


def _economics() -> UniversalEconomicAssessmentV1:
    return UniversalEconomicAssessmentV1.create(
        scope=SCOPE,
        account_id="acct-paper",
        mode="PAPER",
        assessed_at_ns=T,
        expires_at_ns=T + 50_000_000_000,
        assumptions=EconomicAssumptionsV1(
            assumptions_id="economics-path-a-1",
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


def _request(*, mode: str = "paper", disposition: StrategyMatchDisposition = StrategyMatchDisposition.MATCHED) -> ScanRequest:
    definition = StrategyDefinition(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis="deterministic path a momentum",
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
                strategy_id="strategy-path-a-1",
                definition=definition,
                evaluator=lambda _: StrategyEvaluationResult(disposition=disposition),
            ),
        ),
        scope=ScanScope(account_id="acct-paper", mode=mode),
        trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
        decision_time_ns=T,
        expires_at_ns=T + 60_000_000_000,
        budget=ScanBudget(max_evaluations=1, max_cost_units=1),
    )


def _seed_repository() -> InMemoryIntelligenceRepository:
    repository = InMemoryIntelligenceRepository()
    repository.put_event(
        EventV1(
            event_id="path-a-anchor",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=T,
            available_time_ns=T,
            payload={"price": 100.0, "quantity": 10},
            quality=QUALITY,
            source=SourceReference(
                provider_id="fixture",
                source_type="TRADE",
                source_record_id="path-a-anchor",
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
            source_event_refs=(ContractReference(kind="event", id="path-a-anchor"),),
        )
    )
    return repository


def _caller(
    repository: InMemoryIntelligenceRepository,
    champion: ChampionAssignmentV1,
    forecast: ForecastV1,
    *,
    context_mode: str = "PAPER",
) -> PathAScanCaller:
    policy: OpportunityPolicyV1 = build_opportunity_policy(
        champion_scope=champion.champion_scope,
        max_forecast_age_ns=HORIZON,
        max_opportunity_lifetime_ns=20_000_000_000,
        minimum_probability_edge=0.05,
    )
    return PathAScanCaller(
        scanner=UniversalStrategyScanner(query_planner=None, repository=repository),
        repository=repository,
        forecast_resolver=lambda _match: forecast,
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_policy=policy,
        opportunity_context=OpportunityContext(
            snapshot_ref=ContractReference(kind="snapshot", id="snapshot-paper-1"),
            snapshot_available_time_ns=T,
            spread_bps=5,
            spread_available_time_ns=T,
            mode=context_mode,
            scenario_id="paper-path-a",
            account_id="acct-paper",
        ),
        economic_assessment=_economics(),
        engine=OpportunityEngine(),
    )


class PathAScanCallerTests(unittest.TestCase):
    def test_matched_paper_scan_mints_opportunity(self) -> None:
        repository = _seed_repository()
        champion = _champion()
        forecast = _forecast(champion)
        repository.put_forecast(forecast)
        result = _caller(repository, champion, forecast).run(_request())
        self.assertEqual(result.status, STATUS_MINTED)
        self.assertEqual(len(result.opportunities), 1)
        stored = repository.get_opportunity(result.opportunities[0].opportunity_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.opportunity_id, result.opportunities[0].opportunity_id)

    def test_no_matched_strategy_is_honest_empty(self) -> None:
        repository = _seed_repository()
        champion = _champion()
        forecast = _forecast(champion)
        result = _caller(repository, champion, forecast).run(
            _request(disposition=StrategyMatchDisposition.REJECTED)
        )
        self.assertEqual(result.status, STATUS_EMPTY)
        self.assertEqual(result.opportunities, ())
        self.assertEqual(result.reason_codes, ("NO_MATCHED_STRATEGY",))
        self.assertEqual(repository.get_opportunities_by_instrument(INSTRUMENT_ID), ())

    def test_live_mode_is_forbidden(self) -> None:
        repository = _seed_repository()
        champion = _champion()
        forecast = _forecast(champion)
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            _caller(repository, champion, forecast).run(_request(mode="live"))

    def test_live_context_is_forbidden(self) -> None:
        repository = _seed_repository()
        champion = _champion()
        forecast = _forecast(champion)
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            _caller(repository, champion, forecast, context_mode="ACTUAL_LIVE").run(_request())

    def test_demo_mode_is_allowed(self) -> None:
        repository = _seed_repository()
        champion = _champion()
        forecast = _forecast(champion)
        request = _request(mode="demo")
        demo_scope = IntelligenceScope(
            instrument_ids=(INSTRUMENT_ID,),
            context_id="acct-paper:demo:snapshot-paper-1",
        )
        forecast = replace(forecast, scope=demo_scope)
        economics = replace(_economics(), scope=demo_scope, mode="DEMO")
        caller = _caller(repository, champion, forecast, context_mode="DEMO")
        caller.economic_assessment = economics
        result = caller.run(request)
        self.assertEqual(result.mode, "demo")
        self.assertNotEqual(result.status, "LIVE_SCAN_CALLER_FORBIDDEN")

    def test_ingest_still_not_a_scanner(self) -> None:
        source = inspect.getsource(assemble_opportunity_review_rows)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("PathAScanCaller", source)


if __name__ == "__main__":
    unittest.main()
