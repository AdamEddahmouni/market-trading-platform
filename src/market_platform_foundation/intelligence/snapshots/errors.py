"""Structured snapshot engine errors (BUILD 05)."""

from __future__ import annotations

from typing import Any

from ..quality.models import QualityDecision
from ..temporal.models import TemporalIntegrityReport


class SnapshotError(ValueError):
    """Base snapshot-domain error."""


class SnapshotBuildError(SnapshotError):
    """Snapshot composition failed before a valid artifact could be produced."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})
        self.cause = cause


class SnapshotTemporalError(SnapshotBuildError):
    """Temporal validation blocked snapshot production."""

    def __init__(
        self,
        message: str,
        *,
        report: TemporalIntegrityReport,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.report = report


class SnapshotQualityError(SnapshotBuildError):
    """Quality/capability decision blocked snapshot production."""

    def __init__(
        self,
        message: str,
        *,
        decision: QualityDecision,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.decision = decision


class SnapshotReferenceError(SnapshotError):
    """Referenced record missing or wrong kind during resolution."""

    def __init__(
        self,
        message: str,
        *,
        reference_kind: str | None = None,
        reference_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reference_kind = reference_kind
        self.reference_id = reference_id
        self.details = dict(details or {})


class SnapshotIntegrityError(SnapshotError):
    """Persisted snapshot no longer matches its semantic fingerprint."""

    def __init__(
        self,
        message: str,
        *,
        expected_fingerprint: str | None = None,
        observed_fingerprint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.expected_fingerprint = expected_fingerprint
        self.observed_fingerprint = observed_fingerprint
        self.details = dict(details or {})


__all__ = [
    "SnapshotBuildError",
    "SnapshotError",
    "SnapshotIntegrityError",
    "SnapshotQualityError",
    "SnapshotReferenceError",
    "SnapshotTemporalError",
]
