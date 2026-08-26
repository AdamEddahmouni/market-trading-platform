"""Operational reliability contracts (BUILD 32).

Derived operational telemetry, SLO assessments, alerts, backup/recovery artifacts —
never competing sources of truth for portfolio, authorization, order state, or incidents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

OPERATIONAL_RELIABILITY_SCHEMA_VERSION = "1"
OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION = "build32-v1"

BUILD32_KNOWN_LIMITATIONS = (
    "external alert delivery not configured by default (local/console adapter only)",
    "disaster-recovery drills use fixtures and isolated stores only",
    "no geographic redundancy or standby broker connection",
    "Mongo backup/restore optional when IMP_TEST_MONGODB_URI unavailable",
    "wall-clock soak limited to deterministic virtual endurance in CI",
    "single-host local qualification only",
    "broker status feed may be unavailable in local development",
    "no autonomous live trading authority added by BUILD 32",
)

# Bounded metric dimensions — never use order_id, forecast_id, account number, or error text.
ALLOWED_METRIC_DIMENSIONS = frozenset(
    {
        "component",
        "scope",
        "broker",
        "provider",
        "severity",
        "channel",
        "objective",
        "health_class",
    }
)


class ComponentHealthClass(StrEnum):
    LIVENESS = "LIVENESS"
    READINESS = "READINESS"
    HEALTH = "HEALTH"


class ComponentSignalState(StrEnum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NEVER_OBSERVED = "NEVER_OBSERVED"


class SLOObjectiveStatus(StrEnum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertState(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class DeliveryResult(StrEnum):
    SUCCESS = "SUCCESS"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class OperationalReliabilityDisposition(StrEnum):
    OPERATIONAL_RELIABILITY_QUALIFIED = "OPERATIONAL_RELIABILITY_QUALIFIED"
    OPERATIONAL_RELIABILITY_QUALIFIED_WITH_LIMITATIONS = (
        "OPERATIONAL_RELIABILITY_QUALIFIED_WITH_LIMITATIONS"
    )
    OBSERVABILITY_INCOMPLETE = "OBSERVABILITY_INCOMPLETE"
    ALERTING_INCOMPLETE = "ALERTING_INCOMPLETE"
    RECOVERY_INVALID = "RECOVERY_INVALID"
    DR_NOT_READY = "DR_NOT_READY"


class DrillResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ComponentHeartbeatV1:
    component: str
    schema_version: str
    observed_at_ns: int
    expected_interval_ns: int
    stale_after_ns: int
    liveness: str
    readiness: str
    health: str
    blocking_live: bool
    last_success_at_ns: int | None
    current_issue: str | None
    source_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationalHealthMatrixEntryV1:
    component: str
    state: str
    freshness_ns: int | None
    last_success_at_ns: int | None
    current_issue: str | None
    blocking_live: bool
    execution_critical: bool
    scientific_critical: bool
    operational_only: bool


@dataclass(frozen=True)
class OperationalHealthMatrixV1:
    matrix_id: str
    schema_version: str
    as_of_ns: int
    observability_state: str
    entries: tuple[OperationalHealthMatrixEntryV1, ...]
    blocking_dependencies: tuple[str, ...]
    source_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SLOObjectiveV1:
    objective_id: str
    description: str
    warning_threshold: float
    critical_threshold: float
    safety_critical: bool
    missing_data_semantics: str


@dataclass(frozen=True)
class OperationalSLOPolicyV1:
    slo_policy_id: str
    schema_version: str
    scope: str
    measurement_window_ns: int
    evaluation_cadence_ns: int
    objectives: tuple[SLOObjectiveV1, ...]
    minimum_sample: int
    missing_data_semantics: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SLOObjectiveResultV1:
    objective_id: str
    target_warning: float
    target_critical: float
    observed_value: float | None
    sample_count: int
    status: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationalSLOAssessmentV1:
    assessment_id: str
    schema_version: str
    policy_ref: str
    scope: str
    window_start_ns: int
    window_end_ns: int
    as_of_ns: int
    objective_results: tuple[SLOObjectiveResultV1, ...]
    overall_status: str
    reason_codes: tuple[str, ...]
    source_refs: tuple[str, ...] = ()
    implementation_version: str = OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertPolicyV1:
    alert_policy_id: str
    schema_version: str
    source_assessment_types: tuple[str, ...]
    severity_mappings: dict[str, str]
    dedup_window_ns: int
    cooldown_ns: int
    delivery_channels: tuple[str, ...]
    critical_requires_delivery: bool
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertV1:
    alert_id: str
    schema_version: str
    alert_type: str
    severity: str
    state: str
    scope: str
    raised_at_ns: int
    dedup_key: str
    summary: str
    reason_codes: tuple[str, ...]
    source_refs: tuple[str, ...] = ()
    acknowledged_at_ns: int | None = None
    resolved_at_ns: int | None = None
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertDeliveryReceiptV1:
    delivery_receipt_id: str
    schema_version: str
    alert_ref: str
    channel: str
    attempt_time_ns: int
    result: str
    latency_ns: int | None
    failure_reason: str | None
    retry_classification: str | None
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PersistenceHealthSnapshotV1:
    snapshot_id: str
    schema_version: str
    as_of_ns: int
    backend: str
    connection_ready: bool
    write_healthy: bool
    read_healthy: bool
    schema_compatible: bool
    last_successful_write_ns: int | None
    last_successful_read_ns: int | None
    write_errors: int
    read_errors: int
    disposition: str
    blocking_live: bool
    source_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BackupManifestV1:
    backup_manifest_id: str
    schema_version: str
    created_at_ns: int
    source_head: str
    included_stores: tuple[str, ...]
    content_hashes: dict[str, str]
    exclusions: tuple[str, ...]
    integrity_status: str
    encryption_status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryPlanV1:
    recovery_plan_id: str
    schema_version: str
    failure_scenario: str
    restore_order: tuple[str, ...]
    integrity_checks: tuple[str, ...]
    reconciliation_steps: tuple[str, ...]
    startup_mode: str
    requires_operator_approval: bool
    rpo_objective_ns: int
    rto_objective_ns: int
    limitations: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DisasterRecoveryDrillSpecV1:
    drill_spec_id: str
    schema_version: str
    scenario: str
    initial_state: dict[str, Any]
    failure_injection: dict[str, Any]
    expected_unavailable_components: tuple[str, ...]
    expected_safety_state: dict[str, Any]
    restore_source: str | None
    expected_reconciliation: tuple[str, ...]
    required_operator_action: tuple[str, ...]
    expected_final_state: dict[str, Any]
    implementation_version: str


@dataclass(frozen=True)
class DisasterRecoveryDrillReportV1:
    drill_report_id: str
    schema_version: str
    drill_spec_ref: str
    failure_observed: dict[str, Any]
    detection_time_ns: int
    alert_results: tuple[str, ...]
    restore_result: str
    integrity_checks: tuple[str, ...]
    reconciliation_result: str
    operator_workflow: tuple[str, ...]
    final_safe_state: dict[str, Any]
    recovery_duration_ns: int
    data_loss_assessment: str
    real_broker_submits: int
    real_broker_cancels: int
    real_broker_replaces: int
    result: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SoakQualificationSpecV1:
    soak_spec_id: str
    schema_version: str
    duration_ns: int
    mode: str
    health_checks: tuple[str, ...]
    slo_policy_ref: str
    alert_policy_ref: str
    acceptance_criteria: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SoakQualificationReportV1:
    soak_report_id: str
    schema_version: str
    spec_ref: str
    actual_duration_ns: int
    virtual_duration_ns: int
    mode: str
    heartbeat_gaps: int
    provider_reconnects: int
    reconciliation_cycles: int
    persistence_errors: int
    alert_events: int
    disposition: str
    limitations: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationalReliabilityQualificationReportV1:
    report_id: str
    schema_version: str
    build31_source_ref: str
    build32_source_ref: str
    disposition: str
    health_coverage: tuple[str, ...]
    slo_results: dict[str, str]
    alerting_results: dict[str, Any]
    delivery_results: dict[str, Any]
    persistence_health: str
    backup_verified: bool
    restore_verified: bool
    dr_drill_results: dict[str, str]
    soak_disposition: str
    blocking_defects: tuple[str, ...]
    limitations: tuple[str, ...]
    real_broker_side_effects_observed: int
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
