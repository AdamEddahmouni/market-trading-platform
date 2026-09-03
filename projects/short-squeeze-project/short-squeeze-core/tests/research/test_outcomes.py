from datetime import datetime, timezone
from decimal import Decimal

import pytest

from squeeze_core.research.models import (
    OutcomeCompleteness,
    OutcomeLabel,
    RetrospectiveOutcomeObservation,
)
from squeeze_core.research.outcomes import label_outcome
from squeeze_core.research.policies import OUTCOME_POLICY_VERSION, load_outcome_policy
from squeeze_core.research.serialization import serialize_research_model


BOUNDARY = datetime(2026, 7, 17, 14, 23, 58, tzinfo=timezone.utc)
POLICY = load_outcome_policy(OUTCOME_POLICY_VERSION)


def observation(up, down, completeness=OutcomeCompleteness.COMPLETE):
    return RetrospectiveOutcomeObservation(
        case_id="CASE-A",
        symbol="TESTA",
        detection_boundary=BOUNDARY,
        reference_price_policy=POLICY.reference_price_policy,
        reference_price=Decimal("4"),
        horizon=POLICY.horizon,
        maximum_observed_move_percent=up,
        maximum_adverse_move_percent=down,
        completeness=completeness,
        supporting_observation_ids=("observation-a",),
    )


@pytest.mark.parametrize(("up", "down", "completeness", "expected"), [
    (Decimal("25.01"), Decimal("-24"), OutcomeCompleteness.COMPLETE, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE),
    (Decimal("25"), Decimal("-24"), OutcomeCompleteness.PARTIAL, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE),
    (Decimal("24"), Decimal("-25"), OutcomeCompleteness.PARTIAL, OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE),
    (Decimal("25"), Decimal("-25"), OutcomeCompleteness.PARTIAL, OutcomeLabel.MIXED_OR_VOLATILE),
    (Decimal("24.99"), Decimal("-24.99"), OutcomeCompleteness.COMPLETE, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE),
    (Decimal("24.99"), Decimal("-24.99"), OutcomeCompleteness.PARTIAL, OutcomeLabel.OUTCOME_INSUFFICIENT_DATA),
    (None, None, OutcomeCompleteness.UNAVAILABLE, OutcomeLabel.OUTCOME_UNKNOWN),
])
def test_outcome_truth_table_and_threshold_equality(up, down, completeness, expected):
    result = label_outcome(observation(up, down, completeness), POLICY)
    assert result.label is expected
    assert result.outcome_observation_id


def test_partial_window_cannot_prove_no_substantial_move():
    partial = label_outcome(observation(Decimal("3"), Decimal("-2"), OutcomeCompleteness.PARTIAL), POLICY)
    complete = label_outcome(observation(Decimal("3"), Decimal("-2"), OutcomeCompleteness.COMPLETE), POLICY)
    assert partial.label is OutcomeLabel.OUTCOME_INSUFFICIENT_DATA
    assert complete.label is OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE


def test_outcome_label_identity_and_serialization_are_stable():
    source = observation(Decimal("25"), Decimal("-4"), OutcomeCompleteness.PARTIAL)
    first = label_outcome(source, POLICY)
    second = label_outcome(source, POLICY)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_research_model(first) == serialize_research_model(second)
