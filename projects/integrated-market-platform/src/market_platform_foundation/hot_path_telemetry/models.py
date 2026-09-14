"""Hot-path telemetry value types and timestamp vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

HOT_PATH_TIMESTAMP_NAMES: tuple[str, ...] = (
    "source_event_at",
    "provider_received_at",
    "imp_received_at",
    "normalized_at",
    "router_dispatched_at",
    "detected_at",
    "opportunity_created_at",
    "operator_surfaced_at",
)


class TimestampExerciseClass(StrEnum):
    MEASURED = "MEASURED"
    NOT_EXERCISED = "NOT_EXERCISED"


def timestamp_exercise_classes() -> dict[str, TimestampExerciseClass]:
    """Declared measurement coverage for fixture/replay baseline (not live)."""
    return {
        "source_event_at": TimestampExerciseClass.MEASURED,
        "provider_received_at": TimestampExerciseClass.MEASURED,
        "imp_received_at": TimestampExerciseClass.MEASURED,
        "normalized_at": TimestampExerciseClass.MEASURED,
        "router_dispatched_at": TimestampExerciseClass.MEASURED,
        "detected_at": TimestampExerciseClass.MEASURED,
        "opportunity_created_at": TimestampExerciseClass.NOT_EXERCISED,
        "operator_surfaced_at": TimestampExerciseClass.NOT_EXERCISED,
    }


@dataclass(frozen=True, slots=True)
class HotPathQualityCounters:
    received: int = 0
    normalized: int = 0
    pit_accepted: int = 0
    pit_rejected: int = 0
    duplicates: int = 0
    conflicts: int = 0
    stale: int = 0
    unknown_identity: int = 0
    entitlement_blocked: int = 0
    parser_failures: int = 0
    router_failures: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "received": self.received,
            "normalized": self.normalized,
            "pit_accepted": self.pit_accepted,
            "pit_rejected": self.pit_rejected,
            "duplicates": self.duplicates,
            "conflicts": self.conflicts,
            "stale": self.stale,
            "unknown_identity": self.unknown_identity,
            "entitlement_blocked": self.entitlement_blocked,
            "parser_failures": self.parser_failures,
            "router_failures": self.router_failures,
        }


@dataclass(frozen=True, slots=True)
class ReplayLatencyBaselineDocument:
    schema_version: str
    artifact_type: str
    measurement_class: str
    fixture_path: str
    fixture_sha256: str
    timestamp_exercise: dict[str, str]
    timestamp_presence: dict[str, dict[str, int]]
    latency_segments_ns: dict[str, dict[str, Any]]
    quality_counters: dict[str, int]
    rt01_span_count: int
    replay_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "measurement_class": self.measurement_class,
            "fixture_path": self.fixture_path,
            "fixture_sha256": self.fixture_sha256,
            "timestamp_exercise": dict(self.timestamp_exercise),
            "timestamp_presence": dict(self.timestamp_presence),
            "latency_segments_ns": dict(self.latency_segments_ns),
            "quality_counters": dict(self.quality_counters),
            "rt01_span_count": self.rt01_span_count,
            "metadata": dict(self.metadata),
        }
        if self.replay_run_id is not None:
            body["replay_run_id"] = self.replay_run_id
        return body


__all__ = [
    "HOT_PATH_TIMESTAMP_NAMES",
    "HotPathQualityCounters",
    "ReplayLatencyBaselineDocument",
    "TimestampExerciseClass",
    "timestamp_exercise_classes",
]
