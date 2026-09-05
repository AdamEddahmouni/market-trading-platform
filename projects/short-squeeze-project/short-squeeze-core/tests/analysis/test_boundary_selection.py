from datetime import datetime, timezone

import pytest

from squeeze_core.analysis import AnalysisUnit, BoundarySelectionPolicy
from squeeze_core.analysis.boundary_selection import (
    AnalysisBoundarySelectionError,
    select_boundaries,
)
from squeeze_core.research.models import ResearchCaseClassification
from tests.analysis.helpers import load_dataset


def _historical_rows():
    return tuple(row for row in load_dataset().rows if row.symbol == "BIYA")


def test_all_case_boundaries_preserves_both_dependent_biya_rows():
    result = select_boundaries(
        tuple(reversed(_historical_rows())),
        BoundarySelectionPolicy.ALL_CASE_BOUNDARIES,
    )
    assert result.analysis_unit is AnalysisUnit.CASE_BOUNDARY
    assert result.selected_case_ids == (
        "BIYA_ARTIFACT_DISCOVERY",
        "BIYA_EARLIEST_BOUNDARY",
        "BIYA_LATEST_BOUNDARY",
    )
    assert result.excluded_case_ids == ()
    assert result.boundary_count_by_symbol == (("BIYA", 3),)


def test_earliest_boundary_selects_one_biya_row_and_preserves_exclusion():
    result = select_boundaries(
        _historical_rows(),
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
    )
    assert result.analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
    assert result.selected_case_ids == ("BIYA_EARLIEST_BOUNDARY",)
    assert result.excluded_case_ids == ("BIYA_ARTIFACT_DISCOVERY", "BIYA_LATEST_BOUNDARY")
    assert result.boundary_count_by_symbol == (("BIYA", 3),)
    assert result.outcome_blind
    assert {item.code.value for item in result.diagnostics} == {
        "ANALYSIS_BOUNDARY_SELECTION_APPLIED",
        "ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY",
    }


def test_equal_times_are_fully_resolved_by_canonical_case_id():
    row = _historical_rows()[0]
    timestamp = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)
    case_b = row.model_copy(update={"case_id": "CASE-B", "evaluation_as_of": timestamp})
    case_a = row.model_copy(update={"case_id": "CASE-A", "evaluation_as_of": timestamp})
    result = select_boundaries(
        (case_b, case_a),
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
    )
    assert result.selected_case_ids == ("CASE-A",)
    assert result.excluded_case_ids == ("CASE-B",)
    assert "ANALYSIS_BOUNDARY_SELECTION_AMBIGUOUS" not in {
        item.code.value for item in result.diagnostics
    }


def test_selection_is_invariant_to_outcomes_classifications_and_input_order():
    rows = _historical_rows()
    changed = tuple(
        row.model_copy(update={
            "maximum_observed_move_percent": None,
            "maximum_adverse_move_percent": None,
            "research_classification": ResearchCaseClassification.FALSE_NEGATIVE,
            "outcome_label": "OUTCOME_UNKNOWN",
        })
        for row in reversed(rows)
    )
    original = select_boundaries(
        rows,
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
    )
    mutated = select_boundaries(
        changed,
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
    )
    assert original == mutated


def test_multiple_symbols_each_select_their_earliest_boundary():
    rows = load_dataset().rows
    result = select_boundaries(
        rows,
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
    )
    assert len(result.selected_case_ids) == len({row.symbol for row in rows})
    assert "BIYA_EARLIEST_BOUNDARY" in result.selected_case_ids
    assert "BIYA_LATEST_BOUNDARY" in result.excluded_case_ids


def test_absent_required_boundary_data_is_ambiguous():
    row = _historical_rows()[0]
    missing = row.model_copy(update={"evaluation_as_of": None})
    with pytest.raises(
        AnalysisBoundarySelectionError,
        match="ANALYSIS_BOUNDARY_SELECTION_AMBIGUOUS",
    ):
        select_boundaries(
            (missing,),
            BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL,
        )

