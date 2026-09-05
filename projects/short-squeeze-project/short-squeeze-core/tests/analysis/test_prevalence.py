from decimal import Decimal

from squeeze_core.analysis import AnalysisUnit
from squeeze_core.analysis.prevalence import (
    build_classification_prevalence,
    build_detection_prevalence,
    build_outcome_prevalence,
)
from squeeze_core.analysis.proportions import ProportionContext
from tests.analysis.helpers import load_dataset


CONTEXT = ProportionContext(
    cohort_id="historical-boundaries",
    analysis_unit=AnalysisUnit.CASE_BOUNDARY,
    interval_policy_version="phase_3c_interval_policy.v1",
    confidence_level=Decimal("0.95"),
    sample_size_policy_version="phase_3c_sample_size_policy.v1",
    independence_assumption_satisfied=False,
)


def test_historical_detection_outcome_and_classification_prevalence():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    detection = build_detection_prevalence(rows, CONTEXT)
    outcome = build_outcome_prevalence(rows, CONTEXT)
    classification = build_classification_prevalence(rows, CONTEXT)
    assert dict(detection.counts) == {"DETECTED": 2, "NOT_DETECTED": 0, "UNEVALUABLE": 1}
    assert dict(outcome.counts)["SUBSTANTIAL_UPWARD_MOVE"] == 2
    assert dict(classification.counts)["TRUE_POSITIVE"] == 2
    assert detection.proportions[0].metric_name == "detected_prevalence_among_all_cases"
    assert all(
        item.interval is not None and not item.interval.independence_assumption_satisfied
        for item in detection.proportions
        if item.defined
    )


def test_prevalence_preserves_zero_counts_and_stable_enum_order():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    first = build_classification_prevalence(rows, CONTEXT)
    second = build_classification_prevalence(tuple(reversed(rows)), CONTEXT)
    assert first == second
    assert tuple(name for name, _ in first.counts) == (
        "TRUE_POSITIVE",
        "FALSE_POSITIVE",
        "TRUE_NEGATIVE",
        "FALSE_NEGATIVE",
        "UNEVALUABLE",
        "NOT_APPLICABLE",
    )
    assert dict(first.counts)["FALSE_POSITIVE"] == 0


def test_empty_prevalence_has_explicit_zero_denominators():
    result = build_detection_prevalence((), CONTEXT)
    assert all(count == 0 for _, count in result.counts)
    assert all(not item.defined for item in result.proportions)

