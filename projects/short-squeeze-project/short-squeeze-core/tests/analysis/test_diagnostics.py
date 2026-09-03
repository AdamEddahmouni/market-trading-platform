from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.analysis.diagnostics import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCode,
    sort_analysis_diagnostics,
)


def test_phase_3c_diagnostic_catalog_contains_required_boundaries():
    values = {item.value for item in AnalysisDiagnosticCode}
    assert {
        "ANALYSIS_COHORT_EMPTY",
        "ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY",
        "ANALYSIS_BOUNDARY_SELECTION_AMBIGUOUS",
        "ANALYSIS_RATE_UNDEFINED_ZERO_DENOMINATOR",
        "ANALYSIS_INTERVAL_INDEPENDENCE_ASSUMPTION_UNSATISFIED",
        "ANALYSIS_INSUFFICIENT_HISTORICAL_CASES",
        "ANALYSIS_NO_PREDICTIVE_VALIDATION",
        "ANALYSIS_THRESHOLD_OPTIMIZATION_NOT_PERFORMED",
    } <= values


def test_analysis_diagnostics_have_stable_semantic_order():
    later = AnalysisDiagnostic(
        code=AnalysisDiagnosticCode.ANALYSIS_RATE_UNDEFINED_ZERO_DENOMINATOR,
        severity=DiagnosticSeverity.WARNING,
        case_id="CASE-B",
        metric_name="sensitivity",
        input_ids=("z", "a", "a"),
    )
    earlier = AnalysisDiagnostic(
        code=AnalysisDiagnosticCode.ANALYSIS_COHORT_EMPTY,
        severity=DiagnosticSeverity.WARNING,
        cohort_id="cohort-a",
    )
    assert sort_analysis_diagnostics((later, earlier)) == (earlier, later)
    assert later.input_ids == ("a", "z")

