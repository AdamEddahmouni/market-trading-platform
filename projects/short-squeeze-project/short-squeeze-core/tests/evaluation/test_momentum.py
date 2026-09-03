from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.evaluation import RuleEvaluationRequest, RuleOutcome
from squeeze_core.evaluation.policies import lookup_policy, lookup_rule
from squeeze_core.evaluation.rules.momentum import evaluate_momentum_rule
from squeeze_core.metrics import MetricName, MetricUnit

from .helpers import AS_OF, bar, normalized_metric, snapshot

POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")


def evaluate(rule_id: str, *, observations=(), metrics=(), providers=("provider-a",)):
    request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=(rule_id,),
        provider_scope=providers, input_observations=observations, input_metrics=metrics,
    )
    return evaluate_momentum_rule(request, lookup_rule(POLICY, rule_id))


def test_price_range_pass_fail_boundaries_and_missing():
    assert evaluate("PRICE_RANGE", observations=(bar("2"),)).outcome is RuleOutcome.PASS
    assert evaluate("PRICE_RANGE", observations=(bar("20"),)).outcome is RuleOutcome.PASS
    assert evaluate("PRICE_RANGE", observations=(bar("1.99"),)).outcome is RuleOutcome.FAIL
    assert evaluate("PRICE_RANGE", observations=(bar("20.01"),)).outcome is RuleOutcome.FAIL
    missing = evaluate("PRICE_RANGE")
    assert missing.outcome is RuleOutcome.UNKNOWN
    assert missing.observed_value is None


def test_percentage_change_and_relative_volume_use_existing_metrics():
    return_pass = normalized_metric(MetricName.PERCENTAGE_RETURN, "10", MetricUnit.PERCENT)
    return_fail = normalized_metric(MetricName.PERCENTAGE_RETURN, "9.99", MetricUnit.PERCENT)
    assert evaluate("PERCENTAGE_CHANGE_MINIMUM", metrics=(return_pass,)).outcome is RuleOutcome.PASS
    assert evaluate("PERCENTAGE_CHANGE_MINIMUM", metrics=(return_fail,)).outcome is RuleOutcome.FAIL
    relative = normalized_metric(MetricName.RELATIVE_VOLUME, "5", MetricUnit.RATIO)
    assert evaluate("RELATIVE_VOLUME_MINIMUM", metrics=(relative,)).outcome is RuleOutcome.PASS
    assert evaluate("RELATIVE_VOLUME_MINIMUM", metrics=(
        normalized_metric(MetricName.RELATIVE_VOLUME, "4.99", MetricUnit.RATIO),
    )).outcome is RuleOutcome.FAIL


def test_relative_volume_insufficient_history_and_unavailable_are_not_failures():
    insufficient = normalized_metric(MetricName.RELATIVE_VOLUME, None, MetricUnit.RATIO,
                                     state=QualityState.MISSING)
    assert evaluate("RELATIVE_VOLUME_MINIMUM", metrics=(insufficient,)).outcome is RuleOutcome.INSUFFICIENT_DATA
    assert evaluate("RELATIVE_VOLUME_MINIMUM").outcome is RuleOutcome.UNKNOWN


def test_float_known_and_unknown_without_unverified_substitution():
    assert evaluate("FLOAT_MAXIMUM", observations=(snapshot(float_shares=20_000_000),)).outcome is RuleOutcome.PASS
    assert evaluate("FLOAT_MAXIMUM", observations=(snapshot(float_shares=20_000_001),)).outcome is RuleOutcome.FAIL
    assert evaluate("FLOAT_MAXIMUM").outcome is RuleOutcome.UNKNOWN


def test_market_data_and_completed_bar_preserve_partial_and_future_states():
    assert evaluate("MARKET_DATA_AVAILABLE", observations=(bar(),)).outcome is RuleOutcome.PASS
    assert evaluate("COMPLETED_BAR_AVAILABLE", observations=(bar(),)).outcome is RuleOutcome.PASS
    assert evaluate("COMPLETED_BAR_AVAILABLE", observations=(bar(status="PARTIAL"),)).outcome is RuleOutcome.FAIL
    from datetime import timedelta
    assert evaluate("COMPLETED_BAR_AVAILABLE", observations=(bar(source_time=AS_OF + timedelta(minutes=1)),)).outcome is RuleOutcome.UNKNOWN


def test_provider_scope_mismatch_does_not_mix_inputs_and_support_ids_are_stable():
    mixed = evaluate("PRICE_RANGE", observations=(bar(provider="provider-b"),), providers=("provider-a",))
    assert mixed.outcome is RuleOutcome.UNKNOWN
    first = evaluate("PRICE_RANGE", observations=(bar(),))
    second = evaluate("PRICE_RANGE", observations=tuple(reversed((bar(),))))
    assert first.input_observation_ids == second.input_observation_ids
    assert first.deterministic_id == second.deterministic_id
