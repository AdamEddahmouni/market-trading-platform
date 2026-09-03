from pathlib import Path

import pytest

from squeeze_core.evaluation import RuleCategory
from squeeze_core.evaluation.policies import (
    DEFAULT_POLICY_PATH,
    DuplicateRuleError,
    UnknownPolicyError,
    UnknownRuleError,
    load_policy,
    lookup_policy,
    lookup_rule,
    validate_enabled_rules,
)


def test_default_policy_loads_with_exact_rule_inventory():
    policy = load_policy(DEFAULT_POLICY_PATH)
    assert policy.policy_version == "phase_3a_transparent_candidate_policy.v1"
    assert len(policy.rules) == 25
    assert {item.category for item in policy.rules} == set(RuleCategory)
    assert policy.enabled_rule_ids == tuple(sorted(item.rule_id for item in policy.rules))


def test_every_threshold_has_units_operator_provenance_and_provisional_state():
    policy = lookup_policy("phase_3a_transparent_candidate_policy.v1")
    thresholds = [threshold for rule in policy.rules for threshold in rule.thresholds]
    assert thresholds
    for item in thresholds:
        assert item.unit
        assert item.operator
        assert item.source_type
        assert item.source_reference
        assert item.rationale_code
        assert isinstance(item.provisional, bool)


def test_every_rule_has_explicit_provider_session_interval_and_history_contract():
    policy = lookup_policy("phase_3a_transparent_candidate_policy.v1")
    for rule in policy.rules:
        assert isinstance(rule.provider_scope_required, bool)
        assert rule.required_interval is None or rule.required_interval.value
        assert isinstance(rule.required_sessions, tuple)
        assert rule.required_history_samples >= 0


def test_rule_lookup_unknown_policy_and_unknown_rule_are_structured():
    policy = lookup_policy("phase_3a_transparent_candidate_policy.v1")
    assert lookup_rule(policy, "PRICE_RANGE").category is RuleCategory.MOMENTUM_DISCOVERY
    with pytest.raises(UnknownPolicyError) as policy_error:
        lookup_policy("missing-policy")
    assert policy_error.value.code == "EVALUATION_UNSUPPORTED_POLICY"
    with pytest.raises(UnknownRuleError) as rule_error:
        lookup_rule(policy, "MISSING_RULE")
    assert rule_error.value.code == "EVALUATION_UNKNOWN_RULE"


def test_duplicate_enabled_rules_fail_before_deterministic_sorting():
    policy = lookup_policy("phase_3a_transparent_candidate_policy.v1")
    with pytest.raises(DuplicateRuleError) as error:
        validate_enabled_rules(policy, ("PRICE_RANGE", "PRICE_RANGE"))
    assert error.value.code == "EVALUATION_DUPLICATE_RULE"


def test_policy_is_deterministic_and_contains_no_scoring_keys():
    first = load_policy(DEFAULT_POLICY_PATH)
    second = load_policy(Path(DEFAULT_POLICY_PATH))
    assert first == second
    rendered = DEFAULT_POLICY_PATH.read_text(encoding="utf-8").lower()
    for prohibited in ("weight", "score", "rank", "recommendation", "category_importance"):
        assert f'"{prohibited}"' not in rendered
