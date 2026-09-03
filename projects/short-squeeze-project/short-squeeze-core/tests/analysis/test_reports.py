from squeeze_core.analysis import AnalysisCohortType, AnalysisUnit
from squeeze_core.analysis.reports import REPORT_SECTION_ORDER, render_markdown_report
from squeeze_core.analysis.runner import run_research_analysis
from tests.analysis.helpers import analysis_request, load_dataset, load_registry


def _result(cohort_type, analysis_unit, *, registry_source=False):
    dataset = None if registry_source else load_dataset()
    registry = load_registry() if registry_source else None
    statistics = (
        ("DATA_QUALITY",)
        if registry_source
        else (
            "CONFUSION_MATRIX",
            "DETECTION_PREVALENCE",
            "MISSINGNESS",
            "OUTCOME_PREVALENCE",
            "RESEARCH_CLASSIFICATION_PREVALENCE",
            "RULE_OUTCOME_PREVALENCE",
        )
    )
    request = analysis_request(
        cohort_type,
        analysis_unit,
        dataset=dataset,
        registry=registry,
        included_statistics=statistics,
    )
    return run_research_analysis(request, dataset=dataset, registry=registry)


def test_historical_report_is_byte_stable_and_has_fixed_section_order():
    result = _result(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
    )
    first = render_markdown_report(result)
    second = render_markdown_report(result)
    assert first == second
    assert b"\r" not in first
    text = first.decode("utf-8")
    positions = [text.index(f"## {section}") for section in REPORT_SECTION_ORDER]
    assert positions == sorted(positions)


def test_historical_report_preserves_membership_sample_size_and_undefined_rates():
    text = render_markdown_report(_result(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
    )).decode("utf-8")
    assert "BIYA_EARLIEST_BOUNDARY" in text
    assert "BIYA_LATEST_BOUNDARY" in text
    assert "ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY" in text
    assert "SMALL" in text
    assert "Undefined (0/0; ZERO_DENOMINATOR)" in text
    assert "earliest_detection_boundary_per_symbol.v1" in text


def test_every_required_historical_interpretation_is_rendered_verbatim():
    text = render_markdown_report(_result(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
    )).decode("utf-8")
    required = (
        "The historical completed dataset currently represents six unique symbols with one fully detected case (BIYA).",
        "The two BIYA boundaries are dependent observations of the same symbol.",
        "Case-boundary counts are not independent performance samples.",
        "The default unique-symbol analysis selects the earliest boundary without using the outcome.",
        "The historical sample is insufficient for predictive validation.",
        "Outcome confirmation does not prove short-squeeze causation.",
        "Missing short-pressure evidence remains material.",
        "Rule prevalence does not prove predictive importance.",
        "Confidence intervals do not repair an unrepresentative sample.",
        "Synthetic cases are excluded from empirical performance estimates.",
        "Thresholds and policies were not optimized.",
        "No P&L, backtest, entry, exit, recommendation, or trading simulation was performed.",
    )
    assert all(statement in text for statement in required)


def test_synthetic_and_registry_reports_have_prominent_non_empirical_notices():
    synthetic = render_markdown_report(_result(
        AnalysisCohortType.SYNTHETIC_CASES,
        AnalysisUnit.CASE_BOUNDARY,
    )).decode("utf-8")
    registry = render_markdown_report(_result(
        AnalysisCohortType.ALL_REGISTERED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        registry_source=True,
    )).decode("utf-8")
    assert (
        "Synthetic cases test software behavior and classification coverage. "
        "They do not provide empirical evidence about market performance."
    ) in synthetic
    assert (
        "This report describes registry and data quality. It is not a performance estimate."
    ) in registry


def test_report_avoids_prohibited_positive_performance_terminology():
    text = render_markdown_report(_result(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
    )).decode("utf-8").lower()
    assert "accuracy" not in text
    assert "validated performance" not in text
    assert "predictive success rate" not in text
    assert "model quality" not in text
    assert "no candidate score, rank, alert, or trading recommendation is produced" in text


def test_analysis_result_itself_is_policy_complete():
    result = _result(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
    )
    assert result.analysis_unit is AnalysisUnit.CASE_BOUNDARY
    assert result.boundary_selection_policy_version == "all_case_boundaries.v1"
    assert result.statistics_policy_version == "phase_3c_descriptive_statistics_policy.v1"
    assert result.interval_policy_version == "phase_3c_interval_policy.v1"
    assert str(result.confidence_level) == "0.95"
    assert result.sample_size_policy_version == "phase_3c_sample_size_policy.v1"
    assert result.provenance_classifications == ("SANITIZED_PUBLIC_HISTORICAL_DATA",)

