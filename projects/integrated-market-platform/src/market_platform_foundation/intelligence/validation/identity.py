"""Deterministic validation identities (BUILD 19)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    HoldoutCommitmentV1,
    HoldoutSpec,
    StatisticalPlan,
    TemporalKnowledgePolicyV1,
    ValidationPlanV1,
    WalkForwardSpec,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def walk_forward_identity_payload(spec: WalkForwardSpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {
        "mode": spec.mode.value,
        "fold_boundaries_ns": list(spec.fold_boundaries_ns),
        "fold_candidate_ids": list(spec.fold_candidate_ids),
    }


def holdout_identity_payload(spec: HoldoutSpec) -> dict[str, Any]:
    return {
        "holdout_start_ns": spec.holdout_start_ns,
        "holdout_end_ns": spec.holdout_end_ns,
        "selector_ref": spec.selector_ref,
    }


def statistical_plan_identity_payload(plan: StatisticalPlan) -> dict[str, Any]:
    return {
        "block_length": plan.block_length,
        "replicate_count": plan.replicate_count,
        "seed": plan.seed,
        "confidence_level": plan.confidence_level,
        "minimum_paired_sample": plan.minimum_paired_sample,
        "criterion_upper_ci_bound_lt_zero": plan.criterion_upper_ci_bound_lt_zero,
    }


def knowledge_policy_identity_payload(policy: TemporalKnowledgePolicyV1) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "network_policy": policy.network_policy.value,
        "require_declared_model_cutoff": policy.require_declared_model_cutoff,
        "reject_prompt_only_time_travel": policy.reject_prompt_only_time_travel,
        "allow_synthetic_test_teachers": policy.allow_synthetic_test_teachers,
    }


def validation_plan_identity_payload(plan: ValidationPlanV1) -> dict[str, Any]:
    return {
        "experiment_id": plan.experiment_id,
        "candidate_ids": list(plan.candidate_ids),
        "candidate_artifact_hashes": list(plan.candidate_artifact_hashes),
        "control_ref": plan.control_ref,
        "target_kind": plan.target_kind,
        "horizon_ns": plan.horizon_ns,
        "mode": plan.mode,
        "scenario_id": plan.scenario_id,
        "validation_method": plan.validation_method,
        "walk_forward_spec": walk_forward_identity_payload(plan.walk_forward_spec),
        "purge_ns": plan.purge_ns,
        "embargo_ns": plan.embargo_ns,
        "holdout_spec": holdout_identity_payload(plan.holdout_spec),
        "primary_metric": plan.primary_metric,
        "guardrail_metrics": list(plan.guardrail_metrics),
        "statistical_plan": statistical_plan_identity_payload(plan.statistical_plan),
        "temporal_knowledge_policy": knowledge_policy_identity_payload(plan.temporal_knowledge_policy),
        "minimum_paired_sample": plan.minimum_paired_sample,
        "implementation_version": plan.implementation_version,
    }


def derive_validation_plan_id(plan: ValidationPlanV1) -> str:
    return _sha256_prefix("VALPLAN", validation_plan_identity_payload(plan))


def derive_holdout_commitment_id(commitment: HoldoutCommitmentV1) -> str:
    payload = {
        "validation_plan_id": commitment.validation_plan_id,
        "experiment_id": commitment.experiment_id,
        "candidate_ids": list(commitment.candidate_ids),
        "candidate_artifact_hashes": list(commitment.candidate_artifact_hashes),
        "control_ref": commitment.control_ref,
        "holdout_spec": holdout_identity_payload(commitment.holdout_spec),
        "primary_metric": commitment.primary_metric,
        "guardrail_metrics": list(commitment.guardrail_metrics),
        "statistical_plan": statistical_plan_identity_payload(commitment.statistical_plan),
        "temporal_knowledge_policy_id": commitment.temporal_knowledge_policy_id,
        "implementation_version": commitment.implementation_version,
    }
    return _sha256_prefix("HOLD", payload)


def derive_validation_dataset_fingerprint(
    *,
    validation_plan_id: str,
    fold_or_holdout_ref: str,
    forecast_ids: tuple[str, ...],
    outcome_ids: tuple[str, ...],
    decision_start_ns: int,
    decision_end_ns: int,
) -> str:
    payload = {
        "validation_plan_id": validation_plan_id,
        "fold_or_holdout_ref": fold_or_holdout_ref,
        "forecast_ids": sorted(forecast_ids),
        "outcome_ids": sorted(outcome_ids),
        "decision_start_ns": decision_start_ns,
        "decision_end_ns": decision_end_ns,
    }
    return _sha256_prefix("VALDS", payload)


def derive_contamination_record_id(
    *,
    validation_plan_id: str,
    contamination_type: str,
    source_ref: str | None,
    affected_decision_start_ns: int | None,
    affected_decision_end_ns: int | None,
) -> str:
    payload = {
        "validation_plan_id": validation_plan_id,
        "contamination_type": contamination_type,
        "source_ref": source_ref,
        "affected_decision_start_ns": affected_decision_start_ns,
        "affected_decision_end_ns": affected_decision_end_ns,
    }
    return _sha256_prefix("CONTAM", payload)


def derive_validation_report_id(
    *,
    validation_plan_id: str,
    candidate_artifact_hashes: tuple[str, ...],
    control_ref: str,
    holdout_commitment_id: str,
    validation_dataset_fingerprints: tuple[str, ...],
    knowledge_assessment_status: str,
    contamination_disposition: str,
    implementation_version: str,
) -> str:
    payload = {
        "validation_plan_id": validation_plan_id,
        "candidate_artifact_hashes": list(candidate_artifact_hashes),
        "control_ref": control_ref,
        "holdout_commitment_id": holdout_commitment_id,
        "validation_dataset_fingerprints": list(validation_dataset_fingerprints),
        "knowledge_assessment_status": knowledge_assessment_status,
        "contamination_disposition": contamination_disposition,
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("VALRPT", payload)


__all__ = [
    "derive_contamination_record_id",
    "derive_holdout_commitment_id",
    "derive_validation_dataset_fingerprint",
    "derive_validation_plan_id",
    "derive_validation_report_id",
    "validation_plan_identity_payload",
]
