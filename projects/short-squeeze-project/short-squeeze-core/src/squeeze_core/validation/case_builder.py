"""Assembling a validation case, and deriving its methodology conclusion.

The conclusion is *derived*, never authored. It is a deterministic function of the
evidence actually present, so a case's headline cannot drift away from what supports
it. The rule that matters most:

    A subsequent price move is an outcome observation. It is never evidence that the
    original rules were correct, or that their inputs existed at detection.

Adding outcome data to a case whose original values are unrecoverable therefore leaves
the conclusion at INSUFFICIENT_EVIDENCE. `derive_conclusion` is written so that no
argument combination can produce an upgrade from outcome data alone.
"""

from collections.abc import Sequence

from squeeze_core.contracts import Quality
from squeeze_core.contracts.enums import QualityState

from .diagnostics import ValidationDiagnostic, sort_diagnostics
from .identifiers import (
    case_conclusion_identity,
    deterministic_validation_id,
    validation_case_identity,
)
from .models import (
    CandidateOutcomeObservation,
    CaseStatus,
    ComparisonState,
    DetectionTimeEvidence,
    DetectionTimeState,
    FieldComparisonEntry,
    MethodologyConclusion,
    OriginalCandidateSnapshot,
    OriginalRuleDefinition,
    OriginalValueState,
    RebuiltAsOfSnapshot,
    RuleValidationEntry,
    RuleValidationState,
    ValidationArtifact,
    ValidationCase,
    ValidationCaseConclusion,
)

# Rule states that indicate the original decision leaned on evidence that was not
# there at detection, or on a value invented to fill a gap.
_POINT_IN_TIME_FAILURES = frozenset(
    {
        RuleValidationState.UNAVAILABLE_AT_DETECTION,
        RuleValidationState.MISSING_DEFAULT_SUBSTITUTION,
    }
)

_RECOVERED_STATES = frozenset(
    {
        OriginalValueState.RECOVERED,
        OriginalValueState.DERIVED,
        OriginalValueState.DEFAULT_SUBSTITUTED,
    }
)


def derive_conclusion(
    symbol: str,
    *,
    detection_time: DetectionTimeEvidence | None,
    original_snapshot: OriginalCandidateSnapshot | None,
    rule_validations: Sequence[RuleValidationEntry] = (),
    field_comparisons: Sequence[FieldComparisonEntry] = (),
    outcome: CandidateOutcomeObservation | None = None,
    extra_limitations: Sequence[str] = (),
) -> ValidationCaseConclusion:
    findings: list[str] = []
    limitations: list[str] = list(extra_limitations)

    outcome_confirmed = outcome is not None and any(
        window.observed for window in outcome.subsequent_windows
    )

    recovered = (
        [
            value
            for value in original_snapshot.original_field_values
            if value.state in _RECOVERED_STATES
        ]
        if original_snapshot is not None
        else []
    )

    reproducible_comparisons = [
        entry
        for entry in field_comparisons
        if entry.comparison_state
        in {ComparisonState.MATCH, ComparisonState.MATCH_WITH_NORMALIZATION}
    ]

    point_in_time_failures = [
        entry for entry in rule_validations if entry.state in _POINT_IN_TIME_FAILURES
    ]

    # 1. Nothing about the original decision is recoverable. No amount of outcome data
    #    changes this -- there is no recorded decision to validate or invalidate.
    if original_snapshot is None or not recovered:
        if original_snapshot is None:
            findings.append("no original candidate snapshot could be reconstructed")
        else:
            findings.append(
                "every original field value is unknown; no original value survives in any artifact"
            )
        if outcome_confirmed:
            findings.append(
                "a subsequent price move was observed, but an outcome cannot demonstrate that "
                "the original methodology produced the selection validly"
            )
            limitations.append(
                "outcome confirmation does not upgrade this conclusion: no original value exists "
                "to reproduce, compare, or invalidate"
            )
        if detection_time is not None and detection_time.state is DetectionTimeState.BOUNDED_TIME_WINDOW:
            findings.append("detection time is bounded rather than exactly recorded")
        conclusion = MethodologyConclusion.INSUFFICIENT_EVIDENCE

    # 2. The original decision materially depended on evidence absent at detection.
    elif point_in_time_failures:
        findings.append(
            f"{len(point_in_time_failures)} rule(s) depended on evidence unavailable at "
            "detection or on a substituted default"
        )
        conclusion = MethodologyConclusion.NOT_POINT_IN_TIME_VALID

    # 3. The decision is reproducible from evidence available at detection.
    elif reproducible_comparisons and len(reproducible_comparisons) == len(field_comparisons):
        findings.append(
            "every compared field reproduces from evidence available at detection"
        )
        conclusion = MethodologyConclusion.VALIDATED_AS_RECORDED

    # 4. Some rules held, others did not.
    elif any(
        entry.state
        in {
            RuleValidationState.SUPPORTED,
            RuleValidationState.SUPPORTED_WITH_CORRECTION,
            RuleValidationState.MOMENTUM_DISCOVERY_ONLY,
        }
        for entry in rule_validations
    ):
        findings.append(
            "some original rules are supported while others are mislabeled, stale, or incorrect"
        )
        conclusion = MethodologyConclusion.PARTIALLY_VALIDATED

    # 5. An outcome exists but the methodology could not be assessed either way.
    elif outcome_confirmed:
        findings.append(
            "a subsequent move was observed, but the artifacts cannot show the original "
            "methodology produced it validly"
        )
        conclusion = MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED
    else:
        conclusion = MethodologyConclusion.INSUFFICIENT_EVIDENCE

    if outcome is not None and not outcome_confirmed:
        limitations.append("no outcome window could be measured from available market data")

    rationale = {
        MethodologyConclusion.INSUFFICIENT_EVIDENCE: (
            "There is not enough evidence to determine how the original candidate was produced."
        ),
        MethodologyConclusion.NOT_POINT_IN_TIME_VALID: (
            "The original result materially depended on evidence unavailable at detection or on "
            "invalid substitutions."
        ),
        MethodologyConclusion.VALIDATED_AS_RECORDED: (
            "The original decision reproduces from evidence available at detection with "
            "materially accurate semantics."
        ),
        MethodologyConclusion.PARTIALLY_VALIDATED: (
            "Some rules were valid and useful, while others were missing, stale, mislabeled, or "
            "technically incorrect."
        ),
        MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED: (
            "The symbol subsequently moved, but available artifacts cannot prove the original "
            "methodology produced that result validly."
        ),
    }[conclusion]

    draft = ValidationCaseConclusion(
        symbol=symbol.strip().upper(),
        conclusion=conclusion,
        rationale=rationale,
        supporting_findings=tuple(findings),
        limitations=tuple(limitations),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=(),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(case_conclusion_identity(draft))}
    )


def derive_case_status(
    *,
    detection_time: DetectionTimeEvidence | None,
    original_snapshot: OriginalCandidateSnapshot | None,
    replays: Sequence[RebuiltAsOfSnapshot] = (),
    outcome: CandidateOutcomeObservation | None = None,
) -> CaseStatus:
    """Case status reports what was actually assembled. COMPLETE is never reported on
    the strength of artifact discovery alone."""

    if detection_time is None or detection_time.state is DetectionTimeState.UNKNOWN:
        return CaseStatus.BLOCKED_MISSING_DETECTION_TIME

    has_original = original_snapshot is not None and any(
        value.state in _RECOVERED_STATES for value in original_snapshot.original_field_values
    )
    if not has_original:
        return CaseStatus.BLOCKED_MISSING_ORIGINAL_OUTPUT

    has_outcome = outcome is not None and any(
        window.observed for window in outcome.subsequent_windows
    )
    if not has_outcome:
        return CaseStatus.BLOCKED_MISSING_MARKET_DATA

    return CaseStatus.COMPLETE if replays else CaseStatus.PARTIAL


def build_validation_case(
    case_id: str,
    symbol: str,
    *,
    artifacts: Sequence[ValidationArtifact] = (),
    detection_time: DetectionTimeEvidence | None = None,
    original_rules: Sequence[OriginalRuleDefinition] = (),
    original_snapshot: OriginalCandidateSnapshot | None = None,
    replays: Sequence[RebuiltAsOfSnapshot] = (),
    field_comparisons: Sequence[FieldComparisonEntry] = (),
    rule_validations: Sequence[RuleValidationEntry] = (),
    outcome: CandidateOutcomeObservation | None = None,
    limitations: Sequence[str] = (),
    case_status: CaseStatus | None = None,
    extra_diagnostics: Sequence[ValidationDiagnostic] = (),
) -> ValidationCase:
    conclusion = derive_conclusion(
        symbol,
        detection_time=detection_time,
        original_snapshot=original_snapshot,
        rule_validations=rule_validations,
        field_comparisons=field_comparisons,
        outcome=outcome,
    )
    status = case_status or derive_case_status(
        detection_time=detection_time,
        original_snapshot=original_snapshot,
        replays=replays,
        outcome=outcome,
    )

    draft = ValidationCase(
        case_id=case_id,
        symbol=symbol.strip().upper(),
        case_status=status,
        artifacts=tuple(artifacts),
        detection_time_evidence=detection_time,
        original_rules=tuple(original_rules),
        original_snapshot=original_snapshot,
        replays=tuple(replays),
        field_comparisons=tuple(field_comparisons),
        rule_validations=tuple(rule_validations),
        outcome_observation=outcome,
        conclusion=conclusion,
        limitations=tuple(limitations),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(extra_diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(validation_case_identity(draft))}
    )


__all__ = [
    "build_validation_case",
    "derive_case_status",
    "derive_conclusion",
]
