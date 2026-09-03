from collections import Counter
from collections.abc import Callable

from squeeze_core.evaluation import RuleOutcome
from squeeze_core.research.models import (
    CandidateCaseRegistry,
    CandidateCaseStatus,
    CandidateCaseType,
    OriginalPlatformStatus,
    OutcomeLabel,
    ResearchDatasetRow,
)

from .models import (
    DataQualitySummary,
    DomainMissingnessSummary,
    RegistryCaseQuality,
)
from .proportions import ProportionContext


def _diagnostics(row: ResearchDatasetRow) -> set[str]:
    return {
        code
        for codes in row.rule_diagnostic_codes.values()
        for code in codes
    }


def _rule_unavailable(row: ResearchDatasetRow, rule_id: str) -> bool:
    return row.rule_outcomes.get(rule_id) in {
        RuleOutcome.UNKNOWN.value,
        RuleOutcome.INSUFFICIENT_DATA.value,
    }


def _diagnostic(code: str) -> Callable[[ResearchDatasetRow], bool]:
    return lambda row: code in _diagnostics(row)


_MISSINGNESS_PREDICATES: tuple[
    tuple[str, Callable[[ResearchDatasetRow], bool]], ...
] = (
    ("PUBLISHED_SHORT_INTEREST", _diagnostic("EVALUATION_SHORT_INTEREST_UNAVAILABLE")),
    ("PUBLISHED_SHORT_INTEREST_CHANGE", _diagnostic("EVALUATION_SHORT_INTEREST_CHANGE_UNAVAILABLE")),
    ("DAYS_TO_COVER", _diagnostic("EVALUATION_DAYS_TO_COVER_UNAVAILABLE")),
    ("BORROW_FEE", _diagnostic("EVALUATION_BORROW_FEE_UNAVAILABLE")),
    ("BORROW_FEE_CHANGE", _diagnostic("EVALUATION_BORROW_FEE_UNAVAILABLE")),
    ("BORROW_AVAILABILITY", _diagnostic("EVALUATION_BORROW_AVAILABILITY_UNAVAILABLE")),
    ("BORROW_AVAILABILITY_CHANGE", _diagnostic("EVALUATION_BORROW_AVAILABILITY_UNAVAILABLE")),
    ("FLOAT", _diagnostic("EVALUATION_FLOAT_UNAVAILABLE")),
    ("PERCENTAGE_CHANGE_HISTORY", _diagnostic("EVALUATION_RETURN_UNAVAILABLE")),
    ("RELATIVE_VOLUME_HISTORY", _diagnostic("EVALUATION_RELATIVE_VOLUME_UNAVAILABLE")),
    ("NEWS", lambda row: _rule_unavailable(row, "NEWS_AVAILABLE")),
    ("NEWS_TIMESTAMP", lambda row: _rule_unavailable(row, "NEWS_TIMESTAMP_KNOWN")),
    ("SEC_FILINGS", _diagnostic("EVALUATION_SEC_FILING_UNAVAILABLE")),
    ("CORPORATE_ACTION_CONTEXT", lambda row: _rule_unavailable(row, "CORPORATE_ACTION_CONTEXT_AVAILABLE")),
    ("PROVIDER_SCOPE", lambda row: _rule_unavailable(row, "PROVIDER_SCOPE_EXPLICIT")),
    ("CONFLICTED_EVIDENCE", lambda row: bool(row.conflicted_rules)),
    ("INSUFFICIENT_HISTORY", lambda row: (
        "REQUIRED_HISTORY_SUFFICIENT" in row.insufficient_rules
        or "EVALUATION_REQUIRED_HISTORY_INSUFFICIENT" in _diagnostics(row)
    )),
    ("PARTIAL_OUTCOME_WINDOW", lambda row: row.outcome_label is OutcomeLabel.OUTCOME_INSUFFICIENT_DATA),
    ("UNKNOWN_PLATFORM_STATUS", lambda row: row.original_platform_status is OriginalPlatformStatus.UNKNOWN),
    ("IDENTITY_CONFLICT", lambda row: any("identity conflict" in item.lower() for item in row.limitations)),
    ("INCOMPLETE_CANDIDATE_CASE", lambda row: row.case_status is not CandidateCaseStatus.COMPLETE),
)


def build_domain_missingness(
    rows: tuple[ResearchDatasetRow, ...],
    context: ProportionContext,
) -> tuple[DomainMissingnessSummary, ...]:
    symbol_counts = Counter(row.symbol for row in rows)
    predicates = _MISSINGNESS_PREDICATES + ((
        "MULTIPLE_BOUNDARIES_PER_SYMBOL",
        lambda row: symbol_counts[row.symbol] > 1,
    ),)
    summaries = []
    for domain_id, predicate in predicates:
        affected = tuple(sorted((row for row in rows if predicate(row)), key=lambda row: row.case_id))
        summaries.append(DomainMissingnessSummary(
            domain_id=domain_id,
            missing_count=len(affected),
            denominator=len(rows),
            affected_case_ids=tuple(row.case_id for row in affected),
            affected_symbols=tuple(row.symbol for row in affected),
            cohort_id=context.cohort_id,
            analysis_unit=context.analysis_unit,
        ))
    return tuple(summaries)


_PARTIAL_STATUSES = {
    CandidateCaseStatus.PARTIAL,
    CandidateCaseStatus.EVALUATION_ONLY,
    CandidateCaseStatus.OUTCOME_ONLY,
    CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY,
}


def _registry_case(entry) -> RegistryCaseQuality:
    synthetic = entry.case_type is CandidateCaseType.SYNTHETIC_EDGE_CASE
    if synthetic:
        exclusion = "ANALYSIS_COHORT_EXCLUDED_SYNTHETIC_CASE"
    elif entry.case_status is CandidateCaseStatus.COMPLETE:
        exclusion = None
    elif entry.case_status.value.startswith("BLOCKED_"):
        exclusion = "ANALYSIS_COHORT_EXCLUDED_BLOCKED_CASE"
    else:
        exclusion = "ANALYSIS_COHORT_EXCLUDED_INCOMPLETE_CASE"
    return RegistryCaseQuality(
        case_id=entry.case_id,
        symbol=entry.symbol,
        case_status=entry.case_status.value,
        case_type=entry.case_type.value,
        platform_status=entry.original_platform_status.value,
        detection_time_evidence_available=entry.detection_time_evidence_id is not None,
        evaluation_available=entry.evaluation_result_path is not None,
        outcome_available=entry.outcome_observation_path is not None,
        identity_conflict=entry.case_status is CandidateCaseStatus.BLOCKED_CONFLICTING_IDENTITY,
        exclusion_reason=exclusion,
        required_evidence=entry.limitations,
    )


def build_registry_data_quality(
    registry: CandidateCaseRegistry,
) -> DataQualitySummary:
    entries = tuple(sorted(registry.entries, key=lambda entry: entry.case_id))
    return DataQualitySummary(
        registered_case_count=len(entries),
        complete_case_count=sum(entry.case_status is CandidateCaseStatus.COMPLETE for entry in entries),
        synthetic_case_count=sum(entry.case_type is CandidateCaseType.SYNTHETIC_EDGE_CASE for entry in entries),
        partial_case_count=sum(entry.case_status in _PARTIAL_STATUSES for entry in entries),
        blocked_case_count=sum(entry.case_status.value.startswith("BLOCKED_") for entry in entries),
        conflicting_identity_count=sum(
            entry.case_status is CandidateCaseStatus.BLOCKED_CONFLICTING_IDENTITY
            for entry in entries
        ),
        unknown_platform_status_count=sum(
            entry.original_platform_status is OriginalPlatformStatus.UNKNOWN
            for entry in entries
        ),
        registry_cases=tuple(_registry_case(entry) for entry in entries),
    )


__all__ = ["build_domain_missingness", "build_registry_data_quality"]
