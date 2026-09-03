import pytest

from squeeze_core.evaluation import RuleOutcome
from squeeze_core.research.detection import evaluate_research_detection
from squeeze_core.research.models import DetectionStatus
from squeeze_core.research.policies import DETECTION_POLICY_VERSION, load_detection_policy
from squeeze_core.research.serialization import serialize_research_model

from .helpers import evaluation_with_required_outcomes


POLICY = load_detection_policy(DETECTION_POLICY_VERSION)


@pytest.mark.parametrize(("outcomes", "expected"), [
    ((RuleOutcome.PASS, RuleOutcome.PASS, RuleOutcome.PASS), DetectionStatus.DETECTED),
    ((RuleOutcome.PASS, RuleOutcome.FAIL, RuleOutcome.PASS), DetectionStatus.NOT_DETECTED),
    ((RuleOutcome.PASS, RuleOutcome.UNKNOWN, RuleOutcome.PASS), DetectionStatus.UNEVALUABLE),
    ((RuleOutcome.PASS, RuleOutcome.CONFLICTED, RuleOutcome.PASS), DetectionStatus.UNEVALUABLE),
    ((RuleOutcome.PASS, RuleOutcome.INSUFFICIENT_DATA, RuleOutcome.PASS), DetectionStatus.UNEVALUABLE),
    ((RuleOutcome.PASS, RuleOutcome.NOT_APPLICABLE, RuleOutcome.PASS), DetectionStatus.UNEVALUABLE),
])
def test_detection_truth_table(outcomes, expected):
    evaluation = evaluation_with_required_outcomes(outcomes)
    result = evaluate_research_detection(evaluation, POLICY)
    by_rule = {item.rule_id: item for item in evaluation.rule_results}
    assert result.status is expected
    assert result.supporting_rule_result_ids == tuple(
        sorted(by_rule[rule_id].deterministic_id for rule_id in POLICY.required_rule_ids)
    )


def test_detection_identity_and_serialization_are_stable():
    evaluation = evaluation_with_required_outcomes((RuleOutcome.PASS,) * 3)
    first = evaluate_research_detection(evaluation, POLICY)
    second = evaluate_research_detection(evaluation, POLICY)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_research_model(first) == serialize_research_model(second)
