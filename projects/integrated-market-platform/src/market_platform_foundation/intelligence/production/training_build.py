"""Build Path A PRODUCTION model/calibration artifacts from a governed training manifest.

Manifest rows are historical PIT-labelled examples — not quote-print minting and
not empirical Item 7 proof. Contributor ``ForecastV1`` JSON still requires a
lawful hop snapshot emit at RTH unless the manifest includes an explicit
``emit_context`` block for software-only validation dirs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...canonical import load_json_strict, sha256_bytes, canonical_bytes
from ..contracts import ContractKind, ContractReference, IntelligenceScope, QualityState, QualitySummary, SignalV1, SnapshotV1
from ..fusion import DEFAULT_PRODUCTION_FUSION_POLICY, CalibrationMethod
from ..fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES
from ..fusion.types import CalibrationExample
from .calibrator import train_production_calibration
from .emitter import emit_production_forecast
from .identity import path_a_direction_target, path_a_horizon
from .errors import ProductionTrainingError
from .model import ProductionTrainingExample, fit_production_specialist
from .model_store import persist_production_specialist_model
from .readiness import TRAINING_MANIFEST_KIND
from ...strategy.path_a_production_emit import (
    persist_path_a_production_calibration,
    persist_path_a_production_contributor,
)


@dataclass(frozen=True, slots=True)
class ProductionBuildResult:
    status: str
    reason_codes: tuple[str, ...]
    model_id: str | None = None
    training_dataset_fingerprint: str | None = None
    calibration_model_id: str | None = None
    contributor_forecast_id: str | None = None
    artifact_hashes: dict[str, str] | None = None

    @property
    def built(self) -> bool:
        return self.status == "BUILT"


def _manifest_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(dict(payload)))


def load_governed_training_manifest(path: Path) -> dict[str, Any] | None:
    try:
        payload = load_json_strict(path)
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("artifact_kind") or "") != TRAINING_MANIFEST_KIND:
        return None
    return dict(payload)


def _scope_from_manifest(raw: Mapping[str, Any]) -> IntelligenceScope:
    instruments = tuple(str(item) for item in raw.get("instrument_ids") or ())
    return IntelligenceScope(
        instrument_ids=instruments or ("canonical:EQUITY:XNYS:AAPL",),
        context_id=str(raw.get("context_id") or "path-a-training"),
    )


def _examples_from_manifest(payload: Mapping[str, Any]) -> list[ProductionTrainingExample]:
    scope = _scope_from_manifest(dict(payload.get("scope") or {}))
    quality = QualitySummary(state=QualityState.GOOD)
    horizon = path_a_horizon()
    rows: list[ProductionTrainingExample] = []
    for index, raw in enumerate(payload.get("examples") or []):
        if not isinstance(raw, Mapping):
            raise ValueError("EXAMPLE_MUST_BE_OBJECT")
        snapshot_id = str(raw["snapshot_id"])
        decision_time_ns = int(raw["decision_time_ns"])
        label = int(raw["label"])
        label_available_time_ns = int(raw["label_available_time_ns"])
        momentum = float(raw["momentum"])
        nss = float(raw["net_signed_share"])
        snapshot = SnapshotV1(
            snapshot_id=snapshot_id,
            schema_version="1",
            decision_time_ns=decision_time_ns,
            scope=scope,
            quality=quality,
        )
        signals = (
            SignalV1(
                signal_id=f"sig-momentum-{index}",
                schema_version="1",
                signal_type="momentum_simple",
                scope=scope,
                as_of_time_ns=decision_time_ns,
                value=momentum,
                quality=quality,
                source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
                calculation_window=path_a_horizon(),
                calculation_lineage={"calculator_id": "momentum-calculator", "calculator_version": "1"},
                unit="decimal_return",
            ),
            SignalV1(
                signal_id=f"sig-nss-{index}",
                schema_version="1",
                signal_type="net_signed_share",
                scope=scope,
                as_of_time_ns=decision_time_ns,
                value=nss,
                quality=quality,
                source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
                calculation_window=path_a_horizon(),
                calculation_lineage={"calculator_id": "cvd-calculator", "calculator_version": "1"},
                unit="share",
            ),
        )
        rows.append(
            ProductionTrainingExample(
                snapshot=snapshot,
                signals=signals,
                label=label,
                label_available_time_ns=label_available_time_ns,
            )
        )
    return rows


def _calibration_examples_from_manifest(
    payload: Mapping[str, Any],
    *,
    target_instrument: str,
) -> list[CalibrationExample]:
    policy = DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity
    target = path_a_direction_target(target_instrument)
    horizon = path_a_horizon()
    scope = _scope_from_manifest(dict(payload.get("scope") or {}))
    rows: list[CalibrationExample] = []
    for index, raw in enumerate(payload.get("calibration_examples") or payload.get("examples") or []):
        if not isinstance(raw, Mapping):
            continue
        if "raw_probability" not in raw:
            continue
        decision = int(raw.get("forecast_decision_time_ns") or raw.get("decision_time_ns"))
        label = int(raw["label"])
        label_available = int(raw.get("label_available_time_ns") or decision + horizon.duration_ns)
        rows.append(
            CalibrationExample(
                raw_fusion_id=str(raw.get("raw_fusion_id") or f"RFF-build-{index}"),
                raw_probability=float(raw["raw_probability"]),
                target=target,
                horizon=horizon,
                scope=scope,
                forecast_decision_time_ns=decision,
                label=label,
                label_available_time_ns=label_available,
                fusion_policy_identity=policy,
            )
        )
    return rows


def build_path_a_production_artifacts(
    manifest_path: Path,
    *,
    output_dir: Path,
    mode: str,
    decision_time_ns: int,
    calibration_method: CalibrationMethod = CalibrationMethod.LOGISTIC_PROBABILITY,
) -> ProductionBuildResult:
    payload = load_governed_training_manifest(manifest_path)
    if payload is None:
        return ProductionBuildResult(
            status="BLOCKED",
            reason_codes=("NO_GOVERNED_PATH_A_TRAINING_CORPUS",),
        )

    try:
        from ...paper.calibration.dual_corpus.consumption import (
            ProtectedCorpusConsumptionError,
            assert_corpus_consumable_for_selection_or_training,
        )

        assert_corpus_consumable_for_selection_or_training(
            corpus_evidence_authority=str(payload.get("corpus_evidence_authority") or ""),
            payload=payload,
            purpose="path_a_training_build",
        )
    except ProtectedCorpusConsumptionError as error:
        return ProductionBuildResult(status="BLOCKED", reason_codes=(str(error),))

    instrument = str(payload.get("target_instrument_id") or "AAPL").strip().upper()
    target = path_a_direction_target(instrument)
    horizon = path_a_horizon()
    training_cutoff_ns = int(payload["training_cutoff_ns"])
    calibration_cutoff_ns = int(payload.get("calibration_cutoff_ns") or training_cutoff_ns)

    try:
        train_rows = _examples_from_manifest(payload)
    except (KeyError, TypeError, ValueError) as error:
        return ProductionBuildResult(status="BLOCKED", reason_codes=(str(error),))

    try:
        model = fit_production_specialist(
            train_rows,
            target=target,
            horizon=horizon,
            training_cutoff_ns=training_cutoff_ns,
        )
    except ProductionTrainingError as error:
        return ProductionBuildResult(status="BLOCKED", reason_codes=(str(error),))
    if model is None:
        return ProductionBuildResult(
            status="BLOCKED",
            reason_codes=("INSUFFICIENT_LABELLED_PRODUCTION_CORPUS",),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_payload = persist_production_specialist_model(model, destination=output_dir / "model")
    model_hash = sha256_bytes(canonical_bytes(model_payload))

    cal_rows = _calibration_examples_from_manifest(payload, target_instrument=instrument)
    if len(cal_rows) < MINIMUM_CALIBRATION_SAMPLES:
        from ..baselines.features import FeatureVectorBuilder
        from .identity import PATH_A_PRODUCTION_FEATURE_SCHEMA

        for index, example in enumerate(train_rows):
            built, diagnostics = FeatureVectorBuilder(PATH_A_PRODUCTION_FEATURE_SCHEMA).extract(
                example.snapshot,
                example.signals,
                allow_degraded=False,
            )
            if built is None or diagnostics:
                continue
            raw_probability = model.predict_probability_up(built)
            cal_rows.append(
                CalibrationExample(
                    raw_fusion_id=f"RFF-hist-{index}",
                    raw_probability=float(raw_probability),
                    target=target,
                    horizon=horizon,
                    scope=example.snapshot.scope,
                    forecast_decision_time_ns=example.snapshot.decision_time_ns,
                    label=example.label,
                    label_available_time_ns=example.label_available_time_ns,
                    fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
                )
            )
    if len(cal_rows) < MINIMUM_CALIBRATION_SAMPLES:
        return ProductionBuildResult(
            status="BLOCKED",
            reason_codes=("INSUFFICIENT_CALIBRATION_SAMPLES",),
            model_id=model.model_id,
            training_dataset_fingerprint=model.training_dataset_fingerprint,
        )

    trained = train_production_calibration(
        cal_rows,
        method=calibration_method,
        available_time_ns=decision_time_ns,
        decision_time_ns=decision_time_ns,
        target=target,
        horizon=horizon,
        fusion_policy_identity=DEFAULT_PRODUCTION_FUSION_POLICY.policy_identity,
        calibration_cutoff_ns=calibration_cutoff_ns,
        mode=mode,
    )
    if not trained.trained or trained.artifact is None:
        code = trained.reason_codes[-1] if trained.reason_codes else "CALIBRATION_UNAVAILABLE"
        return ProductionBuildResult(
            status="BLOCKED",
            reason_codes=(code,),
            model_id=model.model_id,
            training_dataset_fingerprint=model.training_dataset_fingerprint,
        )

    cal_dir = output_dir / "calibration"
    cal_persist = persist_path_a_production_calibration(
        trained.artifact,
        destination=cal_dir,
        mode=mode,
        decision_time_ns=decision_time_ns,
    )
    if not cal_persist.persisted:
        return ProductionBuildResult(
            status="BLOCKED",
            reason_codes=cal_persist.reason_codes,
            model_id=model.model_id,
        )
    cal_hash = sha256_bytes(canonical_bytes(cal_persist.payload or {}))

    contributor_id = None
    contributor_hash = None
    emit_ctx = payload.get("emit_context")
    if isinstance(emit_ctx, Mapping):
        snapshot = SnapshotV1(
            snapshot_id=str(emit_ctx["snapshot_id"]),
            schema_version="1",
            decision_time_ns=int(emit_ctx["decision_time_ns"]),
            scope=_scope_from_manifest(dict(emit_ctx.get("scope") or payload.get("scope") or {})),
            quality=QualitySummary(state=QualityState.GOOD),
        )
        momentum = float(emit_ctx.get("momentum") or 0.0)
        nss = float(emit_ctx.get("net_signed_share") or 0.0)
        signals = _examples_from_manifest(
            {
                **payload,
                "examples": [
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "decision_time_ns": snapshot.decision_time_ns,
                        "label": 1,
                        "label_available_time_ns": snapshot.decision_time_ns + horizon.duration_ns,
                        "momentum": momentum,
                        "net_signed_share": nss,
                    }
                ],
            }
        )[0].signals
        emitted = emit_production_forecast(
            snapshot=snapshot,
            signals=signals,
            model=model,
            target=target,
            horizon=horizon,
            mode=mode,
            as_of_time_ns=decision_time_ns,
        )
        if emitted.emitted and emitted.forecast is not None:
            contrib_dir = output_dir / "contributors"
            persisted = persist_path_a_production_contributor(
                emitted.forecast,
                destination=contrib_dir,
                mode=mode,
            )
            if persisted.persisted:
                contributor_id = str(emitted.forecast.forecast_id)
                contributor_hash = sha256_bytes(canonical_bytes(persisted.payload or {}))

    manifest_hash = _manifest_fingerprint(payload)
    return ProductionBuildResult(
        status="BUILT",
        reason_codes=("BUILT",),
        model_id=model.model_id,
        training_dataset_fingerprint=model.training_dataset_fingerprint,
        calibration_model_id=trained.artifact.calibration_model_id,
        contributor_forecast_id=contributor_id,
        artifact_hashes={
            "training_manifest_sha256": manifest_hash,
            "model_payload_sha256": model_hash,
            "calibration_payload_sha256": cal_hash,
            **({"contributor_payload_sha256": contributor_hash} if contributor_hash else {}),
        },
    )


__all__ = [
    "ProductionBuildResult",
    "build_path_a_production_artifacts",
    "load_governed_training_manifest",
]
