import pytest

from squeeze_core.analysis import AnalysisUnit, UndefinedReason
from squeeze_core.analysis.confusion_matrix import (
    AnalysisConfusionMatrixError,
    build_confusion_matrix,
)
from squeeze_core.analysis.proportions import ProportionContext
from tests.analysis.helpers import load_dataset


def _context(*, independent: bool):
    from decimal import Decimal

    return ProportionContext(
        cohort_id="historical-case-boundary",
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        interval_policy_version="phase_3c_interval_policy.v1",
        confidence_level=Decimal("0.95"),
        sample_size_policy_version="phase_3c_sample_size_policy.v1",
        independence_assumption_satisfied=independent,
    )


def _by_metric(summary):
    return {item.metric_name: item for item in summary.descriptive_rates}


def test_historical_biya_confusion_counts_are_dependent_descriptions():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    summary = build_confusion_matrix(rows, _context(independent=False))
    assert (
        summary.true_positive_count,
        summary.false_positive_count,
        summary.true_negative_count,
        summary.false_negative_count,
        summary.unevaluable_count,
    ) == (2, 0, 0, 0, 1)
    rates = _by_metric(summary)
    assert rates["sensitivity_descriptive_research_classification_rate"].exact_fraction == "2/2"
    assert rates["positive_predictive_value_descriptive_research_classification_rate"].exact_fraction == "2/2"
    assert rates["specificity_descriptive_research_classification_rate"].undefined_reason is UndefinedReason.ZERO_DENOMINATOR
    assert rates["negative_predictive_value_descriptive_research_classification_rate"].undefined_reason is UndefinedReason.ZERO_DENOMINATOR
    assert not rates["sensitivity_descriptive_research_classification_rate"].interval.independence_assumption_satisfied
    assert "dependent" in summary.dependence_warning.lower()


def test_synthetic_truth_table_covers_all_four_cells_and_unevaluable():
    rows = tuple(row for row in load_dataset().rows if row.case_id.startswith("SYN_"))
    summary = build_confusion_matrix(rows, _context(independent=True))
    assert (
        summary.true_positive_count,
        summary.false_positive_count,
        summary.true_negative_count,
        summary.false_negative_count,
        summary.unevaluable_count,
    ) == (1, 1, 1, 1, 7)
    assert all(
        rate.interval is not None
        for rate in summary.descriptive_rates
        if rate.defined
    )


def test_all_unevaluable_rows_leave_every_binary_rate_undefined():
    rows = tuple(
        row for row in load_dataset().rows
        if row.research_classification.value == "UNEVALUABLE"
        and row.case_id.startswith("SYN_")
    )
    summary = build_confusion_matrix(rows, _context(independent=True))
    assert summary.unevaluable_count == 7
    assert all(not rate.defined for rate in summary.descriptive_rates)
    assert all(rate.interval is None for rate in summary.descriptive_rates)


def test_mixed_historical_and_synthetic_rows_are_rejected():
    rows = load_dataset().rows
    with pytest.raises(
        AnalysisConfusionMatrixError,
        match="ANALYSIS_CONFUSION_MATRIX_MIXED_PROVENANCE",
    ):
        build_confusion_matrix(rows, _context(independent=False))

