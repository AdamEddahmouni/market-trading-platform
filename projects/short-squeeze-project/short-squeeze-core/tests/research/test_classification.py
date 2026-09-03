import pytest

from squeeze_core.evaluation import serialize_candidate_evaluation
from squeeze_core.research.classification import classify_research_case
from squeeze_core.research.models import (
    DetectionStatus,
    OutcomeLabel,
    ResearchCaseClassification,
)


@pytest.mark.parametrize(("detection", "outcome", "expected"), [
    (DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, ResearchCaseClassification.TRUE_POSITIVE),
    (DetectionStatus.DETECTED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE, ResearchCaseClassification.FALSE_POSITIVE),
    (DetectionStatus.NOT_DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, ResearchCaseClassification.FALSE_NEGATIVE),
    (DetectionStatus.NOT_DETECTED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE, ResearchCaseClassification.TRUE_NEGATIVE),
    (DetectionStatus.UNEVALUABLE, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, ResearchCaseClassification.UNEVALUABLE),
    (DetectionStatus.DETECTED, OutcomeLabel.OUTCOME_UNKNOWN, ResearchCaseClassification.UNEVALUABLE),
    (DetectionStatus.NOT_DETECTED, OutcomeLabel.OUTCOME_INSUFFICIENT_DATA, ResearchCaseClassification.UNEVALUABLE),
    (DetectionStatus.DETECTED, OutcomeLabel.MIXED_OR_VOLATILE, ResearchCaseClassification.UNEVALUABLE),
    (DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE, ResearchCaseClassification.UNEVALUABLE),
])
def test_classification_truth_table(detection, outcome, expected):
    result = classify_research_case("CASE-A", detection, outcome, "detection-a", "outcome-a")
    assert result.classification is expected


def test_platform_status_is_structurally_absent_from_classification_input():
    result = classify_research_case(
        "CASE-A", DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE,
        "detection-a", "outcome-a",
    )
    assert "original_platform" not in result.model_dump_json()


def test_later_outcome_work_does_not_mutate_phase_3a_evaluation():
    from .helpers import BASE_EVALUATION

    before = serialize_candidate_evaluation(BASE_EVALUATION)
    classify_research_case(
        "CASE-A", DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE,
        "detection-a", "outcome-a",
    )
    assert serialize_candidate_evaluation(BASE_EVALUATION) == before


def test_classification_additive_diagnostics_for_evaluable_pair():
    result = classify_research_case(
        "CASE-A", DetectionStatus.DETECTED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE,
        "detection-a", "outcome-a",
    )
    assert result.evaluable_pair is True
    assert result.unevaluable_cause is None


def test_classification_additive_diagnostics_for_unevaluable_pair():
    result = classify_research_case(
        "CASE-A", DetectionStatus.UNEVALUABLE, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE,
        "detection-a", "outcome-a",
    )
    assert result.evaluable_pair is False
    assert result.unevaluable_cause == "DETECTION_STATUS_UNEVALUABLE"
