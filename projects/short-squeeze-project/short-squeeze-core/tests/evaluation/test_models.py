from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evaluation import (
    CandidateEvaluationResult,
    CategoryEvaluationSummary,
    RuleCategory,
    RuleEvaluationRequest,
    RuleEvaluationResult,
    RuleOutcome,
    RuleThreshold,
    ThresholdOperator,
    ThresholdSourceType,
    serialize_candidate_evaluation,
    serialize_rule_result,
)

AS_OF = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)


def _threshold() -> RuleThreshold:
    return RuleThreshold(
        threshold_id="price-min-v1",
        rule_id="PRICE_RANGE",
        value=Decimal("2.00"),
        unit="PRICE",
        operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
        policy_version="phase_3a_transparent_candidate_policy.v1",
        source_type=ThresholdSourceType.ORIGINAL_PLATFORM,
        source_reference="phase-2v-original-rule-manifest:RULE-001",
        rationale_code="ORIGINAL_PRICE_BAND_MINIMUM",
        provisional=True,
    )


def _result(**overrides) -> RuleEvaluationResult:
    values = dict(
        rule_id="PRICE_RANGE",
        rule_version="price_range.v1",
        category=RuleCategory.MOMENTUM_DISCOVERY,
        policy_version="phase_3a_transparent_candidate_policy.v1",
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        outcome=RuleOutcome.PASS,
        observed_value=Decimal("2.00"),
        observed_unit="PRICE",
        operator=ThresholdOperator.BETWEEN_INCLUSIVE,
        threshold_values=(Decimal("2.00"), Decimal("20.00")),
        threshold_unit="PRICE",
        provider_scope=("provider-a",),
        input_observation_ids=("obs-b", "obs-a"),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        explanation_code="EVALUATION_CONDITION_SATISFIED",
    )
    values.update(overrides)
    return RuleEvaluationResult(**values)


def test_exact_rule_category_and_outcome_order():
    assert tuple(item.value for item in RuleCategory) == (
        "MOMENTUM_DISCOVERY",
        "SHORT_PRESSURE_CONFIRMATION",
        "CATALYST_EVIDENCE",
        "EVIDENCE_VALIDITY",
    )
    assert tuple(item.value for item in RuleOutcome) == (
        "PASS",
        "FAIL",
        "UNKNOWN",
        "CONFLICTED",
        "INSUFFICIENT_DATA",
        "NOT_APPLICABLE",
    )


def test_threshold_and_request_are_frozen_and_deterministically_sorted():
    threshold = _threshold()
    with pytest.raises(ValidationError):
        threshold.value = Decimal("3")
    request = RuleEvaluationRequest(
        symbol="testa",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        policy_version="phase_3a_transparent_candidate_policy.v1",
        enabled_rule_ids=("RELATIVE_VOLUME_MINIMUM", "PRICE_RANGE"),
        provider_scope=("provider-b", "provider-a"),
    )
    assert request.symbol == "TESTA"
    assert request.enabled_rule_ids == ("PRICE_RANGE", "RELATIVE_VOLUME_MINIMUM")
    assert request.provider_scope == ("provider-a", "provider-b")
    with pytest.raises(ValidationError):
        request.symbol = "OTHER"


def test_rule_result_has_exact_decimal_bytes_and_stable_identity():
    first = _result()
    second = _result(input_observation_ids=("obs-a", "obs-b"))
    assert first.deterministic_id == second.deterministic_id
    assert serialize_rule_result(first) == serialize_rule_result(second)
    assert b'"observed_value":"2"' in serialize_rule_result(first)


def test_same_evidence_under_different_policy_version_has_distinct_identity():
    assert _result().deterministic_id != _result(policy_version="phase_3a_test_policy.v2").deterministic_id


def test_candidate_sorts_rules_and_counts_without_overall_state():
    passed = _result()
    unknown = _result(
        rule_id="FLOAT_MAXIMUM",
        rule_version="float_maximum.v1",
        outcome=RuleOutcome.UNKNOWN,
        observed_value=None,
        observed_unit=None,
        quality=Quality(state=QualityState.UNAVAILABLE, reasons=("float unavailable",)),
        explanation_code="EVALUATION_FLOAT_UNAVAILABLE",
    )
    result = CandidateEvaluationResult(
        evaluation_version="candidate_evaluation.v1",
        policy_version="phase_3a_transparent_candidate_policy.v1",
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        enabled_rule_ids=("PRICE_RANGE", "FLOAT_MAXIMUM"),
        rule_results=(passed, unknown),
        results_by_category=(
            CategoryEvaluationSummary(
                category=RuleCategory.MOMENTUM_DISCOVERY,
                pass_count=1,
                unknown_count=1,
            ),
        ),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    assert result.rule_results[0].rule_id == "FLOAT_MAXIMUM"
    assert result.results_by_category[0].pass_count == 1
    assert result.results_by_category[0].unknown_count == 1
    assert result.deterministic_id
    assert serialize_candidate_evaluation(result) == serialize_candidate_evaluation(result)


def test_no_scoring_ranking_or_recommendation_fields():
    forbidden = (
        "score", "weight", "grade", "rank", "recommend", "prime", "subprime",
        "candidate_label", "confidence_percent", "overall_outcome", "alert",
    )
    from squeeze_core.evaluation import models

    for name in models.__all__:
        obj = getattr(models, name)
        if not hasattr(obj, "model_fields"):
            continue
        for field_name in obj.model_fields:
            assert not any(word in field_name.lower() for word in forbidden), (
                f"{name}.{field_name} is prohibited"
            )
