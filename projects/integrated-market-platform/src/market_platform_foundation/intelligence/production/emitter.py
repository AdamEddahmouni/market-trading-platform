"""Fail-closed Path A PRODUCTION ForecastV1 emitter.

Emits an uncalibrated ``PRODUCTION_RAW`` contributor from a PIT-legal
fitted specialist. This module does not mint a probability from a quote print,
does not construct CONTROL baselines, and does not wrap a research score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..baselines.features import FeatureVectorBuilder
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
from ..fusion.types import ForecastContributorRole, PRODUCTION_FORECAST_STAGE
from .identity import (
    PATH_A_FAMILY_KEY,
    PATH_A_PRODUCTION_FEATURE_SCHEMA,
    PRODUCTION_COMPONENT_ID,
    derive_forecast_id,
    matches_path_a_identity,
)
from .model import ProductionSpecialistModel

STATUS_EMITTED_PRODUCTION_RAW = "EMITTED_PRODUCTION_RAW"
STATUS_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"
STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"
ALLOWED_MODES = frozenset({"demo", "paper"})
FORBIDDEN_LIVE_MODES = frozenset({"live", "actual_live"})


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()


def _derive_quality(snapshot: SnapshotV1, signals: tuple[SignalV1, ...]) -> QualitySummary:
    states = [snapshot.quality.state, *(signal.quality.state for signal in signals)]
    if QualityState.INVALID in states:
        return QualitySummary(state=QualityState.INVALID, flags=snapshot.quality.flags)
    if QualityState.DEGRADED in states:
        flags = tuple(sorted(set(snapshot.quality.flags)))
        return QualitySummary(state=QualityState.DEGRADED, flags=flags)
    return QualitySummary(state=QualityState.GOOD, flags=())


@dataclass(frozen=True, slots=True)
class ProductionEmitResult:
    status: str
    reason_codes: tuple[str, ...]
    forecast: ForecastV1 | None = None

    @property
    def emitted(self) -> bool:
        return self.status == STATUS_EMITTED_PRODUCTION_RAW and self.forecast is not None


def _unavailable(*reason_codes: str) -> ProductionEmitResult:
    codes = tuple(dict.fromkeys((STATUS_FORECAST_UNAVAILABLE, *reason_codes)))
    return ProductionEmitResult(status=STATUS_FORECAST_UNAVAILABLE, reason_codes=codes)


def emit_production_forecast(
    *,
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...] | list[SignalV1],
    model: ProductionSpecialistModel,
    target: ForecastTarget,
    horizon: TimeHorizonNs,
    mode: str,
    as_of_time_ns: int | None = None,
) -> ProductionEmitResult:
    """Emit one Path A PRODUCTION_RAW ForecastV1 from a pre-fitted specialist."""

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        return ProductionEmitResult(
            status=STATUS_LIVE_FORBIDDEN,
            reason_codes=("LIVE_SCAN_CALLER_FORBIDDEN",),
        )
    if mode_n not in ALLOWED_MODES:
        return _unavailable("MODE_NOT_PAPER_OR_DEMO")

    identity_reasons = matches_path_a_identity(target=target, horizon=horizon)
    if identity_reasons:
        return _unavailable(*identity_reasons)
    if target.target_kind != model.target.target_kind or target.instrument_id != model.target.instrument_id:
        return _unavailable("TARGET_MISMATCH")
    if horizon.duration_ns != model.horizon.duration_ns:
        return _unavailable("HORIZON_MISMATCH")
    if model.training_cutoff_ns >= snapshot.decision_time_ns:
        return _unavailable("MODEL_NOT_YET_AVAILABLE")
    if as_of_time_ns is not None and snapshot.decision_time_ns > as_of_time_ns:
        return _unavailable("FORECAST_PIT_VIOLATION")
    if snapshot.quality.state == QualityState.INVALID:
        return _unavailable("SNAPSHOT_QUALITY_REJECTED")

    vector, diagnostics = FeatureVectorBuilder(PATH_A_PRODUCTION_FEATURE_SCHEMA).extract(
        snapshot,
        signals,
        allow_degraded=False,
    )
    if vector is None or diagnostics:
        codes = tuple(item.code.value for item in diagnostics) or ("MISSING_FEATURE",)
        return _unavailable("FEATURE_EXTRACTION_FAILED", *codes)

    try:
        probability = model.predict_probability_up(vector)
        validate_probability(probability)
    except Exception:
        return _unavailable("MODEL_OUTPUT_INVALID")
    if not math.isfinite(probability):
        return _unavailable("MODEL_OUTPUT_NOT_FINITE")

    source_ids = tuple(sorted(signal.signal_id for signal in vector.source_signals))
    forecast_id = derive_forecast_id(
        snapshot_id=snapshot.snapshot_id,
        source_signal_ids=source_ids,
        model_id=model.model_id,
        target=target,
        horizon=horizon,
    )
    quality = _derive_quality(snapshot, vector.source_signals)
    if quality.state == QualityState.INVALID:
        return _unavailable("QUALITY_REJECTED")
    if quality.state == QualityState.DEGRADED:
        return _unavailable("DEGRADED_FEATURE_REJECTED")

    forecast = ForecastV1(
        forecast_id=forecast_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=snapshot.scope,
        decision_time_ns=snapshot.decision_time_ns,
        snapshot_id=snapshot.snapshot_id,
        target=target,
        horizon=horizon,
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
            raw_score=probability,
            calibrated_probability=None,
        ),
        quality=quality,
        resolve_time_ns=snapshot.decision_time_ns + horizon.duration_ns,
        component_lineage=ComponentLineage(
            component_id=PRODUCTION_COMPONENT_ID,
            component_version=model.implementation_version,
            model_id=model.model_id,
            model_version=model.implementation_version,
        ),
        lineage_refs=tuple(
            ContractReference(kind=ContractKind.SIGNAL.value, id=signal_id) for signal_id in source_ids
        ),
        metadata={
            "calibration_status": "UNCALIBRATED",
            "contributor_role": ForecastContributorRole.PRODUCTION.value,
            "forecast_stage": PRODUCTION_FORECAST_STAGE,
            "forecast_family_key": PATH_A_FAMILY_KEY,
            "model_kind": model.model_kind,
            "training_cutoff_ns": model.training_cutoff_ns,
            "training_dataset_fingerprint": model.training_dataset_fingerprint,
            "parameter_fingerprint": model.parameter_fingerprint,
            "feature_schema_fingerprint": model.feature_schema_fingerprint,
        },
    )
    return ProductionEmitResult(
        status=STATUS_EMITTED_PRODUCTION_RAW,
        reason_codes=(STATUS_EMITTED_PRODUCTION_RAW,),
        forecast=forecast,
    )


__all__ = [
    "ALLOWED_MODES",
    "FORBIDDEN_LIVE_MODES",
    "ProductionEmitResult",
    "STATUS_EMITTED_PRODUCTION_RAW",
    "STATUS_FORECAST_UNAVAILABLE",
    "STATUS_LIVE_FORBIDDEN",
    "emit_production_forecast",
]
