"""Reconstructing what the original platform displayed, including what it did not.

The hard requirement here is representing near-total ignorance faithfully. For BIYA
every displayed field is UNKNOWN, and that must survive construction, validation, and
serialization without becoming 0, "", False, or a silently dropped key.
"""

from collections.abc import Sequence

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import Quality
from squeeze_core.contracts.enums import QualityState

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .identifiers import deterministic_validation_id, original_snapshot_identity
from .models import (
    OriginalCandidateSnapshot,
    OriginalFieldValue,
    OriginalRuleResult,
    OriginalValueState,
)


def unknown_field(
    field_id: str,
    *,
    display_label: str | None = None,
    internal_field_name: str | None = None,
    provider: str | None = None,
    source_artifact_ids: Sequence[str] = (),
) -> OriginalFieldValue:
    """A field the artifacts do not record. Carries no value by construction."""

    return OriginalFieldValue(
        field_id=field_id,
        display_label=display_label,
        internal_field_name=internal_field_name,
        state=OriginalValueState.UNKNOWN,
        provider=provider,
        source_artifact_ids=tuple(source_artifact_ids),
    )


def build_original_snapshot(
    symbol: str,
    field_values: Sequence[OriginalFieldValue],
    *,
    detection_time_evidence_id: str | None = None,
    rule_results: Sequence[OriginalRuleResult] = (),
    original_score_if_any: str | None = None,
    original_label_if_any: str | None = None,
    source_artifact_ids: Sequence[str] = (),
) -> OriginalCandidateSnapshot:
    missing = tuple(
        value.field_id
        for value in field_values
        if value.state is OriginalValueState.MISSING_IN_ARTIFACT
    )
    substituted = tuple(
        value.field_id
        for value in field_values
        if value.state is OriginalValueState.DEFAULT_SUBSTITUTED
    )
    unknown = tuple(
        value.field_id for value in field_values if value.state is OriginalValueState.UNKNOWN
    )

    diagnostics: list[ValidationDiagnostic] = []
    for field_id in unknown:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_ORIGINAL_VALUE_UNKNOWN,
                severity=DiagnosticSeverity.WARNING,
                message="no artifact records the original value of this field",
                field_id=field_id,
            )
        )
    for field_id in substituted:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_DEFAULT_SUBSTITUTION,
                severity=DiagnosticSeverity.WARNING,
                message="the original platform substituted a default for a missing value",
                field_id=field_id,
            )
        )

    recovered = [
        value
        for value in field_values
        if value.state
        in {
            OriginalValueState.RECOVERED,
            OriginalValueState.DERIVED,
            OriginalValueState.DEFAULT_SUBSTITUTED,
        }
    ]
    # Per-field unknowns are carried by each OriginalFieldValue.state. Snapshot quality
    # reports whether the reconstruction produced anything at all: MISSING when no
    # original value survives, KNOWN_VALUE once at least one does.
    if not field_values:
        quality = Quality(
            state=QualityState.MISSING, reasons=("no original field was reconstructed",)
        )
    elif not recovered:
        quality = Quality(
            state=QualityState.MISSING,
            reasons=("no original field value survives in any available artifact",),
        )
    else:
        quality = Quality(state=QualityState.KNOWN_VALUE)

    draft = OriginalCandidateSnapshot(
        symbol=symbol.strip().upper(),
        detection_time_evidence_id=detection_time_evidence_id,
        original_field_values=tuple(field_values),
        original_rule_results=tuple(rule_results),
        original_score_if_any=original_score_if_any,
        original_label_if_any=original_label_if_any,
        source_artifact_ids=tuple(source_artifact_ids),
        missing_fields=missing,
        default_substitutions=substituted,
        unknown_fields=unknown,
        quality=quality,
        diagnostics=sort_diagnostics(diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(original_snapshot_identity(draft))}
    )


__all__ = ["build_original_snapshot", "unknown_field"]
