from decimal import Decimal

import pytest

from squeeze_core.evaluation import serialize_candidate_evaluation
from squeeze_core.research.batch import ResearchBatchError, run_research_batch
from squeeze_core.research.models import (
    BatchEvaluationRequest,
    CandidateCaseStatus,
    OrderingPolicy,
    OutcomeCompleteness,
    ResearchCaseClassification,
    RetrospectiveOutcomeObservation,
)
from squeeze_core.research.policies import DETECTION_POLICY_VERSION, OUTCOME_POLICY_VERSION
from squeeze_core.research.serialization import serialize_research_model
from squeeze_core.serialization import canonical_json_bytes

from .helpers import AS_OF, BASE_EVALUATION
from .test_models import entry


def write_registry(tmp_path, entries):
    fixture_root = tmp_path / "fixtures"
    research = fixture_root / "research"
    research.mkdir(parents=True)
    (fixture_root / "evaluation-a.json").write_bytes(
        serialize_candidate_evaluation(BASE_EVALUATION)
    )
    outcome = RetrospectiveOutcomeObservation(
        case_id="CASE-A",
        symbol="BIYA",
        detection_boundary=AS_OF,
        reference_price_policy="first_eligible_trade_bar_close_at_or_after_boundary.v1",
        reference_price=Decimal("4"),
        horizon="24_HOURS",
        maximum_observed_move_percent=Decimal("25"),
        maximum_adverse_move_percent=Decimal("-4"),
        completeness=OutcomeCompleteness.PARTIAL,
        supporting_observation_ids=("observation-a",),
    )
    (fixture_root / "outcome-a.json").write_bytes(serialize_research_model(outcome))
    path = research / "registry.json"
    path.write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0",
        "registry_version": "phase_3b_case_registry.v1",
        "entries": [item.model_dump(mode="json") for item in entries],
    }))
    return path


def request(case_ids=("CASE-A",), fail_fast=False, ordering=OrderingPolicy.REQUEST_ORDER):
    return BatchEvaluationRequest(
        batch_version="phase_3b_batch.v1",
        phase_3a_policy_version="phase_3a_transparent_candidate_policy.v1",
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_POLICY_VERSION,
        case_ids=case_ids,
        case_registry_version="phase_3b_case_registry.v1",
        ordering_policy=ordering,
        fail_fast=fail_fast,
    )


def complete_entry(case_id="CASE-A", symbol="BIYA"):
    return entry(
        case_id=case_id,
        symbol=symbol,
        evaluation_result_path="../evaluation-a.json",
        outcome_observation_path="../outcome-a.json",
    )


def test_batch_builds_complete_case_without_changing_phase_3a_rules(tmp_path):
    registry_path = write_registry(tmp_path, (complete_entry(),))
    before = serialize_candidate_evaluation(BASE_EVALUATION)
    result = run_research_batch(request(), registry_path)
    case = result.case_results[0]
    assert case.case_id == "CASE-A"
    assert case.research_classification is ResearchCaseClassification.TRUE_POSITIVE
    assert tuple(item.outcome for item in case.phase_3a_rule_results) == tuple(
        item.outcome for item in BASE_EVALUATION.rule_results
    )
    assert serialize_candidate_evaluation(BASE_EVALUATION) == before


def test_batch_retains_partial_case_when_not_fail_fast(tmp_path):
    partial = entry(
        case_id="CASE-PARTIAL",
        symbol="TESTP",
        case_status=CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY,
        evaluation_as_of=None,
        evaluation_result_path=None,
        outcome_observation_path=None,
    )
    registry_path = write_registry(tmp_path, (partial,))
    result = run_research_batch(request(("CASE-PARTIAL",)), registry_path)
    assert result.case_results == ()
    assert result.skipped_cases[0].case_id == "CASE-PARTIAL"
    assert {item.code.value for item in result.diagnostics} >= {
        "RESEARCH_BATCH_PARTIAL", "RESEARCH_BATCH_CASE_SKIPPED"
    }


def test_batch_fail_fast_rejects_partial_case(tmp_path):
    partial = entry(
        case_id="CASE-PARTIAL",
        symbol="TESTP",
        case_status=CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY,
        evaluation_as_of=None,
        evaluation_result_path=None,
        outcome_observation_path=None,
    )
    registry_path = write_registry(tmp_path, (partial,))
    with pytest.raises(ResearchBatchError) as error:
        run_research_batch(request(("CASE-PARTIAL",), fail_fast=True), registry_path)
    assert error.value.code == "RESEARCH_BATCH_CASE_FAILED"


def test_batch_repeated_output_is_byte_identical(tmp_path):
    registry_path = write_registry(tmp_path, (complete_entry(),))
    first = run_research_batch(request(), registry_path)
    second = run_research_batch(request(), registry_path)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_research_model(first) == serialize_research_model(second)


def test_empty_batch_is_rejected(tmp_path):
    registry_path = write_registry(tmp_path, (complete_entry(),))
    with pytest.raises(ResearchBatchError) as error:
        run_research_batch(request(()), registry_path)
    assert error.value.code == "RESEARCH_BATCH_EMPTY"
