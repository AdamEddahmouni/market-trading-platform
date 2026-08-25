"""Temporal integrity value types (BUILD 02)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TemporalViolationCode(StrEnum):
    """Stable taxonomy for temporal-integrity diagnostics."""

    FUTURE_INFORMATION = "FUTURE_INFORMATION"
    STALE_INFORMATION = "STALE_INFORMATION"
    EXPIRED_INFORMATION = "EXPIRED_INFORMATION"
    CLOCK_SKEW = "CLOCK_SKEW"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    CONFLICTING_DUPLICATE = "CONFLICTING_DUPLICATE"
    MISSING_TEMPORAL_DATA = "MISSING_TEMPORAL_DATA"
    INVALID_TEMPORAL_RELATION = "INVALID_TEMPORAL_RELATION"
    SIGNAL_AS_OF_AFTER_DECISION = "SIGNAL_AS_OF_AFTER_DECISION"
    MISSING_REFERENCE = "MISSING_REFERENCE"


class TemporalViolationSeverity(StrEnum):
    """Severity for temporal observations — not every anomaly is fatal."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DuplicateClassification(StrEnum):
    """Deterministic duplicate-event classification."""

    NEW = "NEW"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    CONFLICTING_DUPLICATE = "CONFLICTING_DUPLICATE"


@dataclass(frozen=True, slots=True)
class TemporalViolation:
    """Structured temporal diagnostic — references records by id, not payload."""

    code: TemporalViolationCode
    severity: TemporalViolationSeverity
    message: str
    record_kind: str
    record_id: str
    decision_time_ns: int | None = None
    relevant_time_ns: int | None = None
    delta_ns: int | None = None
    policy_context: str | None = None


@dataclass(frozen=True, slots=True)
class TemporalEligibility:
    """Point-in-time eligibility and usability for a single record."""

    eligible: bool
    usable: bool


@dataclass(frozen=True, slots=True)
class TemporalIntegrityReport:
    """Non-throwing temporal inspection result."""

    eligible: bool
    usable: bool
    violations: tuple[TemporalViolation, ...] = ()

    @property
    def warnings(self) -> tuple[TemporalViolation, ...]:
        return tuple(v for v in self.violations if v.severity == TemporalViolationSeverity.WARNING)

    @property
    def hard_failures(self) -> tuple[TemporalViolation, ...]:
        return tuple(v for v in self.violations if v.severity == TemporalViolationSeverity.ERROR)

    @property
    def has_hard_failure(self) -> bool:
        return bool(self.hard_failures)


class TemporalIntegrityError(ValueError):
    """Fail-closed temporal validation error with structured context."""

    def __init__(
        self,
        message: str,
        *,
        code: TemporalViolationCode,
        record_kind: str,
        record_id: str,
        decision_time_ns: int | None = None,
        relevant_time_ns: int | None = None,
        delta_ns: int | None = None,
        violations: tuple[TemporalViolation, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.record_kind = record_kind
        self.record_id = record_id
        self.decision_time_ns = decision_time_ns
        self.relevant_time_ns = relevant_time_ns
        self.delta_ns = delta_ns
        self.violations = violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "record_kind": self.record_kind,
            "record_id": self.record_id,
            "decision_time_ns": self.decision_time_ns,
            "relevant_time_ns": self.relevant_time_ns,
            "delta_ns": self.delta_ns,
            "violation_count": len(self.violations),
        }


__all__ = [
    "DuplicateClassification",
    "TemporalEligibility",
    "TemporalIntegrityError",
    "TemporalIntegrityReport",
    "TemporalViolation",
    "TemporalViolationCode",
    "TemporalViolationSeverity",
]
