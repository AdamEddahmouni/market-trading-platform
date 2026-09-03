from collections import Counter

from squeeze_core.evaluation import RuleCategory, RuleOutcome

from .identifiers import deterministic_research_id
from .models import (
    BatchEvaluationResult,
    DatasetProvenance,
    ResearchCaseClassification,
    ResearchDataset,
    ResearchDatasetRow,
)


DATASET_VERSION = "phase_3b_research_dataset.v1"

_MISSING_DOMAINS = {
    "PUBLISHED_SHORT_INTEREST_AVAILABLE": "PUBLISHED_SHORT_INTEREST",
    "DAYS_TO_COVER_MINIMUM": "DAYS_TO_COVER",
    "BORROW_FEE_MINIMUM": "BORROW_FEE",
    "BORROW_FEE_CHANGE_MINIMUM": "BORROW_FEE",
    "BORROW_AVAILABILITY_MAXIMUM": "BORROW_AVAILABILITY",
    "BORROW_AVAILABILITY_CHANGE_MAXIMUM": "BORROW_AVAILABILITY",
    "FLOAT_MAXIMUM": "FLOAT",
    "RELATIVE_VOLUME_MINIMUM": "RELATIVE_VOLUME_HISTORY",
    "NEWS_TIMESTAMP_KNOWN": "NEWS_TIMESTAMPS",
    "SEC_FILING_AVAILABLE": "SEC_FILINGS",
    "PROVIDER_SCOPE_EXPLICIT": "PROVIDER_SCOPE",
    "REQUIRED_HISTORY_SUFFICIENT": "HISTORY",
}


def _row(case) -> ResearchDatasetRow:
    rules = case.phase_3a_rule_results
    category_counts = {}
    for category in RuleCategory:
        values = [item.outcome for item in rules if item.category is category]
        counts = Counter(values)
        category_counts[category.value] = {
            "pass_count": counts[RuleOutcome.PASS],
            "fail_count": counts[RuleOutcome.FAIL],
            "unknown_count": counts[RuleOutcome.UNKNOWN],
            "conflicted_count": counts[RuleOutcome.CONFLICTED],
            "insufficient_data_count": counts[RuleOutcome.INSUFFICIENT_DATA],
            "not_applicable_count": counts[RuleOutcome.NOT_APPLICABLE],
        }
    missing = tuple(
        _MISSING_DOMAINS[item.rule_id]
        for item in rules
        if item.outcome is RuleOutcome.UNKNOWN and item.rule_id in _MISSING_DOMAINS
    )
    source_ids = (
        *case.original_platform_artifact_ids,
        case.phase_3a_evaluation_id,
        case.outcome_observation_id,
        *case.outcome_supporting_observation_ids,
    )
    identity = {
        "result_type": "PHASE_3B_RESEARCH_DATASET_ROW",
        "dataset_version": DATASET_VERSION,
        "case_id": case.case_id,
        "case_result_id": case.deterministic_id,
        "policy_versions": (
            case.phase_3a_policy_version,
            case.detection_policy_version,
            case.outcome_policy_version,
        ),
        "source_ids": tuple(sorted(set(source_ids))),
        "fixture_classification": case.fixture_classification,
    }
    return ResearchDatasetRow(
        dataset_version=DATASET_VERSION,
        case_id=case.case_id,
        symbol=case.symbol,
        asset_class=case.asset_class,
        case_type=case.case_type,
        case_status=case.case_status,
        evaluation_as_of=case.evaluation_as_of,
        phase_3a_policy_version=case.phase_3a_policy_version,
        research_detection_policy_version=case.detection_policy_version,
        outcome_policy_version=case.outcome_policy_version,
        original_platform_status=case.original_platform_status,
        research_detection_status=case.research_detection_status,
        outcome_label=case.outcome_label,
        research_classification=case.research_classification,
        phase_3a_evaluation_id=case.phase_3a_evaluation_id,
        outcome_observation_id=case.outcome_observation_id,
        rule_outcomes={item.rule_id: item.outcome.value for item in rules},
        rule_observed_values={item.rule_id: item.observed_value for item in rules},
        rule_threshold_values={item.rule_id: item.threshold_values for item in rules},
        rule_diagnostic_codes={
            item.rule_id: tuple(diagnostic.code.value for diagnostic in item.diagnostics)
            for item in rules
        },
        category_counts=category_counts,
        missing_domains=missing,
        conflicted_rules=tuple(item.rule_id for item in rules if item.outcome is RuleOutcome.CONFLICTED),
        insufficient_rules=tuple(item.rule_id for item in rules if item.outcome is RuleOutcome.INSUFFICIENT_DATA),
        outcome_reference_policy=case.outcome_reference_policy,
        outcome_horizon=case.outcome_horizon,
        maximum_observed_move_percent=case.maximum_observed_move_percent,
        maximum_adverse_move_percent=case.maximum_adverse_move_percent,
        fixture_classification=case.fixture_classification,
        source_ids=source_ids,
        limitations=case.limitations,
        row_id=deterministic_research_id(identity),
    )


def _provenance(batch: BatchEvaluationResult, rows) -> DatasetProvenance:
    classifications = Counter(row.fixture_classification.value for row in rows)
    limitations = (
        "historical cases may be incomplete",
        "original-platform surfaced status may be unknown",
        "outcome confirmation does not prove short-squeeze causation",
        "rule prevalence does not prove predictive value",
        "small sample sizes limit interpretation",
        "missing short-pressure evidence may dominate results",
        "public historical sources may differ from original providers",
        "outcome labels are provisional research labels",
        "the detection predicate is provisional",
        "thresholds were not optimized in Phase 3B",
        "no trading simulation was performed",
    )
    return DatasetProvenance(
        dataset_version=DATASET_VERSION,
        generated_from_case_registry_id=batch.case_registry_id,
        phase_3a_policy_version=batch.phase_3a_policy_version,
        research_detection_policy_version=batch.research_detection_policy_version,
        outcome_policy_version=batch.outcome_label_policy_version,
        case_ids=tuple(row.case_id for row in rows),
        row_ids=tuple(row.row_id for row in rows),
        source_fixture_ids=tuple(source for row in rows for source in row.source_ids),
        fixture_classification_counts=tuple(classifications.items()),
        limitations=limitations,
    )


def build_research_dataset(batch: BatchEvaluationResult) -> ResearchDataset:
    rows = tuple(_row(case) for case in batch.case_results)
    return ResearchDataset(
        dataset_version=DATASET_VERSION,
        rows=rows,
        provenance=_provenance(batch, rows),
    )


def filter_research_dataset(
    dataset: ResearchDataset,
    classification: ResearchCaseClassification,
) -> ResearchDataset:
    rows = tuple(row for row in dataset.rows if row.research_classification is classification)
    provenance_values = dataset.provenance.model_dump(exclude={"deterministic_id"})
    provenance_values.update({
        "case_ids": tuple(row.case_id for row in rows),
        "row_ids": tuple(row.row_id for row in rows),
        "source_fixture_ids": tuple(source for row in rows for source in row.source_ids),
        "fixture_classification_counts": tuple(Counter(
            row.fixture_classification.value for row in rows
        ).items()),
    })
    provenance = DatasetProvenance(**provenance_values)
    return ResearchDataset(dataset_version=dataset.dataset_version, rows=rows, provenance=provenance)


__all__ = ["DATASET_VERSION", "build_research_dataset", "filter_research_dataset"]
