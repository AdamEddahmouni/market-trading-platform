from decimal import Decimal

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.research.models import (
    CandidateCaseRegistry,
    FixtureClassification,
    ResearchDataset,
)

from .boundary_selection import select_boundaries
from .cohorts import build_dataset_cohort, build_registry_cohort
from .confusion_matrix import build_confusion_matrix
from .dependence import summarize_symbol_dependence
from .diagnostics import AnalysisDiagnostic, AnalysisDiagnosticCode
from .missingness import build_domain_missingness, build_registry_data_quality
from .models import (
    AnalysisCohortDefinition,
    AnalysisCohortExclusion,
    AnalysisCohortMembership,
    AnalysisCohortType,
    AnalysisProvenanceClassification,
    AnalysisUnit,
    BoundarySelectionPolicy,
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchLimitation,
)
from .prevalence import (
    build_classification_prevalence,
    build_detection_prevalence,
    build_outcome_prevalence,
)
from .proportions import ProportionContext
from .rule_prevalence import build_rule_outcome_prevalence
from .sample_size import assess_sample_size


class AnalysisRunnerError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


HISTORICAL_LIMITATIONS = (
    ResearchLimitation(
        code="HISTORICAL_ONE_UNIQUE_SYMBOL",
        statement="The historical completed dataset currently represents one unique symbol.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="BIYA_BOUNDARIES_DEPENDENT",
        statement="The two BIYA boundaries are dependent observations of the same symbol.",
        affected_case_ids=("BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY"),
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT",
        statement="Case-boundary counts are not independent performance samples.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="EARLIEST_BOUNDARY_SELECTION_OUTCOME_BLIND",
        statement="The default unique-symbol analysis selects the earliest boundary without using the outcome.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="HISTORICAL_SAMPLE_INSUFFICIENT_FOR_PREDICTIVE_VALIDATION",
        statement="The historical sample is insufficient for predictive validation.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="OUTCOME_DOES_NOT_PROVE_SQUEEZE_CAUSATION",
        statement="Outcome confirmation does not prove short-squeeze causation.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="MISSING_SHORT_PRESSURE_EVIDENCE_MATERIAL",
        statement="Missing short-pressure evidence remains material.",
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="RULE_PREVALENCE_NOT_PREDICTIVE_IMPORTANCE",
        statement="Rule prevalence does not prove predictive importance.",
    ),
    ResearchLimitation(
        code="INTERVALS_DO_NOT_REPAIR_REPRESENTATIVENESS",
        statement="Confidence intervals do not repair an unrepresentative sample.",
    ),
    ResearchLimitation(
        code="SYNTHETIC_EXCLUDED_FROM_EMPIRICAL_ESTIMATES",
        statement="Synthetic cases are excluded from empirical performance estimates.",
    ),
    ResearchLimitation(
        code="THRESHOLDS_AND_POLICIES_NOT_OPTIMIZED",
        statement="Thresholds and policies were not optimized.",
    ),
    ResearchLimitation(
        code="NO_TRADING_SIMULATION",
        statement="No P&L, backtest, entry, exit, recommendation, or trading simulation was performed.",
    ),
    ResearchLimitation(
        code="BIYA_PARTIAL_OUTCOME_WINDOW_LIMITATION",
        statement=(
            "The two BIYA outcome labels were established from observed threshold crossings "
            "within partial 24-hour observation windows; partial windows could not establish "
            "absence of a crossing."
        ),
        affected_case_ids=("BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY"),
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="BIYA_PIPELINE_DEMONSTRATION_ONLY",
        statement=(
            "BIYA demonstrates that the deterministic pipeline can preserve a detected case "
            "and a later substantial move without injecting outcome information into the "
            "original evaluation."
        ),
        affected_symbols=("BIYA",),
    ),
    ResearchLimitation(
        code="BIYA_NOT_GENERAL_PREDICTIVE_VALIDATION",
        statement=(
            "It does not validate squeeze causation or general predictive performance."
        ),
        affected_symbols=("BIYA",),
    ),
)


def _selected_membership(membership, rows, selection):
    row_by_id = {row.case_id: row for row in rows}
    additional = tuple(
        AnalysisCohortExclusion(
            case_id=case_id,
            symbol=row_by_id[case_id].symbol,
            reason_code="ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY",
            fixture_classification=row_by_id[case_id].fixture_classification.value,
        )
        for case_id in selection.excluded_case_ids
    )
    selected_rows = tuple(row_by_id[case_id] for case_id in selection.selected_case_ids)
    return AnalysisCohortMembership(
        source_dataset_id=membership.source_dataset_id,
        source_registry_id=membership.source_registry_id,
        cohort_definition=membership.cohort_definition,
        included_case_ids=selection.selected_case_ids,
        included_symbols=tuple(row.symbol for row in selected_rows),
        exclusions=membership.exclusions + additional,
        fixture_classifications=tuple(
            AnalysisProvenanceClassification(row.fixture_classification.value)
            for row in selected_rows
        ),
    ), selected_rows


def _diagnostics_for_dataset(cohort_type, dependence, selection, missingness):
    diagnostics = list(selection.diagnostics)
    diagnostics.extend((
        AnalysisDiagnostic(
            code=AnalysisDiagnosticCode.ANALYSIS_DESCRIPTIVE_ONLY,
            severity=DiagnosticSeverity.INFO,
        ),
        AnalysisDiagnostic(
            code=AnalysisDiagnosticCode.ANALYSIS_NO_PREDICTIVE_VALIDATION,
            severity=DiagnosticSeverity.WARNING,
        ),
        AnalysisDiagnostic(
            code=AnalysisDiagnosticCode.ANALYSIS_THRESHOLD_OPTIMIZATION_NOT_PERFORMED,
            severity=DiagnosticSeverity.INFO,
        ),
    ))
    if cohort_type is AnalysisCohortType.HISTORICAL_COMPLETED_CASES:
        diagnostics.extend((
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_NO_CAUSAL_INFERENCE,
                severity=DiagnosticSeverity.WARNING,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_SYNTHETIC_CASES_EXCLUDED_FROM_EMPIRICAL_RESULTS,
                severity=DiagnosticSeverity.INFO,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_INSUFFICIENT_HISTORICAL_CASES,
                severity=DiagnosticSeverity.WARNING,
            ),
        ))
    if dependence.dependence_detected:
        diagnostics.extend((
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_REPEATED_SYMBOL_DETECTED,
                severity=DiagnosticSeverity.WARNING,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_CASES_NOT_INDEPENDENT,
                severity=DiagnosticSeverity.WARNING,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_INTERVAL_INDEPENDENCE_ASSUMPTION_UNSATISFIED,
                severity=DiagnosticSeverity.WARNING,
            ),
        ))
    missing = {item.domain_id: item for item in missingness}
    if missing.get("PUBLISHED_SHORT_INTEREST") and missing["PUBLISHED_SHORT_INTEREST"].missing_count:
        diagnostics.append(AnalysisDiagnostic(
            code=AnalysisDiagnosticCode.ANALYSIS_MISSING_SHORT_PRESSURE_EVIDENCE,
            severity=DiagnosticSeverity.WARNING,
            input_ids=missing["PUBLISHED_SHORT_INTEREST"].affected_case_ids,
        ))
    return tuple(diagnostics)


def _dataset_result(request: ResearchAnalysisRequest, dataset: ResearchDataset):
    membership = build_dataset_cohort(request, dataset)
    included = set(membership.included_case_ids)
    eligible_rows = tuple(row for row in dataset.rows if row.case_id in included)
    selection = select_boundaries(eligible_rows, request.boundary_selection_policy_version)
    membership, rows = _selected_membership(membership, eligible_rows, selection)
    dependence = summarize_symbol_dependence(rows, request.analysis_unit)
    context = ProportionContext(
        cohort_id=str(membership.deterministic_id),
        analysis_unit=request.analysis_unit,
        interval_policy_version=request.interval_policy_version,
        confidence_level=request.confidence_level,
        sample_size_policy_version=request.sample_size_policy_version,
        independence_assumption_satisfied=dependence.independence_assumption_satisfied,
    )
    missingness = (
        build_domain_missingness(rows, context)
        if "MISSINGNESS" in request.included_statistics
        else ()
    )
    rule_order = tuple(sorted(rows[0].rule_outcomes)) if rows else ()
    sample_size = assess_sample_size(
        len(rows), len({row.symbol for row in rows}),
        request.analysis_unit, request.sample_size_policy_version,
    )
    historical = request.cohort_definition.cohort_type is AnalysisCohortType.HISTORICAL_COMPLETED_CASES
    limitations = HISTORICAL_LIMITATIONS if historical else (
        ResearchLimitation(
            code="SYNTHETIC_CASES_ARE_NOT_EMPIRICAL_EVIDENCE",
            statement="Synthetic cases test software behavior and classification coverage. They do not provide empirical evidence about market performance.",
        ),
        ResearchLimitation(
            code="THRESHOLDS_AND_POLICIES_NOT_OPTIMIZED",
            statement="Thresholds and policies were not optimized.",
        ),
    )
    return ResearchAnalysisResult(
        analysis_version=request.analysis_version,
        source_dataset_id=str(dataset.deterministic_id),
        source_registry_id=request.source_registry_id,
        analysis_unit=request.analysis_unit,
        boundary_selection_policy_version=request.boundary_selection_policy_version,
        statistics_policy_version=request.statistics_policy_version,
        interval_policy_version=request.interval_policy_version,
        confidence_level=request.confidence_level,
        sample_size_policy_version=request.sample_size_policy_version,
        provenance_classifications=membership.fixture_classifications,
        request_id=str(request.deterministic_id),
        cohort_membership=membership,
        boundary_selection=selection,
        case_count=len(rows),
        unique_symbol_count=len({row.symbol for row in rows}),
        boundary_count=sum(count for _, count in selection.boundary_count_by_symbol),
        symbol_dependence_summary=dependence,
        rule_outcome_prevalence=(
            build_rule_outcome_prevalence(rows, rule_order, context)
            if "RULE_OUTCOME_PREVALENCE" in request.included_statistics else ()
        ),
        domain_missingness_summary=missingness,
        detection_prevalence=(
            build_detection_prevalence(rows, context)
            if "DETECTION_PREVALENCE" in request.included_statistics else None
        ),
        outcome_prevalence=(
            build_outcome_prevalence(rows, context)
            if "OUTCOME_PREVALENCE" in request.included_statistics else None
        ),
        classification_prevalence=(
            build_classification_prevalence(rows, context)
            if "RESEARCH_CLASSIFICATION_PREVALENCE" in request.included_statistics else None
        ),
        confusion_matrix=(
            build_confusion_matrix(rows, context)
            if "CONFUSION_MATRIX" in request.included_statistics else None
        ),
        sample_size_assessments=(sample_size,),
        limitations=limitations,
        diagnostics=_diagnostics_for_dataset(
            request.cohort_definition.cohort_type, dependence, selection, missingness
        ),
    )


def _registry_result(request: ResearchAnalysisRequest, registry: CandidateCaseRegistry):
    membership = build_registry_cohort(request, registry)
    included = set(membership.included_case_ids)
    entries = tuple(entry for entry in registry.entries if entry.case_id in included)
    dependence = summarize_symbol_dependence(entries, request.analysis_unit)
    sample_size = assess_sample_size(
        len(entries), len({entry.symbol for entry in entries}),
        request.analysis_unit, request.sample_size_policy_version,
    )
    return ResearchAnalysisResult(
        analysis_version=request.analysis_version,
        source_dataset_id=request.source_dataset_id,
        source_registry_id=str(registry.deterministic_id),
        analysis_unit=request.analysis_unit,
        boundary_selection_policy_version=request.boundary_selection_policy_version,
        statistics_policy_version=request.statistics_policy_version,
        interval_policy_version=request.interval_policy_version,
        confidence_level=request.confidence_level,
        sample_size_policy_version=request.sample_size_policy_version,
        provenance_classifications=membership.fixture_classifications,
        request_id=str(request.deterministic_id),
        cohort_membership=membership,
        case_count=len(entries),
        unique_symbol_count=len({entry.symbol for entry in entries}),
        boundary_count=0,
        symbol_dependence_summary=dependence,
        data_quality_summary=build_registry_data_quality(registry),
        sample_size_assessments=(sample_size,),
        limitations=(
            ResearchLimitation(
                code="REGISTRY_DATA_QUALITY_NOT_PERFORMANCE_ESTIMATE",
                statement="This report describes registry and data quality. It is not a performance estimate.",
            ),
            ResearchLimitation(
                code="INCOMPLETE_CASES_NOT_EMPIRICAL_EVIDENCE",
                statement="Incomplete and blocked cases do not enter complete-case empirical rates.",
            ),
        ),
        diagnostics=(
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_COHORT_MIXED_PROVENANCE,
                severity=DiagnosticSeverity.WARNING,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_DESCRIPTIVE_ONLY,
                severity=DiagnosticSeverity.INFO,
            ),
            AnalysisDiagnostic(
                code=AnalysisDiagnosticCode.ANALYSIS_NO_PREDICTIVE_VALIDATION,
                severity=DiagnosticSeverity.WARNING,
            ),
        ),
    )


def run_research_analysis(
    request: ResearchAnalysisRequest,
    *,
    dataset: ResearchDataset | None = None,
    registry: CandidateCaseRegistry | None = None,
) -> ResearchAnalysisResult:
    cohort_type = request.cohort_definition.cohort_type
    if cohort_type in {
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisCohortType.SYNTHETIC_CASES,
        AnalysisCohortType.MIXED_PROVENANCE_CASES,
    }:
        if dataset is None:
            raise AnalysisRunnerError("ANALYSIS_SOURCE_DATASET_REQUIRED")
        return _dataset_result(request, dataset)
    if registry is None:
        raise AnalysisRunnerError("ANALYSIS_SOURCE_REGISTRY_REQUIRED")
    return _registry_result(request, registry)


def _request(
    cohort_type,
    analysis_unit,
    provenance,
    *,
    dataset=None,
    registry=None,
    statistics,
):
    boundary_policy = (
        BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
        if analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
        else BoundarySelectionPolicy.ALL_CASE_BOUNDARIES
    )
    definition = AnalysisCohortDefinition(
        cohort_type=cohort_type,
        analysis_unit=analysis_unit,
        boundary_selection_policy_version=boundary_policy,
        provenance_classifications=provenance,
        required_complete_cases=cohort_type in {
            AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
            AnalysisCohortType.SYNTHETIC_CASES,
        },
    )
    return ResearchAnalysisRequest(
        source_dataset_id=str(dataset.deterministic_id) if dataset is not None else None,
        source_registry_id=str(registry.deterministic_id) if registry is not None else None,
        cohort_definition=definition,
        analysis_unit=analysis_unit,
        boundary_selection_policy_version=boundary_policy,
        confidence_level=Decimal("0.95"),
        included_statistics=statistics,
        excluded_statistics=("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION"),
    )


def build_standard_analysis_requests(dataset, registry):
    dataset_statistics = (
        "CONFUSION_MATRIX", "DETECTION_PREVALENCE", "MISSINGNESS",
        "OUTCOME_PREVALENCE", "RESEARCH_CLASSIFICATION_PREVALENCE",
        "RULE_OUTCOME_PREVALENCE",
    )
    historical_provenance = (
        AnalysisProvenanceClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
    )
    return (
        _request(
            AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
            AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
            historical_provenance,
            dataset=dataset,
            statistics=dataset_statistics,
        ),
        _request(
            AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
            AnalysisUnit.CASE_BOUNDARY,
            historical_provenance,
            dataset=dataset,
            statistics=dataset_statistics,
        ),
        _request(
            AnalysisCohortType.SYNTHETIC_CASES,
            AnalysisUnit.CASE_BOUNDARY,
            (AnalysisProvenanceClassification.SYNTHETIC_EDGE_CASE,),
            dataset=dataset,
            statistics=dataset_statistics,
        ),
        _request(
            AnalysisCohortType.ALL_REGISTERED_CASES,
            AnalysisUnit.CASE_BOUNDARY,
            (AnalysisProvenanceClassification.MIXED_PROVENANCE,),
            registry=registry,
            statistics=("DATA_QUALITY",),
        ),
        _request(
            AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
            AnalysisUnit.CASE_BOUNDARY,
            (AnalysisProvenanceClassification.SANITIZED_LOCAL_ARTIFACT,),
            registry=registry,
            statistics=("DATA_QUALITY",),
        ),
    )


__all__ = [
    "AnalysisRunnerError", "HISTORICAL_LIMITATIONS",
    "build_standard_analysis_requests", "run_research_analysis",
]
