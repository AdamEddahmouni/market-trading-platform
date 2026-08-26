"""Deployment and change-control contracts (BUILD 34).

Release packaging, environment promotion, service supervision, deployment canaries,
migrations, rollback, and change control — never competing sources of truth for
authorization, order state, broker truth, or scientific policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

DEPLOYMENT_SCHEMA_VERSION = "1"
DEPLOYMENT_IMPLEMENTATION_VERSION = "build34-v1"

BUILD34_KNOWN_LIMITATIONS = (
    "single-machine local deployment qualification only",
    "no production cloud infrastructure or external release registry",
    "Windows-native service supervision via fixture supervisor only",
    "container packaging not canonical — repository is Windows-native dev",
    "no external secret manager configured by default",
    "Mongo migration/backup path fixture-tested when IMP_TEST_MONGODB_URI unavailable",
    "no blue/green or rolling multi-instance deployment",
    "no actual supervised-live environment promotion executed against real broker",
    "deployment canary defaults to zero real orders — fixture qualification only",
    "no autonomous live trading authority added by BUILD 34",
    "human session authorization and per-order confirmation remain mandatory",
)

# Policy-owned fields that deployment config must NOT override
POLICY_OWNED_FIELD_NAMES = frozenset(
    {
        "model_thresholds",
        "risk_limits",
        "opportunity_thresholds",
        "calibration_parameters",
        "provider_selection_thresholds",
        "max_pilot_sessions",
        "max_pilot_orders",
        "max_pilot_fills",
        "max_pilot_single_order_notional_minor",
        "max_pilot_total_notional_minor",
        "max_pilot_live_exposure_minor",
        "champion_model_ref",
        "execution_policy_ref",
        "opportunity_policy_ref",
    }
)

SECRET_PATTERNS = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "apikey",
        "token",
        "private_key",
        "credential",
        "oauth",
    }
)

BUNDLE_EXCLUDE_PATTERNS = (
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".env",
    "credentials",
    "secrets",
    "evidence/ui1/assistant-audit",
    ".cursor/settings.json",
)

BUNDLE_INCLUDE_ROOTS = (
    "src/market_platform_foundation",
    "ui/dist",
    "manifests",
    "phase0-dependency-lock.json",
    "artifacts/deployment-qualification",
)


class EnvironmentKind(StrEnum):
    LOCAL_DEV = "LOCAL_DEV"
    TEST = "TEST"
    QUALIFICATION = "QUALIFICATION"
    SUPERVISED_PILOT = "SUPERVISED_PILOT"
    SUPERVISED_LIVE = "SUPERVISED_LIVE"


class ExecutionMode(StrEnum):
    OFFLINE = "OFFLINE"
    PAPER = "PAPER"
    SUPERVISED_LIVE = "SUPERVISED_LIVE"


class ExecutionAuthority(StrEnum):
    NONE = "NONE"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    PAPER = "PAPER"
    SUPERVISED_LIVE = "SUPERVISED_LIVE"


class BrokerEnvironment(StrEnum):
    NONE = "NONE"
    PAPER = "PAPER"
    TEST = "TEST"
    SUPERVISED_LIVE = "SUPERVISED_LIVE"


class DeploymentDisposition(StrEnum):
    DEPLOYMENT_QUALIFIED = "DEPLOYMENT_QUALIFIED"
    DEPLOYMENT_QUALIFIED_WITH_LIMITATIONS = "DEPLOYMENT_QUALIFIED_WITH_LIMITATIONS"
    RELEASE_NOT_REPRODUCIBLE = "RELEASE_NOT_REPRODUCIBLE"
    ENVIRONMENT_INVALID = "ENVIRONMENT_INVALID"
    MIGRATION_UNSAFE = "MIGRATION_UNSAFE"
    ROLLBACK_UNSAFE = "ROLLBACK_UNSAFE"
    SERVICE_SUPERVISION_INVALID = "SERVICE_SUPERVISION_INVALID"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"
    DEPLOYMENT_BLOCKED = "DEPLOYMENT_BLOCKED"


class ChangeType(StrEnum):
    CODE_RELEASE = "CODE_RELEASE"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    INFRASTRUCTURE_CHANGE = "INFRASTRUCTURE_CHANGE"
    DEPENDENCY_UPDATE = "DEPENDENCY_UPDATE"
    SCHEMA_MIGRATION = "SCHEMA_MIGRATION"
    PROVIDER_CONFIGURATION_CHANGE = "PROVIDER_CONFIGURATION_CHANGE"
    OBSERVABILITY_CHANGE = "OBSERVABILITY_CHANGE"


class ChangeApprovalState(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class DeploymentState(StrEnum):
    PLANNED = "PLANNED"
    PRECHECK = "PRECHECK"
    BACKUP_VERIFIED = "BACKUP_VERIFIED"
    DEPLOYING = "DEPLOYING"
    CANARY = "CANARY"
    VERIFYING = "VERIFYING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    HALTED = "HALTED"


class ServiceDesiredState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    CRASHED = "CRASHED"


class ServiceCriticality(StrEnum):
    CRITICAL = "CRITICAL"
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class RestartPolicy(StrEnum):
    NEVER = "NEVER"
    ON_FAILURE = "ON_FAILURE"
    ALWAYS = "ALWAYS"


class DriftClassification(StrEnum):
    NONE = "NONE"
    INFORMATIONAL = "INFORMATIONAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    ARTIFACT_MISMATCH = "ARTIFACT_MISMATCH"


class RollbackDecision(StrEnum):
    ROLLBACK = "ROLLBACK"
    RETAIN = "RETAIN"
    HALT_ENVIRONMENT = "HALT_ENVIRONMENT"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


class PromotionResult(StrEnum):
    PROMOTED = "PROMOTED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ReleaseManifestV1:
    release_manifest_id: str
    schema_version: str
    source_repository: str
    source_commit_sha: str
    source_branch: str
    build_timestamp_ns: int
    application_version: str
    contract_schema_versions: dict[str, str]
    dependency_lock_hash: str
    source_tree_hash: str
    artifact_hashes: dict[str, str]
    supported_runtime: dict[str, str]
    configuration_schema_version: str
    required_migration_schema_version: str
    included_components: tuple[str, ...]
    excluded_components: tuple[str, ...]
    required_build_qualification_refs: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeploymentConfigurationV1:
    configuration_id: str
    schema_version: str
    runtime_infrastructure: dict[str, Any]
    provider_connectivity: dict[str, Any]
    persistence_endpoints: dict[str, Any]
    operator_server_config: dict[str, Any]
    telemetry_config: dict[str, Any]
    feature_flags: dict[str, bool]
    execution_mode: str
    execution_authority: str
    policy_references: dict[str, str]
    secret_references: dict[str, str]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnvironmentManifestV1:
    environment_manifest_id: str
    schema_version: str
    environment_kind: str
    release_manifest_ref: str
    configuration_ref: str
    configuration_hash: str
    persistence_environment: str
    provider_environment: str
    broker_environment: str
    execution_mode: str
    execution_authority: str
    allowed_policy_refs: tuple[str, ...]
    required_secrets: tuple[str, ...]
    service_definitions: tuple[str, ...]
    health_readiness_requirements: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromotionRecordV1:
    promotion_record_id: str
    schema_version: str
    release_manifest_ref: str
    from_environment: str
    to_environment: str
    qualification_evidence_refs: tuple[str, ...]
    configuration_compatibility_result: str
    required_approvals: tuple[str, ...]
    promotion_time_ns: int
    result: str
    artifact_hash: str
    lineage: dict[str, Any] = field(default_factory=dict)
    implementation_version: str = DEPLOYMENT_IMPLEMENTATION_VERSION


@dataclass(frozen=True)
class DeploymentRecordV1:
    deployment_record_id: str
    schema_version: str
    environment_ref: str
    release_ref: str
    deployment_started_ns: int
    deployment_completed_ns: int | None
    previous_deployment_ref: str | None
    artifact_hashes_observed: dict[str, str]
    configuration_hash_observed: str
    schema_before: str
    schema_after: str
    service_state: dict[str, str]
    health_readiness_result: str
    deployment_disposition: str
    lineage: dict[str, Any] = field(default_factory=dict)
    implementation_version: str = DEPLOYMENT_IMPLEMENTATION_VERSION


@dataclass(frozen=True)
class ConfigurationDriftAssessmentV1:
    drift_assessment_id: str
    schema_version: str
    expected_release: str
    expected_config_hash: str
    observed_release: str
    observed_config: str
    drift_classification: str
    blocking_impact: bool
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceDefinitionV1:
    service_id: str
    schema_version: str
    command: str
    working_directory: str
    environment_manifest_ref: str
    dependencies: tuple[str, ...]
    restart_policy: str
    startup_timeout_ns: int
    shutdown_timeout_ns: int
    liveness_probe: str
    readiness_probe: str
    criticality: str
    log_location: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceSupervisorStatusV1:
    service_id: str
    schema_version: str
    desired_state: str
    observed_state: str
    process_ref: str | None
    release_ref: str
    start_time_ns: int | None
    restart_count: int
    liveness: str
    readiness: str
    last_failure: str | None
    criticality: str
    implementation_version: str


@dataclass(frozen=True)
class DeploymentPlanV1:
    deployment_plan_id: str
    schema_version: str
    target_environment: str
    release_ref: str
    previous_deployment_ref: str | None
    service_changes: tuple[str, ...]
    config_ref: str
    migration_plan_ref: str | None
    backup_prerequisite: bool
    pre_deploy_checks: tuple[str, ...]
    deployment_steps: tuple[str, ...]
    health_checks: tuple[str, ...]
    canary_checks: tuple[str, ...]
    rollback_triggers: tuple[str, ...]
    post_deploy_verification: tuple[str, ...]
    operator_approval_requirements: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeploymentCanarySpecV1:
    deployment_canary_spec_id: str
    schema_version: str
    deployment_plan_ref: str
    minimum_observation_duration_ns: int
    required_services: tuple[str, ...]
    required_health_states: tuple[str, ...]
    provider_observation_requirements: tuple[str, ...]
    broker_readonly_requirements: tuple[str, ...]
    reconciliation_requirements: tuple[str, ...]
    slo_requirements: tuple[str, ...]
    zero_live_order_requirement: bool
    success_criteria: tuple[str, ...]
    failure_criteria: tuple[str, ...]
    implementation_version: str


@dataclass(frozen=True)
class DeploymentCanaryReportV1:
    deployment_canary_report_id: str
    schema_version: str
    canary_spec_ref: str
    observation_duration_ns: int
    services_healthy: bool
    provider_observations_ok: bool
    broker_readonly_ok: bool
    reconciliation_ok: bool
    real_broker_submits: int
    disposition: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationPlanV1:
    migration_plan_id: str
    schema_version: str
    from_schema: str
    to_schema: str
    forward_steps: tuple[str, ...]
    compatibility_window: str
    rollback_supported: bool
    backup_prerequisite: bool
    validation_checks: tuple[str, ...]
    data_loss_risk: str
    implementation_version: str


@dataclass(frozen=True)
class DeploymentChangeRequestV1:
    change_request_id: str
    schema_version: str
    change_type: str
    release_ref: str
    configuration_diff: dict[str, Any]
    migration_diff: dict[str, Any]
    target_environment: str
    reason: str
    risk_classification: str
    required_qualification_refs: tuple[str, ...]
    rollback_target: str
    planned_window_ns: tuple[int, int]
    approval_state: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeploymentRollbackPlanV1:
    rollback_plan_id: str
    schema_version: str
    deployment_ref: str
    rollback_target_release: str
    rollback_target_deployment: str
    preconditions: tuple[str, ...]
    schema_compatibility: str
    service_sequence: tuple[str, ...]
    broker_reconciliation_requirements: tuple[str, ...]
    post_rollback_validation: tuple[str, ...]
    operator_approval_requirements: tuple[str, ...]
    implementation_version: str


@dataclass(frozen=True)
class DeploymentRollbackDecisionV1:
    rollback_decision_id: str
    schema_version: str
    deployment_ref: str
    decision: str
    reasons: tuple[str, ...]
    rollback_plan_ref: str
    implementation_version: str


@dataclass(frozen=True)
class DeploymentQualificationSpecV1:
    qualification_spec_id: str
    schema_version: str
    release_ref: str
    environment_kind: str
    required_reproducibility_checks: tuple[str, ...]
    required_service_health_checks: tuple[str, ...]
    required_deployment_canary: bool
    required_rollback_drill: bool
    required_migration_tests: bool
    required_config_drift_tests: bool
    required_secret_scan: bool
    required_zero_autonomy_invariants: tuple[str, ...]
    implementation_version: str


@dataclass(frozen=True)
class DeploymentQualificationReportV1:
    qualification_report_id: str
    schema_version: str
    qualification_spec_ref: str
    release_reproducibility: str
    environment_validation: str
    deployment_result: str
    service_supervision: str
    deployment_canary: str
    migration: str
    rollback: str
    config_drift: str
    operator_visibility: str
    security: str
    disposition: str
    limitations: tuple[str, ...]
    real_broker_submits: int
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeVersionReportV1:
    service_id: str
    release_id: str
    commit_sha: str
    config_hash: str
    service_version: str
    matches_expected: bool


@dataclass(frozen=True)
class ServiceGraphV1:
    service_graph_id: str
    schema_version: str
    services: tuple[ServiceDefinitionV1, ...]
    startup_order: tuple[str, ...]
    implementation_version: str
