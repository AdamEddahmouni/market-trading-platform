from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from squeeze_core.adapters.diagnostics import DiagnosticSeverity


class ValidationDiagnosticCode(StrEnum):
    """Stable, machine-readable diagnostic codes emitted by squeeze_core.validation.

    Only codes an actually-implemented code path can emit are defined here, matching
    the convention set by squeeze_core.metrics.diagnostics.MetricDiagnosticCode and
    squeeze_core.readiness.diagnostics.ReadinessDiagnosticCode.

    Every code describes an evidence fact -- an artifact's readability, a timestamp's
    provenance, a value's availability at a point in time, a semantic mismatch. None
    carries trading meaning, and none describes candidate quality. A code asserting
    that a candidate is attractive, ranked, or recommended is out of scope for this
    phase by construction (docs/phase-2v-design.md Section 1)."""

    VALIDATION_ARTIFACT_NOT_FOUND = "VALIDATION_ARTIFACT_NOT_FOUND"
    VALIDATION_ARTIFACT_UNREADABLE = "VALIDATION_ARTIFACT_UNREADABLE"
    VALIDATION_ARTIFACT_TIME_UNKNOWN = "VALIDATION_ARTIFACT_TIME_UNKNOWN"
    VALIDATION_ARTIFACT_DUPLICATE_CONTENT = "VALIDATION_ARTIFACT_DUPLICATE_CONTENT"

    VALIDATION_DETECTION_TIME_UNKNOWN = "VALIDATION_DETECTION_TIME_UNKNOWN"
    VALIDATION_DETECTION_WINDOW_ONLY = "VALIDATION_DETECTION_WINDOW_ONLY"
    VALIDATION_DETECTION_TIME_CONFLICTED = "VALIDATION_DETECTION_TIME_CONFLICTED"
    VALIDATION_DETECTION_TIME_FILESYSTEM_ONLY = "VALIDATION_DETECTION_TIME_FILESYSTEM_ONLY"

    VALIDATION_ORIGINAL_VALUE_UNKNOWN = "VALIDATION_ORIGINAL_VALUE_UNKNOWN"
    VALIDATION_ORIGINAL_RULE_UNKNOWN = "VALIDATION_ORIGINAL_RULE_UNKNOWN"
    VALIDATION_DEFAULT_SUBSTITUTION = "VALIDATION_DEFAULT_SUBSTITUTION"
    VALIDATION_ORIGINAL_FIELD_MISLABELED = "VALIDATION_ORIGINAL_FIELD_MISLABELED"
    VALIDATION_SEMANTIC_MISMATCH = "VALIDATION_SEMANTIC_MISMATCH"

    VALIDATION_EVIDENCE_UNAVAILABLE_AT_DETECTION = "VALIDATION_EVIDENCE_UNAVAILABLE_AT_DETECTION"
    VALIDATION_EVIDENCE_STALE = "VALIDATION_EVIDENCE_STALE"

    VALIDATION_REBUILT_METRIC_UNAVAILABLE = "VALIDATION_REBUILT_METRIC_UNAVAILABLE"
    VALIDATION_REBUILT_INPUT_INSUFFICIENT = "VALIDATION_REBUILT_INPUT_INSUFFICIENT"
    VALIDATION_REBUILT_INPUT_CONFLICTED = "VALIDATION_REBUILT_INPUT_CONFLICTED"

    VALIDATION_NEWS_UNAVAILABLE_AT_DETECTION = "VALIDATION_NEWS_UNAVAILABLE_AT_DETECTION"
    VALIDATION_OUTCOME_DATA_INCOMPLETE = "VALIDATION_OUTCOME_DATA_INCOMPLETE"
    VALIDATION_COMPARISON_CASES_UNAVAILABLE = "VALIDATION_COMPARISON_CASES_UNAVAILABLE"
    VALIDATION_PUBLIC_EXPORT_REDACTED = "VALIDATION_PUBLIC_EXPORT_REDACTED"


class ValidationDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ValidationDiagnosticCode
    severity: DiagnosticSeverity
    message: str
    artifact_id: str | None = None
    field_id: str | None = None
    rule_id: str | None = None


def sort_diagnostics(items: Iterable[ValidationDiagnostic]) -> tuple[ValidationDiagnostic, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.code.value,
                item.artifact_id or "",
                item.field_id or "",
                item.rule_id or "",
                item.message,
            ),
        )
    )


__all__ = [
    "ValidationDiagnostic",
    "ValidationDiagnosticCode",
    "sort_diagnostics",
]
