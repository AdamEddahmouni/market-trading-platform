from squeeze_core.analysis import (
    AnalysisCohortType,
    AnalysisUnit,
    SampleSizeState,
)
from squeeze_core.analysis.runner import (
    AnalysisRunnerError,
    build_standard_analysis_requests,
    run_research_analysis,
)
from squeeze_core.research.models import ResearchDataset
from tests.analysis.helpers import analysis_request, load_dataset, load_registry


def _limitation_codes(result):
    return {item.code for item in result.limitations}


def test_historical_case_boundary_analysis_preserves_dependence():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=(
            "CONFUSION_MATRIX",
            "DETECTION_PREVALENCE",
            "OUTCOME_PREVALENCE",
            "RESEARCH_CLASSIFICATION_PREVALENCE",
            "RULE_OUTCOME_PREVALENCE",
            "MISSINGNESS",
        ),
    )
    result = run_research_analysis(request, dataset=dataset)
    assert result.source_dataset_id == dataset.deterministic_id
    assert result.source_registry_id is None
    assert result.case_count == 7
    assert result.unique_symbol_count == 6
    assert result.boundary_count == 7
    assert result.cohort_membership.included_case_ids == (
        "BIYA_EARLIEST_BOUNDARY",
        "BIYA_LATEST_BOUNDARY",
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
    )
    assert result.symbol_dependence_summary.dependence_detected
    assert result.confusion_matrix.true_positive_count == 2
    assert result.confusion_matrix.unevaluable_count == 5
    assert result.sample_size_assessments[0].state is SampleSizeState.SMALL
    assert "HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT" in _limitation_codes(result)


def test_historical_unique_symbol_analysis_selects_earliest_without_outcome():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
        dataset=dataset,
        included_statistics=("CONFUSION_MATRIX", "RULE_OUTCOME_PREVALENCE", "MISSINGNESS"),
    )
    result = run_research_analysis(request, dataset=dataset)
    assert result.case_count == 6
    assert result.unique_symbol_count == 6
    assert result.boundary_count == 7
    assert result.cohort_membership.included_case_ids == (
        "BIYA_EARLIEST_BOUNDARY",
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
    )
    duplicate = next(
        item for item in result.cohort_membership.exclusions
        if item.case_id == "BIYA_LATEST_BOUNDARY"
    )
    assert duplicate.reason_code == "ANALYSIS_COHORT_EXCLUDED_DUPLICATE_SYMBOL_BOUNDARY"
    assert result.boundary_selection.outcome_blind
    assert result.sample_size_assessments[0].state is SampleSizeState.SMALL
    assert result.confusion_matrix.true_positive_count == 1
    assert "HISTORICAL_SAMPLE_INSUFFICIENT_FOR_PREDICTIVE_VALIDATION" in _limitation_codes(result)


def test_synthetic_analysis_is_software_coverage_only():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.SYNTHETIC_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=("CONFUSION_MATRIX", "RULE_OUTCOME_PREVALENCE", "MISSINGNESS"),
    )
    result = run_research_analysis(request, dataset=dataset)
    assert result.case_count == result.unique_symbol_count == 11
    assert result.confusion_matrix.true_positive_count == 1
    assert "SYNTHETIC_CASES_ARE_NOT_EMPIRICAL_EVIDENCE" in _limitation_codes(result)
    assert all(case_id.startswith("SYN_") for case_id in result.cohort_membership.included_case_ids)


def test_registry_standard_cohorts_preserve_registry_id_and_quality():
    registry = load_registry()
    all_request = analysis_request(
        AnalysisCohortType.ALL_REGISTERED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        registry=registry,
    )
    partial_request = analysis_request(
        AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        registry=registry,
    )
    all_result = run_research_analysis(all_request, registry=registry)
    partial_result = run_research_analysis(partial_request, registry=registry)
    assert all_result.source_registry_id == registry.deterministic_id
    assert all_result.source_dataset_id is None
    assert all_result.case_count == 19
    assert all_result.data_quality_summary.registered_case_count == 19
    assert partial_result.case_count == 1
    assert partial_result.data_quality_summary.registered_case_count == 19
    assert "REGISTRY_DATA_QUALITY_NOT_PERFORMANCE_ESTIMATE" in _limitation_codes(all_result)


def test_runner_requires_the_explicit_source_object():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
    )
    try:
        run_research_analysis(request)
    except AnalysisRunnerError as exc:
        assert exc.code == "ANALYSIS_SOURCE_DATASET_REQUIRED"
    else:
        raise AssertionError("runner accepted an absent explicit dataset")


def test_runner_is_input_order_invariant():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=("CONFUSION_MATRIX", "RULE_OUTCOME_PREVALENCE", "MISSINGNESS"),
    )
    reversed_dataset = ResearchDataset.model_construct(
        schema_version=dataset.schema_version,
        dataset_version=dataset.dataset_version,
        rows=tuple(reversed(dataset.rows)),
        provenance=dataset.provenance,
        deterministic_id=dataset.deterministic_id,
    )
    assert run_research_analysis(request, dataset=dataset) == run_research_analysis(
        request, dataset=reversed_dataset
    )


def test_standard_requests_are_self_describing_and_distinct():
    dataset = load_dataset()
    registry = load_registry()
    requests = build_standard_analysis_requests(dataset, registry)
    assert len(requests) == 5
    assert len({item.deterministic_id for item in requests}) == 5
    assert requests[0].analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
    assert requests[0].source_dataset_id == dataset.deterministic_id
    assert requests[3].source_registry_id == registry.deterministic_id
    assert all(item.statistics_policy_version for item in requests)
    assert all(item.interval_policy_version for item in requests)
    assert all(item.sample_size_policy_version for item in requests)

