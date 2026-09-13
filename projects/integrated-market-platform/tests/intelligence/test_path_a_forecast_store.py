"""Paper/Demo PRODUCTION ForecastV1 persist+load for the Path A hop.

The hop only loads a previously persisted ForecastV1. Missing, CONTROL,
RESEARCH, and uncalibrated artifacts are FORECAST_UNAVAILABLE. Catalog
evaluators never call build_preregistration. Live stays LIVE_FORBIDDEN.
A software-constructed ForecastV1 used here is not empirical and is not
item 7 PROVED.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.intelligence.contracts import (
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.contracts.strategy_match import StrategyMatchDisposition
from market_platform_foundation.intelligence.fusion.types import CONTROL_FORECAST_STAGE
from market_platform_foundation.research.forecast import build_forecast
from market_platform_foundation.strategy.evaluation import default_forecast_momentum_spec
from market_platform_foundation.strategy.path_a_forecast_store import (
    load_paper_demo_forecasts,
    persist_paper_demo_forecast,
    select_eligible_forecast,
)
from market_platform_foundation.strategy.path_a_preregistration_store import (
    persist_paper_demo_preregistration,
)
from market_platform_foundation.strategy.path_a_prospective import (
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCallerError
from market_platform_foundation.strategy.path_a_strategy_catalog import (
    NO_QUOTE_OBSERVATION_REASON,
)

T = 1_700_000_000_000_000_000
HORIZON = 300_000_000_000
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"
HONESTY_SCOPE = IntelligenceScope(
    instrument_ids=("canonical:EQUITY:XNYS:AAPL",),
    context_id="acct-paper:paper:snapshot-path-a-honesty-aapl",
)
QUALITY = QualitySummary(state=QualityState.GOOD)


def _quote_event(*, last_price: float = 190.1, event_time_ns: int = T) -> dict:
    return {
        "raw_payload": {"last_price": last_price},
        "clocks": {"event_time_ns": event_time_ns},
    }


def _software_forecast(
    *,
    forecast_id: str = "forecast-path-a-honesty-software-1",
    contributor_role: str = "PRODUCTION",
    forecast_stage: str = "FINAL_FUSED_CALIBRATED",
    calibration_status: str | None = "CALIBRATED",
    calibrated_probability: float | None = 0.62,
    probability: float | None = 0.62,
    champion_candidate_id: str = "candidate-path-a-honesty",
    candidate_artifact_hash: str = "artifact-path-a-honesty",
    account_id: str | None = "acct-paper",
    mode: str | None = "paper",
    horizon_ns: int = HORIZON,
    decision_time_ns: int = T,
    scope: IntelligenceScope | None = None,
) -> ForecastV1:
    metadata = {
        "forecast_stage": forecast_stage,
        "contributor_role": contributor_role,
        "champion_candidate_id": champion_candidate_id,
        "candidate_artifact_hash": candidate_artifact_hash,
    }
    if calibration_status is not None:
        metadata["calibration_status"] = calibration_status
    if account_id is not None:
        metadata["account_id"] = account_id
    if mode is not None:
        metadata["mode"] = mode
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version="1",
        scope=scope or HONESTY_SCOPE,
        decision_time_ns=decision_time_ns,
        snapshot_id="snapshot-path-a-honesty-aapl",
        target=ForecastTarget(target_kind="direction", instrument_id="AAPL", parameters={}),
        horizon=TimeHorizonNs(duration_ns=horizon_ns),
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
            calibrated_probability=calibrated_probability,
        ),
        quality=QUALITY,
        resolve_time_ns=decision_time_ns + horizon_ns,
        metadata=metadata,
    )


class PathAForecastStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_persist_serializes_forecast_v1_and_does_not_mint_probability(self) -> None:
        forecast = _software_forecast()
        payload = persist_paper_demo_forecast(forecast, destination=self.store)
        self.assertEqual(payload["forecast_id"], forecast.forecast_id)
        loaded = load_paper_demo_forecasts(self.store)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].forecast_id, forecast.forecast_id)
        source = inspect.getsource(persist_paper_demo_forecast)
        self.assertNotIn("build_forecast_v1", source)
        self.assertNotIn("probability=0.8", source)
        self.assertIn("FORECAST_V1_REQUIRED", source)

    def test_missing_or_corrupt_store_is_empty(self) -> None:
        self.assertEqual(load_paper_demo_forecasts(self.store / "missing.json"), ())
        bad = self.store / "bad.json"
        bad.write_text("{not-json", encoding="utf-8")
        self.assertEqual(load_paper_demo_forecasts(bad), ())

    def test_research_forecast_dict_is_not_loaded_as_forecast_v1(self) -> None:
        research = build_forecast(
            score="190.1",
            prediction_cutoff=T,
            horizon_ns=HORIZON,
        )
        write_canonical_json(self.store / "research.json", research)
        self.assertEqual(load_paper_demo_forecasts(self.store), ())

    def test_store_module_never_imports_control_or_research_producers(self) -> None:
        from market_platform_foundation.strategy import path_a_forecast_store

        source = inspect.getsource(path_a_forecast_store)
        self.assertNotIn("from ..intelligence.baselines", source)
        self.assertNotIn("from ..research.forecast import", source)
        self.assertNotIn("build_forecast_v1(", source)
        self.assertNotIn("probability=0.8", source)


class PathAForecastLoadHopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)
        self.prereg = self.store / "prereg"
        self.forecasts = self.store / "forecasts"
        self.prereg.mkdir()
        self.forecasts.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _matched_invoke(self, **kwargs):
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.prereg,
        )
        return build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            quote_event=_quote_event(),
            preregistration_path=self.prereg,
            **kwargs,
        )

    def test_catalog_evaluators_never_call_build_preregistration(self) -> None:
        from market_platform_foundation.strategy import path_a_strategy_catalog

        source = inspect.getsource(path_a_strategy_catalog)
        self.assertNotIn("build_preregistration(", source)
        self.assertNotIn("from .preregistration import", source)
        self.assertIn("preregistration=None", source)

    def test_missing_forecast_is_forecast_unavailable(self) -> None:
        invoke = self._matched_invoke()
        scan = invoke.caller.scanner.run(invoke.scan_request)
        matched = [
            row for row in scan.matches if row.disposition == StrategyMatchDisposition.MATCHED
        ]
        self.assertEqual(len(matched), 1)
        self.assertIsNone(invoke.caller.forecast_resolver(matched[0]))
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("FORECAST_RESOLUTION_FAILED",))
        self.assertEqual(result.opportunities, ())
        self.assertEqual(result.assessments, ())

    def test_control_forecast_is_rejected(self) -> None:
        persist_paper_demo_forecast(
            _software_forecast(
                forecast_id="forecast-control-rejected",
                contributor_role="CONTROL",
                forecast_stage=CONTROL_FORECAST_STAGE,
                calibration_status="UNCALIBRATED",
                calibrated_probability=None,
            ),
            destination=self.forecasts,
        )
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("FORECAST_RESOLUTION_FAILED",))
        self.assertEqual(result.opportunities, ())
        self.assertNotEqual(result.status, "SUPPRESSED")

    def test_uncalibrated_production_stage_is_rejected(self) -> None:
        persist_paper_demo_forecast(
            _software_forecast(
                forecast_id="forecast-uncalibrated-rejected",
                calibration_status="UNCALIBRATED",
                calibrated_probability=None,
            ),
            destination=self.forecasts,
        )
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.opportunities, ())

    def test_research_role_is_rejected(self) -> None:
        persist_paper_demo_forecast(
            _software_forecast(
                forecast_id="forecast-research-rejected",
                contributor_role="RESEARCH",
                forecast_stage="RESEARCH_ONLY",
            ),
            destination=self.forecasts,
        )
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.opportunities, ())

    def test_research_build_forecast_dict_is_rejected(self) -> None:
        write_canonical_json(
            self.forecasts / "research.json",
            build_forecast(score="190.1", prediction_cutoff=T, horizon_ns=HORIZON),
        )
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.opportunities, ())

    def test_champion_mismatch_is_rejected(self) -> None:
        persist_paper_demo_forecast(
            _software_forecast(
                forecast_id="forecast-champion-mismatch",
                champion_candidate_id="candidate-other",
                candidate_artifact_hash="artifact-other",
            ),
            destination=self.forecasts,
        )
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")

    def test_eligible_software_forecast_loads_and_is_not_empirical(self) -> None:
        """Load of a software-constructed PRODUCTION artifact is not item 7.

        Fixture MATCHED / loaded ForecastV1 tests stay software-only.
        """

        forecast = _software_forecast()
        persist_paper_demo_forecast(forecast, destination=self.forecasts)
        invoke = self._matched_invoke(forecast_path=self.forecasts)
        scan = invoke.caller.scanner.run(invoke.scan_request)
        matched = [
            row for row in scan.matches if row.disposition == StrategyMatchDisposition.MATCHED
        ]
        self.assertEqual(len(matched), 1)
        loaded = invoke.caller.forecast_resolver(matched[0])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.forecast_id, forecast.forecast_id)
        selected = select_eligible_forecast(
            matched[0],
            (forecast,),
            request=invoke.scan_request,
            champion=invoke.caller.champion_at_forecast,
            policy=invoke.caller.opportunity_policy,
        )
        self.assertEqual(selected.forecast_id, forecast.forecast_id)
        self.assertNotEqual(loaded.metadata.get("contributor_role"), "CONTROL")

    def test_live_still_forbidden_with_forecast_store(self) -> None:
        persist_paper_demo_forecast(_software_forecast(), destination=self.forecasts)
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke(
                "AAPL",
                mode="live",
                as_of_time_ns=T,
                quote_event=_quote_event(),
                forecast_path=self.forecasts,
            )

    def test_composer_threads_fetched_quote_into_scan_context(self) -> None:
        from market_platform_foundation.providers.contracts import ProviderResult

        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.prereg,
        )
        event = {
            "capability": "US_EQUITY_L1",
            "clocks": {
                "event_time_ns": T,
                "provider_time_ns": T,
                "received_time_ns": T + 1_000_000,
            },
            "instrument_id": "AAPL",
            "provider": "test.realtime",
            "provider_symbol": "AAPL",
            "raw_payload": {
                "ask_price": 190.2,
                "ask_vol": 200,
                "bid_price": 190.0,
                "bid_vol": 100,
                "last_price": 190.1,
            },
            "sequence": 7,
            "timeliness": "REAL_TIME",
            "normalization_version": "test/1.0.0",
        }
        fetched = ProviderResult(
            status="available",
            events=(event,),
            provider_id="test.realtime",
            capability="US_EQUITY_SNAPSHOT",
        )

        class _Scripted:
            capability = "US_EQUITY_SNAPSHOT"
            provider_id = "test.realtime"

            def fetch_quote(self, symbol: str) -> ProviderResult:
                del symbol
                return fetched

        result = PathAProspectiveComposer(
            quote_provider=_Scripted(),
            preregistration_path=self.prereg,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(result.path_a)
        self.assertTrue(result.path_a.scan.matches)
        quote = result.path_a.scan.matches[0].context.get("quote")
        self.assertIsNotNone(quote)
        self.assertEqual(quote.get("last_price"), 190.1)
        self.assertNotIn(
            NO_QUOTE_OBSERVATION_REASON,
            result.path_a.scan.matches[0].abstention_reasons,
        )
        self.assertEqual(result.path_a.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.path_a.matched_count, 1)

    def test_prospective_and_cli_never_mint_probability(self) -> None:
        from market_platform_foundation.strategy import path_a_prospective
        from tools import path_a_prospective_run

        prospective = inspect.getsource(path_a_prospective)
        cli = inspect.getsource(path_a_prospective_run.main)
        self.assertNotIn("build_forecast_v1", prospective)
        self.assertNotIn("baselines.forecast", prospective)
        self.assertNotIn("probability=0.8", prospective)
        self.assertIn("forecast_path", prospective)
        self.assertIn("--forecast-path", cli)
        self.assertNotIn("--probability", cli)
        self.assertNotIn("ForecastV1", cli)
        self.assertNotIn("build_paper_demo_path_a_invoke", cli)
        self.assertIn("primary_equity_quote_provider", cli)
        self.assertIn("quote_event=event", inspect.getsource(path_a_prospective.PathAProspectiveComposer.run))


if __name__ == "__main__":
    unittest.main()
