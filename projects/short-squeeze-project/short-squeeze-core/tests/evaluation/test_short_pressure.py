from datetime import timedelta

from squeeze_core.contracts import AssetClass, EventType, QualityState
from squeeze_core.evaluation import RuleEvaluationRequest, RuleOutcome
from squeeze_core.evaluation.policies import lookup_policy, lookup_rule
from squeeze_core.evaluation.rules.short_pressure import evaluate_short_pressure_rule
from squeeze_core.metrics import MetricName, MetricUnit

from .helpers import (
    AS_OF, borrow_availability, borrow_fee, pressure_metric, quality, short_interest,
)

POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")


def evaluate(rule_id: str, *, observations=(), metrics=(), providers=("provider-a",), borrow_provider=None):
    request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=(rule_id,),
        provider_scope=providers, input_observations=observations, input_metrics=metrics,
        borrow_provider=borrow_provider,
    )
    return evaluate_short_pressure_rule(request, lookup_rule(POLICY, rule_id))


def test_published_short_interest_available_missing_future_and_conflicted():
    present = evaluate("PUBLISHED_SHORT_INTEREST_AVAILABLE", observations=(short_interest(),))
    assert present.outcome is RuleOutcome.PASS
    assert present.input_observation_ids
    assert evaluate("PUBLISHED_SHORT_INTEREST_AVAILABLE").outcome is RuleOutcome.UNKNOWN
    future = short_interest().model_copy(update={
        "source_timestamp": AS_OF + timedelta(minutes=1),
        "received_timestamp": AS_OF + timedelta(minutes=1),
        "effective_timestamp": AS_OF + timedelta(minutes=1),
    })
    assert evaluate("PUBLISHED_SHORT_INTEREST_AVAILABLE", observations=(future,)).outcome is RuleOutcome.UNKNOWN
    conflicted = short_interest().model_copy(update={
        "quality": quality(QualityState.CONFLICTED, "material conflict")
    })
    assert evaluate("PUBLISHED_SHORT_INTEREST_AVAILABLE", observations=(conflicted,)).outcome is RuleOutcome.CONFLICTED


def test_short_interest_change_and_days_to_cover_pass_fail_unknown_insufficient():
    assert evaluate("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", metrics=(
        pressure_metric(MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE, "10", MetricUnit.PERCENT),
    )).outcome is RuleOutcome.PASS
    assert evaluate("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", metrics=(
        pressure_metric(MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE, "9", MetricUnit.PERCENT),
    )).outcome is RuleOutcome.FAIL
    assert evaluate("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM").outcome is RuleOutcome.UNKNOWN
    assert evaluate("DAYS_TO_COVER_MINIMUM", metrics=(
        pressure_metric(MetricName.DAYS_TO_COVER, "2", MetricUnit.DAYS),
    )).outcome is RuleOutcome.PASS
    assert evaluate("DAYS_TO_COVER_MINIMUM", metrics=(
        pressure_metric(MetricName.DAYS_TO_COVER, "1.2", MetricUnit.DAYS),
    )).outcome is RuleOutcome.FAIL
    insufficient = pressure_metric(MetricName.DAYS_TO_COVER, None, MetricUnit.DAYS,
                                   state=QualityState.MISSING)
    assert evaluate("DAYS_TO_COVER_MINIMUM", metrics=(insufficient,)).outcome is RuleOutcome.INSUFFICIENT_DATA
    assert evaluate("DAYS_TO_COVER_MINIMUM").outcome is RuleOutcome.UNKNOWN


def test_borrow_fee_value_change_units_and_provider_scope():
    assert evaluate("BORROW_FEE_MINIMUM", observations=(borrow_fee("10"),)).outcome is RuleOutcome.PASS
    assert evaluate("BORROW_FEE_MINIMUM", observations=(borrow_fee("9.9"),)).outcome is RuleOutcome.FAIL
    assert evaluate("BORROW_FEE_MINIMUM").outcome is RuleOutcome.UNKNOWN
    assert evaluate("BORROW_FEE_MINIMUM", observations=(borrow_fee(provider="provider-b"),)).outcome is RuleOutcome.UNKNOWN
    mixed = (borrow_fee("10", provider="provider-a"), borrow_fee("20", provider="provider-b"))
    assert evaluate("BORROW_FEE_MINIMUM", observations=mixed, providers=("provider-a", "provider-b")).outcome is RuleOutcome.UNKNOWN
    assert evaluate("BORROW_FEE_MINIMUM", observations=mixed, providers=("provider-a", "provider-b"), borrow_provider="provider-a").outcome is RuleOutcome.PASS
    assert evaluate("BORROW_FEE_CHANGE_MINIMUM", metrics=(
        pressure_metric(MetricName.BORROW_FEE_ABSOLUTE_CHANGE, "2", MetricUnit.PERCENTAGE_POINTS),
    )).outcome is RuleOutcome.PASS
    assert evaluate("BORROW_FEE_CHANGE_MINIMUM", metrics=(
        pressure_metric(MetricName.BORROW_FEE_ABSOLUTE_CHANGE, "1.9", MetricUnit.PERCENTAGE_POINTS),
    )).outcome is RuleOutcome.FAIL
    mismatch = pressure_metric(MetricName.BORROW_FEE_ABSOLUTE_CHANGE, "2", MetricUnit.PERCENT)
    assert evaluate("BORROW_FEE_CHANGE_MINIMUM", metrics=(mismatch,)).outcome is RuleOutcome.INSUFFICIENT_DATA


def test_borrow_availability_zero_is_known_and_changes_are_independent():
    zero = evaluate("BORROW_AVAILABILITY_MAXIMUM", observations=(borrow_availability(0),))
    assert zero.outcome is RuleOutcome.PASS
    assert zero.observed_value == 0
    assert evaluate("BORROW_AVAILABILITY_MAXIMUM", observations=(
        borrow_availability(100_001),
    )).outcome is RuleOutcome.FAIL
    assert evaluate("BORROW_AVAILABILITY_MAXIMUM").outcome is RuleOutcome.UNKNOWN
    assert evaluate("BORROW_AVAILABILITY_CHANGE_MAXIMUM", metrics=(
        pressure_metric(MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE, "-10000", MetricUnit.SHARES),
    )).outcome is RuleOutcome.PASS
    assert evaluate("BORROW_AVAILABILITY_CHANGE_MAXIMUM", metrics=(
        pressure_metric(MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE, "-9999", MetricUnit.SHARES),
    )).outcome is RuleOutcome.FAIL


def test_daily_short_sale_volume_is_never_a_short_pressure_substitute():
    for rule_id in (
        "PUBLISHED_SHORT_INTEREST_AVAILABLE", "SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM",
        "DAYS_TO_COVER_MINIMUM",
    ):
        assert evaluate(rule_id).outcome is RuleOutcome.UNKNOWN
