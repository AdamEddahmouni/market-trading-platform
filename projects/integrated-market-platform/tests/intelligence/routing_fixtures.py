"""Deterministic BUILD 09 test fixtures."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    EventV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SignalV1,
    SnapshotV1,
    SourceReference,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.quality import (
    DecisionAction,
    IntelligenceCapability,
    QualityAssessment,
    QualityDecision,
)

T = 1_700_000_000_000_000_000
WINDOW_NS = 300 * 1_000_000_000
SCOPE = IntelligenceScope(instrument_ids=("US:XYZ",))


def snapshot(
    snapshot_id: str,
    *,
    decision_time_ns: int = T,
    event_ids: tuple[str, ...] = (),
    quality: QualityState = QualityState.GOOD,
) -> SnapshotV1:
    return SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=decision_time_ns,
        scope=SCOPE,
        quality=QualitySummary(state=quality),
        source_event_refs=tuple(
            ContractReference(kind=ContractKind.EVENT.value, id=event_id)
            for event_id in event_ids
        ),
    )


def signal(
    snapshot_record: SnapshotV1,
    signal_id: str,
    signal_type: str,
    value: float,
    *,
    window_ns: int | None = None,
    quality: QualityState = QualityState.GOOD,
) -> SignalV1:
    lineage = {
        "calculator_id": "cvd-calculator" if signal_type == "net_signed_share" else "spread-calculator",
        "calculator_version": "1",
    }
    return SignalV1(
        signal_id=signal_id,
        schema_version="1",
        signal_type=signal_type,
        scope=SCOPE,
        as_of_time_ns=snapshot_record.decision_time_ns,
        value=value,
        quality=QualitySummary(state=quality),
        source_snapshot_ref=ContractReference(
            kind=ContractKind.SNAPSHOT.value,
            id=snapshot_record.snapshot_id,
        ),
        calculation_window=TimeHorizonNs(window_ns) if window_ns is not None else None,
        calculation_lineage=lineage,
    )


def event(
    snapshot_record: SnapshotV1,
    event_id: str,
    event_type: str,
    payload: dict[str, object],
    *,
    quality: QualityState = QualityState.GOOD,
) -> EventV1:
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type=event_type,
        event_time_ns=snapshot_record.decision_time_ns,
        available_time_ns=snapshot_record.decision_time_ns,
        payload=dict(payload),
        quality=QualitySummary(state=quality),
        source=SourceReference(
            provider_id="fixture",
            source_type=event_type,
            source_record_id=event_id,
        ),
        instrument_id="US:XYZ",
    )


def quality_decision(
    *capabilities: IntelligenceCapability,
    action: DecisionAction = DecisionAction.USE,
    decision_time_ns: int = T,
    degraded: tuple[IntelligenceCapability, ...] = (),
) -> QualityDecision:
    quality_state = QualityState.GOOD if action == DecisionAction.USE and not degraded else QualityState.DEGRADED
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=action,
        quality_state=quality_state,
        assessment=assessment,
        satisfied_requirements=tuple(capabilities),
        degraded_requirements=degraded,
    )
