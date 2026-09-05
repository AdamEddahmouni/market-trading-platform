from squeeze_core.analysis import AnalysisUnit
from squeeze_core.analysis.dependence import summarize_symbol_dependence
from tests.analysis.helpers import load_dataset


def _biya_rows():
    return tuple(row for row in load_dataset().rows if row.symbol == "BIYA")


def test_one_case_per_symbol_satisfies_independence_at_case_boundary_level():
    rows = tuple(row for row in load_dataset().rows if row.symbol != "BIYA")[:3]
    result = summarize_symbol_dependence(rows, AnalysisUnit.CASE_BOUNDARY)
    assert result.case_count == 3
    assert result.unique_symbol_count == 3
    assert result.symbols_with_multiple_boundaries == ()
    assert result.repeated_boundary_count == 0
    assert result.maximum_boundaries_per_symbol == 1
    assert not result.dependence_detected
    assert result.independence_assumption_satisfied
    assert result.recommended_analysis_unit is AnalysisUnit.CASE_BOUNDARY


def test_two_biya_boundaries_are_not_independent_observations():
    result = summarize_symbol_dependence(_biya_rows(), AnalysisUnit.CASE_BOUNDARY)
    assert result.case_count == 3
    assert result.unique_symbol_count == 1
    assert result.symbols_with_multiple_boundaries == ("BIYA",)
    assert result.repeated_boundary_count == 2
    assert result.maximum_boundaries_per_symbol == 3
    assert result.boundary_ids_by_symbol == ((
        "BIYA",
        (
            "BIYA_ARTIFACT_DISCOVERY",
            "BIYA_EARLIEST_BOUNDARY",
            "BIYA_LATEST_BOUNDARY",
        ),
    ),)
    assert result.dependence_detected
    assert not result.independence_assumption_satisfied
    assert (
        result.recommended_analysis_unit
        is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
    )
    assert "not independent" in result.limitations[0].lower()


def test_empty_dependence_summary_is_explicit():
    result = summarize_symbol_dependence((), AnalysisUnit.CASE_BOUNDARY)
    assert result.case_count == 0
    assert result.unique_symbol_count == 0
    assert result.maximum_boundaries_per_symbol == 0
    assert result.independence_assumption_satisfied
    assert result.limitations == ("No observations are available for dependence assessment.",)


def test_dependence_summary_is_input_order_invariant():
    rows = _biya_rows()
    first = summarize_symbol_dependence(rows, AnalysisUnit.CASE_BOUNDARY)
    second = summarize_symbol_dependence(tuple(reversed(rows)), AnalysisUnit.CASE_BOUNDARY)
    assert first == second
    assert first.deterministic_id == second.deterministic_id


def test_policy_selected_single_boundary_removes_repeated_symbol_rows_only():
    selected = (_biya_rows()[0],)
    result = summarize_symbol_dependence(
        selected,
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
    )
    assert result.case_count == result.unique_symbol_count == 1
    assert result.independence_assumption_satisfied
    assert "representative" in result.limitations[0].lower()

