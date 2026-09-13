"""One-shot Path A prospective hop: mocked providers, no Live, no secrets."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

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
    PERSIST_INTENTIONAL_EPHEMERAL,
    PERSIST_NOT_MINTED,
    PERSIST_WRITTEN,
    PathAPersistContext,
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

ROOT = Path(__file__).resolve().parents[2]
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


if __name__ == "__main__":
    unittest.main()
