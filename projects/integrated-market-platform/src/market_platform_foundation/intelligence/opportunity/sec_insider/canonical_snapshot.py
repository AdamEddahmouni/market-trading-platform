"""Canonical SnapshotV1 anchor for SEC insider DetectionV1 / EvidenceV1 identity.

Ingress and BUILD 09 replay may observe the same EventV1 on different frame
snapshots. Detection identity hashes ``source_snapshot_id``; this module fixes
one event-scoped canonical snapshot so both paths derive the same DetectionV1.
"""

from __future__ import annotations

from ...contracts import (
    ContractKind,
    ContractReference,
    EventV1,
    IntelligenceScope,
    QualitySummary,
    SnapshotV1,
)

CANONICAL_SNAPSHOT_ID_PREFIX = "SNAP-SEC-CAN-"


def sec_insider_canonical_snapshot_id(event_id: str) -> str:
    return f"{CANONICAL_SNAPSHOT_ID_PREFIX}{event_id}"


def sec_insider_canonical_decision_time_ns(event: EventV1) -> int:
    """Earliest lawful PIT decision time for disclosure detection (BUILD 09 / ingress)."""
    return event.available_time_ns + 1


def build_sec_insider_canonical_detection_snapshot(event: EventV1) -> SnapshotV1:
    instrument = event.instrument_id or ""
    scope = IntelligenceScope(instrument_ids=(instrument,) if instrument else ())
    return SnapshotV1(
        snapshot_id=sec_insider_canonical_snapshot_id(event.event_id),
        schema_version="1",
        decision_time_ns=sec_insider_canonical_decision_time_ns(event),
        scope=scope,
        quality=QualitySummary(state=event.quality.state, flags=event.quality.flags),
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=event.event_id),),
    )


__all__ = [
    "CANONICAL_SNAPSHOT_ID_PREFIX",
    "build_sec_insider_canonical_detection_snapshot",
    "sec_insider_canonical_decision_time_ns",
    "sec_insider_canonical_snapshot_id",
]
