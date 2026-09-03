from datetime import UTC, datetime, timedelta
from decimal import Decimal

from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation import MethodologyConclusion
from squeeze_core.validation.case_spec import build_case_from_spec, load_case_spec
from squeeze_core.validation.outcome_amendment import (
    BIYA_EARLIEST_BOUNDARY,
    BIYA_LATEST_BOUNDARY,
    build_boundary_outcome,
)
from squeeze_core.validation.outcome_case import (
    OutcomeConfirmationState,
    OutcomeSubstantialMovePolicy,
    build_biya_outcome_amendment_case,
)

from .test_outcome_amendment import bar, dataset


def outcomes(maximum: str = "8"):
    first_start = datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    latest_start = datetime(2026, 7, 17, 16, 55, tzinfo=UTC)
    observations = (
        bar(first_start, "4"),
        bar(latest_start, "4", high="4"),
        bar(latest_start + timedelta(minutes=1), maximum, high=maximum),
    )
    data = dataset(observations)
    return (
        build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, data),
        build_boundary_outcome(BIYA_LATEST_BOUNDARY, data),
    )


def original_case():
    return build_case_from_spec(load_case_spec(__import__("pathlib").Path("tests/fixtures/validation/biya_validation_case.json")))


def test_confirmed_substantial_outcome_with_missing_original_values_is_unverified() -> None:
    result = build_biya_outcome_amendment_case(original_case(), outcomes("8"))
    assert result.confirmation.state is OutcomeConfirmationState.CONFIRMED
    assert result.confirmation.policy is OutcomeSubstantialMovePolicy.BOTH_BOUNDARIES_25_PERCENT
    assert result.conclusion is MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED
    assert result.original_values_recovered == 0


def test_missing_or_flat_outcome_preserves_insufficient_evidence() -> None:
    missing = build_biya_outcome_amendment_case(original_case(), ())
    assert missing.confirmation.state is OutcomeConfirmationState.INSUFFICIENT_DATA
    assert missing.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE

    flat = build_biya_outcome_amendment_case(original_case(), outcomes("4"))
    assert flat.confirmation.state is OutcomeConfirmationState.NOT_CONFIRMED
    assert flat.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE


def test_one_favorable_boundary_cannot_confirm_outcome() -> None:
    earliest, latest = outcomes("8")
    # Keep one complete substantial boundary only; favorable-boundary selection is forbidden.
    result = build_biya_outcome_amendment_case(original_case(), (earliest,))
    assert result.confirmation.state is OutcomeConfirmationState.INSUFFICIENT_DATA
    assert result.conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE


def test_article_or_professor_statement_cannot_enter_confirmation_identity() -> None:
    first = build_biya_outcome_amendment_case(
        original_case(), outcomes("8"), contextual_evidence_ids=("ARTICLE-LATER",)
    )
    second = build_biya_outcome_amendment_case(
        original_case(), outcomes("8"), contextual_evidence_ids=("PROFESSOR-STATEMENT",)
    )
    assert first.confirmation == second.confirmation
    assert first.confirmation.deterministic_id == second.confirmation.deterministic_id


def test_original_phase_2v_case_remains_byte_identical() -> None:
    case = original_case()
    before = canonical_json_bytes(case)
    amendment = build_biya_outcome_amendment_case(case, outcomes("8"))
    assert canonical_json_bytes(case) == before
    assert amendment.original_case_id == case.case_id
    assert amendment.original_case_deterministic_id == case.deterministic_id
    assert amendment.original_conclusion is MethodologyConclusion.INSUFFICIENT_EVIDENCE


def test_amendment_identity_is_stable_and_cannot_validate_methodology() -> None:
    case = original_case()
    first = build_biya_outcome_amendment_case(case, outcomes("8"))
    second = build_biya_outcome_amendment_case(case, tuple(reversed(outcomes("8"))))
    assert first.deterministic_id == second.deterministic_id
    assert first.conclusion not in {
        MethodologyConclusion.VALIDATED_AS_RECORDED,
        MethodologyConclusion.PARTIALLY_VALIDATED,
        MethodologyConclusion.NOT_POINT_IN_TIME_VALID,
    }
    rendered = canonical_json_bytes(first).decode("utf-8").lower()
    for forbidden in ("profit", "p&l", "entry", "exit", "fill_price", "recommendation"):
        assert forbidden not in rendered

