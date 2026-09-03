from collections import defaultdict

from squeeze_core.research.models import ResearchDatasetRow

from .models import AnalysisUnit, SymbolDependenceSummary


def summarize_symbol_dependence(
    rows: tuple[ResearchDatasetRow, ...],
    analysis_unit: AnalysisUnit,
) -> SymbolDependenceSummary:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol.strip().upper()].append(row.case_id)
    boundary_ids = tuple(
        (symbol, tuple(sorted(case_ids)))
        for symbol, case_ids in sorted(grouped.items())
    )
    repeated_symbols = tuple(
        symbol for symbol, case_ids in boundary_ids if len(case_ids) > 1
    )
    repeated_count = sum(len(case_ids) - 1 for _, case_ids in boundary_ids)
    maximum = max((len(case_ids) for _, case_ids in boundary_ids), default=0)
    dependence_detected = bool(repeated_symbols)
    if not rows:
        limitations = ("No observations are available for dependence assessment.",)
    elif dependence_detected:
        limitations = (
            "Repeated boundaries for the same symbol are not independent observations.",
            "Case-boundary uncertainty intervals do not satisfy the independence assumption.",
        )
    elif analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY:
        limitations = (
            "One representative boundary row per symbol removes repeated rows but does not establish market representativeness.",
        )
    elif analysis_unit is AnalysisUnit.UNIQUE_SYMBOL:
        limitations = (
            "Symbol-level aggregation removes repeated boundary units but does not establish market representativeness.",
        )
    else:
        limitations = (
            "No symbol is repeated within this cohort; broader market representativeness is not established.",
        )
    recommended = (
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
        if dependence_detected
        else analysis_unit
    )
    return SymbolDependenceSummary(
        case_count=len(rows),
        unique_symbol_count=len(grouped),
        symbols_with_multiple_boundaries=repeated_symbols,
        repeated_boundary_count=repeated_count,
        maximum_boundaries_per_symbol=maximum,
        boundary_ids_by_symbol=boundary_ids,
        dependence_detected=dependence_detected,
        independence_assumption_satisfied=not dependence_detected,
        recommended_analysis_unit=recommended,
        limitations=limitations,
    )


__all__ = ["summarize_symbol_dependence"]
