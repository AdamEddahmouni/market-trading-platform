"""Minimal SnapshotV1 for congressional PTR ingress / detector hot path."""

from __future__ import annotations

from ..contracts import (
    ContractKind,
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SnapshotV1,
)
from ..contracts.event import EventV1


def build_congressional_disclosure_ingress_snapshot(
    event: EventV1,
    *,
    decision_time_ns: int,
    snapshot_id: str | None = None,
) -> SnapshotV1:
    instrument = event.instrument_id or ""
    scope = IntelligenceScope(instrument_ids=(instrument,) if instrument else ())
    sid = snapshot_id or f"SNAP-PTR-ING-{event.event_id}"
    return SnapshotV1(
        snapshot_id=sid,
        schema_version="1",
        decision_time_ns=decision_time_ns,
        scope=scope,
        quality=QualitySummary(state=event.quality.state, flags=event.quality.flags),
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=event.event_id),),
    )


__all__ = ["build_congressional_disclosure_ingress_snapshot"]
