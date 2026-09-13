"""Fail-closed Path A PRODUCTION ForecastV1 producer (BUILD 14 fusion persist).

The producer may persist only when fusion emits EMITTED_CALIBRATED and hop
gates pass. CONTROL, RESEARCH, uncalibrated, IDENTITY_CONTROL, and missing
calibration persist nothing (FORECAST_UNAVAILABLE). Catalog evaluators never
call build_preregistration. Live stays LIVE_FORBIDDEN. A software-fused
calibrated artifact is not empirical and is not FTEP EMPIRICAL_ACTIVE.
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

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.contracts.strategy_match import StrategyMatchDisposition
from market_platform_foundation.intelligence.fusion import (
    DEFAULT_PRODUCTION_FUSION_POLICY,
    CalibrationMethod,
    build_contributor_ref,
)
from market_platform_foundation.intelligence.fusion.types import (
    CONTROL_FORECAST_STAGE,
    CalibrationModelArtifact,
    ForecastContributorRole,
)
from market_platform_foundation.research.forecast import build_forecast
from market_platform_foundation.providers.contracts import ProviderResult
from market_platform_foundation.strategy.evaluation import default_forecast_momentum_spec
from market_platform_foundation.strategy.path_a_forecast_producer import (
    persist_paper_demo_calibration,
    produce_paper_demo_forecast,
)
from market_platform_foundation.strategy.path_a_forecast_store import (
    load_paper_demo_forecasts,
    persist_paper_demo_forecast,
)
from market_platform_foundation.strategy.path_a_preregistration_store import (
    persist_paper_demo_preregistration,
)
from market_platform_foundation.strategy.path_a_prospective import (
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCallerError
from tests.intelligence.fusion_fixtures import baseline_control_forecast, sample_snapshot

T = 1_700_000_000_000_000_000
HORIZON = 300_000_000_000
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"
HONESTY_SCOPE = IntelligenceScope(
    instrument_ids=("canonical:EQUITY:XNYS:AAPL",),
    context_id="acct-paper:paper:snapshot-path-a-honesty-aapl",
)
QUALITY = QualitySummary(state=QualityState.GOOD)
PATH_A_TARGET = ForecastTarget(target_kind="direction", instrument_id="AAPL", parameters={})
PATH_A_HORIZON = TimeHorizonNs(duration_ns=HORIZON)


def _quote_event(*, last_price: float = 190.1, event_time_ns: int = T) -> dict:
    return {
        "raw_payload": {"last_price": last_price},
        "clocks": {"event_time_ns": event_time_ns},
    }


def _realtime_provider_event(*, last_price: float = 190.1, event_time_ns: int = T) -> dict:
    return {
        "capability": "US_EQUITY_L1",
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns,
            "received_time_ns": event_time_ns + 1_000_000,
        },
        "instrument_id": "AAPL",
        "provider": "test.realtime",
        "provider_symbol": "AAPL",
        "raw_payload": {
            "ask_price": last_price + 0.1,
            "ask_vol": 200,
            "bid_price": last_price - 0.1,
            "bid_vol": 100,
            "last_price": last_price,
        },
        "sequence": 7,
        "timeliness": "REAL_TIME",
        "normalization_version": "test/1.0.0",
    }


class _RealtimeQuoteProvider:
    capability = "US_EQUITY_SNAPSHOT"
    provider_id = "test.realtime"

    def __init__(self, event: dict | None = None) -> None:
        self._event = event or _realtime_provider_event()

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="available",
            events=(self._event,),
            provider_id="test.realtime",
            capability="US_EQUITY_SNAPSHOT",
        )


def _production_contributor(
    *,
    forecast_id: str,
    probability: float,
    family_key: str,
    signal_id: str,
) -> ForecastV1:
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version="1",
        scope=HONESTY_SCOPE,
        decision_time_ns=T,
        snapshot_id="snapshot-path-a-honesty-aapl",
        target=PATH_A_TARGET,
        horizon=PATH_A_HORIZON,
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
            raw_score=probability,
            calibrated_probability=None,
        ),
        quality=QUALITY,
        resolve_time_ns=T + HORIZON,
        component_lineage=ComponentLineage(
            component_id="path-a-production-contributor",
            component_version="1",
            model_id=f"SYNMOD-{family_key}",
            model_version="1",
        ),
        lineage_refs=(ContractReference(kind=ContractKind.SIGNAL.value, id=signal_id),),
        metadata={
            "contributor_role": ForecastContributorRole.PRODUCTION.value,
            "forecast_family_key": family_key,
            "forecast_stage": "PRODUCTION_RAW",
            "calibration_status": "UNCALIBRATED",
        },
    )


def _path_a_contributors() -> tuple[ForecastV1, ForecastV1]:
    return (
        _production_contributor(
            forecast_id="forecast-path-a-contributor-alpha",
            probability=0.61,
            family_key="family-alpha",
            signal_id="signal-path-a-alpha",
        ),
        _production_contributor(
            forecast_id="forecast-path-a-contributor-beta",
            probability=0.72,
            family_key="family-beta",
            signal_id="signal-path-a-beta",
        ),
    )


def _calibration_artifact(*, method: CalibrationMethod = CalibrationMethod.LOGISTIC_PROBABILITY):
    policy = DEFAULT_PRODUCTION_FUSION_POLICY
    if method == CalibrationMethod.IDENTITY_CONTROL:
        parameters = {"kind": "identity"}
        fingerprint = "path-a-identity-control"
        model_id = "CMODEL-path-a-identity-1"
    else:
        parameters = {"coef": [0.4], "intercept": 0.35}
        fingerprint = "path-a-logistic-preexisting"
        model_id = "CMODEL-path-a-logistic-1"
    return CalibrationModelArtifact(
        calibration_model_id=model_id,
        method=method,
        method_version="1",
        target=PATH_A_TARGET,
        horizon=PATH_A_HORIZON,
        fusion_policy_identity=policy.policy_identity,
        dataset_fingerprint="dataset-path-a-preexisting",
        training_cutoff_ns=T - 1,
        available_time_ns=T,
        parameters=parameters,
        parameter_fingerprint=fingerprint,
        min_training_raw_probability=0.21,
        max_training_raw_probability=0.75,
        sample_count=20,
        class_counts={"0": 10, "1": 10},
    )


class PathAForecastProducerHonestyTests(unittest.TestCase):
    def test_producer_source_never_mints_or_promotes_control_research(self) -> None:
        from market_platform_foundation.strategy import path_a_forecast_producer

        source = inspect.getsource(path_a_forecast_producer)
        produce_src = inspect.getsource(produce_paper_demo_forecast)
        self.assertNotIn("last_price", source)
        self.assertNotIn("probability=0.8", source)
        self.assertNotIn("build_forecast_v1(", produce_src)
        self.assertNotIn("from ..intelligence.baselines", source)
        self.assertNotIn("from ..research.forecast import", source)
        self.assertNotIn("build_preregistration(", produce_src)
        self.assertNotIn("build_forecast(", produce_src)
        self.assertIn("ForecastFusionService", source)
        self.assertIn("persist_paper_demo_forecast", source)
        self.assertIn("DEFAULT_PRODUCTION_FINAL_POLICY", source)
        self.assertIn("IDENTITY_CONTROL", source)
        self.assertIn("load_paper_demo_contributors", source)
        self.assertIn("load_paper_demo_calibration", source)


class PathAForecastProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)
        self.prereg = self.store / "prereg"
        self.forecasts = self.store / "forecasts"
        self.prereg.mkdir()
        self.forecasts.mkdir()
        self.contributors = self.store / "contributors"
        self.calibration = self.store / "calibration"
        self.contributors.mkdir()
        self.calibration.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _invoke(self, **kwargs):
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

    def _produce(self, **kwargs):
        invoke = kwargs.pop("invoke", None) or self._invoke()
        contributors = kwargs.pop("contributors", _path_a_contributors())
        calibration_artifact = kwargs.pop("calibration_artifact", _calibration_artifact())
        destination = kwargs.pop("destination", self.forecasts)
        return produce_paper_demo_forecast(
            contributors=contributors,
            calibration_artifact=calibration_artifact,
            champion=invoke.caller.champion_at_forecast,
            policy=invoke.caller.opportunity_policy,
            destination=destination,
            account_id=invoke.scan_request.scope.account_id,
            mode=invoke.scan_request.scope.mode,
            as_of_time_ns=invoke.scan_request.decision_time_ns,
            **kwargs,
        ), invoke

    def test_catalog_evaluators_never_call_build_preregistration(self) -> None:
        from market_platform_foundation.strategy import path_a_strategy_catalog

        source = inspect.getsource(path_a_strategy_catalog)
        self.assertNotIn("build_preregistration(", source)
        self.assertNotIn("from .preregistration import", source)
        self.assertIn("preregistration=None", source)

    def test_control_only_contributors_do_not_persist(self) -> None:
        control = baseline_control_forecast(sample_snapshot("snap-path-a-control"))
        produced, _invoke = self._produce(
            contributors=(control,),
            calibration_artifact=_calibration_artifact(),
        )
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("ABSTAINED_CONTROL_ONLY", produced.reason_codes)
        self.assertIsNone(produced.forecast)
        self.assertFalse(produced.persisted)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_missing_calibration_does_not_persist(self) -> None:
        produced, _invoke = self._produce(calibration_artifact=None)
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("ABSTAINED_CALIBRATION_UNAVAILABLE", produced.reason_codes)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_identity_control_calibrator_does_not_persist_as_production(self) -> None:
        produced, _invoke = self._produce(
            calibration_artifact=_calibration_artifact(method=CalibrationMethod.IDENTITY_CONTROL),
        )
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("IDENTITY_CONTROL_REJECTED", produced.reason_codes)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_research_score_dict_is_not_a_contributor(self) -> None:
        research = build_forecast(score="190.1", prediction_cutoff=T, horizon_ns=HORIZON)
        produced, _invoke = self._produce(contributors=(research,))
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("RESEARCH_REJECTED", produced.reason_codes)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_control_tagged_as_production_is_not_promoted(self) -> None:
        control = baseline_control_forecast(sample_snapshot("snap-path-a-control-promote"))
        produced, _invoke = self._produce(
            contributors=(build_contributor_ref(control, role=ForecastContributorRole.PRODUCTION),),
        )
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("ABSTAINED_CONTROL_ONLY", produced.reason_codes)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_horizon_mismatch_does_not_persist(self) -> None:
        alpha, _beta = _path_a_contributors()
        wrong = ForecastV1(
            forecast_id="forecast-path-a-contributor-wrong-horizon",
            schema_version="1",
            scope=alpha.scope,
            decision_time_ns=alpha.decision_time_ns,
            snapshot_id=alpha.snapshot_id,
            target=alpha.target,
            horizon=TimeHorizonNs(duration_ns=HORIZON * 2),
            estimate=alpha.estimate,
            quality=alpha.quality,
            resolve_time_ns=alpha.decision_time_ns + HORIZON * 2,
            metadata=dict(alpha.metadata),
        )
        produced, _invoke = self._produce(contributors=(wrong,))
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("HORIZON_MISMATCH", produced.reason_codes)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_live_is_forbidden_and_does_not_persist(self) -> None:
        invoke = self._invoke()
        produced = produce_paper_demo_forecast(
            contributors=_path_a_contributors(),
            calibration_artifact=_calibration_artifact(),
            champion=invoke.caller.champion_at_forecast,
            policy=invoke.caller.opportunity_policy,
            destination=self.forecasts,
            account_id="acct-paper",
            mode="live",
        )
        self.assertEqual(produced.status, "LIVE_FORBIDDEN")
        self.assertEqual(produced.reason_codes, ("LIVE_SCAN_CALLER_FORBIDDEN",))
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke(
                "AAPL",
                mode="live",
                as_of_time_ns=T,
                quote_event=_quote_event(),
                forecast_path=self.forecasts,
            )

    def test_fused_calibrated_forecast_persists_and_hop_reaches_opportunity_engine(self) -> None:
        """Software fusion persist is not empirical. Item 7 stays PARTIAL."""

        produced, invoke = self._produce()
        self.assertEqual(produced.status, "EMITTED_CALIBRATED")
        self.assertTrue(produced.persisted)
        assert produced.forecast is not None
        self.assertEqual(produced.forecast.metadata.get("forecast_stage"), "FINAL_FUSED_CALIBRATED")
        self.assertEqual(produced.forecast.metadata.get("calibration_status"), "CALIBRATED")
        self.assertEqual(produced.forecast.metadata.get("contributor_role"), "PRODUCTION")
        self.assertIsNotNone(produced.forecast.estimate.calibrated_probability)
        self.assertNotEqual(produced.forecast.estimate.calibrated_probability, 0.8)
        self.assertNotIn("last_price", produced.forecast.metadata)
        loaded_rows = load_paper_demo_forecasts(self.forecasts)
        self.assertEqual(len(loaded_rows), 1)
        self.assertEqual(loaded_rows[0].forecast_id, produced.forecast.forecast_id)

        hop = self._invoke(forecast_path=self.forecasts)
        scan = hop.caller.scanner.run(hop.scan_request)
        matched = [
            row for row in scan.matches if row.disposition == StrategyMatchDisposition.MATCHED
        ]
        self.assertEqual(len(matched), 1)
        resolved = hop.caller.forecast_resolver(matched[0])
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.forecast_id, produced.forecast.forecast_id)
        result = hop.caller.run(hop.scan_request)
        self.assertEqual(result.status, "MINTED")
        self.assertEqual(result.reason_codes, ("OPPORTUNITY_EMITTED",))
        self.assertTrue(result.assessments)
        self.assertTrue(result.opportunities)
        self.assertNotIn("FORECAST_RESOLUTION_FAILED", result.reason_codes)

    def test_uncalibrated_contributor_json_is_not_treated_as_produced(self) -> None:
        alpha, _beta = _path_a_contributors()
        persist_paper_demo_forecast(alpha, destination=self.forecasts)
        invoke = self._invoke(forecast_path=self.forecasts)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.opportunities, ())

    def test_producer_does_not_persist_control_stage_even_if_serialized_elsewhere(self) -> None:
        invoke = self._invoke()
        controlish = ForecastV1(
            forecast_id="forecast-control-not-produced",
            schema_version="1",
            scope=HONESTY_SCOPE,
            decision_time_ns=T,
            snapshot_id="snapshot-path-a-honesty-aapl",
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.61,
                calibrated_probability=0.61,
            ),
            quality=QUALITY,
            resolve_time_ns=T + HORIZON,
            metadata={
                "forecast_stage": CONTROL_FORECAST_STAGE,
                "contributor_role": "CONTROL",
                "calibration_status": "CALIBRATED",
                "champion_candidate_id": invoke.caller.champion_at_forecast.candidate_id,
                "candidate_artifact_hash": invoke.caller.champion_at_forecast.candidate_artifact_hash,
            },
        )
        produced, _ignored = self._produce(contributors=(controlish,))
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def _persist_hop_inputs(self) -> None:
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.prereg,
        )
        for row in _path_a_contributors():
            persist_paper_demo_forecast(row, destination=self.contributors)
        persist_paper_demo_calibration(_calibration_artifact(), destination=self.calibration)

    def test_hop_produce_reaches_opportunity_engine_without_fixture_probability(self) -> None:
        """Composer MATCHED/OE EMIT uses BUILD 14 produce, not fixture 0.8."""

        self._persist_hop_inputs()
        result = PathAProspectiveComposer(
            quote_provider=_RealtimeQuoteProvider(),
            preregistration_path=self.prereg,
            contributor_path=self.contributors,
            calibration_path=self.calibration,
            forecast_path=self.forecasts,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertTrue(result.freshness.get("actionable"))
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "MINTED")
        self.assertEqual(result.path_a.reason_codes, ("OPPORTUNITY_EMITTED",))
        self.assertTrue(result.path_a.opportunities)
        self.assertEqual(result.status, "MINTED")
        fused = load_paper_demo_forecasts(self.forecasts)
        self.assertEqual(len(fused), 1)
        self.assertNotEqual(fused[0].estimate.calibrated_probability, 0.8)
        self.assertNotEqual(fused[0].estimate.probability, 0.8)
        self.assertEqual(fused[0].metadata.get("forecast_stage"), "FINAL_FUSED_CALIBRATED")
        self.assertEqual(fused[0].metadata.get("calibration_status"), "CALIBRATED")

    def test_hop_produce_fail_closed_without_production_contributors(self) -> None:
        self._persist_hop_inputs()
        empty = self.store / "empty-contributors"
        empty.mkdir()
        result = PathAProspectiveComposer(
            quote_provider=_RealtimeQuoteProvider(),
            preregistration_path=self.prereg,
            contributor_path=empty,
            calibration_path=self.calibration,
            forecast_path=self.forecasts,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.path_a.opportunities, ())
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_hop_produce_fail_closed_without_calibrator(self) -> None:
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.prereg,
        )
        for row in _path_a_contributors():
            persist_paper_demo_forecast(row, destination=self.contributors)
        result = PathAProspectiveComposer(
            quote_provider=_RealtimeQuoteProvider(),
            preregistration_path=self.prereg,
            contributor_path=self.contributors,
            calibration_path=self.calibration,
            forecast_path=self.forecasts,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.path_a.opportunities, ())
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_bootstrap_champion_does_not_suppress_print_timed_forecast(self) -> None:
        invoke = self._invoke()
        self.assertEqual(invoke.caller.champion_at_forecast.effective_from_ns, 0)
        self.assertEqual(
            invoke.caller.champion_at_forecast.assignment_reason.value,
            "BOOTSTRAP",
        )


if __name__ == "__main__":
    unittest.main()
