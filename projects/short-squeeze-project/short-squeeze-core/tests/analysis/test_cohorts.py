import pytest

from squeeze_core.analysis import AnalysisCohortType, AnalysisUnit
from squeeze_core.analysis.cohorts import (
    AnalysisCohortError,
    build_dataset_cohort,
    build_registry_cohort,
)
from squeeze_core.research.models import ResearchDataset
from tests.analysis.helpers import analysis_request, load_dataset, load_registry


def test_historical_completed_cohort_excludes_every_synthetic_row():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=("CONFUSION_MATRIX", "RULE_OUTCOME_PREVALENCE"),
    )
    membership = build_dataset_cohort(request, dataset)
    assert membership.included_case_ids == (
        "ADVB_ARTIFACT_DISCOVERY",
        "APVO_ARTIFACT_DISCOVERY",
        "ATAI_ARTIFACT_DISCOVERY",
        "AVTX_ARTIFACT_DISCOVERY",
        "BHVN_ARTIFACT_DISCOVERY",
        "BIYA_ARTIFACT_DISCOVERY",
        "BIYA_EARLIEST_BOUNDARY",
        "BIYA_LATEST_BOUNDARY",
        "CADL_ARTIFACT_DISCOVERY",
        "CELZ_ARTIFACT_DISCOVERY",
        "CGEM_ARTIFACT_DISCOVERY",
        "GDC_ARTIFACT_DISCOVERY",
        "GOAI_ARTIFACT_DISCOVERY",
        "GPRE_ARTIFACT_DISCOVERY",
        "IOVA_ARTIFACT_DISCOVERY",
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "LMNX_ARTIFACT_DISCOVERY",
        "MGNX_ARTIFACT_DISCOVERY",
        "NXXT_ARTIFACT_DISCOVERY",
        "OBE_ARTIFACT_DISCOVERY",
        "PESI_ARTIFACT_DISCOVERY",
        "PMAX_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
        "SSPC_ARTIFACT_DISCOVERY",
        "STAK_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
        "VMAR_ARTIFACT_DISCOVERY",
        "XNCR_ARTIFACT_DISCOVERY",
        "ZNTL_ARTIFACT_DISCOVERY",
    )
    assert membership.included_symbols == (
        "ADVB", "APVO", "ATAI", "AVTX", "BHVN", "BIYA", "CADL", "CELZ",
        "CGEM", "GDC", "GOAI", "GPRE", "IOVA", "KLRS", "LBGJ", "LMNX",
        "MGNX", "NXXT", "OBE", "PESI", "PMAX", "SG", "SLS", "SSPC",
        "STAK", "TRVI", "VMAR", "XNCR", "ZNTL",
    )
    synthetic_exclusions = tuple(
        item for item in membership.exclusions if item.case_id.startswith("SYN_")
    )
    assert len(synthetic_exclusions) == 11
    assert {item.reason_code for item in synthetic_exclusions} == {
        "ANALYSIS_COHORT_EXCLUDED_SYNTHETIC_CASE"
    }


def test_synthetic_cohort_is_separate_and_never_historical():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.SYNTHETIC_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=("SOFTWARE_TRUTH_TABLE_COVERAGE",),
    )
    membership = build_dataset_cohort(request, dataset)
    assert len(membership.included_case_ids) == 11
    assert all(case_id.startswith("SYN_") for case_id in membership.included_case_ids)
    assert {item.case_id for item in membership.exclusions} == {
        "ADVB_ARTIFACT_DISCOVERY",
        "APVO_ARTIFACT_DISCOVERY",
        "ATAI_ARTIFACT_DISCOVERY",
        "AVTX_ARTIFACT_DISCOVERY",
        "BHVN_ARTIFACT_DISCOVERY",
        "BIYA_ARTIFACT_DISCOVERY",
        "BIYA_EARLIEST_BOUNDARY",
        "BIYA_LATEST_BOUNDARY",
        "CADL_ARTIFACT_DISCOVERY",
        "CELZ_ARTIFACT_DISCOVERY",
        "CGEM_ARTIFACT_DISCOVERY",
        "GDC_ARTIFACT_DISCOVERY",
        "GOAI_ARTIFACT_DISCOVERY",
        "GPRE_ARTIFACT_DISCOVERY",
        "IOVA_ARTIFACT_DISCOVERY",
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "LMNX_ARTIFACT_DISCOVERY",
        "MGNX_ARTIFACT_DISCOVERY",
        "NXXT_ARTIFACT_DISCOVERY",
        "OBE_ARTIFACT_DISCOVERY",
        "PESI_ARTIFACT_DISCOVERY",
        "PMAX_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
        "SSPC_ARTIFACT_DISCOVERY",
        "STAK_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
        "VMAR_ARTIFACT_DISCOVERY",
        "XNCR_ARTIFACT_DISCOVERY",
        "ZNTL_ARTIFACT_DISCOVERY",
    }


def test_all_registered_and_partial_blocked_cohorts_preserve_real_incomplete_cases():
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
    all_membership = build_registry_cohort(all_request, registry)
    partial_membership = build_registry_cohort(partial_request, registry)
    assert len(all_membership.included_case_ids) == 43
    assert partial_membership.included_case_ids == (
        "KLOS_IDENTITY_CONFLICT",
    )
    assert len(partial_membership.exclusions) == 42


def test_registry_cohort_requires_explicit_matching_registry_source():
    registry = load_registry()
    request = analysis_request(
        AnalysisCohortType.ALL_REGISTERED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        registry=registry,
    )
    values = request.model_dump(exclude={"deterministic_id"})
    values["source_registry_id"] = "wrong-registry"
    with pytest.raises(AnalysisCohortError, match="ANALYSIS_SOURCE_REGISTRY_MISMATCH"):
        build_registry_cohort(type(request)(**values), registry)


def test_mixed_provenance_cannot_request_empirical_rates():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.MIXED_PROVENANCE_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
        included_statistics=("CONFUSION_MATRIX",),
    )
    with pytest.raises(AnalysisCohortError, match="ANALYSIS_MIXED_PROVENANCE_EMPIRICAL_RATE"):
        build_dataset_cohort(request, dataset)


def test_dataset_membership_is_input_order_invariant():
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
    )
    reversed_dataset = ResearchDataset.model_construct(
        schema_version=dataset.schema_version,
        dataset_version=dataset.dataset_version,
        rows=tuple(reversed(dataset.rows)),
        provenance=dataset.provenance,
        deterministic_id=dataset.deterministic_id,
    )
    assert build_dataset_cohort(request, dataset) == build_dataset_cohort(
        request, reversed_dataset
    )


def test_duplicate_dataset_case_id_is_rejected():
    dataset = load_dataset()
    duplicate = ResearchDataset.model_construct(
        schema_version=dataset.schema_version,
        dataset_version=dataset.dataset_version,
        rows=dataset.rows + (dataset.rows[0],),
        provenance=dataset.provenance,
        deterministic_id=dataset.deterministic_id,
    )
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        AnalysisUnit.CASE_BOUNDARY,
        dataset=dataset,
    )
    with pytest.raises(AnalysisCohortError, match="ANALYSIS_CASE_ID_DUPLICATE"):
        build_dataset_cohort(request, duplicate)

