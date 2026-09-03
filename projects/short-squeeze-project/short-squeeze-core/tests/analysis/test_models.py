from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.analysis import (
    AnalysisCohortDefinition,
    AnalysisCohortType,
    AnalysisUnit,
    BoundarySelectionPolicy,
    ResearchAnalysisRequest,
)


def _cohort(analysis_unit: AnalysisUnit) -> AnalysisCohortDefinition:
    return AnalysisCohortDefinition(
        cohort_type=AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        analysis_unit=analysis_unit,
        boundary_selection_policy_version=(
            BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
            if analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
            else BoundarySelectionPolicy.ALL_CASE_BOUNDARIES
        ),
        provenance_classifications=("SANITIZED_PUBLIC_HISTORICAL_DATA",),
    )


def _request(analysis_unit: AnalysisUnit) -> ResearchAnalysisRequest:
    return ResearchAnalysisRequest(
        source_dataset_id="phase-3b-dataset-id",
        source_registry_id="phase-3b-registry-id",
        cohort_definition=_cohort(analysis_unit),
        analysis_unit=analysis_unit,
        boundary_selection_policy_version=(
            BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
            if analysis_unit is AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
            else BoundarySelectionPolicy.ALL_CASE_BOUNDARIES
        ),
        confidence_level=Decimal("0.95"),
        included_statistics=("RULE_OUTCOME_PREVALENCE", "CONFUSION_MATRIX"),
        excluded_statistics=("THRESHOLD_OPTIMIZATION", "PREDICTIVE_VALIDATION"),
    )


def test_analysis_units_are_semantically_distinct():
    assert AnalysisUnit.UNIQUE_SYMBOL is not AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
    assert (
        AnalysisUnit.UNIQUE_SYMBOL.value
        != AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY.value
    )


def test_request_preserves_dataset_and_registry_sources_independently():
    request = _request(AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY)
    assert request.source_dataset_id == "phase-3b-dataset-id"
    assert request.source_registry_id == "phase-3b-registry-id"
    assert not hasattr(request, "combined_source_id")


def test_request_is_frozen_and_rejects_extra_fields():
    request = _request(AnalysisUnit.CASE_BOUNDARY)
    with pytest.raises(ValidationError):
        request.analysis_version = "changed"
    with pytest.raises(ValidationError):
        ResearchAnalysisRequest(**request.model_dump(), candidate_score=1)


def test_policy_selected_unit_requires_earliest_boundary_policy():
    values = _request(AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY).model_dump()
    values["boundary_selection_policy_version"] = BoundarySelectionPolicy.ALL_CASE_BOUNDARIES
    with pytest.raises(ValidationError, match="policy-selected boundary"):
        ResearchAnalysisRequest(**values)


def test_request_canonicalizes_set_like_statistics():
    values = _request(AnalysisUnit.CASE_BOUNDARY).model_dump()
    values["included_statistics"] = ("RULE_OUTCOME_PREVALENCE", "CONFUSION_MATRIX")
    values["excluded_statistics"] = ("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION")
    request = ResearchAnalysisRequest(**values)
    assert request.included_statistics == ("CONFUSION_MATRIX", "RULE_OUTCOME_PREVALENCE")
    assert request.excluded_statistics == ("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION")
    assert request.schema_version == "1.0.0"
    assert request.statistics_policy_version == "phase_3c_descriptive_statistics_policy.v1"
    assert request.interval_policy_version == "phase_3c_interval_policy.v1"
    assert request.sample_size_policy_version == "phase_3c_sample_size_policy.v1"
