from squeeze_core.analysis import AnalysisCohortType, AnalysisUnit
from squeeze_core.analysis.runner import (
    build_standard_analysis_requests,
    run_research_analysis,
)
from squeeze_core.analysis.serialization import (
    serialize_analysis_collection,
    serialize_analysis_model,
)
from tests.analysis.helpers import load_dataset, load_registry


def _standard_results():
    dataset = load_dataset()
    registry = load_registry()
    requests = build_standard_analysis_requests(dataset, registry)
    results = tuple(
        run_research_analysis(
            request,
            dataset=dataset if request.source_dataset_id is not None else None,
            registry=registry if request.source_registry_id is not None else None,
        )
        for request in requests
    )
    return requests, results


def test_all_five_standard_cohorts_are_explicit_and_deterministic():
    requests, results = _standard_results()
    assert tuple(item.cohort_definition.cohort_type for item in requests) == (
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisCohortType.SYNTHETIC_CASES,
        AnalysisCohortType.ALL_REGISTERED_CASES,
        AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES,
    )
    assert tuple(item.analysis_unit for item in requests[:2]) == (
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
        AnalysisUnit.CASE_BOUNDARY,
    )
    assert tuple(item.case_count for item in results) == (6, 7, 11, 19, 1)
    assert len({item.deterministic_id for item in results}) == 5
    assert serialize_analysis_collection(results) == serialize_analysis_collection(results)
    assert all(serialize_analysis_model(item) == serialize_analysis_model(item) for item in results)


def test_standard_historical_results_never_include_synthetic_cases():
    _, results = _standard_results()
    for result in results[:2]:
        assert all(
            not case_id.startswith("SYN_")
            for case_id in result.cohort_membership.included_case_ids
        )
        assert sum(
            item.reason_code == "ANALYSIS_COHORT_EXCLUDED_SYNTHETIC_CASE"
            for item in result.cohort_membership.exclusions
        ) == 11


def test_registry_results_keep_source_registry_separate_from_dataset():
    _, results = _standard_results()
    for result in results[3:]:
        assert result.source_registry_id
        assert result.source_dataset_id is None
        assert not hasattr(result, "combined_source_id")

