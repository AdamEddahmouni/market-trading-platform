from decimal import Decimal
from pathlib import Path

from squeeze_core.analysis import (
    AnalysisCohortDefinition,
    AnalysisCohortType,
    AnalysisProvenanceClassification,
    AnalysisUnit,
    BoundarySelectionPolicy,
    ResearchAnalysisRequest,
)
from squeeze_core.research.models import CandidateCaseRegistry
from squeeze_core.research.serialization import deserialize_research_dataset


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_FIXTURES = ROOT / "tests" / "fixtures" / "research"


def load_dataset():
    return deserialize_research_dataset(
        (RESEARCH_FIXTURES / "phase_3b_research_dataset.json").read_bytes()
    )


def load_registry():
    return CandidateCaseRegistry.model_validate_json(
        (RESEARCH_FIXTURES / "phase_3b_case_registry.json").read_bytes()
    )


def analysis_request(
    cohort_type: AnalysisCohortType,
    analysis_unit: AnalysisUnit,
    *,
    dataset=None,
    registry=None,
    included_statistics=("DATA_QUALITY",),
):
    if cohort_type is AnalysisCohortType.HISTORICAL_COMPLETED_CASES:
        provenance = (AnalysisProvenanceClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,)
    elif cohort_type is AnalysisCohortType.SYNTHETIC_CASES:
        provenance = (AnalysisProvenanceClassification.SYNTHETIC_EDGE_CASE,)
    elif cohort_type is AnalysisCohortType.PARTIAL_OR_BLOCKED_CASES:
        provenance = (AnalysisProvenanceClassification.SANITIZED_LOCAL_ARTIFACT,)
    else:
        provenance = (
            AnalysisProvenanceClassification.MIXED_PROVENANCE,
            AnalysisProvenanceClassification.SANITIZED_LOCAL_ARTIFACT,
            AnalysisProvenanceClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
            AnalysisProvenanceClassification.SYNTHETIC_EDGE_CASE,
        )
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
        included_statistics=included_statistics,
        excluded_statistics=("PREDICTIVE_VALIDATION", "THRESHOLD_OPTIMIZATION"),
    )

