from collections import defaultdict

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.research.models import ResearchDatasetRow

from .diagnostics import AnalysisDiagnostic, AnalysisDiagnosticCode
from .models import (
    AnalysisUnit,
    BoundarySelectionPolicy,
    BoundarySelectionResult,
)


class AnalysisBoundarySelectionError(ValueError):
    def __init__(self, code: str, case_id: str | None = None):
        suffix = f":{case_id}" if case_id is not None else ""
        super().__init__(f"{code}{suffix}")
        self.code = code


def _group_rows(
    rows: tuple[ResearchDatasetRow, ...],
) -> dict[str, tuple[ResearchDatasetRow, ...]]:
    grouped: dict[str, list[ResearchDatasetRow]] = defaultdict(list)
    seen_case_ids: set[str] = set()
    for row in rows:
        if row.case_id in seen_case_ids:
            raise AnalysisBoundarySelectionError("ANALYSIS_CASE_ID_DUPLICATE", row.case_id)
        seen_case_ids.add(row.case_id)
        if row.evaluation_as_of is None:
            raise AnalysisBoundarySelectionError(
                "ANALYSIS_BOUNDARY_SELECTION_AMBIGUOUS", row.case_id
            )
        grouped[row.symbol.strip().upper()].append(row)
    return {
        symbol: tuple(sorted(values, key=lambda item: (item.evaluation_as_of, item.case_id)))
        for symbol, values in sorted(grouped.items())
    }


def select_boundaries(
    rows: tuple[ResearchDatasetRow, ...],
    policy: BoundarySelectionPolicy,
) -> BoundarySelectionResult:
    grouped = _group_rows(rows)
    boundary_counts = tuple((symbol, len(values)) for symbol, values in grouped.items())
    if policy is BoundarySelectionPolicy.ALL_CASE_BOUNDARIES:
        return BoundarySelectionResult(
            policy_version=policy,
            analysis_unit=AnalysisUnit.CASE_BOUNDARY,
            selected_case_ids=tuple(sorted(row.case_id for row in rows)),
            excluded_case_ids=(),
            boundary_count_by_symbol=boundary_counts,
            outcome_blind=True,
            rationale_code="ALL_ELIGIBLE_CASE_BOUNDARIES_RETAINED",
        )
    if policy is not BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL:
        raise AnalysisBoundarySelectionError("ANALYSIS_BOUNDARY_POLICY_UNSUPPORTED", str(policy))

    selected = tuple(values[0] for values in grouped.values())
    excluded = tuple(row for values in grouped.values() for row in values[1:])
    diagnostics = [AnalysisDiagnostic(
        code=AnalysisDiagnosticCode.ANALYSIS_BOUNDARY_SELECTION_APPLIED,
        severity=DiagnosticSeverity.INFO,
        input_ids=tuple(row.case_id for row in selected),
    )]
    if excluded:
        diagnostics.append(AnalysisDiagnostic(
            code=AnalysisDiagnosticCode.ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY,
            severity=DiagnosticSeverity.WARNING,
            input_ids=tuple(row.case_id for row in excluded),
        ))
    return BoundarySelectionResult(
        policy_version=policy,
        analysis_unit=AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
        selected_case_ids=tuple(row.case_id for row in selected),
        excluded_case_ids=tuple(row.case_id for row in excluded),
        boundary_count_by_symbol=boundary_counts,
        outcome_blind=True,
        rationale_code="EARLIEST_EVALUATION_AS_OF_THEN_CANONICAL_CASE_ID",
        diagnostics=tuple(diagnostics),
    )


__all__ = ["AnalysisBoundarySelectionError", "select_boundaries"]
