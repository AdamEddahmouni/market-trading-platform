"""Governance serialization (BUILD 23)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..promotion.serialization import _scope_from_dict, _scope_to_dict
from .types import (
    ActivationStatus,
    DataQualityHealthSnapshotV1,
    DriftAssessmentV1,
    DriftPolicyV1,
    DriftSeverity,
    DriftType,
    ExecutionAuthority,
    ExecutionHealthSnapshotV1,
    FailSafeDecisionKind,
    FailSafeDecisionV1,
    FailSafePolicyV1,
    FeatureReferenceDistributionV1,
    GovernanceAction,
    GovernanceAlertV1,
    GovernanceEventType,
    GovernanceEventV1,
    GovernanceOverrideV1,
    GovernanceReasonCode,
    HealthState,
    IntelligenceHealthSnapshotV1,
    MonitoringWindowV1,
    OpportunityHealthSnapshotV1,
    OverrideAction,
    ProviderHealthSnapshotV1,
    RollbackDecisionKind,
    RollbackDecisionV1,
    RollbackPolicyV1,
    RuntimeActivationPolicyV1,
    RuntimeActivationV1,
    RuntimeHealthSnapshotV1,
)


def _enum_values(values: tuple) -> list[str]:
    return [v.value if hasattr(v, "value") else str(v) for v in values]


def _refs_to_dict(refs: tuple[ContractReference, ...]) -> list[dict[str, Any]]:
    return [{"kind": ref.kind, "id": ref.id, "schema_version": ref.schema_version} for ref in refs]


def _refs_from_dict(payload: list[dict[str, Any]] | None) -> tuple[ContractReference, ...]:
    if not payload:
        return ()
    return tuple(
        ContractReference(
            kind=str(row["kind"]),
            id=str(row["id"]),
            schema_version=str(row.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        )
        for row in payload
    )


def monitoring_window_v1_to_dict(window: MonitoringWindowV1) -> dict[str, Any]:
    return {
        "start_ns": window.start_ns,
        "end_ns": window.end_ns,
        "evaluation_as_of_ns": window.evaluation_as_of_ns,
        "scope": _scope_to_dict(window.scope) if window.scope is not None else None,
        "mode": window.mode,
        "scenario_id": window.scenario_id,
    }


def monitoring_window_v1_from_dict(payload: dict[str, Any]) -> MonitoringWindowV1:
    scope_payload = payload.get("scope")
    return MonitoringWindowV1(
        start_ns=int(payload["start_ns"]),
        end_ns=int(payload["end_ns"]),
        evaluation_as_of_ns=payload.get("evaluation_as_of_ns"),
        scope=_scope_from_dict(scope_payload) if scope_payload else None,
        mode=payload.get("mode"),
        scenario_id=payload.get("scenario_id"),
    )


def runtime_activation_policy_v1_to_dict(policy: RuntimeActivationPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "activation_policy_id": policy.activation_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
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
        "metadata": dict(policy.metadata),
    }


def runtime_activation_policy_v1_from_dict(payload: dict[str, Any]) -> RuntimeActivationPolicyV1:
    return RuntimeActivationPolicyV1(
        activation_policy_id=str(payload["activation_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        allowed_execution_modes=tuple(payload.get("allowed_execution_modes", ("PAPER",))),
        allowed_data_modes=tuple(payload.get("allowed_data_modes", ("ACTUAL_LIVE",))),
        require_champion_assignment=bool(payload.get("require_champion_assignment", True)),
        require_artifact_integrity=bool(payload.get("require_artifact_integrity", True)),
        require_validation_lineage=bool(payload.get("require_validation_lineage", False)),
        require_promotion_lineage=bool(payload.get("require_promotion_lineage", True)),
        require_provider_health=bool(payload.get("require_provider_health", True)),
        require_quality_health=bool(payload.get("require_quality_health", True)),
        require_runtime_dependencies=bool(payload.get("require_runtime_dependencies", True)),
        max_activation_age_ns=payload.get("max_activation_age_ns"),
        paper_execution_only=bool(payload.get("paper_execution_only", True)),
        live_execution_forbidden=bool(payload.get("live_execution_forbidden", True)),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def runtime_activation_v1_to_dict(activation: RuntimeActivationV1) -> dict[str, Any]:
    return {
        "schema_version": activation.schema_version,
        "activation_id": activation.activation_id,
        "champion_scope": _scope_to_dict(activation.champion_scope),
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
        "runtime_config_refs": _refs_to_dict(activation.runtime_config_refs),
        "previous_activation_id": activation.previous_activation_id,
        "status": activation.status.value,
        "lineage_refs": _refs_to_dict(activation.lineage_refs),
        "metadata": dict(activation.metadata),
    }


def runtime_activation_v1_from_dict(payload: dict[str, Any]) -> RuntimeActivationV1:
    return RuntimeActivationV1(
        activation_id=str(payload["activation_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        champion_assignment_id=str(payload["champion_assignment_id"]),
        candidate_id=str(payload["candidate_id"]),
        candidate_artifact_hash=str(payload["candidate_artifact_hash"]),
        promotion_decision_id=payload.get("promotion_decision_id"),
        activation_policy_id=str(payload["activation_policy_id"]),
        effective_from_ns=int(payload["effective_from_ns"]),
        effective_until_ns=payload.get("effective_until_ns"),
        execution_mode=str(payload.get("execution_mode", "PAPER")),
        data_mode=str(payload.get("data_mode", "ACTUAL_LIVE")),
        execution_authority=ExecutionAuthority(str(payload.get("execution_authority", ExecutionAuthority.PAPER_EXECUTION.value))),
        runtime_config_refs=_refs_from_dict(payload.get("runtime_config_refs")),
        previous_activation_id=payload.get("previous_activation_id"),
        status=ActivationStatus(str(payload.get("status", ActivationStatus.ACTIVE.value))),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )


def drift_policy_v1_to_dict(policy: DriftPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "drift_policy_id": policy.drift_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
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
        "actions_by_severity": dict(policy.actions_by_severity),
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def drift_policy_v1_from_dict(payload: dict[str, Any]) -> DriftPolicyV1:
    return DriftPolicyV1(
        drift_policy_id=str(payload["drift_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        minimum_sample=int(payload.get("minimum_sample", 10)),
        schema_mismatch_action=GovernanceAction(str(payload.get("schema_mismatch_action", GovernanceAction.DISABLE_SCOPE.value))),
        feature_missingness_threshold=float(payload.get("feature_missingness_threshold", 0.10)),
        feature_mean_shift_threshold=float(payload.get("feature_mean_shift_threshold", 2.0)),
        feature_quantile_threshold=float(payload.get("feature_quantile_threshold", 0.25)),
        forecast_distribution_threshold=float(payload.get("forecast_distribution_threshold", 0.15)),
        performance_metric=str(payload.get("performance_metric", "brier")),
        performance_degradation_threshold=float(payload.get("performance_degradation_threshold", 0.05)),
        calibration_ece_threshold=float(payload.get("calibration_ece_threshold", 0.10)),
        ood_fraction_threshold=float(payload.get("ood_fraction_threshold", 0.20)),
        provider_staleness_threshold_ns=int(payload.get("provider_staleness_threshold_ns", 60_000_000_000)),
        quality_fail_closed_rate_threshold=float(payload.get("quality_fail_closed_rate_threshold", 0.10)),
        risk_fail_closed_rate_threshold=float(payload.get("risk_fail_closed_rate_threshold", 0.10)),
        actions_by_severity=dict(payload.get("actions_by_severity", {})),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def drift_assessment_v1_to_dict(assessment: DriftAssessmentV1) -> dict[str, Any]:
    return {
        "schema_version": assessment.schema_version,
        "drift_assessment_id": assessment.drift_assessment_id,
        "policy_id": assessment.policy_id,
        "window": monitoring_window_v1_to_dict(assessment.window),
        "reference_id": assessment.reference_id,
        "metric_observations": dict(assessment.metric_observations),
        "sample_counts": dict(assessment.sample_counts),
        "severity": assessment.severity.value,
        "drift_types": _enum_values(assessment.drift_types),
        "reason_codes": _enum_values(assessment.reason_codes),
        "recommended_action": assessment.recommended_action.value,
        "lineage_refs": _refs_to_dict(assessment.lineage_refs),
        "metadata": dict(assessment.metadata),
    }


def drift_assessment_v1_from_dict(payload: dict[str, Any]) -> DriftAssessmentV1:
    return DriftAssessmentV1(
        drift_assessment_id=str(payload["drift_assessment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        policy_id=str(payload["policy_id"]),
        window=monitoring_window_v1_from_dict(payload["window"]),
        reference_id=payload.get("reference_id"),
        metric_observations=dict(payload.get("metric_observations", {})),
        sample_counts={k: int(v) for k, v in payload.get("sample_counts", {}).items()},
        severity=DriftSeverity(str(payload.get("severity", DriftSeverity.UNKNOWN.value))),
        drift_types=tuple(DriftType(v) for v in payload.get("drift_types", [])),
        reason_codes=tuple(GovernanceReasonCode(v) for v in payload.get("reason_codes", [])),
        recommended_action=GovernanceAction(str(payload.get("recommended_action", GovernanceAction.ALLOW.value))),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )


def fail_safe_policy_v1_to_dict(policy: FailSafePolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "fail_safe_policy_id": policy.fail_safe_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
        "runtime_mismatch_action": policy.runtime_mismatch_action.value,
        "provider_critical_action": policy.provider_critical_action.value,
        "schema_drift_action": policy.schema_drift_action.value,
        "quality_fail_closed_action": policy.quality_fail_closed_action.value,
        "risk_subsystem_action": policy.risk_subsystem_action.value,
        "artifact_integrity_action": policy.artifact_integrity_action.value,
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def fail_safe_policy_v1_from_dict(payload: dict[str, Any]) -> FailSafePolicyV1:
    return FailSafePolicyV1(
        fail_safe_policy_id=str(payload["fail_safe_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        runtime_mismatch_action=FailSafeDecisionKind(str(payload.get("runtime_mismatch_action", FailSafeDecisionKind.DISABLE_SCOPE.value))),
        provider_critical_action=FailSafeDecisionKind(str(payload.get("provider_critical_action", FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES.value))),
        schema_drift_action=FailSafeDecisionKind(str(payload.get("schema_drift_action", FailSafeDecisionKind.DISABLE_SCOPE.value))),
        quality_fail_closed_action=FailSafeDecisionKind(str(payload.get("quality_fail_closed_action", FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES.value))),
        risk_subsystem_action=FailSafeDecisionKind(str(payload.get("risk_subsystem_action", FailSafeDecisionKind.DISABLE_NEW_PAPER_ORDERS.value))),
        artifact_integrity_action=FailSafeDecisionKind(str(payload.get("artifact_integrity_action", FailSafeDecisionKind.FAIL_CLOSED.value))),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def fail_safe_decision_v1_to_dict(decision: FailSafeDecisionV1) -> dict[str, Any]:
    return {
        "schema_version": decision.schema_version,
        "decision_id": decision.decision_id,
        "policy_id": decision.policy_id,
        "champion_scope": _scope_to_dict(decision.champion_scope),
        "decision_time_ns": decision.decision_time_ns,
        "decision": decision.decision.value,
        "trigger_refs": _refs_to_dict(decision.trigger_refs),
        "reason_codes": _enum_values(decision.reason_codes),
        "lineage_refs": _refs_to_dict(decision.lineage_refs),
        "metadata": dict(decision.metadata),
    }


def fail_safe_decision_v1_from_dict(payload: dict[str, Any]) -> FailSafeDecisionV1:
    return FailSafeDecisionV1(
        decision_id=str(payload["decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        policy_id=str(payload["policy_id"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        decision=FailSafeDecisionKind(str(payload["decision"])),
        trigger_refs=_refs_from_dict(payload.get("trigger_refs")),
        reason_codes=tuple(GovernanceReasonCode(v) for v in payload.get("reason_codes", [])),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )


def rollback_policy_v1_to_dict(policy: RollbackPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "rollback_policy_id": policy.rollback_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
        "allowed_trigger_types": _enum_values(policy.allowed_trigger_types),
        "minimum_trigger_severity": policy.minimum_trigger_severity.value,
        "require_previous_known_good": policy.require_previous_known_good,
        "require_artifact_integrity": policy.require_artifact_integrity,
        "cooldown_ns": policy.cooldown_ns,
        "consecutive_failure_threshold": policy.consecutive_failure_threshold,
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def rollback_policy_v1_from_dict(payload: dict[str, Any]) -> RollbackPolicyV1:
    return RollbackPolicyV1(
        rollback_policy_id=str(payload["rollback_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        allowed_trigger_types=tuple(DriftType(v) for v in payload.get("allowed_trigger_types", [])),
        minimum_trigger_severity=DriftSeverity(str(payload.get("minimum_trigger_severity", DriftSeverity.CRITICAL.value))),
        require_previous_known_good=bool(payload.get("require_previous_known_good", True)),
        require_artifact_integrity=bool(payload.get("require_artifact_integrity", True)),
        cooldown_ns=int(payload.get("cooldown_ns", 0)),
        consecutive_failure_threshold=int(payload.get("consecutive_failure_threshold", 1)),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def rollback_decision_v1_to_dict(decision: RollbackDecisionV1) -> dict[str, Any]:
    return {
        "schema_version": decision.schema_version,
        "rollback_decision_id": decision.rollback_decision_id,
        "policy_id": decision.policy_id,
        "current_activation_id": decision.current_activation_id,
        "target_activation_id": decision.target_activation_id,
        "trigger_refs": _refs_to_dict(decision.trigger_refs),
        "decision": decision.decision.value,
        "reason_codes": _enum_values(decision.reason_codes),
        "effective_time_ns": decision.effective_time_ns,
        "lineage_refs": _refs_to_dict(decision.lineage_refs),
        "metadata": dict(decision.metadata),
    }


def rollback_decision_v1_from_dict(payload: dict[str, Any]) -> RollbackDecisionV1:
    return RollbackDecisionV1(
        rollback_decision_id=str(payload["rollback_decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        policy_id=str(payload["policy_id"]),
        current_activation_id=str(payload["current_activation_id"]),
        target_activation_id=payload.get("target_activation_id"),
        trigger_refs=_refs_from_dict(payload.get("trigger_refs")),
        decision=RollbackDecisionKind(str(payload["decision"])),
        reason_codes=tuple(GovernanceReasonCode(v) for v in payload.get("reason_codes", [])),
        effective_time_ns=int(payload.get("effective_time_ns", 0)),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )


def governance_alert_v1_to_dict(alert: GovernanceAlertV1) -> dict[str, Any]:
    return {
        "schema_version": alert.schema_version,
        "alert_id": alert.alert_id,
        "champion_scope": _scope_to_dict(alert.champion_scope),
        "severity": alert.severity.value,
        "alert_type": alert.alert_type,
        "source_refs": _refs_to_dict(alert.source_refs),
        "observed_at_ns": alert.observed_at_ns,
        "recommended_action": alert.recommended_action.value,
        "reason_codes": _enum_values(alert.reason_codes),
        "lineage_refs": _refs_to_dict(alert.lineage_refs),
        "metadata": dict(alert.metadata),
    }


def governance_alert_v1_from_dict(payload: dict[str, Any]) -> GovernanceAlertV1:
    return GovernanceAlertV1(
        alert_id=str(payload["alert_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        severity=DriftSeverity(str(payload["severity"])),
        alert_type=str(payload["alert_type"]),
        source_refs=_refs_from_dict(payload.get("source_refs")),
        observed_at_ns=int(payload["observed_at_ns"]),
        recommended_action=GovernanceAction(str(payload["recommended_action"])),
        reason_codes=tuple(GovernanceReasonCode(v) for v in payload.get("reason_codes", [])),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )


def governance_event_v1_to_dict(event: GovernanceEventV1) -> dict[str, Any]:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "champion_scope": _scope_to_dict(event.champion_scope),
        "effective_at_ns": event.effective_at_ns,
        "source_refs": _refs_to_dict(event.source_refs),
        "reason_codes": _enum_values(event.reason_codes),
        "lineage_refs": _refs_to_dict(event.lineage_refs),
        "metadata": dict(event.metadata),
    }


def governance_event_v1_from_dict(payload: dict[str, Any]) -> GovernanceEventV1:
    return GovernanceEventV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        event_type=GovernanceEventType(str(payload["event_type"])),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        effective_at_ns=int(payload["effective_at_ns"]),
        source_refs=_refs_from_dict(payload.get("source_refs")),
        reason_codes=tuple(GovernanceReasonCode(v) for v in payload.get("reason_codes", [])),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        metadata=dict(payload.get("metadata", {})),
    )
