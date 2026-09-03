from decimal import Decimal

import pytest

from squeeze_core.research.models import OutcomeCompleteness
from squeeze_core.research.policies import (
    DETECTION_POLICY_VERSION,
    OUTCOME_POLICY_VERSION,
    ResearchPolicyConfigurationError,
    load_detection_policy,
    load_outcome_policy,
)


def test_approved_policies_are_exact_provisional_and_unoptimized():
    detection = load_detection_policy(DETECTION_POLICY_VERSION)
    outcome = load_outcome_policy(OUTCOME_POLICY_VERSION)
    assert detection.required_rule_ids == (
        "PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE"
    )
    assert detection.provisional is True
    assert outcome.reference_price_policy == (
        "first_eligible_trade_bar_close_at_or_after_boundary.v1"
    )
    assert outcome.horizon == "24_HOURS"
    assert outcome.upward_threshold_percent == Decimal("25")
    assert outcome.downward_threshold_percent == Decimal("-25")
    assert outcome.provisional is True
    assert OutcomeCompleteness.PARTIAL.value == "PARTIAL"


def test_unsupported_policy_versions_are_structured_errors():
    with pytest.raises(ResearchPolicyConfigurationError) as error:
        load_detection_policy("unsupported.v1")
    assert error.value.code == "RESEARCH_DETECTION_POLICY_UNSUPPORTED"
    with pytest.raises(ResearchPolicyConfigurationError) as error:
        load_outcome_policy("unsupported.v1")
    assert error.value.code == "RESEARCH_OUTCOME_POLICY_UNSUPPORTED"
