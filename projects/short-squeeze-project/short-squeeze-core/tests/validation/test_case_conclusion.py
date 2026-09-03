import json
from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.validation import (
    CaseStatus,
    ComparisonState,
    MethodologyConclusion,
    OriginalFieldValue,
    OriginalValueState,
    OutcomeWindow,
    RuleValidationState,
    build_field_comparison,
    build_original_snapshot,
    build_outcome_observation,
    build_outcome_window,
    build_rule_validation,
    build_validation_case,
    derive_case_status,
    derive_conclusion,
    serialize_case_conclusion,
    unknown_field,
    unobserved_outcome,
)

from .conftest import biya_log_artifact, biya_meeting_artifact, recovered_field
from squeeze_core.validation import build_detection_time_evidence

REF_TIME = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)


def _detection():
    return build_detection_time_evidence(
        "TEST", (biya_log_artifact(), biya_meeting_artifact())
    )


def _observed_outcome(symbol="TEST"):
    window = build_outcome_window(
        OutcomeWindow.HOUR_1,
        reference_price=Decimal("10"),
        window_end_time=REF_TIME,
        high_price=Decimal("25"),
        low_price=Decimal("9.5"),
        close_price=Decimal("24"),
    )
    return build_outcome_observation(
        symbol, (window,), reference_price=Decimal("10"), reference_price_time=REF_TIME
    )


def _snapshot_with(*fields):
    return build_original_snapshot("TEST", fields)


def test_validated_as_recorded_when_every_comparison_reproduces():
    snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    comparison = build_field_comparison(
        "price",
        recovered_field("price", Decimal("4.20"), unit="USD"),
        rebuilt_value=Decimal("4.20"),
        rebuilt_unit="USD",
    )
    assert comparison.comparison_state is ComparisonState.MATCH
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(build_rule_validation("R1", RuleValidationState.SUPPORTED, "ok"),),
        field_comparisons=(comparison,),
    )
    assert conclusion.conclusion is MethodologyConclusion.VALIDATED_AS_RECORDED


def test_partially_validated_when_some_rules_hold_and_others_do_not():
    snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(
            build_rule_validation("R1", RuleValidationState.SUPPORTED_WITH_CORRECTION, "fixable"),
            build_rule_validation("R2", RuleValidationState.MISLABELED, "bad label"),
        ),
        field_comparisons=(),
    )
    assert conclusion.conclusion is MethodologyConclusion.PARTIALLY_VALIDATED


def test_not_point_in_time_valid_when_a_rule_needed_absent_evidence():
    snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(
            build_rule_validation("R1", RuleValidationState.SUPPORTED, "ok"),
            build_rule_validation(
                "R2", RuleValidationState.UNAVAILABLE_AT_DETECTION, "arrived later"
            ),
        ),
    )
    assert conclusion.conclusion is MethodologyConclusion.NOT_POINT_IN_TIME_VALID


def test_default_substitution_also_breaks_point_in_time_validity():
    snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(
            build_rule_validation(
                "R1", RuleValidationState.MISSING_DEFAULT_SUBSTITUTION, "defaulted"
            ),
        ),
    )
    assert conclusion.conclusion is MethodologyConclusion.NOT_POINT_IN_TIME_VALID


def test_outcome_confirmed_methodology_unverified():
    """An original value survives, no rule is classifiable either way, and the symbol
    moved."""

    ambiguous = OriginalFieldValue(
        field_id="price",
        state=OriginalValueState.AMBIGUOUS,
        value="4.20",
        ambiguity_note="units not recorded",
    )
    snapshot = build_original_snapshot("TEST", (recovered_field("price", Decimal("4.20")), ambiguous))
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(build_rule_validation("R1", RuleValidationState.UNKNOWN, "unclear"),),
        field_comparisons=(),
        outcome=_observed_outcome(),
    )
    assert conclusion.conclusion is MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED


def test_insufficient_evidence_when_no_original_value_survives():
    snapshot = build_original_snapshot(
        "TEST", (unknown_field("price"), unknown_field("days_to_cover"))
    )
    conclusion = derive_conclusion(
        "TEST", detection_time=_detection(), original_snapshot=snapshot
    )
    assert conclusion.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE


def test_insufficient_evidence_when_the_snapshot_is_missing_entirely():
    conclusion = derive_conclusion("TEST", detection_time=_detection(), original_snapshot=None)
    assert conclusion.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE
    assert any("no original candidate snapshot" in item for item in conclusion.supporting_findings)


def test_later_evidence_cannot_retroactively_validate_the_original_decision():
    """The load-bearing rule of the phase: a large subsequent move added to a case with
    no recoverable original values must not upgrade the conclusion."""

    snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    without = derive_conclusion(
        "TEST", detection_time=_detection(), original_snapshot=snapshot
    )
    with_outcome = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        outcome=_observed_outcome(),
    )
    assert without.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE
    assert with_outcome.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE
    assert any(
        "does not upgrade" in item for item in with_outcome.limitations
    ), with_outcome.limitations


def test_missing_outcome_data_is_recorded_as_a_limitation():
    snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    conclusion = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(build_rule_validation("R1", RuleValidationState.SUPPORTED, "ok"),),
        outcome=unobserved_outcome("TEST"),
    )
    assert any("no outcome window" in item for item in conclusion.limitations)


def test_bounded_window_is_reported_in_the_findings():
    snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    conclusion = derive_conclusion(
        "TEST", detection_time=_detection(), original_snapshot=snapshot
    )
    assert any("bounded" in item for item in conclusion.supporting_findings)


def test_conclusion_is_deterministic():
    snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    first = derive_conclusion("TEST", detection_time=_detection(), original_snapshot=snapshot)
    second = derive_conclusion("TEST", detection_time=_detection(), original_snapshot=snapshot)
    assert first.deterministic_id == second.deterministic_id
    assert serialize_case_conclusion(first) == serialize_case_conclusion(second)


def test_different_conclusions_have_different_identities():
    unknown_snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    known_snapshot = _snapshot_with(recovered_field("price", Decimal("4.20"), unit="USD"))
    insufficient = derive_conclusion(
        "TEST", detection_time=_detection(), original_snapshot=unknown_snapshot
    )
    partial = derive_conclusion(
        "TEST",
        detection_time=_detection(),
        original_snapshot=known_snapshot,
        rule_validations=(build_rule_validation("R1", RuleValidationState.MOMENTUM_DISCOVERY_ONLY, "m"),),
    )
    assert insufficient.deterministic_id != partial.deterministic_id


def test_conclusion_carries_no_candidate_quality_field():
    snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    conclusion = derive_conclusion("TEST", detection_time=_detection(), original_snapshot=snapshot)
    payload = json.loads(serialize_case_conclusion(conclusion))
    keys = {key.lower() for key in payload}
    for forbidden in ("score", "rank", "tier", "prime", "recommend", "signal", "confidence"):
        assert not any(forbidden in key for key in keys)


def test_case_status_reports_the_first_real_blocker():
    unknown_snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    assert (
        derive_case_status(detection_time=None, original_snapshot=unknown_snapshot)
        is CaseStatus.BLOCKED_MISSING_DETECTION_TIME
    )
    assert (
        derive_case_status(detection_time=_detection(), original_snapshot=unknown_snapshot)
        is CaseStatus.BLOCKED_MISSING_ORIGINAL_OUTPUT
    )
    known_snapshot = _snapshot_with(recovered_field("price", Decimal("4.20")))
    assert (
        derive_case_status(
            detection_time=_detection(), original_snapshot=known_snapshot, outcome=unobserved_outcome("TEST")
        )
        is CaseStatus.BLOCKED_MISSING_MARKET_DATA
    )


def test_case_status_is_never_complete_from_artifact_discovery_alone():
    snapshot = build_original_snapshot("TEST", (unknown_field("price"),))
    case = build_validation_case(
        "case-test", "TEST",
        artifacts=(biya_log_artifact(), biya_meeting_artifact()),
        detection_time=_detection(),
        original_snapshot=snapshot,
        outcome=unobserved_outcome("TEST"),
    )
    assert case.case_status is not CaseStatus.COMPLETE


def test_full_biya_shaped_case_concludes_insufficient_evidence():
    snapshot = build_original_snapshot(
        "BIYA", tuple(unknown_field(name) for name in ("price", "short_interest_percent", "days_to_cover"))
    )
    case = build_validation_case(
        "case-biya", "BIYA",
        artifacts=(biya_log_artifact(), biya_meeting_artifact()),
        detection_time=_detection(),
        original_snapshot=snapshot,
        rule_validations=(
            build_rule_validation("R1", RuleValidationState.MOMENTUM_DISCOVERY_ONLY, "m"),
            build_rule_validation("R2", RuleValidationState.MISLABELED, "l"),
        ),
        outcome=unobserved_outcome("BIYA"),
    )
    assert case.conclusion is not None
    assert case.conclusion.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE
    assert case.case_status is CaseStatus.BLOCKED_MISSING_ORIGINAL_OUTPUT
