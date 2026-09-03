import pytest

from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evaluation import (
    RuleCategory, RuleEvaluationRequest, RuleEvaluationResult, RuleOutcome,
    serialize_candidate_evaluation,
)
from squeeze_core.evaluation.candidate import summarize_results
from squeeze_core.evaluation.evaluator import evaluate_candidate
from squeeze_core.evaluation.policies import DuplicateRuleError, UnknownRuleError, lookup_policy

from .helpers import AS_OF, bar, borrow_fee, news

POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")


def test_inapplicable_asset_class_returns_not_applicable_for_each_rule():
    candidate_request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.ETF, as_of=AS_OF,
        policy_version=POLICY.policy_version,
        enabled_rule_ids=("PRICE_RANGE", "NEWS_AVAILABLE"),
        provider_scope=("provider-a",),
    )
    result = evaluate_candidate(candidate_request, POLICY)
    assert {item.outcome for item in result.rule_results} == {RuleOutcome.NOT_APPLICABLE}


def request(enabled, observations):
    return RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=enabled,
        provider_scope=("provider-a", "news-a"), input_observations=observations,
    )


def synthetic_result(outcome: RuleOutcome) -> RuleEvaluationResult:
    state = {
        RuleOutcome.PASS: QualityState.KNOWN_VALUE,
        RuleOutcome.FAIL: QualityState.KNOWN_VALUE,
        RuleOutcome.UNKNOWN: QualityState.UNAVAILABLE,
        RuleOutcome.CONFLICTED: QualityState.CONFLICTED,
        RuleOutcome.INSUFFICIENT_DATA: QualityState.MISSING,
        RuleOutcome.NOT_APPLICABLE: QualityState.NOT_APPLICABLE,
    }[outcome]
    return RuleEvaluationResult(
        rule_id=f"RULE_{outcome.value}", rule_version="v1",
        category=RuleCategory.MOMENTUM_DISCOVERY,
        policy_version=POLICY.policy_version, symbol="TESTA", asset_class=AssetClass.EQUITY,
        as_of=AS_OF, outcome=outcome,
        quality=Quality(state=state, reasons=() if state is QualityState.KNOWN_VALUE else (outcome.value,)),
        explanation_code=f"EVALUATION_{outcome.value}",
    )


def test_candidate_dispatches_across_categories_without_aggregate_outcome():
    enabled = (
        "PRICE_RANGE", "BORROW_FEE_MINIMUM", "NEWS_AVAILABLE", "NO_DEFAULT_SUBSTITUTION",
    )
    result = evaluate_candidate(request(enabled, (bar("10"), borrow_fee("5"), news())), POLICY)
    assert {item.category for item in result.rule_results} == set(RuleCategory)
    outcomes = {item.rule_id: item.outcome for item in result.rule_results}
    assert outcomes == {
        "BORROW_FEE_MINIMUM": RuleOutcome.FAIL,
        "NEWS_AVAILABLE": RuleOutcome.PASS,
        "NO_DEFAULT_SUBSTITUTION": RuleOutcome.PASS,
        "PRICE_RANGE": RuleOutcome.PASS,
    }
    assert "overall_outcome" not in type(result).model_fields


def test_category_summary_counts_each_exact_outcome():
    summary = summarize_results(tuple(synthetic_result(item) for item in RuleOutcome))[0]
    assert summary.pass_count == 1
    assert summary.fail_count == 1
    assert summary.unknown_count == 1
    assert summary.conflicted_count == 1
    assert summary.insufficient_data_count == 1
    assert summary.not_applicable_count == 1


def test_rule_and_input_order_invariance_and_stable_candidate_id():
    observations = (bar("10"), borrow_fee("5"), news())
    enabled = ("PRICE_RANGE", "BORROW_FEE_MINIMUM", "NEWS_AVAILABLE")
    first = evaluate_candidate(request(enabled, observations), POLICY)
    second = evaluate_candidate(request(tuple(reversed(enabled)), tuple(reversed(observations))), POLICY)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_candidate_evaluation(first) == serialize_candidate_evaluation(second)


def test_duplicate_and_unknown_rules_are_structured_errors():
    with pytest.raises(DuplicateRuleError):
        evaluate_candidate(request(("PRICE_RANGE", "PRICE_RANGE"), (bar(),)), POLICY)
    with pytest.raises(UnknownRuleError):
        evaluate_candidate(request(("NOT_A_RULE",), (bar(),)), POLICY)
