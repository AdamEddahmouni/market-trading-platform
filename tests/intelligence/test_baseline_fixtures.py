"""Shared BUILD 08 baseline test fixtures."""

from __future__ import annotations

from market_platform_foundation.intelligence.baselines import direction_up_down_target
from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SnapshotV1,
    TimeHorizonNs,
    SignalV1,
)
from tests.intelligence.test_persistence_fixtures import DECISION_NS, INSTRUMENT, QUALITY, SCOPE

T = DECISION_NS
WINDOW = 300 * 1_000_000_000
HORIZON_5M = 5 * 60 * 1_000_000_000


def sample_snapshot(snapshot_id: str = "snap-baseline-1") -> SnapshotV1:
    return SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=T,
        scope=SCOPE,
        quality=QUALITY,
    )


def momentum_signal(
    *,
    snapshot_id: str,
    value: float,
    signal_id: str = "sig-momentum",
    window_ns: int = WINDOW,
) -> SignalV1:
    return SignalV1(
        signal_id=signal_id,
        schema_version="1",
        signal_type="momentum_simple",
        scope=SCOPE,
        as_of_time_ns=T,
        value=value,
        quality=QUALITY,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
        calculation_window=TimeHorizonNs(duration_ns=window_ns),
        calculation_lineage={
            "calculator_id": "momentum-calculator",
            "calculator_version": "1",
        },
        unit="decimal_return",
    )


def statistical_feature_signal(
    *,
    snapshot_id: str,
    signal_type: str,
    value: float,
    signal_id: str,
    window_ns: int | None = WINDOW,
    calculator_id: str,
) -> SignalV1:
    return SignalV1(
        signal_id=signal_id,
        schema_version="1",
        signal_type=signal_type,
        scope=SCOPE,
        as_of_time_ns=T,
        value=value,
        quality=QUALITY,
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
        calculation_window=TimeHorizonNs(duration_ns=window_ns) if window_ns is not None else None,
        calculation_lineage={"calculator_id": calculator_id, "calculator_version": "1"},
    )


def default_target():
    return direction_up_down_target(INSTRUMENT)


def default_horizon():
    return TimeHorizonNs(duration_ns=HORIZON_5M)


__all__ = [
    "HORIZON_5M",
    "INSTRUMENT",
    "QUALITY",
    "SCOPE",
    "T",
    "WINDOW",
    "default_horizon",
    "default_target",
    "momentum_signal",
    "sample_snapshot",
    "statistical_feature_signal",
]
