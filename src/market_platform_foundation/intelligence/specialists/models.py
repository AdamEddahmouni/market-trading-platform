"""Runtime models for BUILD 11 specialist execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import EvidenceV1


class SpecialistExecutionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"
    STALE = "STALE"
    FAILED = "FAILED"


class SpecialistDiagnosticCode(StrEnum):
    UNSUPPORTED_DOMAIN = "UNSUPPORTED_DOMAIN"
    UNSUPPORTED_SEMANTIC_EVENT = "UNSUPPORTED_SEMANTIC_EVENT"
    MISSING_REQUIRED_SOURCE = "MISSING_REQUIRED_SOURCE"
    WRONG_SIGNAL_TYPE = "WRONG_SIGNAL_TYPE"
    SOURCE_SNAPSHOT_MISMATCH = "SOURCE_SNAPSHOT_MISMATCH"
    ROUTE_DETECTION_MISMATCH = "ROUTE_DETECTION_MISMATCH"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    STALE_INFERENCE = "STALE_INFERENCE"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    REFERENCE_RESOLUTION_FAILED = "REFERENCE_RESOLUTION_FAILED"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    EXECUTION_FAILED = "EXECUTION_FAILED"


@dataclass(frozen=True, slots=True)
class SpecialistDiagnostic:
    code: SpecialistDiagnosticCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SpecialistResult:
    status: SpecialistExecutionStatus
    evidence: tuple[EvidenceV1, ...] = ()
    diagnostics: tuple[SpecialistDiagnostic, ...] = ()
    started_at_ns: int | None = None
    completed_at_ns: int | None = None
    deadline_missed: bool = False
    stale: bool = False


@dataclass(frozen=True, slots=True)
class SpecialistExecutionOutcome:
    job_id: str
    status: SpecialistExecutionStatus
    evidence: tuple[EvidenceV1, ...] = ()
    diagnostics: tuple[SpecialistDiagnostic, ...] = ()
    started_at_ns: int | None = None
    completed_at_ns: int | None = None
    deadline_missed: bool = False
    stale: bool = False


__all__ = [
    "SpecialistDiagnostic",
    "SpecialistDiagnosticCode",
    "SpecialistExecutionOutcome",
    "SpecialistExecutionStatus",
    "SpecialistResult",
]
