"""Serialization for BUILD 17 research artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .types import (
    ComplexityBudget,
    ComponentMutationSpec,
    DataSpecification,
    EvidenceTier,
    ExperimentKind,
    ExperimentManifestV1,
    FalsificationCriterion,
    GuardrailCriterion,
    MetricObservation,
    MetricPlan,
    ResearchEntityKind,
    ResearchFindingType,
    ResearchFindingV1,
    ResearchHypothesisKind,
    ResearchHypothesisV1,
    ResearchKnowledgeFootprint,
    ResearchLifecycleEventV1,
    ResearchLifecycleState,
    ResourceBudget,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
)


def _mutation_to_dict(spec: ComponentMutationSpec) -> dict[str, Any]:
    body: dict[str, Any] = {
        "component": spec.component,
        "parameter": spec.parameter,
        "details": dict(spec.details),
    }
    if spec.baseline_ref is not None:
        body["baseline_ref"] = spec.baseline_ref
    if spec.candidate_ref is not None:
        body["candidate_ref"] = spec.candidate_ref
    if spec.mutation_kind is not None:
        body["mutation_kind"] = spec.mutation_kind
    return body


def _mutation_from_dict(payload: dict[str, Any]) -> ComponentMutationSpec:
    return ComponentMutationSpec(
        component=str(payload["component"]),
        parameter=str(payload["parameter"]),
        baseline_ref=payload.get("baseline_ref"),
        candidate_ref=payload.get("candidate_ref"),
        mutation_kind=payload.get("mutation_kind"),
        details=dict(payload.get("details") or {}),
    )


def _metric_observation_to_dict(obs: MetricObservation) -> dict[str, Any]:
    body: dict[str, Any] = {
        "metric_name": obs.metric_name,
        "sample_count": obs.sample_count,
    }
    if obs.value is not None:
        body["value"] = obs.value
    if obs.baseline_value is not None:
        body["baseline_value"] = obs.baseline_value
    if obs.delta is not None:
        body["delta"] = obs.delta
    return body


def _metric_observation_from_dict(payload: dict[str, Any]) -> MetricObservation:
    return MetricObservation(
        metric_name=str(payload["metric_name"]),
        value=payload.get("value"),
        sample_count=int(payload["sample_count"]),
        baseline_value=payload.get("baseline_value"),
        delta=payload.get("delta"),
    )


def _footprint_to_dict(fp: ResearchKnowledgeFootprint) -> dict[str, Any]:
    body: dict[str, Any] = {
        "evaluation_report_ids": list(fp.evaluation_report_ids),
        "evaluation_spec_ids": list(fp.evaluation_spec_ids),
        "cohort_fingerprints": list(fp.cohort_fingerprints),
        "slice_keys": list(fp.slice_keys),
        "comparison_keys": list(fp.comparison_keys),
    }
    if fp.decision_start_ns is not None:
        body["decision_start_ns"] = fp.decision_start_ns
    if fp.decision_end_ns is not None:
        body["decision_end_ns"] = fp.decision_end_ns
    if fp.mode is not None:
        body["mode"] = fp.mode
    if fp.scenario_id is not None:
        body["scenario_id"] = fp.scenario_id
    if fp.evidence_tier is not None:
        body["evidence_tier"] = fp.evidence_tier.value
    return body


def _footprint_from_dict(payload: dict[str, Any]) -> ResearchKnowledgeFootprint:
    tier = payload.get("evidence_tier")
    return ResearchKnowledgeFootprint(
        evaluation_report_ids=tuple(payload.get("evaluation_report_ids") or []),
        evaluation_spec_ids=tuple(payload.get("evaluation_spec_ids") or []),
        cohort_fingerprints=tuple(payload.get("cohort_fingerprints") or []),
        decision_start_ns=payload.get("decision_start_ns"),
        decision_end_ns=payload.get("decision_end_ns"),
        slice_keys=tuple(payload.get("slice_keys") or []),
        comparison_keys=tuple(payload.get("comparison_keys") or []),
        mode=payload.get("mode"),
        scenario_id=payload.get("scenario_id"),
        evidence_tier=EvidenceTier(tier) if tier is not None else None,
    )


def research_finding_v1_to_dict(record: ResearchFindingV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "finding_id": record.finding_id,
        "schema_version": record.schema_version,
        "finding_type": record.finding_type.value,
        "evaluation_report_id": record.evaluation_report_id,
        "evaluation_spec_id": record.evaluation_spec_id,
        "cohort_fingerprint": record.cohort_fingerprint,
        "metric_observations": [
            _metric_observation_to_dict(obs) for obs in record.metric_observations
        ],
        "sample_count": record.sample_count,
        "mode": record.mode,
        "evidence_tier": record.evidence_tier.value,
        "observation_summary": record.observation_summary,
    }
    if record.slice_dimension is not None:
        body["slice_dimension"] = record.slice_dimension
    if record.slice_value is not None:
        body["slice_value"] = record.slice_value
    if record.comparison_key is not None:
        body["comparison_key"] = record.comparison_key
    if record.scenario_id is not None:
        body["scenario_id"] = record.scenario_id
    if record.limitations:
        body["limitations"] = list(record.limitations)
    if record.finding_policy_id is not None:
        body["finding_policy_id"] = record.finding_policy_id
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def research_finding_v1_from_dict(payload: dict[str, Any]) -> ResearchFindingV1:
    return ResearchFindingV1(
        finding_id=str(payload["finding_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        finding_type=ResearchFindingType(str(payload["finding_type"])),
        evaluation_report_id=str(payload["evaluation_report_id"]),
        evaluation_spec_id=str(payload["evaluation_spec_id"]),
        cohort_fingerprint=str(payload["cohort_fingerprint"]),
        metric_observations=tuple(
            _metric_observation_from_dict(item)
            for item in payload.get("metric_observations") or []
        ),
        sample_count=int(payload["sample_count"]),
        mode=str(payload["mode"]),
        evidence_tier=EvidenceTier(str(payload["evidence_tier"])),
        slice_dimension=payload.get("slice_dimension"),
        slice_value=payload.get("slice_value"),
        comparison_key=payload.get("comparison_key"),
        scenario_id=payload.get("scenario_id"),
        limitations=tuple(payload.get("limitations") or []),
        finding_policy_id=payload.get("finding_policy_id"),
        observation_summary=str(payload.get("observation_summary") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


def research_hypothesis_v1_to_dict(record: ResearchHypothesisV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "research_hypothesis_id": record.research_hypothesis_id,
        "schema_version": record.schema_version,
        "title": record.title,
        "hypothesis_kind": record.hypothesis_kind.value,
        "source_finding_ids": list(record.source_finding_ids),
        "claim": record.claim,
        "treatment": _mutation_to_dict(record.treatment),
        "control": _mutation_to_dict(record.control),
        "primary_metric": record.primary_metric,
        "expected_direction": record.expected_direction,
        "falsification": {
            "description": record.falsification.description,
            "metric_name": record.falsification.metric_name,
            "failure_condition": record.falsification.failure_condition,
        },
        "knowledge_footprint": _footprint_to_dict(record.knowledge_footprint),
    }
    if record.mechanism is not None:
        body["mechanism"] = record.mechanism
    if record.secondary_metrics:
        body["secondary_metrics"] = list(record.secondary_metrics)
    if record.guardrails:
        body["guardrails"] = [
            {
                "metric_name": g.metric_name,
                "max_regression": g.max_regression,
                "min_value": g.min_value,
                "max_value": g.max_value,
            }
            for g in record.guardrails
        ]
    if record.target_kind is not None:
        body["target_kind"] = record.target_kind
    if record.horizon_ns is not None:
        body["horizon_ns"] = record.horizon_ns
    if record.mode is not None:
        body["mode"] = record.mode
    if record.scenario_id is not None:
        body["scenario_id"] = record.scenario_id
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def research_hypothesis_v1_from_dict(payload: dict[str, Any]) -> ResearchHypothesisV1:
    fals = payload.get("falsification") or {}
    guardrails = tuple(
        GuardrailCriterion(
            metric_name=str(item["metric_name"]),
            max_regression=item.get("max_regression"),
            min_value=item.get("min_value"),
            max_value=item.get("max_value"),
        )
        for item in payload.get("guardrails") or []
    )
    return ResearchHypothesisV1(
        research_hypothesis_id=str(payload["research_hypothesis_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        title=str(payload["title"]),
        hypothesis_kind=ResearchHypothesisKind(str(payload["hypothesis_kind"])),
        source_finding_ids=tuple(payload.get("source_finding_ids") or []),
        claim=str(payload["claim"]),
        treatment=_mutation_from_dict(payload["treatment"]),
        control=_mutation_from_dict(payload["control"]),
        primary_metric=str(payload["primary_metric"]),
        expected_direction=str(payload["expected_direction"]),
        falsification=FalsificationCriterion(
            description=str(fals.get("description") or ""),
            metric_name=fals.get("metric_name"),
            failure_condition=fals.get("failure_condition"),
        ),
        knowledge_footprint=_footprint_from_dict(payload["knowledge_footprint"]),
        mechanism=payload.get("mechanism"),
        secondary_metrics=tuple(payload.get("secondary_metrics") or []),
        guardrails=guardrails,
        target_kind=payload.get("target_kind"),
        horizon_ns=payload.get("horizon_ns"),
        mode=payload.get("mode"),
        scenario_id=payload.get("scenario_id"),
        metadata=dict(payload.get("metadata") or {}),
    )


def experiment_manifest_v1_to_dict(record: ExperimentManifestV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "experiment_id": record.experiment_id,
        "schema_version": record.schema_version,
        "research_hypothesis_id": record.research_hypothesis_id,
        "experiment_kind": record.experiment_kind.value,
        "treatment": _mutation_to_dict(record.treatment),
        "control": _mutation_to_dict(record.control),
        "data_spec": {
            "target_kind": record.data_spec.target_kind,
            "horizon_ns": record.data_spec.horizon_ns,
            "mode": record.data_spec.mode,
            "decision_start_ns": record.data_spec.decision_start_ns,
            "decision_end_ns": record.data_spec.decision_end_ns,
            "scenario_id": record.data_spec.scenario_id,
            "instrument_ids": list(record.data_spec.instrument_ids),
            "quality_requirements": list(record.data_spec.quality_requirements),
            "feature_schema_fingerprint": record.data_spec.feature_schema_fingerprint,
        },
        "metric_plan": {
            "primary_metric": record.metric_plan.primary_metric,
            "secondary_metrics": list(record.metric_plan.secondary_metrics),
            "guardrails": list(record.metric_plan.guardrails),
            "expected_direction": record.metric_plan.expected_direction,
        },
        "success_criteria": record.success_criteria,
        "falsification": {
            "description": record.falsification.description,
            "metric_name": record.falsification.metric_name,
            "failure_condition": record.falsification.failure_condition,
        },
        "knowledge_footprint": _footprint_to_dict(record.knowledge_footprint),
        "validation_requirements": {
            "requires_walk_forward": record.validation_requirements.requires_walk_forward,
            "requires_purge": record.validation_requirements.requires_purge,
            "requires_embargo": record.validation_requirements.requires_embargo,
            "requires_locked_holdout": record.validation_requirements.requires_locked_holdout,
            "validation_policy_ref": record.validation_requirements.validation_policy_ref,
        },
        "complexity_budget": record.complexity_budget.value,
        "allowed_changes": list(record.allowed_changes),
        "forbidden_changes": list(record.forbidden_changes),
        "implementation_version": record.implementation_version,
    }
    if record.guardrails:
        body["guardrails"] = [
            {
                "metric_name": g.metric_name,
                "max_regression": g.max_regression,
                "min_value": g.min_value,
                "max_value": g.max_value,
            }
            for g in record.guardrails
        ]
    if record.search_space is not None:
        body["search_space"] = {
            "parameters": {
                key: list(values) for key, values in record.search_space.parameters.items()
            }
        }
    if record.seed_policy is not None:
        body["seed_policy"] = {
            "fixed_seeds": list(record.seed_policy.fixed_seeds),
            "derivation_algorithm": record.seed_policy.derivation_algorithm,
        }
    if record.resource_budget is not None:
        body["resource_budget"] = {
            "max_training_runs": record.resource_budget.max_training_runs,
            "max_candidates": record.resource_budget.max_candidates,
            "max_gpu_hours": record.resource_budget.max_gpu_hours,
        }
    if record.evaluation_spec_id is not None:
        body["evaluation_spec_id"] = record.evaluation_spec_id
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def experiment_manifest_v1_from_dict(payload: dict[str, Any]) -> ExperimentManifestV1:
    data = payload["data_spec"]
    metric = payload["metric_plan"]
    fals = payload.get("falsification") or {}
    validation = payload.get("validation_requirements") or {}
    search_raw = payload.get("search_space")
    seed_raw = payload.get("seed_policy")
    resource_raw = payload.get("resource_budget")
    return ExperimentManifestV1(
        experiment_id=str(payload["experiment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        research_hypothesis_id=str(payload["research_hypothesis_id"]),
        experiment_kind=ExperimentKind(str(payload["experiment_kind"])),
        treatment=_mutation_from_dict(payload["treatment"]),
        control=_mutation_from_dict(payload["control"]),
        data_spec=DataSpecification(
            target_kind=str(data["target_kind"]),
            horizon_ns=int(data["horizon_ns"]),
            mode=str(data["mode"]),
            decision_start_ns=int(data["decision_start_ns"]),
            decision_end_ns=int(data["decision_end_ns"]),
            scenario_id=data.get("scenario_id"),
            instrument_ids=tuple(data.get("instrument_ids") or []),
            quality_requirements=tuple(data.get("quality_requirements") or []),
            feature_schema_fingerprint=data.get("feature_schema_fingerprint"),
        ),
        metric_plan=MetricPlan(
            primary_metric=str(metric["primary_metric"]),
            secondary_metrics=tuple(metric.get("secondary_metrics") or []),
            guardrails=tuple(metric.get("guardrails") or []),
            expected_direction=metric.get("expected_direction"),
        ),
        success_criteria=str(payload["success_criteria"]),
        falsification=FalsificationCriterion(
            description=str(fals.get("description") or ""),
            metric_name=fals.get("metric_name"),
            failure_condition=fals.get("failure_condition"),
        ),
        knowledge_footprint=_footprint_from_dict(payload["knowledge_footprint"]),
        validation_requirements=ValidationRequirements(
            requires_walk_forward=bool(validation.get("requires_walk_forward", True)),
            requires_purge=bool(validation.get("requires_purge", True)),
            requires_embargo=bool(validation.get("requires_embargo", True)),
            requires_locked_holdout=bool(validation.get("requires_locked_holdout", True)),
            validation_policy_ref=validation.get("validation_policy_ref"),
        ),
        guardrails=tuple(
            GuardrailCriterion(
                metric_name=str(item["metric_name"]),
                max_regression=item.get("max_regression"),
                min_value=item.get("min_value"),
                max_value=item.get("max_value"),
            )
            for item in payload.get("guardrails") or []
        ),
        search_space=(
            SearchSpaceSpec(
                parameters={
                    key: tuple(values)
                    for key, values in search_raw.get("parameters", {}).items()
                }
            )
            if search_raw is not None
            else None
        ),
        seed_policy=(
            SeedPolicy(
                fixed_seeds=tuple(seed_raw.get("fixed_seeds") or []),
                derivation_algorithm=seed_raw.get("derivation_algorithm"),
            )
            if seed_raw is not None
            else None
        ),
        complexity_budget=ComplexityBudget(
            str(payload.get("complexity_budget", ComplexityBudget.SAME_COMPLEXITY.value))
        ),
        resource_budget=(
            ResourceBudget(
                max_training_runs=resource_raw.get("max_training_runs"),
                max_candidates=resource_raw.get("max_candidates"),
                max_gpu_hours=resource_raw.get("max_gpu_hours"),
            )
            if resource_raw is not None
            else None
        ),
        allowed_changes=tuple(payload.get("allowed_changes") or []),
        forbidden_changes=tuple(payload.get("forbidden_changes") or []),
        evaluation_spec_id=payload.get("evaluation_spec_id"),
        implementation_version=str(
            payload.get("implementation_version", "research-experiment-system-v1")
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def research_lifecycle_event_v1_to_dict(record: ResearchLifecycleEventV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": record.event_id,
        "schema_version": record.schema_version,
        "entity_kind": record.entity_kind.value,
        "entity_id": record.entity_id,
        "lifecycle_state": record.lifecycle_state.value,
        "recorded_at_ns": record.recorded_at_ns,
    }
    if record.details:
        body["details"] = dict(record.details)
    return body


def research_lifecycle_event_v1_from_dict(payload: dict[str, Any]) -> ResearchLifecycleEventV1:
    return ResearchLifecycleEventV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        entity_kind=ResearchEntityKind(str(payload["entity_kind"])),
        entity_id=str(payload["entity_id"]),
        lifecycle_state=ResearchLifecycleState(str(payload["lifecycle_state"])),
        recorded_at_ns=int(payload["recorded_at_ns"]),
        details=dict(payload.get("details") or {}),
    )


__all__ = [
    "experiment_manifest_v1_from_dict",
    "experiment_manifest_v1_to_dict",
    "research_finding_v1_from_dict",
    "research_finding_v1_to_dict",
    "research_hypothesis_v1_from_dict",
    "research_hypothesis_v1_to_dict",
    "research_lifecycle_event_v1_from_dict",
    "research_lifecycle_event_v1_to_dict",
]
