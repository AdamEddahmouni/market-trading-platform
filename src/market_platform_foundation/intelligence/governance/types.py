"""Runtime governance, monitoring, and rollback contracts (BUILD 23)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..promotion.types import ChampionScopeV1

GOVERNANCE_IMPLEMENTATION_VERSION = "governance-monitoring-rollback-v1"


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"


class ActivationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    DEACTIVATED = "DEACTIVATED"


class ExecutionAuthority(StrEnum):
    PAPER_OBSERVATIONAL = "PAPER_OBSERVATIONAL"
    PAPER_EXECUTION = "PAPER_EXECUTION"


class DriftType(StrEnum):
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    FEATURE_DISTRIBUTION_DRIFT = "FEATURE_DISTRIBUTION_DRIFT"
    MISSINGNESS_DRIFT = "MISSINGNESS_DRIFT"
    FORECAST_DISTRIBUTION_DRIFT = "FORECAST_DISTRIBUTION_DRIFT"
    PERFORMANCE_DRIFT = "PERFORMANCE_DRIFT"
    CALIBRATION_DRIFT = "CALIBRATION_DRIFT"
    OOD_RATE_DRIFT = "OOD_RATE_DRIFT"
    PROVIDER_HEALTH_DRIFT = "PROVIDER_HEALTH_DRIFT"
    QUALITY_DRIFT = "QUALITY_DRIFT"
    EXECUTION_ANOMALY = "EXECUTION_ANOMALY"


class DriftSeverity(StrEnum):
    NONE = "NONE"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class GovernanceAction(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    DEGRADE = "DEGRADE"
    DISABLE_NEW_OPPORTUNITIES = "DISABLE_NEW_OPPORTUNITIES"
    DISABLE_NEW_PAPER_ORDERS = "DISABLE_NEW_PAPER_ORDERS"
    DISABLE_SCOPE = "DISABLE_SCOPE"
    FAIL_CLOSED = "FAIL_CLOSED"
    ROLLBACK = "ROLLBACK"


class FailSafeDecisionKind(StrEnum):
    ALLOW = "ALLOW"
    DEGRADE = "DEGRADE"
    DISABLE_NEW_OPPORTUNITIES = "DISABLE_NEW_OPPORTUNITIES"
    DISABLE_NEW_PAPER_ORDERS = "DISABLE_NEW_PAPER_ORDERS"
    DISABLE_SCOPE = "DISABLE_SCOPE"
    FAIL_CLOSED = "FAIL_CLOSED"


class RollbackDecisionKind(StrEnum):
    ROLLBACK = "ROLLBACK"
    RETAIN = "RETAIN"
    DISABLE_ONLY = "DISABLE_ONLY"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


class GovernanceEventType(StrEnum):
    ACTIVATED = "ACTIVATED"
    DEACTIVATED = "DEACTIVATED"
    HEALTH_DEGRADED = "HEALTH_DEGRADED"
    HEALTH_RECOVERED = "HEALTH_RECOVERED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    ALERT_RAISED = "ALERT_RAISED"
    FAIL_SAFE_TRIGGERED = "FAIL_SAFE_TRIGGERED"
    ROLLBACK_EVALUATED = "ROLLBACK_EVALUATED"
    ROLLBACK_APPLIED = "ROLLBACK_APPLIED"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"


class GovernanceReasonCode(StrEnum):
    ACTIVATION_CRITERIA_MET = "ACTIVATION_CRITERIA_MET"
    ACTIVATION_ARTIFACT_INTEGRITY_FAILED = "ACTIVATION_ARTIFACT_INTEGRITY_FAILED"
    ACTIVATION_CHAMPION_MISMATCH = "ACTIVATION_CHAMPION_MISMATCH"
    ACTIVATION_SCOPE_MISMATCH = "ACTIVATION_SCOPE_MISMATCH"
    ACTIVATION_LIVE_EXECUTION_FORBIDDEN = "ACTIVATION_LIVE_EXECUTION_FORBIDDEN"
    ACTIVATION_UNPROMOTED_CANDIDATE = "ACTIVATION_UNPROMOTED_CANDIDATE"
    RUNTIME_ASSIGNMENT_MISMATCH = "RUNTIME_ASSIGNMENT_MISMATCH"
    RUNTIME_POLICY_MISMATCH = "RUNTIME_POLICY_MISMATCH"
    RUNTIME_IDENTITY_MISSING = "RUNTIME_IDENTITY_MISSING"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    PROVIDER_STALE = "PROVIDER_STALE"
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    CALIBRATION_DRIFT_DETECTED = "CALIBRATION_DRIFT_DETECTED"
    PERFORMANCE_DRIFT_DETECTED = "PERFORMANCE_DRIFT_DETECTED"
    SCHEMA_DRIFT_DETECTED = "SCHEMA_DRIFT_DETECTED"
    FEATURE_DRIFT_DETECTED = "FEATURE_DRIFT_DETECTED"
    FORECAST_DRIFT_DETECTED = "FORECAST_DRIFT_DETECTED"
    QUALITY_FAIL_CLOSED_SPIKE = "QUALITY_FAIL_CLOSED_SPIKE"
    RISK_SUBSYSTEM_UNHEALTHY = "RISK_SUBSYSTEM_UNHEALTHY"
    ROLLBACK_TARGET_VALID = "ROLLBACK_TARGET_VALID"
    ROLLBACK_TARGET_INVALID = "ROLLBACK_TARGET_INVALID"
    ROLLBACK_NO_KNOWN_GOOD = "ROLLBACK_NO_KNOWN_GOOD"
    ROLLBACK_ARTIFACT_INTEGRITY_FAILED = "ROLLBACK_ARTIFACT_INTEGRITY_FAILED"
    ROLLBACK_SCOPE_MISMATCH = "ROLLBACK_SCOPE_MISMATCH"
    ROLLBACK_UNPROMOTED_TARGET = "ROLLBACK_UNPROMOTED_TARGET"
    RUNTIME_GOVERNANCE_DISABLED = "RUNTIME_GOVERNANCE_DISABLED"
    PAPER_EXECUTION_DISABLED = "PAPER_EXECUTION_DISABLED"
    TRUE_PREDICTION_COVERAGE_UNAVAILABLE = "TRUE_PREDICTION_COVERAGE_UNAVAILABLE"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    OVERRIDE_FORBIDDEN = "OVERRIDE_FORBIDDEN"


class OverrideAction(StrEnum):
    DISABLE_SCOPE = "DISABLE_SCOPE"
    RETAIN_DISABLED = "RETAIN_DISABLED"
    REACTIVATE_KNOWN_GOOD = "REACTIVATE_KNOWN_GOOD"


@dataclass(frozen=True, slots=True)
class MonitoringWindowV1:
    """Explicit half-open monitoring interval [start_ns, end_ns)."""

    start_ns: int
    end_ns: int
    evaluation_as_of_ns: int | None = None
    scope: ChampionScopeV1 | None = None
    mode: str | None = None
    scenario_id: str | None = None

    def __post_init__(self) -> None:
        if self.start_ns < 0 or self.end_ns < 0:
            raise ValueError("WINDOW_TIMESTAMP_INVALID")
        if self.end_ns <= self.start_ns:
            raise ValueError("WINDOW_END_MUST_EXCEED_START")


@dataclass(frozen=True, slots=True)
class RuntimeReportedIdentityV1:
    """Runtime-reported artifact/config identity for consistency checks."""

    candidate_id: str | None = None
    candidate_artifact_hash: str | None = None
    model_config_hash: str | None = None
    policy_stack_hash: str | None = None
    feature_schema_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeActivationPolicyV1:
    activation_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    allowed_execution_modes: tuple[str, ...] = ("PAPER",)
    allowed_data_modes: tuple[str, ...] = ("ACTUAL_LIVE",)
    require_champion_assignment: bool = True
    require_artifact_integrity: bool = True
    require_validation_lineage: bool = False
    require_promotion_lineage: bool = True
    require_provider_health: bool = True
    require_quality_health: bool = True
    require_runtime_dependencies: bool = True
    max_activation_age_ns: int | None = None
    paper_execution_only: bool = True
    live_execution_forbidden: bool = True
    implementation_version: str = GOVERNANCE_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.live_execution_forbidden and "LIVE" in self.allowed_execution_modes:
            raise ValueError("LIVE_EXECUTION_FORBIDDEN")
        if not self.paper_execution_only:
            raise ValueError("PAPER_EXECUTION_ONLY_REQUIRED")


@dataclass(frozen=True, slots=True)
class RuntimeActivationV1:
    activation_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    champion_assignment_id: str
    candidate_id: str
    candidate_artifact_hash: str
    promotion_decision_id: str | None
    activation_policy_id: str
    effective_from_ns: int
    effective_until_ns: int | None = None
    execution_mode: str = "PAPER"
    data_mode: str = "ACTUAL_LIVE"
    execution_authority: ExecutionAuthority = ExecutionAuthority.PAPER_EXECUTION
    runtime_config_refs: tuple[ContractReference, ...] = ()
    previous_activation_id: str | None = None
    status: ActivationStatus = ActivationStatus.ACTIVE
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.execution_mode != "PAPER":
            raise ValueError("LIVE_EXECUTION_FORBIDDEN")
        if self.effective_from_ns < 0:
            raise ValueError("EFFECTIVE_FROM_INVALID")
        if self.effective_until_ns is not None and self.effective_until_ns <= self.effective_from_ns:
            raise ValueError("EFFECTIVE_UNTIL_INVALID")


@dataclass(frozen=True, slots=True)
class ProviderHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    provider: str
    capability: str | None
    observed_at_ns: int
    window: MonitoringWindowV1
    connected: bool | None = None
    last_event_available_time_ns: int | None = None
    last_event_received_time_ns: int | None = None
    event_count: int = 0
    invalid_quote_count: int = 0
    crossed_book_count: int = 0
    clock_drift_count: int = 0
    disconnect_count: int = 0
    staleness_ns: int | None = None
    health_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DataQualityHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    window: MonitoringWindowV1
    observation_count: int = 0
    usable_count: int = 0
    degraded_count: int = 0
    abstain_count: int = 0
    fail_closed_count: int = 0
    invalid_quote_count: int = 0
    crossed_book_count: int = 0
    clock_drift_count: int = 0
    capability_unavailable_count: int = 0
    health_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntelligenceHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    window: MonitoringWindowV1
    champion_scope: ChampionScopeV1
    forecast_count: int = 0
    abstention_count: int = 0
    settlement_coverage: float | None = None
    labelable_fraction: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None
    ece: float | None = None
    ood_fraction: float | None = None
    quality_degraded_fraction: float | None = None
    health_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    window: MonitoringWindowV1
    execution_mode: str = "PAPER"
    proposal_count: int = 0
    risk_approval_count: int = 0
    risk_reduction_count: int = 0
    risk_rejection_count: int = 0
    risk_fail_closed_count: int = 0
    paper_order_count: int = 0
    fill_count: int = 0
    no_fill_count: int = 0
    cancel_count: int = 0
    duplicate_prevention_count: int = 0
    daily_loss_guard_count: int = 0
    health_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OpportunityHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    window: MonitoringWindowV1
    assessment_count: int = 0
    emitted_count: int = 0
    suppressed_count: int = 0
    abstained_count: int = 0
    fail_closed_count: int = 0
    expired_before_risk_count: int = 0
    quality_suppressed_count: int = 0
    ood_suppressed_count: int = 0
    spread_suppressed_count: int = 0
    health_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeatureReferenceDistributionV1:
    reference_id: str
    schema_version: str
    feature_schema_fingerprint: str
    feature_means: dict[str, float] = field(default_factory=dict)
    feature_stds: dict[str, float] = field(default_factory=dict)
    feature_missingness_rates: dict[str, float] = field(default_factory=dict)
    feature_quantiles: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    sample_count: int = 0
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DriftPolicyV1:
    drift_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    minimum_sample: int = 10
    schema_mismatch_action: GovernanceAction = GovernanceAction.DISABLE_SCOPE
    feature_missingness_threshold: float = 0.10
    feature_mean_shift_threshold: float = 2.0
    feature_quantile_threshold: float = 0.25
    forecast_distribution_threshold: float = 0.15
    performance_metric: str = "brier"
    performance_degradation_threshold: float = 0.05
    calibration_ece_threshold: float = 0.10
    ood_fraction_threshold: float = 0.20
    provider_staleness_threshold_ns: int = 60_000_000_000
    quality_fail_closed_rate_threshold: float = 0.10
    risk_fail_closed_rate_threshold: float = 0.10
    actions_by_severity: dict[str, str] = field(default_factory=dict)
    implementation_version: str = GOVERNANCE_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.minimum_sample <= 0:
            raise ValueError("MINIMUM_SAMPLE_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class DriftAssessmentV1:
    drift_assessment_id: str
    schema_version: str
    policy_id: str
    window: MonitoringWindowV1
    reference_id: str | None
    metric_observations: dict[str, float] = field(default_factory=dict)
    sample_counts: dict[str, int] = field(default_factory=dict)
    severity: DriftSeverity = DriftSeverity.UNKNOWN
    drift_types: tuple[DriftType, ...] = ()
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    recommended_action: GovernanceAction = GovernanceAction.ALLOW
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GovernanceAlertV1:
    alert_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    severity: DriftSeverity
    alert_type: str
    source_refs: tuple[ContractReference, ...]
    observed_at_ns: int
    recommended_action: GovernanceAction
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FailSafePolicyV1:
    fail_safe_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    runtime_mismatch_action: FailSafeDecisionKind = FailSafeDecisionKind.DISABLE_SCOPE
    provider_critical_action: FailSafeDecisionKind = FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES
    schema_drift_action: FailSafeDecisionKind = FailSafeDecisionKind.DISABLE_SCOPE
    quality_fail_closed_action: FailSafeDecisionKind = FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES
    risk_subsystem_action: FailSafeDecisionKind = FailSafeDecisionKind.DISABLE_NEW_PAPER_ORDERS
    artifact_integrity_action: FailSafeDecisionKind = FailSafeDecisionKind.FAIL_CLOSED
    implementation_version: str = GOVERNANCE_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FailSafeDecisionV1:
    decision_id: str
    schema_version: str
    policy_id: str
    champion_scope: ChampionScopeV1
    decision_time_ns: int
    decision: FailSafeDecisionKind
    trigger_refs: tuple[ContractReference, ...]
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RollbackPolicyV1:
    rollback_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    allowed_trigger_types: tuple[DriftType, ...] = (
        DriftType.PERFORMANCE_DRIFT,
        DriftType.CALIBRATION_DRIFT,
        DriftType.SCHEMA_DRIFT,
        DriftType.PROVIDER_HEALTH_DRIFT,
        DriftType.EXECUTION_ANOMALY,
    )
    minimum_trigger_severity: DriftSeverity = DriftSeverity.CRITICAL
    require_previous_known_good: bool = True
    require_artifact_integrity: bool = True
    cooldown_ns: int = 0
    consecutive_failure_threshold: int = 1
    implementation_version: str = GOVERNANCE_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RollbackDecisionV1:
    rollback_decision_id: str
    schema_version: str
    policy_id: str
    current_activation_id: str
    target_activation_id: str | None
    trigger_refs: tuple[ContractReference, ...]
    decision: RollbackDecisionKind
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    effective_time_ns: int = 0
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GovernanceOverrideV1:
    override_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    action: OverrideAction
    effective_from_ns: int
    reason: str
    actor: str
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GovernanceEventV1:
    event_id: str
    schema_version: str
    event_type: GovernanceEventType
    champion_scope: ChampionScopeV1
    effective_at_ns: int
    source_refs: tuple[ContractReference, ...] = ()
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeHealthSnapshotV1:
    """Aggregate runtime health across subsystems."""

    snapshot_id: str
    schema_version: str
    activation_id: str
    champion_scope: ChampionScopeV1
    observed_at_ns: int
    window: MonitoringWindowV1
    overall_state: HealthState = HealthState.UNKNOWN
    provider_state: HealthState = HealthState.UNKNOWN
    data_quality_state: HealthState = HealthState.UNKNOWN
    intelligence_state: HealthState = HealthState.UNKNOWN
    execution_state: HealthState = HealthState.UNKNOWN
    opportunity_state: HealthState = HealthState.UNKNOWN
    runtime_consistency_state: HealthState = HealthState.UNKNOWN
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    subsystem_snapshot_ids: dict[str, str] = field(default_factory=dict)
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResearchTriggerV1:
    trigger_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    window: MonitoringWindowV1
    drift_assessment_refs: tuple[ContractReference, ...] = ()
    health_snapshot_refs: tuple[ContractReference, ...] = ()
    activation_ref: ContractReference | None = None
    reason_codes: tuple[GovernanceReasonCode, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeGovernanceState:
    """Resolved operational authorization for BUILD 21/22 gates."""

    activation: RuntimeActivationV1 | None
    fail_safe_decision: FailSafeDecisionV1 | None
    opportunities_allowed: bool
    paper_execution_allowed: bool
    scope_disabled: bool
    active_fallback_divergence: bool = False
    latest_champion_assignment_id: str | None = None


__all__ = [
    "GOVERNANCE_IMPLEMENTATION_VERSION",
    "ActivationStatus",
    "DataQualityHealthSnapshotV1",
    "DriftAssessmentV1",
    "DriftPolicyV1",
    "DriftSeverity",
    "DriftType",
    "ExecutionAuthority",
    "ExecutionHealthSnapshotV1",
    "FailSafeDecisionKind",
    "FailSafeDecisionV1",
    "FailSafePolicyV1",
    "FeatureReferenceDistributionV1",
    "GovernanceAction",
    "GovernanceAlertV1",
    "GovernanceEventType",
    "GovernanceEventV1",
    "GovernanceOverrideV1",
    "GovernanceReasonCode",
    "HealthState",
    "IntelligenceHealthSnapshotV1",
    "MonitoringWindowV1",
    "OpportunityHealthSnapshotV1",
    "OverrideAction",
    "ProviderHealthSnapshotV1",
    "ResearchTriggerV1",
    "RollbackDecisionKind",
    "RollbackDecisionV1",
    "RollbackPolicyV1",
    "RuntimeActivationPolicyV1",
    "RuntimeActivationV1",
    "RuntimeGovernanceState",
    "RuntimeHealthSnapshotV1",
    "RuntimeReportedIdentityV1",
]
