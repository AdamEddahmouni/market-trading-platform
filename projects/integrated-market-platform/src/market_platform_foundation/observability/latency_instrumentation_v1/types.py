"""Latency instrumentation v1 value types.

Timestamp definitions, domains, and UNAVAILABLE stages: see COVERAGE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LatencyStageId(StrEnum):
    NORMALIZATION_COMPLETED = "normalization_completed"
    PIT_COMPLETED = "pit_completed"
    DETECTOR_STARTED = "detector_started"
    DETECTOR_COMPLETED = "detector_completed"
    OPPORTUNITY_PERSISTED = "opportunity_persisted"
    RANK_GENERATED = "rank_generated"
    API_PAYLOAD_GENERATED = "api_payload_generated"


class EligibilityClockId(StrEnum):
    SOURCE_PUBLICATION = "source_publication"
    PROVIDER_RETRIEVED = "provider_retrieved"
    IMP_SERVER_RECEIVED = "imp_server_received"


class StageObservationStatus(StrEnum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNAVAILABLE = "UNAVAILABLE"


# Operator/UI stages owned by another lane — never guessed here.
UNAVAILABLE_OPERATOR_STAGES: tuple[str, ...] = (
    "ui_received",
    "ui_first_visible",
    "operator_interaction",
)

SOFTWARE_PROCESSING_STAGES: tuple[LatencyStageId, ...] = tuple(LatencyStageId)


@dataclass(slots=True)
class StageStamp:
    """One observed software-processing instant.

    wall_ns: monotonic_wall_ns() domain (absolute).
    mono_ns: time.perf_counter_ns() domain (duration math only).
    """

    wall_ns: int | None = None
    mono_ns: int | None = None

    @property
    def status(self) -> StageObservationStatus:
        if self.wall_ns is None and self.mono_ns is None:
            return StageObservationStatus.NOT_OBSERVED
        return StageObservationStatus.OBSERVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_ns": self.wall_ns,
            "mono_ns": self.mono_ns,
            "status": str(self.status),
        }


@dataclass
class LatencyTraceV1:
    """Per-event correlated clocks. Missing stages stay NOT_OBSERVED."""

    correlation_id: str
    opportunity_id: str | None = None
    evidence_class: str = "SOFTWARE_CONTROLLED"
    eligibility_ns: dict[str, int | None] = field(default_factory=dict)
    stages: dict[str, StageStamp] = field(default_factory=dict)

    def stage(self, stage_id: LatencyStageId | str) -> StageStamp:
        key = str(stage_id)
        existing = self.stages.get(key)
        if existing is not None:
            return existing
        stamp = StageStamp()
        self.stages[key] = stamp
        return stamp

    def observed_stage_ids(self) -> tuple[str, ...]:
        return tuple(
            key
            for key, stamp in self.stages.items()
            if stamp.status == StageObservationStatus.OBSERVED
        )

    def coverage_note(self) -> dict[str, Any]:
        return {
            "software_stages_observed": list(self.observed_stage_ids()),
            "software_stages_not_observed": [
                str(stage)
                for stage in SOFTWARE_PROCESSING_STAGES
                if str(stage) not in self.observed_stage_ids()
            ],
            "operator_ui_stages": {
                name: str(StageObservationStatus.UNAVAILABLE)
                for name in UNAVAILABLE_OPERATOR_STAGES
            },
            "eligibility_vs_processing": (
                "eligibility_ns are information clocks; stages.*.wall/mono are software processing"
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "opportunity_id": self.opportunity_id,
            "evidence_class": self.evidence_class,
            "eligibility_ns": dict(self.eligibility_ns),
            "stages": {key: stamp.to_dict() for key, stamp in self.stages.items()},
            "coverage": self.coverage_note(),
        }


__all__ = [
    "EligibilityClockId",
    "LatencyStageId",
    "LatencyTraceV1",
    "SOFTWARE_PROCESSING_STAGES",
    "StageObservationStatus",
    "StageStamp",
    "UNAVAILABLE_OPERATOR_STAGES",
]
