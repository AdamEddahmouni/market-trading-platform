import pytest

from squeeze_core.readiness.policies import (
    OPERATION_REQUIREMENT_POLICIES,
    UnsupportedOperationError,
    UnsupportedPolicyVersionError,
    lookup_policy,
)

_EXPECTED_OPERATIONS = {
    "ABSOLUTE_RETURN",
    "PERCENTAGE_RETURN",
    "ABSOLUTE_SESSION_GAP",
    "PERCENTAGE_SESSION_GAP",
    "ABSOLUTE_BAR_RANGE",
    "PERCENTAGE_BAR_RANGE",
    "MEAN_VOLUME_BASELINE",
    "RELATIVE_VOLUME",
    "VOLUME_Z_SCORE",
    "PERCENTAGE_RETURN_Z_SCORE",
    "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
    "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE",
    "DAYS_TO_COVER",
    "BORROW_FEE_ABSOLUTE_CHANGE",
    "BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE",
    "BORROW_AVAILABILITY_ABSOLUTE_CHANGE",
    "BORROW_AVAILABILITY_PERCENTAGE_CHANGE",
}


def test_all_seventeen_operations_registered():
    assert set(OPERATION_REQUIREMENT_POLICIES) == _EXPECTED_OPERATIONS


def test_known_operation_lookup_succeeds():
    policy = lookup_policy("DAYS_TO_COVER")
    assert policy.policy_version == "phase_2d_readiness_policy.v1"


def test_unknown_operation_raises_typed_error():
    with pytest.raises(UnsupportedOperationError):
        lookup_policy("COMPOSITE_SQUEEZE_SCORE")


def test_unsupported_policy_version_raises_typed_error():
    with pytest.raises(UnsupportedPolicyVersionError):
        lookup_policy("DAYS_TO_COVER", policy_version="phase_2d_readiness_policy.v2")


def test_required_and_optional_domains_disjoint_for_every_policy():
    for policy in OPERATION_REQUIREMENT_POLICIES.values():
        assert not set(policy.required_domains) & set(policy.optional_domains)


def test_days_to_cover_requires_short_interest_and_bars():
    from squeeze_core.evidence import CoverageDomain

    policy = lookup_policy("DAYS_TO_COVER")
    assert set(policy.required_domains) == {
        CoverageDomain.PUBLISHED_SHORT_INTEREST,
        CoverageDomain.MARKET_BARS,
    }
    assert policy.requires_trailing_window is True


def test_relative_volume_references_mean_volume_baseline():
    policy = lookup_policy("RELATIVE_VOLUME")
    assert policy.required_metric_names == ("MEAN_VOLUME_BASELINE",)


def test_borrow_fee_policy_requires_only_borrow_fee_domain():
    from squeeze_core.evidence import CoverageDomain

    policy = lookup_policy("BORROW_FEE_ABSOLUTE_CHANGE")
    assert policy.required_domains == (CoverageDomain.BORROW_FEE,)


def test_no_policy_defines_a_trading_threshold_field():
    forbidden = ("threshold", "min_price", "max_price", "score", "rank")
    for policy in OPERATION_REQUIREMENT_POLICIES.values():
        for field_name in type(policy).model_fields:
            lowered = field_name.lower()
            for term in forbidden:
                assert term not in lowered


def test_policy_registry_is_stable_across_two_lookups():
    first = lookup_policy("ABSOLUTE_RETURN")
    second = lookup_policy("ABSOLUTE_RETURN")
    assert first == second
