"""Fail-closed Path A PRODUCTION specialist emitter + temporal calibrator.

Software emit/persist is not empirical and is not FTEP EMPIRICAL_ACTIVE.
Item 7 stays PARTIAL until a real weekday G7-actionable hop consumes the files.
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
    ContractKind,
    ContractReference,
    ForecastTarget,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SignalV1,
    SnapshotV1,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.fusion import (
    DEFAULT_PRODUCTION_FUSION_POLICY,
    CalibrationExample,
    CalibrationMethod,
    PRODUCTION_FORECAST_STAGE,
    resolve_contributor_role,
)
from market_platform_foundation.intelligence.fusion.types import ForecastContributorRole
from market_platform_foundation.intelligence.production.calibrator import train_production_calibration
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast
from market_platform_foundation.intelligence.production.identity import (
    PATH_A_FAMILY_KEY,
    PATH_A_HORIZON_NS,
    path_a_direction_target,
    path_a_horizon,
)
from market_platform_foundation.intelligence.production.model import (
    ProductionTrainingExample,
    fit_production_specialist,
)
from market_platform_foundation.strategy.evaluation import default_forecast_momentum_spec
from market_platform_foundation.strategy.path_a_forecast_producer import (
    load_paper_demo_calibration,
    load_paper_demo_contributors,
    produce_paper_demo_forecast,
)
from market_platform_foundation.strategy.path_a_forecast_store import load_paper_demo_forecasts
from market_platform_foundation.strategy.path_a_preregistration_store import persist_paper_demo_preregistration
from market_platform_foundation.strategy.path_a_production_emit import (
    persist_path_a_production_calibration,
    persist_path_a_production_contributor,
)
from market_platform_foundation.strategy.path_a_prospective import build_paper_demo_path_a_invoke
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCallerError

T = 1_700_000_000_000_000_000
HORIZON = PATH_A_HORIZON_NS
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"
HONESTY_SCOPE = IntelligenceScope(
    instrument_ids=("canonical:EQUITY:XNYS:AAPL",),
    context_id="acct-paper:paper:snapshot-path-a-honesty-aapl",
)
QUALITY = QualitySummary(state=QualityState.GOOD)
PATH_A_TARGET = path_a_direction_target("AAPL")
PATH_A_HORIZON = path_a_horizon()
EMIT_SNAPSHOT_ID = "snapshot-path-a-honesty-aapl"
WINDOW = HORIZON


def _snapshot(snapshot_id: str, decision_time_ns: int) -> SnapshotV1:
    return SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=decision_time_ns,
        scope=HONESTY_SCOPE,
        quality=QUALITY,
    )


def _feature_signals(snapshot_id: str, *, momentum: float, nss: float, as_of_time_ns: int) -> tuple[SignalV1, SignalV1]:
    return (
        SignalV1(
            signal_id=f"sig-momentum-{snapshot_id}",
            schema_version="1",
            signal_type="momentum_simple",
            scope=HONESTY_SCOPE,
            as_of_time_ns=as_of_time_ns,
            value=momentum,
            quality=QUALITY,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
            calculation_window=TimeHorizonNs(duration_ns=WINDOW),
            calculation_lineage={"calculator_id": "momentum-calculator", "calculator_version": "1"},
            unit="decimal_return",
        ),
        SignalV1(
            signal_id=f"sig-nss-{snapshot_id}",
            schema_version="1",
            signal_type="net_signed_share",
            scope=HONESTY_SCOPE,
            as_of_time_ns=as_of_time_ns,
            value=nss,
            quality=QUALITY,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
            calculation_window=TimeHorizonNs(duration_ns=WINDOW),
            calculation_lineage={"calculator_id": "cvd-calculator", "calculator_version": "1"},
        ),
    )


def _training_examples(*, cutoff_ns: int) -> list[ProductionTrainingExample]:
    examples: list[ProductionTrainingExample] = []
    for index in range(12):
        decision = cutoff_ns - ((12 - index) * HORIZON * 2)
        snapshot_id = f"snap-train-{index}"
        momentum = -0.03 + (index * 0.005)
        nss = -0.5 + (index * 0.08)
        label = 1 if momentum > 0 else 0
        snapshot = _snapshot(snapshot_id, decision)
        examples.append(
            ProductionTrainingExample(
                snapshot=snapshot,
                signals=_feature_signals(snapshot_id, momentum=momentum, nss=nss, as_of_time_ns=decision),
                label=label,
                label_available_time_ns=decision + HORIZON,
            )
        )
    return examples


def _fitted_model(*, cutoff_ns: int):
    model = fit_production_specialist(
        _training_examples(cutoff_ns=cutoff_ns),
        target=PATH_A_TARGET,
        horizon=PATH_A_HORIZON,
        training_cutoff_ns=cutoff_ns,
    )
    assert model is not None
    return model


def _emit_snapshot() -> SnapshotV1:
    return _snapshot(EMIT_SNAPSHOT_ID, T)


def _emit_signals(*, momentum: float = 0.012, nss: float = 0.18) -> tuple[SignalV1, SignalV1]:
    return _feature_signals(EMIT_SNAPSHOT_ID, momentum=momentum, nss=nss, as_of_time_ns=T)


def _quote_event(*, event_time_ns: int = T) -> dict:
    return {
        "raw_payload": {"trade_price": 190.1},
        "clocks": {"event_time_ns": event_time_ns},
    }


def _calibration_examples(*, cutoff_ns: int) -> list[CalibrationExample]:
    policy = DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity
    examples: list[CalibrationExample] = []
    for index in range(20):
        decision = cutoff_ns - ((20 - index) * HORIZON * 2)
        probability = 0.08 + (index * 0.04)
        examples.append(
            CalibrationExample(
                raw_fusion_id=f"RFF-path-a-{index}",
                raw_probability=probability,
                target=PATH_A_TARGET,
                horizon=PATH_A_HORIZON,
                scope=HONESTY_SCOPE,
                forecast_decision_time_ns=decision,
                label=1 if probability >= 0.5 else 0,
                label_available_time_ns=decision + HORIZON,
                fusion_policy_identity=policy,
            )
        )
    return examples


class PathAProductionEmitHonestyTests(unittest.TestCase):
    def test_library_source_never_mints_or_promotes_control_research(self) -> None:
        from market_platform_foundation.intelligence import production as production_pkg
        from market_platform_foundation.intelligence.production import calibrator, emitter, model
        from market_platform_foundation.strategy import path_a_production_emit

        sources = [
            inspect.getsource(production_pkg),
            inspect.getsource(emitter),
            inspect.getsource(model),
            inspect.getsource(calibrator),
            inspect.getsource(path_a_production_emit),
        ]
        joined = "\n".join(sources)
        self.assertNotIn("last_price", joined)
        self.assertNotIn("probability=0.8", joined)
        self.assertNotIn("build_forecast_v1(", joined)
        self.assertNotIn("from ..research.forecast import", joined)
        self.assertNotIn("from ...research.forecast import", joined)
        self.assertNotIn("from ..intelligence.baselines.forecast import", joined)
        self.assertNotIn("IDENTITY_CONTROL", inspect.getsource(emit_production_forecast))
        self.assertIn("PRODUCTION_FORECAST_STAGE", inspect.getsource(emitter))
        self.assertIn("CalibrationDatasetBuilder", inspect.getsource(calibrator))
        self.assertIn("IDENTITY_CONTROL_REJECTED", inspect.getsource(calibrator))


class PathAProductionEmitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)
        self.contributors = self.store / "contributors"
        self.calibration = self.store / "calibration"
        self.forecasts = self.store / "forecasts"
        self.prereg = self.store / "prereg"
        self.contributors.mkdir()
        self.calibration.mkdir()
        self.forecasts.mkdir()
        self.prereg.mkdir()
        self.cutoff = T - (HORIZON * 3)
        self.model = _fitted_model(cutoff_ns=self.cutoff)

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

    def test_emits_innate_production_raw_path_a_identity(self) -> None:
        result = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        self.assertEqual(result.status, "EMITTED_PRODUCTION_RAW")
        assert result.forecast is not None
        forecast = result.forecast
        self.assertEqual(forecast.metadata.get("contributor_role"), "PRODUCTION")
        self.assertEqual(forecast.metadata.get("forecast_stage"), PRODUCTION_FORECAST_STAGE)
        self.assertEqual(forecast.metadata.get("calibration_status"), "UNCALIBRATED")
        self.assertEqual(forecast.metadata.get("forecast_family_key"), PATH_A_FAMILY_KEY)
        self.assertEqual(resolve_contributor_role(forecast), ForecastContributorRole.PRODUCTION)
        self.assertEqual(forecast.target.target_kind, "direction")
        self.assertEqual(forecast.horizon.duration_ns, HORIZON)
        self.assertIsNone(forecast.estimate.calibrated_probability)
        self.assertIsNotNone(forecast.estimate.probability)
        self.assertNotEqual(forecast.estimate.probability, 0.8)
        self.assertNotIn("last_price", forecast.metadata)
        self.assertTrue(forecast.forecast_id.startswith("PSFC-"))
        self.assertTrue(forecast.component_lineage.model_id.startswith("PSMOD-"))

    def test_emit_is_deterministic(self) -> None:
        first = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        second = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        self.assertTrue(first.emitted and second.emitted)
        self.assertEqual(first.forecast.forecast_id, second.forecast.forecast_id)
        self.assertEqual(first.forecast.estimate.probability, second.forecast.estimate.probability)

    def test_wrong_horizon_and_target_fail_closed(self) -> None:
        wrong_horizon = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=TimeHorizonNs(duration_ns=HORIZON * 2),
            mode="paper",
        )
        self.assertEqual(wrong_horizon.status, "FORECAST_UNAVAILABLE")
        self.assertIn("HORIZON_MISMATCH", wrong_horizon.reason_codes)
        self.assertIsNone(wrong_horizon.forecast)

        wrong_target = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=ForecastTarget(target_kind="direction_up_down", instrument_id="AAPL", parameters={}),
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        self.assertEqual(wrong_target.status, "FORECAST_UNAVAILABLE")
        self.assertIn("TARGET_MISMATCH", wrong_target.reason_codes)

    def test_future_signal_and_unready_model_fail_closed(self) -> None:
        future_signals = _feature_signals(
            EMIT_SNAPSHOT_ID,
            momentum=0.01,
            nss=0.1,
            as_of_time_ns=T + 1,
        )
        future = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=future_signals,
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        self.assertEqual(future.status, "FORECAST_UNAVAILABLE")
        self.assertIn("FEATURE_EXTRACTION_FAILED", future.reason_codes)

        late_model = _fitted_model(cutoff_ns=T)
        unready = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=late_model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        self.assertEqual(unready.status, "FORECAST_UNAVAILABLE")
        self.assertIn("MODEL_NOT_YET_AVAILABLE", unready.reason_codes)

    def test_live_emit_is_forbidden(self) -> None:
        result = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="live",
        )
        self.assertEqual(result.status, "LIVE_FORBIDDEN")
        self.assertEqual(result.reason_codes, ("LIVE_SCAN_CALLER_FORBIDDEN",))
        self.assertIsNone(result.forecast)

    def test_future_training_label_rejected(self) -> None:
        examples = _training_examples(cutoff_ns=self.cutoff)
        leaked = ProductionTrainingExample(
            snapshot=examples[0].snapshot,
            signals=examples[0].signals,
            label=1,
            label_available_time_ns=self.cutoff + 1,
        )
        with self.assertRaises(Exception):
            fit_production_specialist(
                [leaked],
                target=PATH_A_TARGET,
                horizon=PATH_A_HORIZON,
                training_cutoff_ns=self.cutoff,
            )

    def test_calibrator_trains_logistic_with_temporal_firewall(self) -> None:
        trained = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertEqual(trained.status, "TRAINED")
        assert trained.artifact is not None
        self.assertEqual(trained.artifact.method, CalibrationMethod.LOGISTIC_PROBABILITY)
        self.assertEqual(trained.artifact.target.target_kind, "direction")
        self.assertEqual(trained.artifact.horizon.duration_ns, HORIZON)
        self.assertEqual(
            trained.artifact.fusion_policy_identity,
            DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
        )
        self.assertLessEqual(trained.artifact.available_time_ns, T)
        self.assertTrue(trained.artifact.calibration_model_id.startswith("CALM-"))

    def test_calibrator_trains_isotonic(self) -> None:
        trained = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.ISOTONIC,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertEqual(trained.status, "TRAINED")
        assert trained.artifact is not None
        self.assertEqual(trained.artifact.method, CalibrationMethod.ISOTONIC)

    def test_identity_control_and_future_calibrator_fail_closed(self) -> None:
        identity = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.IDENTITY_CONTROL,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertEqual(identity.status, "CALIBRATION_UNAVAILABLE")
        self.assertIn("IDENTITY_CONTROL_REJECTED", identity.reason_codes)
        self.assertIsNone(identity.artifact)

        too_late = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T + 1,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertIn("CALIBRATION_NOT_YET_AVAILABLE", too_late.reason_codes)

        live = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="live",
        )
        self.assertEqual(live.status, "LIVE_FORBIDDEN")

    def test_lawful_persist_then_producer_consumes_tempdir_json(self) -> None:
        """Tempdir JSON is software proof, not empirical. Item 7 stays PARTIAL."""

        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        self.assertTrue(emitted.emitted)
        persisted = persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        self.assertTrue(persisted.persisted)

        trained = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertTrue(trained.trained)
        cal_persist = persist_path_a_production_calibration(
            trained.artifact,
            destination=self.calibration,
            mode="paper",
            decision_time_ns=T,
        )
        self.assertTrue(cal_persist.persisted)

        contributors = load_paper_demo_contributors(self.contributors)
        artifact = load_paper_demo_calibration(self.calibration)
        self.assertEqual(len(contributors), 1)
        self.assertIsNotNone(artifact)
        self.assertEqual(contributors[0].metadata.get("contributor_role"), "PRODUCTION")
        self.assertEqual(contributors[0].metadata.get("forecast_stage"), "PRODUCTION_RAW")

        invoke = self._invoke()
        produced = produce_paper_demo_forecast(
            contributors=contributors,
            calibration_artifact=artifact,
            champion=invoke.caller.champion_at_forecast,
            policy=invoke.caller.opportunity_policy,
            destination=self.forecasts,
            account_id=invoke.scan_request.scope.account_id,
            mode="paper",
            as_of_time_ns=invoke.scan_request.decision_time_ns,
        )
        self.assertEqual(produced.status, "EMITTED_CALIBRATED")
        self.assertTrue(produced.persisted)
        assert produced.forecast is not None
        self.assertEqual(produced.forecast.metadata.get("forecast_stage"), "FINAL_FUSED_CALIBRATED")
        self.assertEqual(produced.forecast.metadata.get("calibration_status"), "CALIBRATED")
        self.assertNotEqual(produced.forecast.estimate.calibrated_probability, 0.8)
        self.assertEqual(len(load_paper_demo_forecasts(self.forecasts)), 1)

    def test_unlawful_persist_writes_nothing(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
        )
        live = persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="live",
        )
        self.assertEqual(live.status, "LIVE_FORBIDDEN")
        self.assertEqual(load_paper_demo_contributors(self.contributors), ())

        trained = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        late = persist_path_a_production_calibration(
            trained.artifact,
            destination=self.calibration,
            mode="paper",
            decision_time_ns=T - 1,
        )
        self.assertEqual(late.status, "CALIBRATION_UNAVAILABLE")
        self.assertIn("CALIBRATION_NOT_YET_AVAILABLE", late.reason_codes)
        self.assertIsNone(load_paper_demo_calibration(self.calibration))

    def test_live_invoke_still_forbidden(self) -> None:
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke("AAPL", mode="live", as_of_time_ns=T)


if __name__ == "__main__":
    unittest.main()
