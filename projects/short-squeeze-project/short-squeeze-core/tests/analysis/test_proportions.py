from decimal import Decimal

import pytest

from squeeze_core.analysis import AnalysisUnit, UndefinedReason
from squeeze_core.analysis.proportions import ProportionContext, build_proportion


CONTEXT = ProportionContext(
    cohort_id="cohort-id",
    analysis_unit=AnalysisUnit.CASE_BOUNDARY,
    interval_policy_version="phase_3c_interval_policy.v1",
    confidence_level=Decimal("0.95"),
    sample_size_policy_version="phase_3c_sample_size_policy.v1",
)


@pytest.mark.parametrize(
    ("numerator", "denominator", "fraction", "decimal", "percentage"),
    (
        (0, 1, "0/1", Decimal("0"), Decimal("0")),
        (1, 1, "1/1", Decimal("1"), Decimal("100")),
        (1, 2, "1/2", Decimal("0.5"), Decimal("50.0")),
        (
            2,
            3,
            "2/3",
            Decimal("0.6666666666666666666666666667"),
            Decimal("66.66666666666666666666666667"),
        ),
    ),
)
def test_defined_proportions_preserve_exact_counts_and_decimals(
    numerator, denominator, fraction, decimal, percentage
):
    result = build_proportion("pass_rate_among_evaluable_cases", numerator, denominator, CONTEXT)
    assert result.defined
    assert result.numerator == numerator
    assert result.denominator == denominator
    assert result.exact_fraction == fraction
    assert result.decimal_value == decimal
    assert result.percentage_value == percentage
    assert result.undefined_reason is None
    assert result.cohort_id == "cohort-id"
    assert result.analysis_unit is AnalysisUnit.CASE_BOUNDARY


def test_zero_denominator_is_undefined_not_zero_percent():
    result = build_proportion("sensitivity", 0, 0, CONTEXT)
    assert not result.defined
    assert result.exact_fraction == "0/0"
    assert result.decimal_value is None
    assert result.percentage_value is None
    assert result.undefined_reason is UndefinedReason.ZERO_DENOMINATOR
    assert result.interval is None


@pytest.mark.parametrize(("numerator", "denominator"), ((-1, 1), (1, -1), (2, 1)))
def test_invalid_proportion_counts_are_rejected(numerator, denominator):
    with pytest.raises(ValueError, match="ANALYSIS_PROPORTION_COUNTS_INVALID"):
        build_proportion("coverage_rate_among_all_cases", numerator, denominator, CONTEXT)


def test_proportion_identity_is_stable_and_policy_complete():
    first = build_proportion("evaluability_rate_among_all_cases", 1, 2, CONTEXT)
    second = build_proportion("evaluability_rate_among_all_cases", 1, 2, CONTEXT)
    changed_context = CONTEXT.model_copy(update={"confidence_level": Decimal("0.90")})
    changed = build_proportion("evaluability_rate_among_all_cases", 1, 2, changed_context)
    assert first.deterministic_id == second.deterministic_id
    assert first.deterministic_id != changed.deterministic_id

