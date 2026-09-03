from collections import Counter

from squeeze_core.research.models import (
    CandidateCaseRegistry,
    CandidateCaseStatus,
    FixtureClassification,
    OutcomeLabel,
    ResearchDataset,
)

from .models import (
    AnalysisCohortExclusion,
    AnalysisCohortMembership,
    AnalysisCohortType,
    AnalysisProvenanceClassification,
    ResearchAnalysisRequest,
)


class AnalysisCohortError(ValueError):
    def __init__(self, code: str, value: str | None = None):
        suffix = f":{value}" if value is not None else ""
        super().__init__(f"{code}{suffix}")
        self.code = code


_EMPIRICAL_STATISTICS = {
    "CONFUSION_MATRIX",
    "DETECTION_PREVALENCE",
    "OUTCOME_PREVALENCE",
    "RESEARCH_CLASSIFICATION_PREVALENCE",
}


def _analysis_provenance(value: FixtureClassification) -> AnalysisProvenanceClassification:
    return AnalysisProvenanceClassification(value.value)


def _verify_unique_case_ids(case_ids: tuple[str, ...]) -> None:
    duplicates = tuple(sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1))
    if duplicates:
        raise AnalysisCohortError("ANALYSIS_CASE_ID_DUPLICATE", ",".join(duplicates))


def _dataset_decision(request: ResearchAnalysisRequest, row) -> tuple[bool, str | None]:
    cohort_type = request.cohort_definition.cohort_type
    if cohort_type is AnalysisCohortType.HISTORICAL_COMPLETED_CASES:
        if row.fixture_classification is FixtureClassification.SYNTHETIC_EDGE_CASE:
            return False, "ANALYSIS_COHORT_EXCLUDED_SYNTHETIC_CASE"
        if row.case_status is not CandidateCaseStatus.COMPLETE:
            return False, "ANALYSIS_COHORT_EXCLUDED_INCOMPLETE_CASE"
        if row.outcome_label in {OutcomeLabel.OUTCOME_UNKNOWN, OutcomeLabel.OUTCOME_INSUFFICIENT_DATA}:
            return False, "ANALYSIS_COHORT_EXCLUDED_OUTCOME_UNKNOWN"
        return True, None
    if cohort_type is AnalysisCohortType.SYNTHETIC_CASES:
        if row.fixture_classification is FixtureClassification.SYNTHETIC_EDGE_CASE:
            return True, None
        return False, "ANALYSIS_COHORT_EXCLUDED_HISTORICAL_CASE"
    if cohort_type is AnalysisCohortType.MIXED_PROVENANCE_CASES:
        return True, None
    raise AnalysisCohortError("ANALYSIS_COHORT_SOURCE_INCOMPATIBLE", cohort_type.value)


def build_dataset_cohort(
    request: ResearchAnalysisRequest,
    dataset: ResearchDataset,
) -> AnalysisCohortMembership:
    if request.source_dataset_id != str(dataset.deterministic_id):
        raise AnalysisCohortError("ANALYSIS_SOURCE_DATASET_MISMATCH")
    if (
        request.cohort_definition.cohort_type is AnalysisCohortType.MIXED_PROVENANCE_CASES
        and _EMPIRICAL_STATISTICS.intersection(request.included_statistics)
    ):
        raise AnalysisCohortError("ANALYSIS_MIXED_PROVENANCE_EMPIRICAL_RATE")
    case_ids = tuple(row.case_id for row in dataset.rows)
    _verify_unique_case_ids(case_ids)

    included = []
    exclusions = []
    for row in sorted(dataset.rows, key=lambda item: item.case_id):
        keep, reason = _dataset_decision(request, row)
        if keep:
            included.append(row)
        else:
            exclusions.append(AnalysisCohortExclusion(
                case_id=row.case_id,
                symbol=row.symbol,
                reason_code=str(reason),
                fixture_classification=row.fixture_classification.value,
            ))
    return AnalysisCohortMembership(
        source_dataset_id=str(dataset.deterministic_id),
        source_registry_id=request.source_registry_id,
        cohort_definition=request.cohort_definition,
        included_case_ids=tuple(row.case_id for row in included),
        included_symbols=tuple(row.symbol for row in included),
        exclusions=tuple(exclusions),
        fixture_classifications=tuple(
            _analysis_provenance(row.fixture_classification) for row in included
        ),
    )


def _registry_decision(request: ResearchAnalysisRequest, entry) -> tuple[bool, str | None]:
    cohort_type = request.cohort_definition.cohort_type
    if cohort_type is AnalysisCohortType.ALL_REGISTERED_CASES:
        return True, None
    if cohort_type is AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES:
        if entry.case_status is CandidateCaseStatus.COMPLETE:
            return False, "ANALYSIS_COHORT_EXCLUDED_COMPLETE_CASE"
        return True, None
    if cohort_type is AnalysisCohortType.MIXED_PROVENANCE_CASES:
        return True, None
    raise AnalysisCohortError("ANALYSIS_COHORT_SOURCE_INCOMPATIBLE", cohort_type.value)


def build_registry_cohort(
    request: ResearchAnalysisRequest,
    registry: CandidateCaseRegistry,
) -> AnalysisCohortMembership:
    if request.source_registry_id != str(registry.deterministic_id):
        raise AnalysisCohortError("ANALYSIS_SOURCE_REGISTRY_MISMATCH")
    case_ids = tuple(entry.case_id for entry in registry.entries)
    _verify_unique_case_ids(case_ids)

    included = []
    exclusions = []
    for entry in sorted(registry.entries, key=lambda item: item.case_id):
        keep, reason = _registry_decision(request, entry)
        if keep:
            included.append(entry)
        else:
            exclusions.append(AnalysisCohortExclusion(
                case_id=entry.case_id,
                symbol=entry.symbol,
                reason_code=str(reason),
                fixture_classification=entry.fixture_classification.value,
            ))
    return AnalysisCohortMembership(
        source_dataset_id=request.source_dataset_id,
        source_registry_id=str(registry.deterministic_id),
        cohort_definition=request.cohort_definition,
        included_case_ids=tuple(entry.case_id for entry in included),
        included_symbols=tuple(entry.symbol for entry in included),
        exclusions=tuple(exclusions),
        fixture_classifications=tuple(
            _analysis_provenance(entry.fixture_classification) for entry in included
        ),
    )


__all__ = ["AnalysisCohortError", "build_dataset_cohort", "build_registry_cohort"]
