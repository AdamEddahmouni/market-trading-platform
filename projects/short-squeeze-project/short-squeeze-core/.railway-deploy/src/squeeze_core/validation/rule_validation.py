"""Methodology classification for original platform rules.

Every state here judges a *rule*, never a stock. There is no score, rank, tier,
confidence, or recommendation in this module, and `tests/validation/
test_rule_validation.py` scans serialized output to keep it that way.
"""

from collections.abc import Sequence

from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .identifiers import deterministic_validation_id, rule_validation_identity
from .models import RuleValidationEntry, RuleValidationState

# The diagnostic each classification implies, where one exists. States describing a
# judgement about design (SUPPORTED, MOMENTUM_DISCOVERY_ONLY, REDUNDANT, UNSUPPORTED)
# carry no diagnostic -- they are conclusions, not evidence facts.
_STATE_DIAGNOSTICS = {
    RuleValidationState.MISLABELED: (
        ValidationDiagnosticCode.VALIDATION_ORIGINAL_FIELD_MISLABELED,
        DiagnosticSeverity.WARNING,
        "the displayed label does not accurately represent the underlying value",
    ),
    RuleValidationState.STALE: (
        ValidationDiagnosticCode.VALIDATION_EVIDENCE_STALE,
        DiagnosticSeverity.INFO,
        "the value's age or reporting period materially differs from how it was presented",
    ),
    RuleValidationState.UNAVAILABLE_AT_DETECTION: (
        ValidationDiagnosticCode.VALIDATION_EVIDENCE_UNAVAILABLE_AT_DETECTION,
        DiagnosticSeverity.WARNING,
        "the evidence this rule requires became available only after detection",
    ),
    RuleValidationState.MISSING_DEFAULT_SUBSTITUTION: (
        ValidationDiagnosticCode.VALIDATION_DEFAULT_SUBSTITUTION,
        DiagnosticSeverity.WARNING,
        "a default was substituted for missing evidence",
    ),
    RuleValidationState.UNKNOWN: (
        ValidationDiagnosticCode.VALIDATION_ORIGINAL_RULE_UNKNOWN,
        DiagnosticSeverity.WARNING,
        "available artifacts are insufficient to classify this rule",
    ),
}


def build_rule_validation(
    rule_id: str,
    state: RuleValidationState,
    rationale: str,
    *,
    corrections_required: Sequence[str] = (),
    supporting_artifact_ids: Sequence[str] = (),
    supporting_field_ids: Sequence[str] = (),
    extra_diagnostics: Sequence[ValidationDiagnostic] = (),
) -> RuleValidationEntry:
    diagnostics = list(extra_diagnostics)
    implied = _STATE_DIAGNOSTICS.get(state)
    if implied is not None:
        code, severity, message = implied
        diagnostics.append(
            ValidationDiagnostic(
                code=code, severity=severity, message=message, rule_id=rule_id
            )
        )

    draft = RuleValidationEntry(
        rule_id=rule_id,
        state=state,
        rationale=rationale,
        corrections_required=tuple(corrections_required),
        supporting_artifact_ids=tuple(supporting_artifact_ids),
        supporting_field_ids=tuple(supporting_field_ids),
        diagnostics=sort_diagnostics(diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(rule_validation_identity(draft))}
    )


def sort_rule_validations(
    entries: Sequence[RuleValidationEntry],
) -> tuple[RuleValidationEntry, ...]:
    return tuple(sorted(entries, key=lambda item: item.rule_id))


def states_by_rule(entries: Sequence[RuleValidationEntry]) -> dict[str, RuleValidationState]:
    return {entry.rule_id: entry.state for entry in entries}


__all__ = ["build_rule_validation", "sort_rule_validations", "states_by_rule"]
