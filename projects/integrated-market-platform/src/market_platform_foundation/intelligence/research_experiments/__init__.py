"""Research hypothesis and experiment system (BUILD 17)."""

from .builders import build_research_hypothesis, design_experiment
from .errors import ResearchExperimentError
from .findings import DEFAULT_FINDING_POLICY, FindingExtractionPolicy, extract_findings
from .identity import (
    derive_experiment_id,
    derive_finding_id,
    derive_hypothesis_id,
)
from .serialization import (
    experiment_manifest_v1_from_dict,
    experiment_manifest_v1_to_dict,
    research_finding_v1_from_dict,
    research_finding_v1_to_dict,
    research_hypothesis_v1_from_dict,
    research_hypothesis_v1_to_dict,
)
from .service import ResearchExperimentService
from .types import (
    RESEARCH_IMPLEMENTATION_VERSION,
    ComponentMutationSpec,
    DataSpecification,
    ExperimentManifestV1,
    ExperimentKind,
    FalsificationCriterion,
    GuardrailCriterion,
    MetricPlan,
    ResearchFindingV1,
    ResearchFindingType,
    ResearchHypothesisKind,
    ResearchHypothesisV1,
    ResearchKnowledgeFootprint,
    ResearchLifecycleState,
    ResourceBudget,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
)

__all__ = [
    "ComponentMutationSpec",
    "DataSpecification",
    "DEFAULT_FINDING_POLICY",
    "ExperimentKind",
    "ExperimentManifestV1",
    "FalsificationCriterion",
    "FindingExtractionPolicy",
    "GuardrailCriterion",
    "MetricPlan",
    "RESEARCH_IMPLEMENTATION_VERSION",
    "ResearchExperimentError",
    "ResearchExperimentService",
    "ResearchFindingType",
    "ResearchFindingV1",
    "ResearchHypothesisKind",
    "ResearchHypothesisV1",
    "ResearchKnowledgeFootprint",
    "ResearchLifecycleState",
    "ResourceBudget",
    "SearchSpaceSpec",
    "SeedPolicy",
    "ValidationRequirements",
    "build_research_hypothesis",
    "design_experiment",
    "derive_experiment_id",
    "derive_finding_id",
    "derive_hypothesis_id",
    "experiment_manifest_v1_from_dict",
    "experiment_manifest_v1_to_dict",
    "extract_findings",
    "research_finding_v1_from_dict",
    "research_finding_v1_to_dict",
    "research_hypothesis_v1_from_dict",
    "research_hypothesis_v1_to_dict",
]
