"""Item 7 Lane B production readiness diagnostics."""

from __future__ import annotations

import sys
from dataclasses import replace
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
from market_platform_foundation.intelligence.fusion import DEFAULT_PRODUCTION_FUSION_POLICY, CalibrationMethod
from market_platform_foundation.intelligence.fusion.types import (
    CONTROL_FORECAST_STAGE,
    ForecastContributorRole,
    PRODUCTION_FORECAST_STAGE,
)
from market_platform_foundation.intelligence.production.readiness import (
    BLOCKER_NO_GOVERNED_TRAINING_CORPUS,
    BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR,
    STATUS_BLOCKED_PREFIX,
    STATUS_ARTIFACT_READY,
    assess_production_readiness,
    forecast_binding_refusal_reasons,
    is_lawful_production_raw_contributor,
    production_contributor_refusal_reasons,
)
from market_platform_foundation.intelligence.production.progression import build_item7_progression_report
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production.calibrator import train_production_calibration
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast
from market_platform_foundation.intelligence.production.readiness import TRAINING_MANIFEST_KIND
from market_platform_foundation.intelligence.production.training_build import build_path_a_production_artifacts
from market_platform_foundation.strategy.path_a_production_emit import (
    persist_path_a_production_calibration,
    persist_path_a_production_contributor,
)
from tests.intelligence.outcome_fixtures import baseline_control_forecast
from tests.intelligence.test_path_a_production_emit import (
    PATH_A_HORIZON,
    PATH_A_TARGET,
    T,
    _calibration_examples,
    _emit_signals,
    _emit_snapshot,
    _fitted_model,
)

HORIZON = PATH_A_HORIZON.duration_ns


class Item7ProductionReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.contributors = self.root / "contributors"
        self.calibration = self.root / "calibration"
        self.contributors.mkdir()
        self.calibration.mkdir()
        self.cutoff = T - (HORIZON * 3)
        self.model = _fitted_model(cutoff_ns=self.cutoff)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _persist_lawful_contributor(self) -> str:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        return str(emitted.forecast.forecast_id)

    def _persist_lawful_calibration(self) -> None:
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
        assert trained.artifact is not None
        persist_path_a_production_calibration(
            trained.artifact,
            destination=self.calibration,
            mode="paper",
            decision_time_ns=T,
        )

    def test_control_forecast_not_production_available(self) -> None:
        repo = InMemoryIntelligenceRepository()
        control = baseline_control_forecast(repo)
        reasons = production_contributor_refusal_reasons(control)
        self.assertTrue(reasons)
        self.assertFalse(is_lawful_production_raw_contributor(control))

    def test_valid_production_contributor_recognized(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        self.assertEqual(
            emitted.forecast.metadata.get("contributor_role"),
            ForecastContributorRole.PRODUCTION.value,
        )
        self.assertEqual(
            emitted.forecast.metadata.get("forecast_stage"),
            PRODUCTION_FORECAST_STAGE,
        )
        self.assertFalse(production_contributor_refusal_reasons(emitted.forecast))

    def test_wrong_horizon_rejected(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=TimeHorizonNs(duration_ns=60_000_000_000),
            mode="paper",
            as_of_time_ns=T,
        )
        self.assertFalse(emitted.emitted)

    def test_pit_invalid_contributor_rejected(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T - 1,
        )
        self.assertFalse(emitted.emitted)

    def test_missing_calibrator_rejected_on_assess(self) -> None:
        self._persist_lawful_contributor()
        report = assess_production_readiness(
            contributor_path=self.contributors,
            calibration_path=None,
            decision_time_ns=T,
        )
        self.assertNotEqual(report.disposition, STATUS_ARTIFACT_READY)
        self.assertIn("CALIBRATION", report.first_blocker)

    def test_invalid_calibration_future_rejected(self) -> None:
        self._persist_lawful_contributor()
        trained = train_production_calibration(
            _calibration_examples(cutoff_ns=self.cutoff),
            method=CalibrationMethod.LOGISTIC_PROBABILITY,
            available_time_ns=T + 10,
            decision_time_ns=T,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
            calibration_cutoff_ns=self.cutoff,
            mode="paper",
        )
        self.assertIsNone(trained.artifact)
        self.assertIn("CALIBRATION_NOT_YET_AVAILABLE", trained.reason_codes)
        report = assess_production_readiness(
            contributor_path=self.contributors,
            calibration_path=self.calibration,
            decision_time_ns=T,
        )
        self.assertNotEqual(report.disposition, STATUS_ARTIFACT_READY)

    def test_assess_ready_when_lawful_artifacts_present(self) -> None:
        self._persist_lawful_contributor()
        self._persist_lawful_calibration()
        report = assess_production_readiness(
            contributor_path=self.contributors,
            calibration_path=self.calibration,
            decision_time_ns=T,
        )
        self.assertEqual(report.disposition, STATUS_ARTIFACT_READY)
        self.assertEqual(report.first_blocker, "none")

    def test_progression_passes_production_forecast_available_with_contributor(self) -> None:
        forecast_id = self._persist_lawful_contributor()
        repo = InMemoryIntelligenceRepository()
        report = build_item7_progression_report(
            repository=repo,
            as_of_ns=T,
            session_start_ns=T - 1,
            contributor_path=self.contributors,
        )
        self.assertTrue(report.stage_vector.production_forecast_available)
        self.assertIn(forecast_id, report.production_contributor_ids)

    def test_binding_rejects_control(self) -> None:
        repo = InMemoryIntelligenceRepository()
        control = baseline_control_forecast(repo)
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        reasons = forecast_binding_refusal_reasons(
            forecast_id=control.forecast_id,
            contributor_path=self.contributors,
        )
        self.assertTrue(reasons)

    def test_binding_accepts_lawful_contributor(self) -> None:
        forecast_id = self._persist_lawful_contributor()
        reasons = forecast_binding_refusal_reasons(
            forecast_id=forecast_id,
            contributor_path=self.contributors,
        )
        self.assertFalse(reasons)

    def test_no_paths_blocked_on_training_corpus(self) -> None:
        report = assess_production_readiness(decision_time_ns=T)
        self.assertEqual(report.first_blocker, BLOCKER_NO_GOVERNED_TRAINING_CORPUS)
        self.assertEqual(
            report.disposition,
            f"{STATUS_BLOCKED_PREFIX}{BLOCKER_NO_GOVERNED_TRAINING_CORPUS}",
        )

    def test_account_mismatch_on_persisted_contributor(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        bound = replace(
            emitted.forecast,
            metadata={**dict(emitted.forecast.metadata), "account_id": "acct-paper"},
        )
        persist_path_a_production_contributor(bound, destination=self.contributors, mode="paper")
        reasons = production_contributor_refusal_reasons(bound, expected_account_id="acct-other")
        self.assertIn("ACCOUNT_MISMATCH", reasons)
        report = assess_production_readiness(
            contributor_path=self.contributors,
            calibration_path=self.calibration,
            decision_time_ns=T,
            expected_account_id="acct-other",
        )
        self.assertEqual(report.first_blocker, BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR)

    def test_mode_mismatch_on_persisted_contributor(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        bound = replace(
            emitted.forecast,
            metadata={**dict(emitted.forecast.metadata), "mode": "paper"},
        )
        persist_path_a_production_contributor(bound, destination=self.contributors, mode="paper")
        self.assertIn(
            "MODE_MISMATCH",
            production_contributor_refusal_reasons(bound, expected_mode="demo"),
        )

    def test_wrong_instrument_on_persisted_contributor(self) -> None:
        forecast_id = self._persist_lawful_contributor()
        from market_platform_foundation.strategy.path_a_forecast_producer import load_paper_demo_contributors

        loaded = load_paper_demo_contributors(self.contributors)[0]
        self.assertIn(
            "TARGET_INSTRUMENT_MISMATCH",
            production_contributor_refusal_reasons(loaded, expected_instrument_id="MSFT"),
        )
        report = assess_production_readiness(
            contributor_path=self.contributors,
            decision_time_ns=T,
            expected_instrument_id="MSFT",
        )
        self.assertEqual(report.first_blocker, BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR)
        self.assertNotIn(forecast_id, report.valid_contributor_ids)

    def test_wrong_target_kind_on_persisted_contributor(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        wrong_target = ForecastTarget(target_kind="return", instrument_id="AAPL", parameters={})
        tampered = replace(emitted.forecast, target=wrong_target)
        persist_path_a_production_contributor(tampered, destination=self.contributors, mode="paper")
        self.assertIn("TARGET_MISMATCH", production_contributor_refusal_reasons(tampered))

    def test_pit_invalid_manifest_build_blocked_not_raised(self) -> None:
        decision = self.cutoff - HORIZON
        manifest = {
            "artifact_kind": TRAINING_MANIFEST_KIND,
            "target_instrument_id": "AAPL",
            "training_cutoff_ns": self.cutoff,
            "scope": {"instrument_ids": ["canonical:EQUITY:XNYS:AAPL"], "context_id": "x"},
            "examples": [
                {
                    "snapshot_id": "snap-pit-bad",
                    "decision_time_ns": decision,
                    "label": 1,
                    "label_available_time_ns": decision - 1,
                    "momentum": 0.01,
                    "net_signed_share": 0.1,
                }
            ],
        }
        manifest_path = self.root / "pit-bad.json"
        manifest_path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
        result = build_path_a_production_artifacts(
            manifest_path,
            output_dir=self.root / "pit-out",
            mode="paper",
            decision_time_ns=T,
        )
        self.assertFalse(result.built)
        self.assertIn("LABEL_AVAILABLE_BEFORE_FORECAST", result.reason_codes)

    def test_build_does_not_synthesize_from_quote(self) -> None:
        """Training build has no quote/trade inputs; default assess stays corpus-blocked."""
        report = assess_production_readiness(decision_time_ns=T)
        self.assertEqual(report.first_blocker, BLOCKER_NO_GOVERNED_TRAINING_CORPUS)
        self.assertFalse(list(self.contributors.glob("*.json")))

    def test_build_from_governed_manifest_in_tempdir(self) -> None:
        manifest = {
            "artifact_kind": TRAINING_MANIFEST_KIND,
            "target_instrument_id": "AAPL",
            "training_cutoff_ns": self.cutoff,
            "calibration_cutoff_ns": self.cutoff,
            "scope": {
                "instrument_ids": ["canonical:EQUITY:XNYS:AAPL"],
                "context_id": "acct-paper:paper:snapshot-path-a-honesty-aapl",
            },
            "examples": [
                {
                    "snapshot_id": f"snap-train-{index}",
                    "decision_time_ns": self.cutoff - ((22 - index) * HORIZON * 2),
                    "label": 1 if index % 2 == 0 else 0,
                    "label_available_time_ns": self.cutoff - ((22 - index) * HORIZON * 2) + HORIZON,
                    "momentum": -0.02 + (index * 0.004),
                    "net_signed_share": -0.4 + (index * 0.07),
                }
                for index in range(22)
            ],
            "emit_context": {
                "snapshot_id": "snapshot-path-a-honesty-aapl",
                "decision_time_ns": T,
                "momentum": 0.012,
                "net_signed_share": 0.18,
            },
        }
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
        out = self.root / "built"
        result = build_path_a_production_artifacts(
            manifest_path,
            output_dir=out,
            mode="paper",
            decision_time_ns=T,
        )
        self.assertTrue(result.built)
        report = assess_production_readiness(
            contributor_path=out / "contributors",
            calibration_path=out / "calibration",
            decision_time_ns=T,
        )
        self.assertEqual(report.disposition, STATUS_ARTIFACT_READY)


if __name__ == "__main__":
    unittest.main()
