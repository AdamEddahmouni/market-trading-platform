"""One-shot Path A prospective hop: mocked providers, no Live, no secrets."""

from __future__ import annotations

import inspect
import json
import unittest

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
from market_platform_foundation.market_data.runtime_composition import ObservationalRuntimeComposition
from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
    YahooDelayedEquityQuoteProvider,
)
from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
    UnreachableOpenDEquityQuoteProvider,
)
from market_platform_foundation.providers.contracts import ProviderResult
from market_platform_foundation.providers.equity_quote_discovery import (
    FINVIZ_TOKEN_NAMES,
    names_present,
)
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.providers.stubs import UnconfiguredEquityQuoteProvider
from market_platform_foundation.strategy.path_a_prospective import (
    DELAYED_SOURCE,
    PathAProspectiveComposer,
)
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCaller
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
from market_platform_foundation.ui_api.opportunity_projections import _opportunity_source
from market_platform_foundation.ui_api.store import ReplayStore


T = 1_700_000_000_000_000_000
HORIZON = 300_000_000_000
INSTRUMENT = InstrumentIdentity("canonical", "AAPL", "EQUITY", "XNYS", "USD")
INSTRUMENT_ID = INSTRUMENT.qualified_id()
QUALITY = QualitySummary(state=QualityState.GOOD)
SCOPE = IntelligenceScope(
    instrument_ids=(INSTRUMENT_ID,),
    context_id="acct-paper:paper:snapshot-paper-1",
)


def _quote_event(*, symbol: str = "AAPL", seq: int = 7, delayed: bool = True) -> dict:
    return {
        "capability": "US_EQUITY_L1",
        "clocks": {
            "event_time_ns": T,
            "provider_time_ns": T,
            "received_time_ns": T + 1_000_000,
        },
        "instrument_id": symbol,
        "provider": "yahoo.finance.delayed" if delayed else "test.realtime",
        "provider_symbol": symbol,
        "raw_payload": {
            "ask_price": 190.2,
            "ask_vol": 200,
            "bid_price": 190.0,
            "bid_vol": 100,
            "last_price": 190.1,
        },
        "sequence": seq,
        "timeliness": "DELAYED" if delayed else "REAL_TIME",
        "normalization_version": "test/1.0.0",
    }


class ScriptedQuoteProvider:
    provider_id = "yahoo.finance.delayed"
    capability = "US_EQUITY_SNAPSHOT"

    def __init__(self, result: ProviderResult) -> None:
        self._result = result

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return self._result


def _champion() -> ChampionAssignmentV1:
    return ChampionAssignmentV1(
        assignment_id="champion-path-a-prospective-1",
        schema_version="1",
        champion_scope=ChampionScopeV1(
            component="forecast",
            target_kind="direction",
            horizon_ns=HORIZON,
            mode="PAPER",
            scenario_id="paper-path-a",
        ),
        candidate_id="candidate-path-a-prospective-1",
        candidate_artifact_hash="artifact-path-a-prospective-1",
        promotion_decision_id=None,
        previous_assignment_id=None,
        effective_from_ns=T - 1,
        assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
    )


def _forecast(champion: ChampionAssignmentV1) -> ForecastV1:
    return ForecastV1(
        forecast_id="forecast-path-a-prospective-1",
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


def _scan_request(*, mode: str = "paper") -> ScanRequest:
    definition = StrategyDefinition(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis="prospective path a",
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
                strategy_id="strategy-path-a-prospective-1",
                definition=definition,
                evaluator=lambda _: StrategyEvaluationResult(
                    disposition=StrategyMatchDisposition.REJECTED
                ),
            ),
        ),
        scope=ScanScope(account_id="acct-paper", mode=mode),
        trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
        decision_time_ns=T,
        expires_at_ns=T + 60_000_000_000,
        budget=ScanBudget(max_evaluations=1, max_cost_units=1),
    )


def _caller(repository: InMemoryIntelligenceRepository, champion: ChampionAssignmentV1, forecast: ForecastV1) -> PathAScanCaller:
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
            mode="PAPER",
            scenario_id="paper-path-a",
            account_id="acct-paper",
        ),
        economic_assessment=UniversalEconomicAssessmentV1.create(
            scope=SCOPE,
            account_id="acct-paper",
            mode="PAPER",
            assessed_at_ns=T,
            expires_at_ns=T + 50_000_000_000,
            assumptions=EconomicAssumptionsV1(assumptions_id="economics-p", version="1"),
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
        ),
        engine=OpportunityEngine(),
    )


class PathAProspectiveTests(unittest.TestCase):
    def test_config_discovery_does_not_leak_secrets(self) -> None:
        present = names_present(FINVIZ_TOKEN_NAMES)
        self.assertIsInstance(present, tuple)
        dumped = json.dumps(present)
        self.assertNotIn("secret", dumped.lower())
        self.assertNotIn("api_key=", dumped.lower())

    def test_unconfigured_provider_is_unavailable(self) -> None:
        result = PathAProspectiveComposer(
            quote_provider=UnconfiguredEquityQuoteProvider(),
        ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertIn("PROVIDER_NOT_CONFIGURED", result.reason_codes)

    def test_opend_disconnected_is_unavailable_not_mock(self) -> None:
        result = PathAProspectiveComposer(
            quote_provider=UnreachableOpenDEquityQuoteProvider(),
        ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("OPEND_UNAVAILABLE",))

    def test_live_mode_forbidden(self) -> None:
        available = ProviderResult(
            status="available",
            events=(_quote_event(),),
            provider_id="yahoo.finance.delayed",
            capability="US_EQUITY_SNAPSHOT",
        )
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(available),
        ).run("AAPL", mode="live", as_of_time_ns=T)
        self.assertEqual(result.status, "LIVE_FORBIDDEN")

    def test_malformed_record(self) -> None:
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(
                ProviderResult(
                    status="unavailable",
                    reason_code="MALFORMED_RECORD",
                    provider_id="yahoo.finance.delayed",
                    capability="US_EQUITY_SNAPSHOT",
                )
            ),
        ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "MALFORMED")

    def test_timeout(self) -> None:
        def boom(_url: str) -> tuple[int, bytes]:
            raise TimeoutError("slow")

        result = PathAProspectiveComposer(
            quote_provider=YahooDelayedEquityQuoteProvider(fetch=boom),
        ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("PROVIDER_TIMEOUT",))

    def test_rate_limit(self) -> None:
        result = PathAProspectiveComposer(
            quote_provider=YahooDelayedEquityQuoteProvider(fetch=lambda _url: (429, b"")),
        ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("RATE_LIMIT",))

    def test_yahoo_normalizes_delayed_provenance(self) -> None:
        chart = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": 190.1,
                            "regularMarketTime": 1_700_000_000,
                            "bid": 190.0,
                            "ask": 190.2,
                        },
                        "timestamp": [1_700_000_000],
                    }
                ],
                "error": None,
            }
        }
        provider = YahooDelayedEquityQuoteProvider(
            fetch=lambda _url: (200, json.dumps(chart).encode("utf-8"))
        )
        fetched = provider.fetch_quote("AAPL")
        self.assertEqual(fetched.status, "available")
        event = fetched.events[0]
        self.assertEqual(event["timeliness"], "DELAYED")
        self.assertEqual(event["provider"], "yahoo.finance.delayed")
        self.assertEqual(event["clocks"]["event_time_ns"], 1_700_000_000 * 1_000_000_000)

    def test_delayed_quote_through_g7_is_not_actionable(self) -> None:
        available = ProviderResult(
            status="available",
            events=(_quote_event(),),
            provider_id="yahoo.finance.delayed",
            capability="US_EQUITY_SNAPSHOT",
        )
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
                    provider_id="yahoo.finance.delayed",
                    source_type="QUOTE",
                    source_record_id="aapl-1",
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
        champion = _champion()
        forecast = _forecast(champion)
        repository.put_forecast(forecast)
        composer = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(available),
            composition=ObservationalRuntimeComposition(),
            path_a_caller=_caller(repository, champion, forecast),
        )
        result = composer.run(
            "AAPL",
            mode="paper",
            scan_request=_scan_request(),
            as_of_time_ns=T + 2_000_000,
        )
        self.assertEqual(result.source, DELAYED_SOURCE)
        self.assertEqual(result.timeliness, "DELAYED")
        self.assertFalse(result.freshness.get("actionable"))
        self.assertEqual(result.freshness.get("reason_code"), "DELAYED_WHEN_REALTIME_REQUIRED")
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertEqual(result.selection.get("outcome"), "NO_PROVIDER")
        self.assertNotEqual(result.selection.get("provider_id"), "ibkr.observational")
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "EMPTY")
        self.assertEqual(result.provenance.get("provider"), "yahoo.finance.delayed")
        self.assertIn("freshness", result.freshness_payload)

    def test_two_instruments_stay_isolated(self) -> None:
        aapl = ProviderResult(
            status="available",
            events=(_quote_event(symbol="AAPL", seq=1),),
            provider_id="yahoo.finance.delayed",
        )
        msft = ProviderResult(
            status="available",
            events=(_quote_event(symbol="MSFT", seq=2),),
            provider_id="yahoo.finance.delayed",
        )
        composition = ObservationalRuntimeComposition()
        PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(aapl),
            composition=composition,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(msft),
            composition=composition,
        ).run("MSFT", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(composition.store.quote_for("AAPL"))
        self.assertIsNotNone(composition.store.quote_for("MSFT"))
        self.assertEqual(composition.store.quote_for("AAPL").instrument_id, "AAPL")
        self.assertEqual(composition.store.quote_for("MSFT").instrument_id, "MSFT")

    def test_projections_keep_replay_default(self) -> None:
        store = ReplayStore(collection_root=None)
        self.assertEqual(_opportunity_source(store), "REPLAY")
        store.opportunity_source = DELAYED_SOURCE
        self.assertEqual(_opportunity_source(store), DELAYED_SOURCE)

    def test_ingest_still_not_a_scanner(self) -> None:
        source = inspect.getsource(assemble_opportunity_review_rows)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("PathAScanCaller", source)
        self.assertNotIn("PathAProspectiveComposer", source)


if __name__ == "__main__":
    unittest.main()
