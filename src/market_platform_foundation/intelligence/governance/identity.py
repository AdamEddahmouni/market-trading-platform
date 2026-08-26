"""Deterministic governance identities (BUILD 23)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..promotion.identity import champion_scope_identity_payload
from .types import (
    DriftPolicyV1,
    FailSafePolicyV1,
    FeatureReferenceDistributionV1,
    MonitoringWindowV1,
    RollbackPolicyV1,
    RuntimeActivationPolicyV1,
    RuntimeActivationV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def monitoring_window_identity_payload(window: MonitoringWindowV1) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "start_ns": window.start_ns,
        "end_ns": window.end_ns,
        "evaluation_as_of_ns": window.evaluation_as_of_ns,
        "mode": window.mode,
        "scenario_id": window.scenario_id,
    }
    if window.scope is not None:
        payload["scope"] = champion_scope_identity_payload(window.scope)
    return payload


def activation_policy_identity_payload(policy: RuntimeActivationPolicyV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
        "allowed_execution_modes": list(policy.allowed_execution_modes),
        "allowed_data_modes": list(policy.allowed_data_modes),
        "require_champion_assignment": policy.require_champion_assignment,
        "require_artifact_integrity": policy.require_artifact_integrity,
        "require_validation_lineage": policy.require_validation_lineage,
        "require_promotion_lineage": policy.require_promotion_lineage,
        "require_provider_health": policy.require_provider_health,
        "require_quality_health": policy.require_quality_health,
        "require_runtime_dependencies": policy.require_runtime_dependencies,
        "max_activation_age_ns": policy.max_activation_age_ns,
        "paper_execution_only": policy.paper_execution_only,
        "live_execution_forbidden": policy.live_execution_forbidden,
        "implementation_version": policy.implementation_version,
    }


def derive_activation_policy_id(policy: RuntimeActivationPolicyV1) -> str:
    return _sha256_prefix("ACTPOL", activation_policy_identity_payload(policy))


def runtime_activation_identity_payload(activation: RuntimeActivationV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(activation.champion_scope),
        "champion_assignment_id": activation.champion_assignment_id,
        "candidate_id": activation.candidate_id,
        "candidate_artifact_hash": activation.candidate_artifact_hash,
        "promotion_decision_id": activation.promotion_decision_id,
        "activation_policy_id": activation.activation_policy_id,
        "effective_from_ns": activation.effective_from_ns,
        "effective_until_ns": activation.effective_until_ns,
        "execution_mode": activation.execution_mode,
        "data_mode": activation.data_mode,
        "execution_authority": activation.execution_authority.value,
        "previous_activation_id": activation.previous_activation_id,
        "status": activation.status.value,
    }


def derive_runtime_activation_id(activation: RuntimeActivationV1) -> str:
    return _sha256_prefix("RTACT", runtime_activation_identity_payload(activation))


def drift_policy_identity_payload(policy: DriftPolicyV1) -> dict[str, Any]:
    return {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
        "minimum_sample": policy.minimum_sample,
        "schema_mismatch_action": policy.schema_mismatch_action.value,
        "feature_missingness_threshold": policy.feature_missingness_threshold,
        "feature_mean_shift_threshold": policy.feature_mean_shift_threshold,
        "feature_quantile_threshold": policy.feature_quantile_threshold,
        "forecast_distribution_threshold": policy.forecast_distribution_threshold,
        "performance_metric": policy.performance_metric,
        "performance_degradation_threshold": policy.performance_degradation_threshold,
        "calibration_ece_threshold": policy.calibration_ece_threshold,
        "ood_fraction_threshold": policy.ood_fraction_threshold,
        "provider_staleness_threshold_ns": policy.provider_staleness_threshold_ns,
        "quality_fail_closed_rate_threshold": policy.quality_fail_closed_rate_threshold,
        "risk_fail_closed_rate_threshold": policy.risk_fail_closed_rate_threshold,
        "actions_by_severity": dict(sorted(policy.actions_by_severity.items())),
        "implementation_version": policy.implementation_version,
    }


def derive_drift_policy_id(policy: DriftPolicyV1) -> str:
    return _sha256_prefix("DRFPOL", drift_policy_identity_payload(policy))


def derive_drift_assessment_id(
    *,
    policy_id: str,
    window: MonitoringWindowV1,
    reference_id: str | None,
) -> str:
    payload = {
        "policy_id": policy_id,
        "window": monitoring_window_identity_payload(window),
        "reference_id": reference_id,
    }
    return _sha256_prefix("DRFASM", payload)


def derive_fail_safe_policy_id(policy: FailSafePolicyV1) -> str:
    payload = {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
        "runtime_mismatch_action": policy.runtime_mismatch_action.value,
        "provider_critical_action": policy.provider_critical_action.value,
        "schema_drift_action": policy.schema_drift_action.value,
        "quality_fail_closed_action": policy.quality_fail_closed_action.value,
        "risk_subsystem_action": policy.risk_subsystem_action.value,
        "artifact_integrity_action": policy.artifact_integrity_action.value,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("FSPOL", payload)


def derive_fail_safe_decision_id(
    *,
    policy_id: str,
    decision_time_ns: int,
    decision: str,
    trigger_key: str,
) -> str:
    payload = {
        "policy_id": policy_id,
        "decision_time_ns": decision_time_ns,
        "decision": decision,
        "trigger_key": trigger_key,
    }
    return _sha256_prefix("FSDEC", payload)


def derive_rollback_policy_id(policy: RollbackPolicyV1) -> str:
    payload = {
        "champion_scope": champion_scope_identity_payload(policy.champion_scope),
        "allowed_trigger_types": [t.value for t in policy.allowed_trigger_types],
        "minimum_trigger_severity": policy.minimum_trigger_severity.value,
        "require_previous_known_good": policy.require_previous_known_good,
        "require_artifact_integrity": policy.require_artifact_integrity,
        "cooldown_ns": policy.cooldown_ns,
        "consecutive_failure_threshold": policy.consecutive_failure_threshold,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("RBKPOL", payload)


def derive_rollback_decision_id(
    *,
    policy_id: str,
    current_activation_id: str,
    target_activation_id: str | None,
    decision: str,
    effective_time_ns: int,
) -> str:
    payload = {
        "policy_id": policy_id,
        "current_activation_id": current_activation_id,
        "target_activation_id": target_activation_id,
        "decision": decision,
        "effective_time_ns": effective_time_ns,
    }
    return _sha256_prefix("RBKDEC", payload)


def derive_governance_alert_id(
    *,
    champion_scope: dict[str, Any],
    alert_type: str,
    observed_at_ns: int,
    severity: str,
    source_key: str,
) -> str:
    payload = {
        "champion_scope": champion_scope,
        "alert_type": alert_type,
        "observed_at_ns": observed_at_ns,
        "severity": severity,
        "source_key": source_key,
    }
    return _sha256_prefix("GOVALT", payload)


def derive_governance_event_id(
    *,
    event_type: str,
    champion_scope: dict[str, Any],
    effective_at_ns: int,
    source_key: str,
) -> str:
    payload = {
        "event_type": event_type,
        "champion_scope": champion_scope,
        "effective_at_ns": effective_at_ns,
        "source_key": source_key,
    }
    return _sha256_prefix("GOVEVT", payload)


def derive_health_snapshot_id(*, kind: str, window: MonitoringWindowV1, context_key: str) -> str:
    payload = {
        "kind": kind,
        "window": monitoring_window_identity_payload(window),
        "context_key": context_key,
    }
    return _sha256_prefix("HLTHSN", payload)


def derive_feature_reference_id(reference: FeatureReferenceDistributionV1) -> str:
    payload = {
        "feature_schema_fingerprint": reference.feature_schema_fingerprint,
        "feature_means": dict(sorted(reference.feature_means.items())),
        "feature_stds": dict(sorted(reference.feature_stds.items())),
        "feature_missingness_rates": dict(sorted(reference.feature_missingness_rates.items())),
        "sample_count": reference.sample_count,
    }
    return _sha256_prefix("FEATREF", payload)


def derive_research_trigger_id(
    *,
    champion_scope: dict[str, Any],
    window: MonitoringWindowV1,
    drift_assessment_ids: tuple[str, ...],
) -> str:
    payload = {
        "champion_scope": champion_scope,
        "window": monitoring_window_identity_payload(window),
        "drift_assessment_ids": list(drift_assessment_ids),
    }
    return _sha256_prefix("RSRTRG", payload)
