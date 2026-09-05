from decimal import Decimal

from squeeze_core.analysis import AnalysisUnit
from squeeze_core.analysis.missingness import build_domain_missingness
from squeeze_core.analysis.proportions import ProportionContext
from tests.analysis.helpers import load_dataset


CONTEXT = ProportionContext(
    cohort_id="missingness-cohort",
    analysis_unit=AnalysisUnit.CASE_BOUNDARY,
    interval_policy_version="phase_3c_interval_policy.v1",
    confidence_level=Decimal("0.95"),
    sample_size_policy_version="phase_3c_sample_size_policy.v1",
)


def _by_domain(items):
    return {item.domain_id: item for item in items}


def test_historical_missing_short_pressure_and_history_are_explicit():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    summary = _by_domain(build_domain_missingness(rows, CONTEXT))
    for domain in (
        "DAYS_TO_COVER",
        "BORROW_FEE",
        "BORROW_FEE_CHANGE",
        "BORROW_AVAILABILITY",
        "BORROW_AVAILABILITY_CHANGE",
        "SEC_FILINGS",
        "MULTIPLE_BOUNDARIES_PER_SYMBOL",
    ):
        assert summary[domain].missing_count == 3
        assert summary[domain].denominator == 3
        assert summary[domain].affected_case_ids == (
            "BIYA_ARTIFACT_DISCOVERY",
            "BIYA_EARLIEST_BOUNDARY",
            "BIYA_LATEST_BOUNDARY",
        )
        assert summary[domain].affected_symbols == ("BIYA",)
    assert summary["PUBLISHED_SHORT_INTEREST"].missing_count == 0
    assert summary["NEWS"].missing_count == 1
    assert summary["NEWS"].affected_case_ids == ("BIYA_ARTIFACT_DISCOVERY",)
    assert summary["NEWS_TIMESTAMP"].missing_count == 1
    assert summary["NEWS_TIMESTAMP"].affected_case_ids == ("BIYA_ARTIFACT_DISCOVERY",)
    assert summary["PROVIDER_SCOPE"].missing_count == 1
    assert summary["PROVIDER_SCOPE"].affected_case_ids == ("BIYA_ARTIFACT_DISCOVERY",)


def test_conflict_insufficiency_and_partial_outcome_cases_are_not_failures():
    rows = tuple(row for row in load_dataset().rows if row.case_id.startswith("SYN_"))
    summary = _by_domain(build_domain_missingness(rows, CONTEXT))
    assert summary["CONFLICTED_EVIDENCE"].affected_case_ids == (
        "SYN_UNEVALUABLE_CONFLICTED",
    )
    assert summary["PARTIAL_OUTCOME_WINDOW"].affected_case_ids == (
        "SYN_OUTCOME_INSUFFICIENT",
    )
    assert summary["UNKNOWN_PLATFORM_STATUS"].missing_count > 0
    assert all(item.denominator == 11 for item in summary.values())


def test_missingness_summary_is_stable_and_preserves_cohort_identity():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    first = build_domain_missingness(rows, CONTEXT)
    second = build_domain_missingness(tuple(reversed(rows)), CONTEXT)
    assert first == second
    assert all(item.cohort_id == "missingness-cohort" for item in first)
    assert all(item.analysis_unit is AnalysisUnit.CASE_BOUNDARY for item in first)
    assert len({item.deterministic_id for item in first}) == len(first)

