"""Deterministic research artifact identity (BUILD 17)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .types import (
    ComponentMutationSpec,
    DataSpecification,
    ExperimentManifestV1,
    MetricObservation,
    MetricPlan,
    ResearchFindingV1,
    ResearchHypothesisV1,
    ResearchKnowledgeFootprint,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
)

FINDING_ID_VERSION = "research-finding-sha256-v1"
HYPOTHESIS_ID_VERSION = "research-hypothesis-sha256-v1"
EXPERIMENT_ID_VERSION = "experiment-manifest-sha256-v1"
FINDING_POLICY_ID_VERSION = "finding-policy-sha256-v1"
LIFECYCLE_EVENT_ID_VERSION = "research-lifecycle-event-sha256-v1"


def _mutation_payload(spec: ComponentMutationSpec) -> dict[str, Any]:
    return {
        "component": spec.component,
        "parameter": spec.parameter,
        "baseline_ref": spec.baseline_ref,
        "candidate_ref": spec.candidate_ref,
        "mutation_kind": spec.mutation_kind,
        "details": spec.details,
    }


def _metric_observation_payload(obs: MetricObservation) -> dict[str, Any]:
    return {
        "metric_name": obs.metric_name,
        "value": obs.value,
        "sample_count": obs.sample_count,
        "baseline_value": obs.baseline_value,
        "delta": obs.delta,
    }


def _footprint_payload(fp: ResearchKnowledgeFootprint) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "evaluation_report_ids": list(fp.evaluation_report_ids),
        "evaluation_spec_ids": list(fp.evaluation_spec_ids),
        "cohort_fingerprints": list(fp.cohort_fingerprints),
        "slice_keys": list(fp.slice_keys),
        "comparison_keys": list(fp.comparison_keys),
    }
    if fp.decision_start_ns is not None:
        payload["decision_start_ns"] = fp.decision_start_ns
    if fp.decision_end_ns is not None:
        payload["decision_end_ns"] = fp.decision_end_ns
    if fp.mode is not None:
        payload["mode"] = fp.mode
    if fp.scenario_id is not None:
        payload["scenario_id"] = fp.scenario_id
    if fp.evidence_tier is not None:
        payload["evidence_tier"] = fp.evidence_tier.value
    return payload


def derive_finding_id(finding: ResearchFindingV1) -> str:
    payload = {
        "identity_version": FINDING_ID_VERSION,
        "finding_type": finding.finding_type.value,
        "evaluation_report_id": finding.evaluation_report_id,
        "evaluation_spec_id": finding.evaluation_spec_id,
        "cohort_fingerprint": finding.cohort_fingerprint,
        "slice_dimension": finding.slice_dimension,
        "slice_value": finding.slice_value,
        "comparison_key": finding.comparison_key,
        "mode": finding.mode,
        "scenario_id": finding.scenario_id,
        "evidence_tier": finding.evidence_tier.value,
        "finding_policy_id": finding.finding_policy_id,
        "metric_observations": [
            _metric_observation_payload(obs) for obs in finding.metric_observations
        ],
        "observation_summary": finding.observation_summary,
    }
    return f"RFND-{sha256_bytes(canonical_bytes(payload))}"


def derive_hypothesis_id(hypothesis: ResearchHypothesisV1) -> str:
    payload = {
        "identity_version": HYPOTHESIS_ID_VERSION,
        "title": hypothesis.title,
        "hypothesis_kind": hypothesis.hypothesis_kind.value,
        "source_finding_ids": sorted(hypothesis.source_finding_ids),
        "claim": hypothesis.claim,
        "mechanism": hypothesis.mechanism,
        "treatment": _mutation_payload(hypothesis.treatment),
        "control": _mutation_payload(hypothesis.control),
        "primary_metric": hypothesis.primary_metric,
        "secondary_metrics": sorted(hypothesis.secondary_metrics),
        "expected_direction": hypothesis.expected_direction,
        "falsification": {
            "description": hypothesis.falsification.description,
            "metric_name": hypothesis.falsification.metric_name,
            "failure_condition": hypothesis.falsification.failure_condition,
        },
        "target_kind": hypothesis.target_kind,
        "horizon_ns": hypothesis.horizon_ns,
        "mode": hypothesis.mode,
        "scenario_id": hypothesis.scenario_id,
        "knowledge_footprint": _footprint_payload(hypothesis.knowledge_footprint),
    }
    return f"RHYP-{sha256_bytes(canonical_bytes(payload))}"


def _data_spec_payload(spec: DataSpecification) -> dict[str, Any]:
    return {
        "target_kind": spec.target_kind,
        "horizon_ns": spec.horizon_ns,
        "mode": spec.mode,
        "decision_start_ns": spec.decision_start_ns,
        "decision_end_ns": spec.decision_end_ns,
        "scenario_id": spec.scenario_id,
        "instrument_ids": sorted(spec.instrument_ids),
        "quality_requirements": sorted(spec.quality_requirements),
        "feature_schema_fingerprint": spec.feature_schema_fingerprint,
    }


def _metric_plan_payload(plan: MetricPlan) -> dict[str, Any]:
    return {
        "primary_metric": plan.primary_metric,
        "secondary_metrics": sorted(plan.secondary_metrics),
        "guardrails": sorted(plan.guardrails),
        "expected_direction": plan.expected_direction,
    }


def _validation_payload(req: ValidationRequirements) -> dict[str, Any]:
    return {
        "requires_walk_forward": req.requires_walk_forward,
        "requires_purge": req.requires_purge,
        "requires_embargo": req.requires_embargo,
        "requires_locked_holdout": req.requires_locked_holdout,
        "validation_policy_ref": req.validation_policy_ref,
    }


def _search_space_payload(space: SearchSpaceSpec | None) -> dict[str, Any] | None:
    if space is None:
        return None
    return {
        "parameters": {
            key: list(values) for key, values in sorted(space.parameters.items())
        }
    }


def _seed_policy_payload(policy: SeedPolicy | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "fixed_seeds": list(policy.fixed_seeds),
        "derivation_algorithm": policy.derivation_algorithm,
    }


def derive_experiment_id(manifest: ExperimentManifestV1) -> str:
    payload = {
        "identity_version": EXPERIMENT_ID_VERSION,
        "research_hypothesis_id": manifest.research_hypothesis_id,
        "experiment_kind": manifest.experiment_kind.value,
        "treatment": _mutation_payload(manifest.treatment),
        "control": _mutation_payload(manifest.control),
        "data_spec": _data_spec_payload(manifest.data_spec),
        "metric_plan": _metric_plan_payload(manifest.metric_plan),
        "success_criteria": manifest.success_criteria,
        "falsification": {
            "description": manifest.falsification.description,
            "metric_name": manifest.falsification.metric_name,
            "failure_condition": manifest.falsification.failure_condition,
        },
        "knowledge_footprint": _footprint_payload(manifest.knowledge_footprint),
        "validation_requirements": _validation_payload(manifest.validation_requirements),
        "search_space": _search_space_payload(manifest.search_space),
        "seed_policy": _seed_policy_payload(manifest.seed_policy),
        "complexity_budget": manifest.complexity_budget.value,
        "resource_budget": (
            {
                "max_training_runs": manifest.resource_budget.max_training_runs,
                "max_candidates": manifest.resource_budget.max_candidates,
                "max_gpu_hours": manifest.resource_budget.max_gpu_hours,
            }
            if manifest.resource_budget is not None
            else None
        ),
        "allowed_changes": sorted(manifest.allowed_changes),
        "forbidden_changes": sorted(manifest.forbidden_changes),
        "evaluation_spec_id": manifest.evaluation_spec_id,
        "implementation_version": manifest.implementation_version,
    }
    return f"EXP-{sha256_bytes(canonical_bytes(payload))}"


def derive_finding_policy_id(
    *,
    policy_name: str,
    thresholds: dict[str, Any],
    implementation_version: str,
) -> str:
    payload = {
        "identity_version": FINDING_POLICY_ID_VERSION,
        "policy_name": policy_name,
        "thresholds": thresholds,
        "implementation_version": implementation_version,
    }
    return f"RFPL-{sha256_bytes(canonical_bytes(payload))}"


def derive_lifecycle_event_id(
    *,
    entity_kind: str,
    entity_id: str,
    lifecycle_state: str,
    recorded_at_ns: int,
) -> str:
    payload = {
        "identity_version": LIFECYCLE_EVENT_ID_VERSION,
        "entity_kind": entity_kind,
        "entity_id": entity_id,
        "lifecycle_state": lifecycle_state,
        "recorded_at_ns": recorded_at_ns,
    }
    return f"RLCE-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "derive_experiment_id",
    "derive_finding_id",
    "derive_finding_policy_id",
    "derive_hypothesis_id",
    "derive_lifecycle_event_id",
]
