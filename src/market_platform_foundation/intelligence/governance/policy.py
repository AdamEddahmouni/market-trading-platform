"""Policy builders for runtime governance (BUILD 23)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..promotion.types import ChampionScopeV1
from .identity import (
    derive_activation_policy_id,
    derive_drift_policy_id,
    derive_fail_safe_policy_id,
    derive_rollback_policy_id,
)
from .types import (
    DriftPolicyV1,
    DriftSeverity,
    DriftType,
    FailSafeDecisionKind,
    FailSafePolicyV1,
    GOVERNANCE_IMPLEMENTATION_VERSION,
    GovernanceAction,
    RollbackPolicyV1,
    RuntimeActivationPolicyV1,
)


def build_activation_policy(
    *,
    champion_scope: ChampionScopeV1,
    require_promotion_lineage: bool = True,
    require_artifact_integrity: bool = True,
    **kwargs,
) -> RuntimeActivationPolicyV1:
    body = RuntimeActivationPolicyV1(
        activation_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        require_promotion_lineage=require_promotion_lineage,
        require_artifact_integrity=require_artifact_integrity,
        implementation_version=kwargs.pop("implementation_version", GOVERNANCE_IMPLEMENTATION_VERSION),
        **kwargs,
    )
    policy_id = derive_activation_policy_id(body)
    return RuntimeActivationPolicyV1(
        activation_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        allowed_execution_modes=body.allowed_execution_modes,
        allowed_data_modes=body.allowed_data_modes,
        require_champion_assignment=body.require_champion_assignment,
        require_artifact_integrity=body.require_artifact_integrity,
        require_validation_lineage=body.require_validation_lineage,
        require_promotion_lineage=body.require_promotion_lineage,
        require_provider_health=body.require_provider_health,
        require_quality_health=body.require_quality_health,
        require_runtime_dependencies=body.require_runtime_dependencies,
        max_activation_age_ns=body.max_activation_age_ns,
        paper_execution_only=body.paper_execution_only,
        live_execution_forbidden=body.live_execution_forbidden,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


def build_drift_policy(
    *,
    champion_scope: ChampionScopeV1,
    minimum_sample: int = 10,
    **kwargs,
) -> DriftPolicyV1:
    body = DriftPolicyV1(
        drift_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        minimum_sample=minimum_sample,
        actions_by_severity=kwargs.pop(
            "actions_by_severity",
            {
                DriftSeverity.INFO.value: GovernanceAction.WARN.value,
                DriftSeverity.WARNING.value: GovernanceAction.DEGRADE.value,
                DriftSeverity.CRITICAL.value: GovernanceAction.DISABLE_SCOPE.value,
            },
        ),
        implementation_version=kwargs.pop("implementation_version", GOVERNANCE_IMPLEMENTATION_VERSION),
        **kwargs,
    )
    policy_id = derive_drift_policy_id(body)
    return DriftPolicyV1(
        drift_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        minimum_sample=body.minimum_sample,
        schema_mismatch_action=body.schema_mismatch_action,
        feature_missingness_threshold=body.feature_missingness_threshold,
        feature_mean_shift_threshold=body.feature_mean_shift_threshold,
        feature_quantile_threshold=body.feature_quantile_threshold,
        forecast_distribution_threshold=body.forecast_distribution_threshold,
        performance_metric=body.performance_metric,
        performance_degradation_threshold=body.performance_degradation_threshold,
        calibration_ece_threshold=body.calibration_ece_threshold,
        ood_fraction_threshold=body.ood_fraction_threshold,
        provider_staleness_threshold_ns=body.provider_staleness_threshold_ns,
        quality_fail_closed_rate_threshold=body.quality_fail_closed_rate_threshold,
        risk_fail_closed_rate_threshold=body.risk_fail_closed_rate_threshold,
        actions_by_severity=body.actions_by_severity,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


def build_fail_safe_policy(
    *,
    champion_scope: ChampionScopeV1,
    **kwargs,
) -> FailSafePolicyV1:
    body = FailSafePolicyV1(
        fail_safe_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        implementation_version=kwargs.pop("implementation_version", GOVERNANCE_IMPLEMENTATION_VERSION),
        **kwargs,
    )
    policy_id = derive_fail_safe_policy_id(body)
    return FailSafePolicyV1(
        fail_safe_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        runtime_mismatch_action=body.runtime_mismatch_action,
        provider_critical_action=body.provider_critical_action,
        schema_drift_action=body.schema_drift_action,
        quality_fail_closed_action=body.quality_fail_closed_action,
        risk_subsystem_action=body.risk_subsystem_action,
        artifact_integrity_action=body.artifact_integrity_action,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )


def build_rollback_policy(
    *,
    champion_scope: ChampionScopeV1,
    allowed_trigger_types: tuple[DriftType, ...] | None = None,
    minimum_trigger_severity: DriftSeverity = DriftSeverity.CRITICAL,
    cooldown_ns: int = 0,
    consecutive_failure_threshold: int = 1,
    **kwargs,
) -> RollbackPolicyV1:
    body = RollbackPolicyV1(
        rollback_policy_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=champion_scope,
        allowed_trigger_types=allowed_trigger_types
        or (
            DriftType.PERFORMANCE_DRIFT,
            DriftType.CALIBRATION_DRIFT,
            DriftType.SCHEMA_DRIFT,
            DriftType.PROVIDER_HEALTH_DRIFT,
            DriftType.EXECUTION_ANOMALY,
        ),
        minimum_trigger_severity=minimum_trigger_severity,
        cooldown_ns=cooldown_ns,
        consecutive_failure_threshold=consecutive_failure_threshold,
        implementation_version=kwargs.pop("implementation_version", GOVERNANCE_IMPLEMENTATION_VERSION),
        **kwargs,
    )
    policy_id = derive_rollback_policy_id(body)
    return RollbackPolicyV1(
        rollback_policy_id=policy_id,
        schema_version=body.schema_version,
        champion_scope=body.champion_scope,
        allowed_trigger_types=body.allowed_trigger_types,
        minimum_trigger_severity=body.minimum_trigger_severity,
        require_previous_known_good=body.require_previous_known_good,
        require_artifact_integrity=body.require_artifact_integrity,
        cooldown_ns=body.cooldown_ns,
        consecutive_failure_threshold=body.consecutive_failure_threshold,
        implementation_version=body.implementation_version,
        metadata=body.metadata,
    )
