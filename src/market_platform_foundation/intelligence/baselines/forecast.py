"""ForecastV1 construction for baseline predictions (BUILD 08)."""

from __future__ import annotations

import math

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractKind,
    ContractReference,
    ForecastEstimate,
    ForecastTarget,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
    validate_probability,
)
from ..contracts.forecast import ForecastV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from .errors import BaselinePredictionError
from .identity import derive_forecast_id
from ..fusion.types import CONTROL_FORECAST_STAGE, ForecastContributorRole
from .types import BaselineClassLabel, BaselineModelDescriptor, BaselineModelOutput


def _derive_quality(
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...],
) -> QualitySummary:
    states = [snapshot.quality.state, *(signal.quality.state for signal in signals)]
    if QualityState.INVALID in states:
        return QualitySummary(state=QualityState.INVALID, flags=snapshot.quality.flags)
    if QualityState.DEGRADED in states:
        flags = tuple(sorted(set(snapshot.quality.flags)))
        return QualitySummary(state=QualityState.DEGRADED, flags=flags)
    return QualitySummary(state=QualityState.GOOD, flags=())


def _validate_model_output(output: BaselineModelOutput) -> None:
    if output.abstain:
        return
    if output.raw_probability_up is not None:
        if not math.isfinite(output.raw_probability_up):
            raise BaselinePredictionError("MODEL_OUTPUT_NOT_FINITE")
        validate_probability(output.raw_probability_up)
    if output.raw_score is not None and not math.isfinite(output.raw_score):
        raise BaselinePredictionError("MODEL_OUTPUT_NOT_FINITE")


def build_forecast_v1(
    *,
    snapshot: SnapshotV1,
    source_signals: tuple[SignalV1, ...],
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    model_output: BaselineModelOutput,
    descriptor: BaselineModelDescriptor,
) -> ForecastV1:
    if model_output.abstain:
        raise BaselinePredictionError("CANNOT_BUILD_FORECAST_FOR_ABSTENTION")
    _validate_model_output(model_output)
    if model_output.raw_probability_up is None:
        raise BaselinePredictionError("PROBABILITY_REQUIRED_FOR_FORECAST")

    signal_ids = tuple(sorted(signal.signal_id for signal in source_signals))
    forecast_id = derive_forecast_id(
        snapshot_id=snapshot.snapshot_id,
        source_signal_ids=signal_ids,
        model_id=descriptor.model_id,
        target=target,
        horizon=horizon,
    )
    lineage_refs = tuple(
        ContractReference(kind=ContractKind.SIGNAL.value, id=signal_id)
        for signal_id in signal_ids
    )
    predicted_class = model_output.predicted_class
    if predicted_class is None:
        predicted_class = (
            BaselineClassLabel.UP
            if model_output.raw_probability_up >= 0.5
            else BaselineClassLabel.DOWN
        )

    return ForecastV1(
        forecast_id=forecast_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=snapshot.scope,
        decision_time_ns=snapshot.decision_time_ns,
        snapshot_id=snapshot.snapshot_id,
        target=target,
        horizon=horizon,
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=model_output.raw_probability_up,
            raw_score=model_output.raw_score,
            calibrated_probability=None,
        ),
        quality=_derive_quality(snapshot, source_signals),
        resolve_time_ns=snapshot.decision_time_ns + horizon.duration_ns,
        component_lineage=ComponentLineage(
            component_id=descriptor.model_kind,
            component_version=descriptor.implementation_version,
            model_id=descriptor.model_id,
            model_version=descriptor.implementation_version,
        ),
        lineage_refs=lineage_refs,
        metadata={
            "calibration_status": "UNCALIBRATED",
            "contributor_role": ForecastContributorRole.CONTROL.value,
            "forecast_stage": CONTROL_FORECAST_STAGE,
            "baseline_model_kind": descriptor.model_kind,
            "predicted_direction": predicted_class.value,
            "feature_schema_fingerprint": descriptor.feature_schema_fingerprint,
            "training_dataset_fingerprint": descriptor.training_dataset_fingerprint,
            "training_cutoff_ns": descriptor.training_cutoff_ns,
            "parameter_fingerprint": descriptor.parameter_fingerprint,
        },
    )


__all__ = ["build_forecast_v1"]
