"""Research hypothesis and experiment builders (BUILD 17)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .errors import ResearchExperimentError
from .identity import derive_experiment_id, derive_hypothesis_id
from .types import (
    ComponentMutationSpec,
    DataSpecification,
    ExperimentKind,
    ExperimentManifestV1,
    FalsificationCriterion,
    GuardrailCriterion,
    MetricPlan,
    ResearchHypothesisKind,
    ResearchHypothesisV1,
    ResearchKnowledgeFootprint,
    ResourceBudget,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
)


def build_research_hypothesis(
    *,
    title: str,
    hypothesis_kind: ResearchHypothesisKind,
    source_finding_ids: tuple[str, ...],
    claim: str,
    treatment: ComponentMutationSpec,
    control: ComponentMutationSpec,
    primary_metric: str,
    expected_direction: str,
    falsification: FalsificationCriterion,
    knowledge_footprint: ResearchKnowledgeFootprint,
    mechanism: str | None = None,
    secondary_metrics: tuple[str, ...] = (),
    guardrails: tuple[GuardrailCriterion, ...] = (),
    target_kind: str | None = None,
    horizon_ns: int | None = None,
    mode: str | None = None,
    scenario_id: str | None = None,
) -> ResearchHypothesisV1:
    if not source_finding_ids:
        raise ResearchExperimentError("SOURCE_FINDINGS_REQUIRED")
    if not claim.strip():
        raise ResearchExperimentError("CLAIM_REQUIRED")
    if not primary_metric:
        raise ResearchExperimentError("PRIMARY_METRIC_REQUIRED")
    if not expected_direction:
        raise ResearchExperimentError("EXPECTED_DIRECTION_REQUIRED")
    if not falsification.description:
        raise ResearchExperimentError("FALSIFICATION_REQUIRED")
    if treatment.identity_key == control.identity_key:
        raise ResearchExperimentError("TREATMENT_EQUALS_CONTROL")

    provisional = ResearchHypothesisV1(
        research_hypothesis_id="pending",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        title=title,
        hypothesis_kind=hypothesis_kind,
        source_finding_ids=tuple(sorted(source_finding_ids)),
        claim=claim,
        treatment=treatment,
        control=control,
        primary_metric=primary_metric,
        expected_direction=expected_direction,
        falsification=falsification,
        knowledge_footprint=knowledge_footprint,
        mechanism=mechanism,
        secondary_metrics=tuple(sorted(secondary_metrics)),
        guardrails=guardrails,
        target_kind=target_kind,
        horizon_ns=horizon_ns,
        mode=mode,
        scenario_id=scenario_id,
    )
    hypothesis_id = derive_hypothesis_id(provisional)
    return ResearchHypothesisV1(
        research_hypothesis_id=hypothesis_id,
        schema_version=provisional.schema_version,
        title=provisional.title,
        hypothesis_kind=provisional.hypothesis_kind,
        source_finding_ids=provisional.source_finding_ids,
        claim=provisional.claim,
        treatment=provisional.treatment,
        control=provisional.control,
        primary_metric=provisional.primary_metric,
        expected_direction=provisional.expected_direction,
        falsification=provisional.falsification,
        knowledge_footprint=provisional.knowledge_footprint,
        mechanism=provisional.mechanism,
        secondary_metrics=provisional.secondary_metrics,
        guardrails=provisional.guardrails,
        target_kind=provisional.target_kind,
        horizon_ns=provisional.horizon_ns,
        mode=provisional.mode,
        scenario_id=provisional.scenario_id,
    )


def design_experiment(
    *,
    hypothesis: ResearchHypothesisV1,
    experiment_kind: ExperimentKind,
    treatment: ComponentMutationSpec,
    control: ComponentMutationSpec,
    data_spec: DataSpecification,
    metric_plan: MetricPlan,
    success_criteria: str,
    falsification: FalsificationCriterion,
    knowledge_footprint: ResearchKnowledgeFootprint,
    validation_requirements: ValidationRequirements | None = None,
    guardrails: tuple[GuardrailCriterion, ...] = (),
    search_space: SearchSpaceSpec | None = None,
    seed_policy: SeedPolicy | None = None,
    complexity_budget=None,
    resource_budget: ResourceBudget | None = None,
    allowed_changes: tuple[str, ...] = (),
    forbidden_changes: tuple[str, ...] = (),
    evaluation_spec_id: str | None = None,
) -> ExperimentManifestV1:
    from .types import ComplexityBudget

    if treatment.identity_key == control.identity_key:
        raise ResearchExperimentError("TREATMENT_EQUALS_CONTROL")
    if not metric_plan.primary_metric:
        raise ResearchExperimentError("PRIMARY_METRIC_REQUIRED")
    if not success_criteria:
        raise ResearchExperimentError("SUCCESS_CRITERIA_REQUIRED")
    if not falsification.description:
        raise ResearchExperimentError("FALSIFICATION_REQUIRED")
    if hypothesis.target_kind is not None and data_spec.target_kind != hypothesis.target_kind:
        raise ResearchExperimentError(
            "TARGET_MISMATCH",
            details={"hypothesis": hypothesis.target_kind, "data": data_spec.target_kind},
        )
    if hypothesis.horizon_ns is not None and data_spec.horizon_ns != hypothesis.horizon_ns:
        raise ResearchExperimentError("HORIZON_MISMATCH")
    if hypothesis.mode is not None and data_spec.mode != hypothesis.mode:
        raise ResearchExperimentError("MODE_MISMATCH")
    if hypothesis.scenario_id is not None and data_spec.scenario_id != hypothesis.scenario_id:
        raise ResearchExperimentError("SCENARIO_MISMATCH")

    budget = complexity_budget or ComplexityBudget.SAME_COMPLEXITY

    provisional = ExperimentManifestV1(
        experiment_id="pending",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        research_hypothesis_id=hypothesis.research_hypothesis_id,
        experiment_kind=experiment_kind,
        treatment=treatment,
        control=control,
        data_spec=data_spec,
        metric_plan=metric_plan,
        success_criteria=success_criteria,
        falsification=falsification,
        knowledge_footprint=knowledge_footprint,
        validation_requirements=validation_requirements or ValidationRequirements(),
        guardrails=guardrails,
        search_space=search_space,
        seed_policy=seed_policy,
        complexity_budget=budget,
        resource_budget=resource_budget,
        allowed_changes=tuple(sorted(allowed_changes)),
        forbidden_changes=tuple(
            sorted(
                forbidden_changes
                or (
                    "settlement_semantics",
                    "evaluation_metric_formula",
                    "holdout_window",
                    "target_definition",
                )
            )
        ),
        evaluation_spec_id=evaluation_spec_id or hypothesis.knowledge_footprint.evaluation_spec_ids[0]
        if hypothesis.knowledge_footprint.evaluation_spec_ids
        else None,
    )
    experiment_id = derive_experiment_id(provisional)
    return ExperimentManifestV1(
        experiment_id=experiment_id,
        schema_version=provisional.schema_version,
        research_hypothesis_id=provisional.research_hypothesis_id,
        experiment_kind=provisional.experiment_kind,
        treatment=provisional.treatment,
        control=provisional.control,
        data_spec=provisional.data_spec,
        metric_plan=provisional.metric_plan,
        success_criteria=provisional.success_criteria,
        falsification=provisional.falsification,
        knowledge_footprint=provisional.knowledge_footprint,
        validation_requirements=provisional.validation_requirements,
        guardrails=provisional.guardrails,
        search_space=provisional.search_space,
        seed_policy=provisional.seed_policy,
        complexity_budget=provisional.complexity_budget,
        resource_budget=provisional.resource_budget,
        allowed_changes=provisional.allowed_changes,
        forbidden_changes=provisional.forbidden_changes,
        evaluation_spec_id=provisional.evaluation_spec_id,
        implementation_version=provisional.implementation_version,
    )


__all__ = ["build_research_hypothesis", "design_experiment"]
