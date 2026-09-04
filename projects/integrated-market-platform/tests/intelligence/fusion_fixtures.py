"""Shared BUILD 14 fusion test fixtures."""

from __future__ import annotations

from market_platform_foundation.intelligence.baselines import (
    AlwaysUpBaseline,
    BaselinePredictionEngine,
    BaselinePredictionRequest,
    direction_up_down_target,
)
from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    ForecastV1,
    SnapshotV1,
    ComponentLineage,
    ForecastEstimate,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.fusion import (
    CONTROL_FORECAST_STAGE,
    ForecastContributorRole,
    FusionContributorRef,
    build_contributor_ref,
)
from tests.intelligence.test_baseline_fixtures import (
    HORIZON_5M,
    INSTRUMENT,
    QUALITY,
    SCOPE,
    T,
    default_horizon,
    default_target,
    momentum_signal,
    sample_snapshot,
)


def synthetic_production_forecast(
    *,
    forecast_id: str,
    snapshot: SnapshotV1,
    probability: float,
    signal_ids: tuple[str, ...],
    forecast_family_key: str,
    target=None,
    horizon=None,
) -> ForecastV1:
    target = target or default_target()
    horizon = horizon or default_horizon()
    lineage_refs = tuple(
        ContractReference(kind=ContractKind.SIGNAL.value, id=signal_id) for signal_id in sorted(signal_ids)
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
            probability=probability,
            raw_score=probability,
            calibrated_probability=None,
        ),
        quality=QUALITY,
        resolve_time_ns=snapshot.decision_time_ns + horizon.duration_ns,
        component_lineage=ComponentLineage(
            component_id="synthetic-production",
            component_version="1",
            model_id=f"SYNMOD-{forecast_family_key}",
            model_version="1",
        ),
        lineage_refs=lineage_refs,
        metadata={
            "contributor_role": ForecastContributorRole.PRODUCTION.value,
            "forecast_family_key": forecast_family_key,
            "forecast_stage": "PRODUCTION_RAW",
            "calibration_status": "UNCALIBRATED",
        },
    )


def baseline_control_forecast(snapshot: SnapshotV1 | None = None):
    snapshot = snapshot or sample_snapshot()
    signal = momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.01)
    engine = BaselinePredictionEngine()
    result = engine.predict(
        BaselinePredictionRequest(
            snapshot=snapshot,
            signals=(signal,),
            target=default_target(),
            horizon=default_horizon(),
        ),
        AlwaysUpBaseline().bind_target(default_target()),
    )
    assert result.forecast is not None
    return result.forecast


def production_contributor(forecast: ForecastV1, *, weight: float = 1.0, family_key: str | None = None) -> FusionContributorRef:
    return build_contributor_ref(
        forecast,
        role=ForecastContributorRole.PRODUCTION,
        contributor_weight=weight,
        forecast_family_key=family_key or forecast.metadata.get("forecast_family_key"),
    )


def control_contributor(forecast: ForecastV1) -> FusionContributorRef:
    return build_contributor_ref(forecast, role=ForecastContributorRole.CONTROL)


__all__ = [
    "HORIZON_5M",
    "INSTRUMENT",
    "QUALITY",
    "SCOPE",
    "T",
    "baseline_control_forecast",
    "control_contributor",
    "default_horizon",
    "default_target",
    "production_contributor",
    "sample_snapshot",
    "synthetic_production_forecast",
]
