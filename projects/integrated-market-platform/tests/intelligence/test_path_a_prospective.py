"""One-shot Path A prospective hop: mocked providers, no Live, no secrets."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
    ES_SYMBOL_BLOCKED,
    YAHOO_CAPABILITY,
    YahooDelayedEquityQuoteProvider,
)
from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
    MOOMOO_OPEND_PROVIDER_ID,
    OPEND_UNAVAILABLE,
    MoomooOpenDEquityQuoteProvider,
)
from market_platform_foundation.providers.contracts import ProviderResult
from market_platform_foundation.providers.equity_quote_discovery import (
    FINVIZ_TOKEN_NAMES,
    EquityQuoteDiscovery,
    discover_equity_quote_stack,
    names_present,
)
from market_platform_foundation.providers.equity_quote_selection import (
    delayed_cloud_overlay_provider,
    primary_equity_quote_provider,
)
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.providers.stubs import UnconfiguredEquityQuoteProvider
from market_platform_foundation.strategy.path_a_prospective import (
    DELAYED_SOURCE,
    PERSIST_INTENTIONAL_EPHEMERAL,
    PERSIST_NOT_MINTED,
    PERSIST_SKIPPED_NO_SESSION,
    PERSIST_WRITTEN,
    PathAHonestyInvoke,
    PathAPersistContext,
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCaller, PathAScanCallerError
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "intelligence"))
from forward_test_activation_support import (
    BASELINE_POLICY,
    CAMPAIGN_SLUG,
    POLICY_VERSION,
    create_activated_session,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)


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
    capability = "US_EQUITY_SNAPSHOT"

    def __init__(self, result: ProviderResult, *, provider_id: str = "yahoo.finance.delayed") -> None:
        self._result = result
        self.provider_id = provider_id

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


def _scan_request(
    *,
    mode: str = "paper",
    disposition: StrategyMatchDisposition = StrategyMatchDisposition.REJECTED,
) -> ScanRequest:
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
                evaluator=lambda _: StrategyEvaluationResult(disposition=disposition),
            ),
        ),
        scope=ScanScope(account_id="acct-paper", mode=mode),
        trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
        decision_time_ns=T,
        expires_at_ns=T + 60_000_000_000,
        budget=ScanBudget(max_evaluations=1, max_cost_units=1),
    )


class RecordingOpportunityEngine(OpportunityEngine):
    """Test double: real assess, with a call count. Not a live fill."""

    def __init__(self) -> None:
        super().__init__()
        self.assess_calls = 0

    def assess(self, **kwargs):  # type: ignore[no-untyped-def]
        self.assess_calls += 1
        return super().assess(**kwargs)


def _caller(
    repository: InMemoryIntelligenceRepository,
    champion: ChampionAssignmentV1,
    forecast: ForecastV1,
    *,
    engine: OpportunityEngine | None = None,
    context_mode: str = "PAPER",
    scope: IntelligenceScope | None = None,
) -> PathAScanCaller:
    mode_n = str(context_mode or "PAPER").strip().upper()
    used_scope = scope if scope is not None else SCOPE
    scenario_id = "demo-path-a" if mode_n == "DEMO" else "paper-path-a"
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
            mode=mode_n,
            scenario_id=scenario_id,
            account_id="acct-paper",
        ),
        economic_assessment=UniversalEconomicAssessmentV1.create(
            scope=used_scope,
            account_id="acct-paper",
            mode=mode_n,
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
        engine=engine if engine is not None else OpportunityEngine(),
    )


def _delayed_available() -> ProviderResult:
    return ProviderResult(
        status="available",
        events=(_quote_event(),),
        provider_id="yahoo.finance.delayed",
        capability="US_EQUITY_SNAPSHOT",
    )


def _run_matched_fixture_hop(*, mode: str = "paper") -> tuple[object, RecordingOpportunityEngine]:
    """Paper/Demo MATCHED fixture through the prospective composer. Not empirical."""

    repository, champion, forecast = _seed_repository()
    engine = RecordingOpportunityEngine()
    mode_n = str(mode).strip().lower()
    context_mode = mode_n.upper()
    scope = SCOPE
    if mode_n == "demo":
        scope = IntelligenceScope(
            instrument_ids=(INSTRUMENT_ID,),
            context_id="acct-paper:demo:snapshot-paper-1",
        )
        champion = replace(
            champion,
            champion_scope=replace(
                champion.champion_scope, mode="DEMO", scenario_id="demo-path-a"
            ),
        )
        forecast = replace(
            forecast,
            forecast_id="forecast-path-a-prospective-demo-1",
            scope=scope,
            metadata={**dict(forecast.metadata), "mode": "DEMO", "scenario_id": "demo-path-a"},
        )
        repository.put_forecast(forecast)
    caller = _caller(
        repository,
        champion,
        forecast,
        engine=engine,
        context_mode=context_mode,
        scope=scope,
    )
    result = PathAProspectiveComposer(
        quote_provider=ScriptedQuoteProvider(_delayed_available()),
        composition=ObservationalRuntimeComposition(),
        path_a_caller=caller,
    ).run(
        "AAPL",
        mode=mode_n,
        scan_request=_scan_request(mode=mode_n, disposition=StrategyMatchDisposition.MATCHED),
        as_of_time_ns=T + 2_000_000,
    )
    return result, engine


def _matched_fixture_invoke(*, mode: str = "paper") -> PathAHonestyInvoke:
    """MATCHED fixture caller/request pair, for CLI-level persist wiring tests.

    Timeliness/G7 outcome is controlled by whichever quote provider the
    caller injects separately; this only supplies the strategy match so
    Path A can reach MINTED.
    """

    repository, champion, forecast = _seed_repository()
    mode_n = str(mode).strip().lower()
    context_mode = mode_n.upper()
    scope = SCOPE
    if mode_n == "demo":
        scope = IntelligenceScope(
            instrument_ids=(INSTRUMENT_ID,),
            context_id="acct-paper:demo:snapshot-paper-1",
        )
        champion = replace(
            champion,
            champion_scope=replace(
                champion.champion_scope, mode="DEMO", scenario_id="demo-path-a"
            ),
        )
        forecast = replace(
            forecast,
            forecast_id="forecast-path-a-prospective-demo-1",
            scope=scope,
            metadata={**dict(forecast.metadata), "mode": "DEMO", "scenario_id": "demo-path-a"},
        )
        repository.put_forecast(forecast)
    caller = _caller(repository, champion, forecast, context_mode=context_mode, scope=scope)
    request = _scan_request(mode=mode_n, disposition=StrategyMatchDisposition.MATCHED)
    return PathAHonestyInvoke(caller=caller, scan_request=request)


def _seed_repository() -> tuple[InMemoryIntelligenceRepository, ChampionAssignmentV1, ForecastV1]:
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
                provider_id="test.realtime",
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
    return repository, champion, forecast


def _realtime_quote(*, symbol: str = "AAPL") -> ProviderResult:
    return ProviderResult(
        status="available",
        events=(_quote_event(symbol=symbol, delayed=False),),
        provider_id="test.realtime",
        capability="US_EQUITY_SNAPSHOT",
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
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            result = PathAProspectiveComposer(
                quote_provider=MoomooOpenDEquityQuoteProvider(),
            ).run("AAPL", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertEqual(result.reason_codes, (OPEND_UNAVAILABLE,))
        self.assertEqual(result.provenance.get("provider"), MOOMOO_OPEND_PROVIDER_ID)

    def test_opend_hop_l1_is_known_g7_provider(self) -> None:
        event = _quote_event(delayed=False)
        event["provider"] = MOOMOO_OPEND_PROVIDER_ID
        event["capability"] = "US_EQUITY_L1"
        quote = ProviderResult(
            status="available",
            events=(event,),
            provider_id=MOOMOO_OPEND_PROVIDER_ID,
            capability="US_EQUITY_L1",
        )
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(
                quote, provider_id=MOOMOO_OPEND_PROVIDER_ID
            ),
        ).run("AAPL", mode="paper", as_of_time_ns=T + 1_000_000)
        diagnostics = tuple(result.selection.get("diagnostics") or ())
        self.assertNotIn(f"UNKNOWN_PROVIDER:{MOOMOO_OPEND_PROVIDER_ID}", diagnostics)
        self.assertEqual(result.selection.get("provider_id"), MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(result.selection.get("outcome"), "SELECTED")
        self.assertNotIn("G7_SELECTION_NO_PROVIDER", result.reason_codes)

    def test_discovery_does_not_swap_yahoo_when_opend_down(self) -> None:
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            provider, discovery = discover_equity_quote_stack()
            primary = primary_equity_quote_provider()
            overlay = delayed_cloud_overlay_provider()
        self.assertIsInstance(provider, MoomooOpenDEquityQuoteProvider)
        self.assertEqual(provider.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(primary.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(discovery.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertFalse(discovery.opend_reachable)
        self.assertEqual(discovery.reason_code, OPEND_UNAVAILABLE)
        self.assertNotEqual(discovery.provider_id, overlay.provider_id)
        self.assertEqual(discovery.overlay_provider_id, overlay.provider_id)
        self.assertIsInstance(overlay, YahooDelayedEquityQuoteProvider)

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
        self.assertEqual(event["capability"], YAHOO_CAPABILITY)
        self.assertEqual(event["capability"], "US_EQUITY_SNAPSHOT")
        self.assertEqual(event["provider"], "yahoo.finance.delayed")
        self.assertEqual(event["clocks"]["event_time_ns"], 1_700_000_000 * 1_000_000_000)

    def test_yahoo_overlay_rejects_es_before_http(self) -> None:
        calls: list[str] = []

        def boom(_url: str) -> tuple[int, bytes]:
            calls.append(_url)
            raise AssertionError("ES overlay must not HTTP")

        result = PathAProspectiveComposer(
            quote_provider=YahooDelayedEquityQuoteProvider(fetch=boom),
        ).run("ES=F", mode="paper", as_of_time_ns=T)
        self.assertEqual(result.status, "PROVIDER_UNAVAILABLE")
        self.assertEqual(result.reason_codes, (ES_SYMBOL_BLOCKED,))
        self.assertEqual(calls, [])

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

    def test_cli_source_injects_path_a_caller(self) -> None:
        from tools import path_a_prospective_run

        source = inspect.getsource(path_a_prospective_run.main)
        self.assertIn("PathAProspectiveComposer", source)
        self.assertIn("primary_equity_quote_provider", source)
        self.assertNotIn("build_paper_demo_path_a_invoke", source)
        self.assertNotIn("LiveObservationalRuntime", source)
        composer_run = inspect.getsource(PathAProspectiveComposer.run)
        self.assertIn("quote_event=event", composer_run)
        self.assertIn("forecast_path=self.forecast_path", composer_run)
        self.assertIn("contributor_path=self.contributor_path", composer_run)
        self.assertIn("calibration_path=self.calibration_path", composer_run)

    def test_honesty_invoke_refuses_live(self) -> None:
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke("AAPL", mode="live")
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke("AAPL", mode="actual_live")

    def test_honesty_invoke_loads_real_catalog_but_stays_honest_empty(self) -> None:
        """The empty-catalog gap is closed: real strategies load, but with no
        preregistration authority wired into this hop they legitimately
        abstain rather than mint a fabricated MATCHED row."""
        invoke = build_paper_demo_path_a_invoke("AAPL", mode="paper", as_of_time_ns=T)
        self.assertGreater(len(invoke.scan_request.strategies), 0)
        self.assertEqual(invoke.scan_request.scope.mode, "paper")
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "EMPTY")
        self.assertEqual(result.reason_codes, ("NO_MATCHED_STRATEGY",))
        self.assertEqual(result.matched_count, 0)
        self.assertEqual(result.opportunities, ())
        matches = invoke.caller.scanner.run(invoke.scan_request).matches
        self.assertTrue(matches)
        self.assertTrue(
            all(match.disposition == StrategyMatchDisposition.ABSTAINED for match in matches)
        )
        self.assertTrue(
            any("ABSTAIN_NO_PREREGISTRATION" in match.abstention_reasons for match in matches)
        )

    def test_honesty_invoke_catalog_is_real_not_a_lambda_fixture(self) -> None:
        from market_platform_foundation.strategy import path_a_strategy_catalog

        catalog = path_a_strategy_catalog.build_paper_demo_strategy_catalog()
        self.assertGreater(len(catalog), 0)
        source = inspect.getsource(path_a_strategy_catalog)
        self.assertNotIn("lambda", source)
        self.assertIn("interpret_strategy", source)

    def test_composer_invokes_path_a_without_injected_caller(self) -> None:
        available = ProviderResult(
            status="available",
            events=(_quote_event(),),
            provider_id="yahoo.finance.delayed",
            capability="US_EQUITY_SNAPSHOT",
        )
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(available),
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "EMPTY")
        self.assertEqual(result.path_a.reason_codes, ("NO_MATCHED_STRATEGY",))
        self.assertEqual(result.to_dict()["path_a_status"], "EMPTY")

    def test_composer_demo_invokes_path_a_honesty_empty(self) -> None:
        available = ProviderResult(
            status="available",
            events=(_quote_event(),),
            provider_id="yahoo.finance.delayed",
            capability="US_EQUITY_SNAPSHOT",
        )
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(available),
        ).run("AAPL", mode="demo", as_of_time_ns=T + 2_000_000)
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertEqual(result.mode, "demo")
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "EMPTY")

    def test_cli_paper_opend_down_is_unavailable_not_yahoo(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch("sys.stdout", stdout):
                code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        self.assertEqual(payload["discovery"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertNotEqual(payload["discovery"]["provider_id"], "yahoo.finance.delayed")
        self.assertEqual(payload["discovery"]["overlay_provider_id"], "yahoo.finance.delayed")
        self.assertFalse(payload["discovery"]["opend_reachable"])
        self.assertEqual(payload["discovery"]["reason_code"], OPEND_UNAVAILABLE)
        self.assertEqual(payload["result"]["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(payload["result"]["reason_codes"], [OPEND_UNAVAILABLE])
        self.assertEqual(payload["result"]["provenance"].get("provider"), MOOMOO_OPEND_PROVIDER_ID)
        self.assertIsNone(payload["result"]["path_a_status"])
        self.assertEqual(payload["opend_preflight"]["start_requested"], True)
        self.assertFalse(payload["opend_preflight"]["ready"])
        self.assertEqual(set(payload["opend_preflight"]), {"ready", "start_requested", "status"})
        self.assertNotIn("moomoo_OpenD.exe", dumped)
        self.assertNotIn("APPDATA", dumped)

    def test_cli_starts_opend_before_quote_fetch_and_fails_closed(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        order: list[object] = []

        def fake_diagnose(*, start: bool = False) -> dict[str, object]:
            order.append(("diagnose", start))
            return {"ready_for_live_observational": False, "status": "OPEN_D_NOT_INSTALLED"}

        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch("tools.path_a_prospective_run.diagnose_opend", side_effect=fake_diagnose):
                with patch("sys.stdout", stdout):
                    code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        self.assertEqual(order, [("diagnose", True)])
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        self.assertEqual(payload["opend_preflight"]["start_requested"], True)
        self.assertEqual(payload["opend_preflight"]["status"], "OPEN_D_NOT_INSTALLED")
        self.assertFalse(payload["opend_preflight"]["ready"])
        self.assertEqual(set(payload["opend_preflight"]), {"ready", "start_requested", "status"})
        self.assertNotIn("moomoo_OpenD.exe", dumped)
        self.assertNotIn("APPDATA", dumped)
        self.assertEqual(payload["discovery"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertNotEqual(payload["discovery"]["provider_id"], "yahoo.finance.delayed")
        self.assertEqual(payload["result"]["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(payload["result"]["reason_codes"], [OPEND_UNAVAILABLE])
        self.assertIsNone(payload["result"]["path_a_status"])

    def test_cli_diagnose_runs_before_discovery(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        order: list[str] = []

        def fake_diagnose(*, start: bool = False) -> dict[str, object]:
            del start
            order.append("diagnose")
            return {"ready_for_live_observational": False, "status": "OPEN_D_NOT_RUNNING"}

        def fake_discover():
            order.append("discover")
            return discover_equity_quote_stack()

        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch("tools.path_a_prospective_run.diagnose_opend", side_effect=fake_diagnose):
                with patch(
                    "tools.path_a_prospective_run.discover_equity_quote_stack",
                    side_effect=fake_discover,
                ):
                    with patch("sys.stdout", stdout):
                        code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        self.assertEqual(order, ["diagnose", "discover"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["result"]["reason_codes"], [OPEND_UNAVAILABLE])
        self.assertNotEqual(payload["result"]["provider_id"], "yahoo.finance.delayed")

    def test_cli_ignores_yahoo_injected_via_discovery(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        yahoo = ScriptedQuoteProvider(_delayed_available())
        discovery = EquityQuoteDiscovery(
            provider_id="yahoo.finance.delayed",
            classification="AVAILABLE_NOT_ACTIVE",
            timeliness="DELAYED",
            reason_code="YAHOO_DELAYED_OVERLAY",
            config_names_present=(),
            finviz_token_names_present=(),
            opend_reachable=False,
        )
        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch(
                "tools.path_a_prospective_run.diagnose_opend",
                return_value={"ready_for_live_observational": False, "status": "OPEN_D_NOT_RUNNING"},
            ):
                with patch(
                    "tools.path_a_prospective_run.discover_equity_quote_stack",
                    return_value=(yahoo, discovery),
                ):
                    with patch("sys.stdout", stdout):
                        code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["result"]["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(payload["result"]["reason_codes"], [OPEND_UNAVAILABLE])
        self.assertEqual(payload["result"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertNotEqual(payload["result"]["provider_id"], "yahoo.finance.delayed")

    def test_cli_paper_path_a_status_is_empty_not_null(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        available = ProviderResult(
            status="available",
            events=(_quote_event(),),
            provider_id="yahoo.finance.delayed",
            capability="US_EQUITY_SNAPSHOT",
        )
        discovery = EquityQuoteDiscovery(
            provider_id=MOOMOO_OPEND_PROVIDER_ID,
            classification="UNAVAILABLE",
            timeliness="REAL_TIME",
            reason_code=OPEND_UNAVAILABLE,
            config_names_present=(),
            finviz_token_names_present=(),
            opend_reachable=False,
        )
        stdout = StringIO()
        with patch(
            "market_platform_foundation.strategy.path_a_prospective.monotonic_wall_ns",
            return_value=T + 2_000_000,
        ):
            with patch(
                "tools.path_a_prospective_run.diagnose_opend",
                return_value={"ready_for_live_observational": False, "status": "OPEN_D_NOT_RUNNING"},
            ):
                with patch(
                    "tools.path_a_prospective_run.primary_equity_quote_provider",
                    return_value=ScriptedQuoteProvider(available),
                ):
                    with patch(
                        "tools.path_a_prospective_run.discover_equity_quote_stack",
                        return_value=(MoomooOpenDEquityQuoteProvider(), discovery),
                    ):
                        with patch("sys.stdout", stdout):
                            code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["result"]["path_a_status"], "EMPTY")
        self.assertEqual(payload["result"]["status"], "G7_NOT_ACTIONABLE")
        self.assertEqual(payload["result"]["mode"], "paper")
        self.assertIsNotNone(payload["result"]["path_a_status"])

    def test_cli_live_mode_is_refused(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit):
                path_a_cli_main(["--mode", "live"])

    def test_matched_loop_source_calls_bridge_and_engine(self) -> None:
        source = inspect.getsource(PathAScanCaller.run)
        self.assertIn("bridge_strategy_match_to_opportunity", source)
        self.assertIn("engine=self.engine", source)
        self.assertIn("NO_MATCHED_STRATEGY", source)

    def test_matched_paper_fixture_invokes_opportunity_engine_g7_fail_close(self) -> None:
        result, engine = _run_matched_fixture_hop(mode="paper")
        self.assertGreaterEqual(engine.assess_calls, 1)
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "MINTED")
        self.assertEqual(len(result.path_a.assessments), engine.assess_calls)
        self.assertEqual(len(result.path_a.opportunities), 1)
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertFalse(result.freshness.get("actionable"))
        self.assertEqual(result.freshness.get("reason_code"), "DELAYED_WHEN_REALTIME_REQUIRED")
        self.assertEqual(result.persist_status, PERSIST_NOT_MINTED)
        self.assertNotEqual(result.path_a.status, "EMPTY")
        self.assertNotIn("NO_MATCHED_STRATEGY", result.path_a.reason_codes)

    def test_matched_demo_fixture_invokes_opportunity_engine_g7_fail_close(self) -> None:
        result, engine = _run_matched_fixture_hop(mode="demo")
        self.assertGreaterEqual(engine.assess_calls, 1)
        self.assertEqual(result.mode, "demo")
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "MINTED")
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertEqual(result.persist_status, PERSIST_NOT_MINTED)

    def test_honesty_empty_does_not_invoke_opportunity_engine(self) -> None:
        with patch(
            "market_platform_foundation.strategy.path_a_scan_caller.bridge_strategy_match_to_opportunity"
        ) as bridged:
            result = PathAProspectiveComposer(
                quote_provider=ScriptedQuoteProvider(_delayed_available()),
            ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertEqual(result.status, "G7_NOT_ACTIONABLE")
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "EMPTY")
        self.assertEqual(result.path_a.reason_codes, ("NO_MATCHED_STRATEGY",))
        self.assertEqual(result.path_a.matched_count, 0)
        bridged.assert_not_called()

    def test_matched_fixture_live_does_not_invoke_engine(self) -> None:
        repository, champion, forecast = _seed_repository()
        engine = RecordingOpportunityEngine()
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(_delayed_available()),
            path_a_caller=_caller(repository, champion, forecast, engine=engine),
        ).run(
            "AAPL",
            mode="live",
            scan_request=_scan_request(disposition=StrategyMatchDisposition.MATCHED),
            as_of_time_ns=T,
        )
        self.assertEqual(result.status, "LIVE_FORBIDDEN")
        self.assertEqual(engine.assess_calls, 0)
        self.assertIsNone(result.path_a)


class PathAProspectivePersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_persist = os.environ.get("IMP_PERSIST_STATE")
        self._saved_dir = os.environ.get("IMP_STATE_DIR")
        self._saved_campaigns = os.environ.get("IMP_FORWARD_TEST_CAMPAIGNS_DIR")
        self._saved_force = os.environ.get("IMP_FORWARD_TEST_EVAL_FORCE")
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        reset_local_state_for_tests()
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        if self._saved_persist is not None:
            os.environ["IMP_PERSIST_STATE"] = self._saved_persist
        if self._saved_dir is not None:
            os.environ["IMP_STATE_DIR"] = self._saved_dir
        if self._saved_campaigns is not None:
            os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = self._saved_campaigns
        if self._saved_force is not None:
            os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = self._saved_force
        self._tmp.cleanup()

    def _enable_persist(self) -> Path:
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(campaigns_root, universe_symbols=("AAPL", "MSFT"))
        return campaigns_root

    def _composer(self, *, persist=None):
        repository, champion, forecast = _seed_repository()
        return PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(
                _realtime_quote(), provider_id="test.realtime"
            ),
            composition=ObservationalRuntimeComposition(),
            path_a_caller=_caller(repository, champion, forecast),
            persist=persist,
        )

    def test_persist_off_minted_decision_is_intentional_ephemeral(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge import (
            ForwardTestService,
            create_forward_test_repository,
        )
        from market_platform_foundation.local_state.startup import (
            open_local_state,
            reset_local_state_for_tests,
        )

        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        service = ForwardTestService(create_forward_test_repository(connection=None))
        result = self._composer(
            persist=PathAPersistContext(
                service=service,
                account_id="paper-a",
                session_id="sess-ephemeral",
                strategy_id=BASELINE_POLICY,
                strategy_version=POLICY_VERSION,
            )
        ).run(
            "AAPL",
            mode="paper",
            scan_request=_scan_request(disposition=StrategyMatchDisposition.MATCHED),
            as_of_time_ns=T + 2_000_000,
        )
        self.assertEqual(result.status, "MINTED")
        self.assertEqual(result.persist_status, PERSIST_INTENTIONAL_EPHEMERAL)
        self.assertIsNone(result.forward_test_id)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        reset_local_state_for_tests()
        local = open_local_state(force=True)
        assert local is not None
        count = local.connection.execute(
            "SELECT COUNT(*) FROM forward_test_decisions"
        ).fetchone()
        self.assertEqual(int(count[0]), 0)
        links = local.connection.execute(
            "SELECT COUNT(*) FROM forward_test_signal_links"
        ).fetchone()
        self.assertEqual(int(links[0]), 0)

    def test_persist_on_minted_decision_reconstructs_after_restart(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge import (
            ForwardTestService,
            create_forward_test_repository,
        )
        from market_platform_foundation.intelligence.paper_forward_bridge.reconstruction import (
            reconstruct_campaign,
        )
        from market_platform_foundation.local_state.startup import (
            open_local_state,
            reset_local_state_for_tests,
        )

        campaigns_root = self._enable_persist()
        reset_local_state_for_tests()
        local = open_local_state(force=True)
        assert local is not None
        service = ForwardTestService(
            create_forward_test_repository(connection=local.connection)
        )
        session = create_activated_session(
            service,
            campaigns_root,
            universe=("AAPL", "MSFT"),
            evaluation_horizon_ns=3_600_000_000_000,
            created_at_ns=T,
        )
        result = self._composer(
            persist=PathAPersistContext(
                service=service,
                account_id="paper-a",
                session_id=session.session_id,
                strategy_id=BASELINE_POLICY,
                strategy_version=POLICY_VERSION,
            )
        ).run(
            "AAPL",
            mode="paper",
            scan_request=_scan_request(disposition=StrategyMatchDisposition.MATCHED),
            as_of_time_ns=T + 2_000_000,
        )
        self.assertEqual(result.status, "MINTED")
        self.assertEqual(result.persist_status, PERSIST_WRITTEN)
        self.assertIsNotNone(result.forward_test_id)
        opportunity_id = result.path_a.opportunities[0].opportunity_id
        self.assertIn("freshness", result.freshness_payload)
        reset_local_state_for_tests()
        reopened = open_local_state(force=True)
        assert reopened is not None
        reconstructed = reconstruct_campaign(
            reopened.connection,
            account_id="paper-a",
            campaign_id=CAMPAIGN_SLUG,
        )
        self.assertEqual(len(reconstructed["decisions"]), 1)
        row = reconstructed["decisions"][0]
        self.assertEqual(row["opportunity_id"], opportunity_id)
        self.assertEqual(row["symbol"], "AAPL")
        self.assertIsNotNone(row["freshness"])
        self.assertEqual(row["freshness"]["status"], "FRESH")
        self.assertIsNotNone(row["signal_link"])
        other_account = reconstruct_campaign(
            reopened.connection,
            account_id="paper-b",
            campaign_id=CAMPAIGN_SLUG,
        )
        self.assertEqual(other_account["decisions"], [])
        msft = create_forward_test_repository(connection=reopened.connection).list_decisions(
            account_id="paper-a",
            symbol="MSFT",
        )
        self.assertEqual(msft, [])

    def test_live_mode_does_not_persist(self) -> None:
        result = PathAProspectiveComposer(
            quote_provider=ScriptedQuoteProvider(_realtime_quote(), provider_id="test.realtime"),
        ).run("AAPL", mode="live", as_of_time_ns=T)
        self.assertEqual(result.status, "LIVE_FORBIDDEN")
        self.assertEqual(result.persist_status, PERSIST_NOT_MINTED)
        self.assertIsNone(result.forward_test_id)


class PathACliPersistTests(unittest.TestCase):
    """Production CLI (tools/path_a_prospective_run.py) can inject
    PathAPersistContext for Paper/Demo, closing the reachability gap left
    after PR #42's PathAProspectiveComposer-level persist hop."""

    def setUp(self) -> None:
        self._saved_persist = os.environ.get("IMP_PERSIST_STATE")
        self._saved_dir = os.environ.get("IMP_STATE_DIR")
        self._saved_campaigns = os.environ.get("IMP_FORWARD_TEST_CAMPAIGNS_DIR")
        self._saved_force = os.environ.get("IMP_FORWARD_TEST_EVAL_FORCE")
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        reset_local_state_for_tests()
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        if self._saved_persist is not None:
            os.environ["IMP_PERSIST_STATE"] = self._saved_persist
        if self._saved_dir is not None:
            os.environ["IMP_STATE_DIR"] = self._saved_dir
        if self._saved_campaigns is not None:
            os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = self._saved_campaigns
        if self._saved_force is not None:
            os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = self._saved_force
        self._tmp.cleanup()

    @staticmethod
    def _realtime_discovery_and_provider() -> tuple[ScriptedQuoteProvider, EquityQuoteDiscovery]:
        discovery = EquityQuoteDiscovery(
            provider_id="test.realtime",
            classification="AVAILABLE_NOT_ACTIVE",
            timeliness="REAL_TIME",
            reason_code="TEST_REALTIME_FIXTURE",
            config_names_present=(),
            finviz_token_names_present=(),
            opend_reachable=False,
        )
        provider = ScriptedQuoteProvider(_realtime_quote(), provider_id="test.realtime")
        return provider, discovery

    @staticmethod
    def _delayed_discovery_and_provider() -> tuple[ScriptedQuoteProvider, EquityQuoteDiscovery]:
        discovery = EquityQuoteDiscovery(
            provider_id="yahoo.finance.delayed",
            classification="AVAILABLE_NOT_ACTIVE",
            timeliness="DELAYED",
            reason_code="YAHOO_DELAYED_OVERLAY",
            config_names_present=(),
            finviz_token_names_present=(),
            opend_reachable=False,
        )
        return ScriptedQuoteProvider(_delayed_available()), discovery

    def _activated_session(self, *, universe: tuple[str, ...] = ("AAPL", "MSFT")):
        from market_platform_foundation.intelligence.paper_forward_bridge import (
            ForwardTestService,
            create_forward_test_repository,
        )
        from market_platform_foundation.local_state.startup import (
            open_local_state,
            reset_local_state_for_tests,
        )

        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(campaigns_root, universe_symbols=universe)
        reset_local_state_for_tests()
        local = open_local_state(force=True)
        assert local is not None
        setup_service = ForwardTestService(create_forward_test_repository(connection=local.connection))
        session = create_activated_session(
            setup_service,
            campaigns_root,
            universe=universe,
            evaluation_horizon_ns=3_600_000_000_000,
            created_at_ns=T,
        )
        reset_local_state_for_tests()
        return session

    def _run_cli(self, argv: list[str], *, provider, discovery, invoke) -> tuple[int, dict]:
        from tools.path_a_prospective_run import main as path_a_cli_main

        stdout = StringIO()
        with patch(
            "market_platform_foundation.strategy.path_a_prospective.monotonic_wall_ns",
            return_value=T + 2_000_000,
        ):
            with patch(
                "tools.path_a_prospective_run.diagnose_opend",
                return_value={"ready_for_live_observational": False, "status": "OPEN_D_NOT_RUNNING"},
            ):
                with patch(
                    "tools.path_a_prospective_run.primary_equity_quote_provider",
                    return_value=provider,
                ):
                    with patch(
                        "tools.path_a_prospective_run.discover_equity_quote_stack",
                        return_value=(MoomooOpenDEquityQuoteProvider(), discovery),
                    ):
                        with patch(
                            "market_platform_foundation.strategy.path_a_prospective.build_paper_demo_path_a_invoke",
                            return_value=invoke,
                        ):
                            with patch("sys.stdout", stdout):
                                code = path_a_cli_main(argv)
        return code, json.loads(stdout.getvalue())

    def test_persist_context_requires_all_four_identifiers(self) -> None:
        from tools.path_a_prospective_run import build_cli_persist_context

        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        complete = dict(
            mode="paper",
            persist_account_id="paper-a",
            persist_session_id="sess-1",
            persist_strategy_id=BASELINE_POLICY,
            persist_strategy_version=POLICY_VERSION,
        )
        for missing in (
            "persist_account_id",
            "persist_session_id",
            "persist_strategy_id",
            "persist_strategy_version",
        ):
            partial = dict(complete)
            partial[missing] = None
            self.assertIsNone(build_cli_persist_context(SimpleNamespace(**partial)))
        live_args = dict(complete)
        live_args["mode"] = "live"
        self.assertIsNone(build_cli_persist_context(SimpleNamespace(**live_args)))

    def test_persist_context_none_when_persistence_switch_off(self) -> None:
        from tools.path_a_prospective_run import build_cli_persist_context

        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        args = SimpleNamespace(
            mode="paper",
            persist_account_id="paper-a",
            persist_session_id="sess-1",
            persist_strategy_id=BASELINE_POLICY,
            persist_strategy_version=POLICY_VERSION,
        )
        self.assertIsNone(build_cli_persist_context(args))

    def test_cli_persist_off_minted_is_intentional_ephemeral_no_create_decision(self) -> None:
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        provider, discovery = self._realtime_discovery_and_provider()
        code, payload = self._run_cli(
            ["--symbol", "AAPL", "--mode", "paper"],
            provider=provider,
            discovery=discovery,
            invoke=_matched_fixture_invoke(mode="paper"),
        )
        self.assertEqual(code, 0)
        result = payload["result"]
        self.assertFalse(payload["persist_context_injected"])
        self.assertEqual(result["path_a_status"], "MINTED")
        self.assertEqual(result["persist_status"], PERSIST_INTENTIONAL_EPHEMERAL)
        self.assertIsNone(result["forward_test_id"])

    def test_cli_persist_on_without_session_args_is_skipped_no_session(self) -> None:
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        provider, discovery = self._realtime_discovery_and_provider()
        code, payload = self._run_cli(
            ["--symbol", "AAPL", "--mode", "paper"],
            provider=provider,
            discovery=discovery,
            invoke=_matched_fixture_invoke(mode="paper"),
        )
        self.assertEqual(code, 0)
        result = payload["result"]
        self.assertFalse(payload["persist_context_injected"])
        self.assertEqual(result["path_a_status"], "MINTED")
        self.assertEqual(result["persist_status"], PERSIST_SKIPPED_NO_SESSION)
        self.assertIsNone(result["forward_test_id"])

    def test_cli_persist_on_paper_with_injected_context_exercises_create_decision(self) -> None:
        from market_platform_foundation.local_state.startup import open_local_state

        session = self._activated_session()
        provider, discovery = self._realtime_discovery_and_provider()
        code, payload = self._run_cli(
            [
                "--symbol",
                "AAPL",
                "--mode",
                "paper",
                "--persist-account-id",
                "paper-a",
                "--persist-session-id",
                session.session_id,
                "--persist-strategy-id",
                BASELINE_POLICY,
                "--persist-strategy-version",
                POLICY_VERSION,
            ],
            provider=provider,
            discovery=discovery,
            invoke=_matched_fixture_invoke(mode="paper"),
        )
        self.assertEqual(code, 0)
        result = payload["result"]
        self.assertTrue(payload["persist_context_injected"])
        self.assertEqual(result["path_a_status"], "MINTED")
        self.assertEqual(result["persist_status"], PERSIST_WRITTEN)
        self.assertIsNotNone(result["forward_test_id"])
        reopened = open_local_state(force=True)
        assert reopened is not None
        count = reopened.connection.execute(
            "SELECT COUNT(*) FROM forward_test_decisions"
        ).fetchone()
        self.assertEqual(int(count[0]), 1)

    def test_cli_persist_on_demo_with_injected_context_stays_intentional_ephemeral(self) -> None:
        from market_platform_foundation.local_state.startup import open_local_state

        session = self._activated_session()
        provider, discovery = self._realtime_discovery_and_provider()
        code, payload = self._run_cli(
            [
                "--symbol",
                "AAPL",
                "--mode",
                "demo",
                "--persist-account-id",
                "paper-a",
                "--persist-session-id",
                session.session_id,
                "--persist-strategy-id",
                BASELINE_POLICY,
                "--persist-strategy-version",
                POLICY_VERSION,
            ],
            provider=provider,
            discovery=discovery,
            invoke=_matched_fixture_invoke(mode="demo"),
        )
        self.assertEqual(code, 0)
        result = payload["result"]
        self.assertTrue(payload["persist_context_injected"])
        self.assertEqual(result["mode"], "demo")
        self.assertEqual(result["path_a_status"], "MINTED")
        self.assertEqual(result["persist_status"], PERSIST_INTENTIONAL_EPHEMERAL)
        self.assertIsNone(result["forward_test_id"])
        reopened = open_local_state(force=True)
        assert reopened is not None
        count = reopened.connection.execute(
            "SELECT COUNT(*) FROM forward_test_decisions"
        ).fetchone()
        self.assertEqual(int(count[0]), 0)

    def test_cli_g7_fail_close_binds_even_with_persist_context_injected(self) -> None:
        session = self._activated_session()
        provider, discovery = self._delayed_discovery_and_provider()
        code, payload = self._run_cli(
            [
                "--symbol",
                "AAPL",
                "--mode",
                "paper",
                "--persist-account-id",
                "paper-a",
                "--persist-session-id",
                session.session_id,
                "--persist-strategy-id",
                BASELINE_POLICY,
                "--persist-strategy-version",
                POLICY_VERSION,
            ],
            provider=provider,
            discovery=discovery,
            invoke=_matched_fixture_invoke(mode="paper"),
        )
        self.assertEqual(code, 0)
        result = payload["result"]
        self.assertTrue(payload["persist_context_injected"])
        self.assertEqual(result["status"], "G7_NOT_ACTIONABLE")
        self.assertEqual(result["path_a_status"], "MINTED")
        self.assertEqual(result["persist_status"], PERSIST_NOT_MINTED)
        self.assertIsNone(result["forward_test_id"])

    def test_cli_live_mode_refused_even_with_persist_args(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit):
                path_a_cli_main(
                    [
                        "--mode",
                        "live",
                        "--persist-account-id",
                        "paper-a",
                        "--persist-session-id",
                        "sess-1",
                        "--persist-strategy-id",
                        BASELINE_POLICY,
                        "--persist-strategy-version",
                        POLICY_VERSION,
                    ]
                )


class PathACliFinvizOverlayTests(unittest.TestCase):
    """Finviz Elite overlay on OpenD Path A hop CLI. Never L1. Token-absent fail-closed."""

    def test_cli_source_joins_overlay_without_replacing_opend(self) -> None:
        from tools import path_a_prospective_run

        source = inspect.getsource(path_a_prospective_run.main)
        helper = inspect.getsource(path_a_prospective_run._finviz_hop_overlay)
        self.assertIn("_finviz_hop_overlay", source)
        self.assertIn("equity_context", source)
        self.assertIn("primary_equity_quote_provider", source)
        self.assertIn("with_finviz_elite_observational_context", source)
        self.assertIn("discover_finviz_context_stack", helper)
        self.assertIn("overlay_payload", helper)
        self.assertNotIn("fetch_quote", helper)
        self.assertNotIn("yahoo.finance.delayed", helper)

    def test_cli_opend_down_emits_not_configured_overlay_classifier(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        stdout = StringIO()
        with tempfile.TemporaryDirectory() as secret_dir:
            isolated = {
                "IMP_MOOMOO_HOST": "127.0.0.1",
                "IMP_MOOMOO_PORT": "1",
                "IMP_FINVIZ_SECRET_DIR": secret_dir,
                "IMP_FINVIZ_LIVE": "",
                "FINVIZ_API_KEY": "",
                "FINVIZ_AUTH_TOKEN": "",
                "FINVIZ_API_TOKEN": "",
                "FINVIZ_ELITE_TOKEN": "",
                "IMP_FINVIZ_ELITE_TOKEN": "",
                "IMP_FINVIZ_TOKEN": "",
                "FINVIZ_USERNAME": "",
                "FINVIZ_PASSWORD": "",
            }
            with patch.dict(os.environ, isolated, clear=False):
                with patch("sys.stdout", stdout):
                    code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        overlay = payload["equity_context"]
        discovery = overlay["discovery"]
        result = overlay["result"]
        self.assertEqual(payload["discovery"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(payload["result"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertNotEqual(payload["discovery"]["provider_id"], "yahoo.finance.delayed")
        self.assertEqual(payload["discovery"]["overlay_provider_id"], "yahoo.finance.delayed")
        self.assertEqual(payload["result"]["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(payload["result"]["reason_codes"], [OPEND_UNAVAILABLE])
        self.assertEqual(discovery["provider_id"], "finviz.elite.context")
        self.assertEqual(discovery["classification"], "NOT_CONFIGURED")
        self.assertEqual(discovery["reason_code"], "NOT_CONFIGURED")
        self.assertEqual(discovery["timeliness"], "DELAYED")
        self.assertNotEqual(discovery["timeliness"], "REAL_TIME")
        self.assertFalse(discovery["is_l1"])
        self.assertFalse(discovery["is_paper_comparator"])
        self.assertFalse(discovery["overlay_token_present"])
        self.assertFalse(discovery["live_enabled"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason_code"], "NOT_CONFIGURED")
        self.assertFalse(result["is_l1"])
        self.assertFalse(result["is_paper_comparator"])
        self.assertEqual(result["provider_id"], "finviz.elite.context")
        self.assertNotIn("yahoo.finance.delayed", json.dumps(overlay))
        self.assertNotIn("password", dumped.casefold())
        self.assertNotIn("EMPIRICAL_ACTIVE", dumped)

    def test_cli_fetched_overlay_stays_live_disabled_and_not_l1(self) -> None:
        from market_platform_foundation.providers.adapters.finviz_elite_context import (
            overlay_payload,
        )
        from market_platform_foundation.providers.finviz_context_discovery import (
            discover_finviz_context_stack,
        )
        from tools.path_a_prospective_run import main as path_a_cli_main

        env = {
            "FINVIZ_API_KEY": "",
            "FINVIZ_AUTH_TOKEN": "",
            "FINVIZ_API_TOKEN": "",
            "FINVIZ_ELITE_TOKEN": "",
            "IMP_FINVIZ_ELITE_TOKEN": "",
            "IMP_FINVIZ_TOKEN": "",
            "FINVIZ_USERNAME": "operator@example.com",
            "FINVIZ_PASSWORD": "not-a-real-password",
            "IMP_FINVIZ_LIVE": "",
        }
        adapter, discovery = discover_finviz_context_stack(
            env=env,
            token_fetcher=lambda: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        )
        overlay = overlay_payload(
            discovery=discovery.to_dict(),
            result=adapter.fetch_context("AAPL"),
        )
        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch(
                "tools.path_a_prospective_run._finviz_hop_overlay",
                return_value=(adapter, overlay),
            ):
                with patch("sys.stdout", stdout):
                    code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        hop_overlay = payload["equity_context"]
        self.assertEqual(payload["discovery"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(payload["result"]["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(payload["result"]["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(hop_overlay["discovery"]["provider_id"], "finviz.elite.context")
        self.assertEqual(hop_overlay["discovery"]["auto_fetch_status"], "FETCHED")
        self.assertEqual(hop_overlay["discovery"]["classification"], "CONFIGURED_BLOCKED")
        self.assertEqual(hop_overlay["discovery"]["reason_code"], "LIVE_DISABLED")
        self.assertTrue(hop_overlay["discovery"]["overlay_token_present"])
        self.assertFalse(hop_overlay["discovery"]["is_l1"])
        self.assertFalse(hop_overlay["result"]["is_l1"])
        self.assertEqual(hop_overlay["result"]["reason_code"], "LIVE_DISABLED")
        self.assertNotIn("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", dumped)
        self.assertNotIn("not-a-real-password", dumped)
        self.assertNotIn("EMPIRICAL_ACTIVE", dumped)


if __name__ == "__main__":
    unittest.main()
