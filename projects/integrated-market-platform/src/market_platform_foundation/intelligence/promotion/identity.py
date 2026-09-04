"""Deterministic promotion governance identities (BUILD 20)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    ChampionScopeV1,
    ComplexityPolicy,
    GuardrailRule,
    PromotionPolicyV1,
    ShadowEvidenceManifestV1,
    ShadowMatchedObservation,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def champion_scope_identity_payload(scope: ChampionScopeV1) -> dict[str, Any]:
    return {
        "component": scope.component,
        "target_kind": scope.target_kind,
        "horizon_ns": scope.horizon_ns,
        "mode": scope.mode,
        "scenario_id": scope.scenario_id,
    }


def derive_champion_scope_id(scope: ChampionScopeV1) -> str:
    return _sha256_prefix("CHSCOPE", champion_scope_identity_payload(scope))


def guardrail_rule_identity_payload(rule: GuardrailRule) -> dict[str, Any]:
    return {
        "metric_name": rule.metric_name,
        "direction": rule.direction.value,
        "max_regression": rule.max_regression,
        "max_absolute": rule.max_absolute,
    }


def complexity_policy_identity_payload(policy: ComplexityPolicy) -> dict[str, Any]:
    return {
        "kind": policy.kind.value,
        "base_required_improvement": policy.base_required_improvement,
        "minor_complexity_additional_margin": policy.minor_complexity_additional_margin,
        "major_complexity_additional_margin": policy.major_complexity_additional_margin,
    }


def promotion_policy_identity_payload(policy: PromotionPolicyV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
        "required_validation_dispositions": [d.value for d in policy.required_validation_dispositions],
        "require_clean_contamination": policy.require_clean_contamination,
        "require_temporal_knowledge_pass": policy.require_temporal_knowledge_pass,
        "require_artifact_integrity": policy.require_artifact_integrity,
        "primary_metric": policy.primary_metric,
        "primary_metric_direction": policy.primary_metric_direction.value,
        "required_improvement": policy.required_improvement,
        "secondary_metrics": list(policy.secondary_metrics),
        "guardrails": [guardrail_rule_identity_payload(g) for g in policy.guardrails],
        "minimum_walk_forward_folds": policy.minimum_walk_forward_folds,
        "minimum_holdout_samples": policy.minimum_holdout_samples,
        "minimum_shadow_samples": policy.minimum_shadow_samples,
        "minimum_shadow_duration_ns": policy.minimum_shadow_duration_ns,
        "require_locked_holdout": policy.require_locked_holdout,
        "require_shadow_evidence": policy.require_shadow_evidence,
        "require_forward_shadow_evidence": policy.require_forward_shadow_evidence,
        "allowed_shadow_evidence_tiers": [t.value for t in policy.allowed_shadow_evidence_tiers],
        "statistical_requirement": policy.statistical_requirement.value,
        "complexity_policy": complexity_policy_identity_payload(policy.complexity_policy),
        "allowed_validation_modes": list(policy.allowed_validation_modes),
        "implementation_version": policy.implementation_version,
    }


def derive_promotion_policy_id(policy: PromotionPolicyV1) -> str:
    return _sha256_prefix("PROMPOL", promotion_policy_identity_payload(policy))


def derive_eligibility_assessment_id(
    *,
    promotion_policy_id: str,
    candidate_id: str,
    candidate_artifact_hash: str,
    validation_report_id: str,
) -> str:
    payload = {
        "promotion_policy_id": promotion_policy_id,
        "candidate_id": candidate_id,
        "candidate_artifact_hash": candidate_artifact_hash,
        "validation_report_id": validation_report_id,
    }
    return _sha256_prefix("PROMELIG", payload)


def derive_challenger_registration_id(
    *,
    promotion_policy_id: str,
    candidate_id: str,
    candidate_artifact_hash: str,
    current_champion_assignment_id: str,
    champion_scope: ChampionScopeV1,
) -> str:
    payload = {
        "promotion_policy_id": promotion_policy_id,
        "candidate_id": candidate_id,
        "candidate_artifact_hash": candidate_artifact_hash,
        "current_champion_assignment_id": current_champion_assignment_id,
        "champion_scope": champion_scope_identity_payload(champion_scope),
    }
    return _sha256_prefix("CHREG", payload)


def shadow_observation_identity_payload(obs: ShadowMatchedObservation) -> dict[str, Any]:
    return {
        "opportunity_key": obs.opportunity_key,
        "decision_time_ns": obs.decision_time_ns,
        "champion_forecast_id": obs.champion_forecast_id,
        "challenger_forecast_id": obs.challenger_forecast_id,
        "outcome_id": obs.outcome_id,
        "settled": obs.settled,
        "champion_probability": obs.champion_probability,
        "challenger_probability": obs.challenger_probability,
        "binary_label": obs.binary_label,
    }


def shadow_evidence_identity_payload(manifest: ShadowEvidenceManifestV1) -> dict[str, Any]:
    observations = sorted(
        [shadow_observation_identity_payload(o) for o in manifest.matched_observations],
        key=lambda item: (item["opportunity_key"], item["decision_time_ns"]),
    )
    return {
        "challenger_registration_id": manifest.challenger_registration_id,
        "champion_assignment_id": manifest.champion_assignment_id,
        "promotion_policy_id": manifest.promotion_policy_id,
        "evidence_tier": manifest.evidence_tier.value,
        "decision_start_ns": manifest.decision_start_ns,
        "decision_end_ns": manifest.decision_end_ns,
        "matched_observations": observations,
        "unmatched_champion_count": manifest.unmatched_champion_count,
        "unmatched_challenger_count": manifest.unmatched_challenger_count,
        "settlement_complete": manifest.settlement_complete,
        "evaluation_report_ids": sorted(manifest.evaluation_report_ids),
        "implementation_version": manifest.implementation_version,
    }


def derive_shadow_evidence_id(manifest: ShadowEvidenceManifestV1) -> str:
    return _sha256_prefix("SHADOWEV", shadow_evidence_identity_payload(manifest))


def derive_promotion_decision_id(
    *,
    promotion_policy_id: str,
    current_champion_assignment_id: str,
    challenger_registration_id: str,
    candidate_artifact_hash: str,
    validation_report_ids: tuple[str, ...],
    shadow_evidence_id: str | None,
) -> str:
    payload = {
        "promotion_policy_id": promotion_policy_id,
        "current_champion_assignment_id": current_champion_assignment_id,
        "challenger_registration_id": challenger_registration_id,
        "candidate_artifact_hash": candidate_artifact_hash,
        "validation_report_ids": sorted(validation_report_ids),
        "shadow_evidence_id": shadow_evidence_id,
    }
    return _sha256_prefix("PROMDEC", payload)


def derive_champion_assignment_id(
    *,
    champion_scope: ChampionScopeV1,
    candidate_id: str,
    candidate_artifact_hash: str,
    promotion_decision_id: str | None,
    previous_assignment_id: str | None,
    effective_from_ns: int,
    assignment_reason: str,
) -> str:
    payload = {
        "champion_scope": champion_scope_identity_payload(champion_scope),
        "candidate_id": candidate_id,
        "candidate_artifact_hash": candidate_artifact_hash,
        "promotion_decision_id": promotion_decision_id,
        "previous_assignment_id": previous_assignment_id,
        "effective_from_ns": effective_from_ns,
        "assignment_reason": assignment_reason,
    }
    return _sha256_prefix("CHAMP", payload)


def derive_lifecycle_event_id(
    *,
    challenger_registration_id: str,
    to_state: str,
    effective_at_ns: int,
    reason_code: str | None,
) -> str:
    payload = {
        "challenger_registration_id": challenger_registration_id,
        "to_state": to_state,
        "effective_at_ns": effective_at_ns,
        "reason_code": reason_code,
    }
    return _sha256_prefix("CHLIFE", payload)


__all__ = [
    "champion_scope_identity_payload",
    "derive_challenger_registration_id",
    "derive_champion_assignment_id",
    "derive_champion_scope_id",
    "derive_eligibility_assessment_id",
    "derive_lifecycle_event_id",
    "derive_promotion_decision_id",
    "derive_promotion_policy_id",
    "derive_shadow_evidence_id",
    "promotion_policy_identity_payload",
    "shadow_evidence_identity_payload",
]
