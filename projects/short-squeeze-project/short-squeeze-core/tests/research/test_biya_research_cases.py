from pathlib import Path

from squeeze_core.evaluation import RuleCategory, RuleOutcome
from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.models import BatchEvaluationRequest, OrderingPolicy
from squeeze_core.research.policies import DETECTION_POLICY_VERSION, OUTCOME_POLICY_VERSION


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "tests" / "fixtures" / "research" / "phase_3b_case_registry.json"


def _request(case_ids):
    return BatchEvaluationRequest(
        batch_version="phase_3b_batch.v1",
        phase_3a_policy_version="phase_3a_transparent_candidate_policy.v1",
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_POLICY_VERSION,
        case_ids=case_ids,
        case_registry_version="phase_3b_case_registry.v1",
        ordering_policy=OrderingPolicy.REQUEST_ORDER,
    )


def test_biya_boundaries_are_separate_complete_true_positive_cases():
    batch = run_research_batch(
        _request(("BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY")), REGISTRY
    )
    assert [case.case_id for case in batch.case_results] == [
        "BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY"
    ]
    assert [case.phase_3a_evaluation_id for case in batch.case_results] == [
        "3faed0a7-8764-51d6-be7c-da0998013898",
        "f81a3617-022c-5f6c-8ecd-a7b078588444",
    ]
    for case in batch.case_results:
        assert case.research_detection_status.value == "DETECTED"
        assert case.outcome_label.value == "SUBSTANTIAL_UPWARD_MOVE"
        assert case.research_classification.value == "TRUE_POSITIVE"
        short_pressure = [
            item for item in case.phase_3a_rule_results
            if item.category is RuleCategory.SHORT_PRESSURE_CONFIRMATION
        ]
        assert short_pressure
        outcomes = {item.outcome for item in short_pressure}
        assert RuleOutcome.PASS in outcomes
        assert RuleOutcome.UNKNOWN in outcomes
        assert outcomes <= {RuleOutcome.PASS, RuleOutcome.UNKNOWN}


def test_incomplete_historical_cases_remain_explicit_and_unfabricated():
    case_ids = (
        "KLOS_IDENTITY_CONFLICT",
    )
    batch = run_research_batch(_request(case_ids), REGISTRY)
    assert batch.case_results == ()
    assert {item.case_id for item in batch.skipped_cases} == set(case_ids)
