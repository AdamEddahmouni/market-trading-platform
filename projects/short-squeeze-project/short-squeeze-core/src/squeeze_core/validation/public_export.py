"""Deterministic public export for the research demonstration.

Built by **whitelist projection**: `PublicValidationCase` is constructed field by field
out of named sources, never by copying a `ValidationCase` and deleting keys. The
difference matters -- under projection, a field added to the internal model is absent
by default. Under copy-and-strip it would leak until someone remembered to redact it.

Excluded unconditionally: filesystem paths of any kind, sensitive artifacts,
credentials and tokens, personal names, email addresses, private URLs, account
identifiers, and every internal diagnostic message (which can quote raw artifact text).
"""

import re
from collections.abc import Sequence

from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .artifacts import public_artifact_summary, public_artifacts
from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode
from .identifiers import deterministic_validation_id, public_case_identity
from .models import (
    DetectionTimeState,
    PublicValidationCase,
    ValidationCase,
)

# Patterns that must never survive into a published artifact. Checked as a last-line
# assertion over the rendered bytes, not as the primary defence -- projection is.
_FORBIDDEN_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]"),  # drive-rooted local path
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),  # UNC path
    re.compile(r"\bauth=[0-9a-fA-F-]{8,}"),  # credential in a query string
    re.compile(r"\bapi[_-]?key\s*[=:]", re.IGNORECASE),
    re.compile(r"\btoken\s*[=:]", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email address
)


class PublicExportError(ValueError):
    """Raised when a rendered public export still contains something disallowed."""


def assert_export_is_clean(rendered: bytes) -> None:
    text = rendered.decode("utf-8")
    for pattern in _FORBIDDEN_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            raise PublicExportError(
                f"public export contains disallowed content matching {pattern.pattern!r}"
            )


def build_public_validation_case(
    case: ValidationCase,
    *,
    extra_limitations: Sequence[str] = (),
) -> PublicValidationCase:
    detection = case.detection_time_evidence

    rules = tuple(
        {
            "rule_id": entry.rule_id,
            "classification": entry.state.value,
            "rationale": entry.rationale,
        }
        for entry in sorted(case.rule_validations, key=lambda item: item.rule_id)
    )

    comparisons = tuple(
        {
            "field_id": entry.field_id,
            "display_name": entry.display_name or entry.field_id,
            "original_value": "unknown" if entry.original_value is None else str(entry.original_value),
            "rebuilt_value": "unavailable" if entry.rebuilt_value is None else str(entry.rebuilt_value),
            "comparison_state": entry.comparison_state.value,
            "available_at_detection": (
                "unknown" if entry.available_at_detection is None else str(entry.available_at_detection).lower()
            ),
        }
        for entry in sorted(case.field_comparisons, key=lambda item: item.field_id)
    )

    outcome = case.outcome_observation
    outcome_available = outcome is not None and any(
        window.observed for window in outcome.subsequent_windows
    )

    limitations = list(case.limitations) + list(extra_limitations)
    if case.conclusion is not None:
        limitations.extend(case.conclusion.limitations)

    draft = PublicValidationCase(
        case_id=case.case_id,
        symbol=case.symbol,
        case_status=case.case_status,
        detection_time_state=(
            detection.state if detection is not None else DetectionTimeState.UNKNOWN
        ),
        detection_window_start=None if detection is None else detection.window_start,
        detection_window_end=None if detection is None else detection.window_end,
        detection_timezone=None if detection is None else detection.timezone,
        detection_confidence_basis=None if detection is None else detection.confidence_basis,
        artifact_summaries=tuple(
            public_artifact_summary(artifact) for artifact in public_artifacts(case.artifacts)
        ),
        rules=rules,
        field_comparisons=comparisons,
        replay_labels=tuple(replay.label for replay in case.replays),
        outcome_available=outcome_available,
        outcome_limitations=() if outcome is None else tuple(outcome.limitations),
        conclusion=case.conclusion.conclusion,  # type: ignore[union-attr]
        conclusion_rationale=case.conclusion.rationale,  # type: ignore[union-attr]
        limitations=tuple(limitations),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(public_case_identity(draft))}
    )


def redaction_diagnostics(case: ValidationCase) -> tuple[ValidationDiagnostic, ...]:
    """One diagnostic per artifact withheld from the public export."""

    withheld = [artifact for artifact in case.artifacts if artifact.sensitive]
    return tuple(
        ValidationDiagnostic(
            code=ValidationDiagnosticCode.VALIDATION_PUBLIC_EXPORT_REDACTED,
            severity=DiagnosticSeverity.INFO,
            message="artifact withheld from the public export because it is marked sensitive",
            artifact_id=artifact.artifact_id,
        )
        for artifact in sorted(withheld, key=lambda item: item.artifact_id)
    )


__all__ = [
    "PublicExportError",
    "assert_export_is_clean",
    "build_public_validation_case",
    "redaction_diagnostics",
]
