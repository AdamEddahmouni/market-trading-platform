from .models import (
    DetectionStatus,
    OutcomeLabel,
    ResearchCaseClassification,
    ResearchClassificationResult,
)


_CLASSIFICATION_TABLE = {
    (DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE): (
        ResearchCaseClassification.TRUE_POSITIVE
    ),
    (DetectionStatus.DETECTED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE): (
        ResearchCaseClassification.FALSE_POSITIVE
    ),
    (DetectionStatus.NOT_DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE): (
        ResearchCaseClassification.FALSE_NEGATIVE
    ),
    (DetectionStatus.NOT_DETECTED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE): (
        ResearchCaseClassification.TRUE_NEGATIVE
    ),
}


def _unevaluable_cause(
    detection_status: DetectionStatus,
    outcome_label: OutcomeLabel,
) -> str | None:
    if (detection_status, outcome_label) in _CLASSIFICATION_TABLE:
        return None
    if detection_status is DetectionStatus.UNEVALUABLE:
        return "DETECTION_STATUS_UNEVALUABLE"
    if outcome_label is OutcomeLabel.OUTCOME_UNKNOWN:
        return "OUTCOME_UNKNOWN"
    if outcome_label is OutcomeLabel.OUTCOME_INSUFFICIENT_DATA:
        return "OUTCOME_INSUFFICIENT_DATA"
    if outcome_label is OutcomeLabel.MIXED_OR_VOLATILE:
        return "OUTCOME_MIXED_OR_VOLATILE"
    if outcome_label is OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE:
        return "OUTCOME_SUBSTANTIAL_DOWNWARD_MOVE"
    return "UNMAPPED_PAIR_UNEVALUABLE"


def classify_research_case(
    case_id: str,
    detection_status: DetectionStatus,
    outcome_label: OutcomeLabel,
    detection_result_id: str,
    outcome_label_result_id: str,
) -> ResearchClassificationResult:
    classification = _CLASSIFICATION_TABLE.get(
        (detection_status, outcome_label), ResearchCaseClassification.UNEVALUABLE
    )
    cause = _unevaluable_cause(detection_status, outcome_label)
    return ResearchClassificationResult(
        case_id=case_id,
        detection_status=detection_status,
        outcome_label=outcome_label,
        classification=classification,
        detection_result_id=detection_result_id,
        outcome_label_result_id=outcome_label_result_id,
        evaluable_pair=cause is None,
        unevaluable_cause=cause,
    )


__all__ = ["classify_research_case"]
