"""BUILD 09 replay persistence for SEC insider vertical (canonical identity)."""

from __future__ import annotations

from ...contracts import DetectionV1, EventV1, SnapshotV1
from ...persistence import IntelligenceRepository, RepositoryPutResult
from ...routing import DetectionFrame, EventDetectorEngine
from .adapters import accepts_sec_insider_event
from .canonical_snapshot import build_sec_insider_canonical_detection_snapshot
from .persistence import persist_sec_insider_vertical
from .pipeline import run_sec_insider_vertical


def persist_sec_insider_from_detection_frame(
    repository: IntelligenceRepository,
    engine: EventDetectorEngine,
    frame: DetectionFrame,
) -> tuple[DetectionV1 | None, tuple[RepositoryPutResult, RepositoryPutResult] | None]:
    """Run BUILD 09 SEC path and persist canonical detection/evidence when emitted."""
    result = engine.detect(frame)
    insider_detections = [
        row
        for row in result.detections
        if row.semantic_event_type.value == "SEC_INSIDER_DISCLOSURE"
    ]
    if not insider_detections:
        return None, None
    events = [row for row in frame.events if accepts_sec_insider_event(row)]
    if len(events) != 1:
        return insider_detections[0], None
    event = events[0]
    vertical = run_sec_insider_vertical(event=event, snapshot=frame.snapshot)
    if not vertical.ok or vertical.detection is None:
        return insider_detections[0], None
    snapshot = build_sec_insider_canonical_detection_snapshot(event)
    puts = persist_sec_insider_vertical(repository, vertical, snapshot=snapshot)
    return vertical.detection, puts


__all__ = ["persist_sec_insider_from_detection_frame"]
