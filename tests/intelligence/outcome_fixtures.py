"""Shared BUILD 15 outcome settlement fixtures."""

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
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SnapshotV1,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.test_baseline_fixtures import HORIZON_5M, INSTRUMENT, T
from tests.intelligence.test_signal_fixtures import trade_event

ONE_MIN = 60 * 1_000_000_000
QUALITY = QualitySummary(state=QualityState.GOOD)
SCOPE = IntelligenceScope(instrument_ids=(INSTRUMENT,))


def seed_anchor_trade(
    repo: InMemoryIntelligenceRepository,
    *,
    price: float = 100.0,
    event_time_ns: int = T,
    available_time_ns: int | None = None,
    event_id: str = "anchor-trade",
) -> None:
    repo.put_event(
        trade_event(
            event_id,
            event_time_ns=event_time_ns,
            price=price,
            quantity=10,
            available_time_ns=available_time_ns or event_time_ns,
        )
    )


def seed_terminal_trade(
    repo: InMemoryIntelligenceRepository,
    *,
    price: float,
    event_time_ns: int,
    available_time_ns: int | None = None,
    event_id: str = "terminal-trade",
) -> None:
    repo.put_event(
        trade_event(
            event_id,
            event_time_ns=event_time_ns,
            price=price,
            quantity=10,
            available_time_ns=available_time_ns or event_time_ns,
        )
    )


def baseline_control_forecast(
    repo: InMemoryIntelligenceRepository,
    *,
    snapshot_id: str = "snap-control",
    anchor_price: float = 100.0,
) -> ForecastV1:
    snapshot = SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=T,
        scope=SCOPE,
        quality=QUALITY,
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id="anchor-trade"),),
    )
    seed_anchor_trade(repo, price=anchor_price)
    repo.put_snapshot(snapshot)
    engine = BaselinePredictionEngine()
    result = engine.predict(
        BaselinePredictionRequest(
            snapshot=snapshot,
            signals=(),
            target=direction_up_down_target(INSTRUMENT),
            horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
        ),
        AlwaysUpBaseline().bind_target(direction_up_down_target(INSTRUMENT)),
    )
    assert result.forecast is not None
    repo.put_forecast(result.forecast)
    return result.forecast


def synthetic_final_forecast(
    repo: InMemoryIntelligenceRepository,
    *,
    forecast_id: str = "fc-final-synthetic",
    probability: float = 0.72,
    anchor_price: float = 100.0,
) -> ForecastV1:
    snapshot = SnapshotV1(
        snapshot_id="snap-final",
        schema_version="1",
        decision_time_ns=T,
        scope=SCOPE,
        quality=QUALITY,
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id="anchor-trade"),),
    )
    seed_anchor_trade(repo, price=anchor_price)
    repo.put_snapshot(snapshot)
    from market_platform_foundation.intelligence.contracts.common import ForecastEstimate

    forecast = ForecastV1(
        forecast_id=forecast_id,
        schema_version="1",
        scope=SCOPE,
        decision_time_ns=T,
        snapshot_id=snapshot.snapshot_id,
        target=direction_up_down_target(INSTRUMENT),
        horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
            calibrated_probability=probability,
        ),
        quality=QUALITY,
        metadata={
            "contributor_role": "PRODUCTION",
            "forecast_stage": "FINAL_FUSED_CALIBRATED",
            "calibration_status": "CALIBRATED",
        },
    )
    repo.put_forecast(forecast)
    return forecast


def target_time_for(forecast: ForecastV1) -> int:
    return forecast.decision_time_ns + forecast.horizon.duration_ns


def cutoff_for(forecast: ForecastV1) -> int:
    target = target_time_for(forecast)
    return target + ONE_MIN


__all__ = [
    "HORIZON_5M",
    "INSTRUMENT",
    "ONE_MIN",
    "QUALITY",
    "SCOPE",
    "T",
    "baseline_control_forecast",
    "cutoff_for",
    "seed_anchor_trade",
    "seed_terminal_trade",
    "synthetic_final_forecast",
    "target_time_for",
]
