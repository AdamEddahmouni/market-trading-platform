"""Compatibility adapters between shadow P6 records and intelligence contracts."""

from __future__ import annotations

from typing import Any

from ...shadow.records import (
    ShadowOutcomeLabel,
    ShadowPredictionRecord,
    ShadowRunManifest,
)
from .common import (
    ContractKind,
    ContractReference,
    Direction,
    ForecastEstimate,
    ForecastTarget,
    IntelligenceScope,
    OutcomeResolutionStatus,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
)
from .forecast import ForecastV1
from .outcome import OutcomeV1
from .run_manifest import RunManifestV1


def shadow_prediction_to_forecast_v1(record: ShadowPredictionRecord) -> ForecastV1:
    """Map immutable shadow prediction to canonical ForecastV1 without mutating shadow storage."""
    if record.abstained:
        raise ValueError("ABSTAINED_SHADOW_PREDICTION_NOT_FORECAST")
    instrument_id = record.instrument_id
    target = ForecastTarget(
        target_kind="binary_positive_class",
        instrument_id=instrument_id,
        parameters={"threshold": 0.5, "metric": "predicted_positive"},
    )
    estimate = ForecastEstimate(
        estimate_kind="classification_probability",
        probability=record.predicted_probability,
        raw_score=record.predicted_probability,
    )
    scope = IntelligenceScope(instrument_ids=(instrument_id,))
    quality = QualitySummary(state=QualityState.GOOD)
    return ForecastV1(
        forecast_id=record.prediction_id,
        schema_version="1",
        scope=scope,
        decision_time_ns=record.decision_time_ns,
        snapshot_id=record.pit_snapshot_ref or f"shadow-run:{record.run_id}",
        target=target,
        horizon=TimeHorizonNs(duration_ns=record.horizon_ns),
        estimate=estimate,
        quality=quality,
        resolve_time_ns=record.decision_time_ns + record.horizon_ns,
        metadata={
            "shadow_run_id": record.run_id,
            "shadow_payload": dict(record.payload),
            "adapter": "shadow_prediction_to_forecast_v1",
        },
    )


def forecast_v1_to_shadow_prediction_fields(forecast: ForecastV1) -> dict[str, Any]:
    """Extract shadow-compatible prediction fields from ForecastV1 for dual-write paths."""
    instrument_ids = forecast.scope.instrument_ids
    if len(instrument_ids) != 1:
        raise ValueError("FORECAST_SCOPE_REQUIRES_SINGLE_INSTRUMENT_FOR_SHADOW_ADAPTER")
    probability = forecast.estimate.probability
    if probability is None:
        raise ValueError("FORECAST_PROBABILITY_REQUIRED_FOR_SHADOW_ADAPTER")
    return {
        "instrument_id": instrument_ids[0],
        "decision_time_ns": forecast.decision_time_ns,
        "horizon_ns": forecast.horizon.duration_ns,
        "predicted_probability": probability,
        "pit_snapshot_ref": forecast.snapshot_id,
        "payload": dict(forecast.metadata.get("shadow_payload") or forecast.metadata),
    }


def shadow_label_to_outcome_v1(
    label: ShadowOutcomeLabel,
    *,
    forecast_id: str | None = None,
) -> OutcomeV1:
    """Map shadow outcome label to canonical OutcomeV1."""
    linked_forecast_id = forecast_id or label.prediction_id
    realized_direction = Direction.LONG if label.observed_positive else Direction.SHORT
    realized_return: float | None = None
    if label.observed_return_bps is not None:
        realized_return = float(label.observed_return_bps) / 10000.0
    return OutcomeV1(
        outcome_id=label.label_id,
        schema_version="1",
        forecast_id=linked_forecast_id,
        adjudicated_at_ns=label.label_time_ns,
        resolution_status=OutcomeResolutionStatus.SETTLED,
        quality=QualitySummary(state=QualityState.GOOD),
        start_observation={"decision_time_ns": label.label_time_ns - 1},
        end_observation={
            "label_time_ns": label.label_time_ns,
            "available_time_ns": label.available_time_ns,
        },
        realized_return=realized_return,
        realized_direction=realized_direction,
        lineage_refs=(
            ContractReference(kind=ContractKind.FORECAST.value, id=linked_forecast_id),
        ),
        metadata={
            "shadow_run_id": label.run_id,
            "label_source": label.label_source,
            "labeler_version": label.labeler_version,
            "adapter": "shadow_label_to_outcome_v1",
        },
    )


def shadow_manifest_to_run_manifest_v1(
    manifest: ShadowRunManifest,
    *,
    data_mode: str | None = "FIXTURE_REPLAY",
    execution_mode: str | None = "NONE",
    execution_authority: str | None = "BLOCKED",
    code_revision: str | None = None,
) -> RunManifestV1:
    """Wrap ShadowRunManifest as RunManifestV1 preserving shadow identity."""
    return RunManifestV1(
        run_id=manifest.run_id,
        schema_version="1",
        created_at_ns=manifest.created_at_ns,
        quality=QualitySummary(state=QualityState.GOOD),
        run_window_start_ns=manifest.eval_window_start_ns,
        run_window_end_ns=manifest.eval_window_end_ns,
        data_mode=data_mode,
        execution_mode=execution_mode,
        execution_authority=execution_authority,
        code_revision=code_revision,
        config_identity=manifest.manifest_hash,
        strategy_version=manifest.strategy_version,
        prediction_version=manifest.prediction_version,
        provider_config_refs=tuple(dict(item) for item in manifest.data_window_refs),
        environment={
            "shadow_schema": "1.0.0",
            "train_window_end_ns": manifest.train_window_end_ns,
            "universe": list(manifest.universe),
        },
        metadata={
            "shadow_config": dict(manifest.config),
            "adapter": "shadow_manifest_to_run_manifest_v1",
        },
    )


__all__ = [
    "forecast_v1_to_shadow_prediction_fields",
    "shadow_label_to_outcome_v1",
    "shadow_manifest_to_run_manifest_v1",
    "shadow_prediction_to_forecast_v1",
]
