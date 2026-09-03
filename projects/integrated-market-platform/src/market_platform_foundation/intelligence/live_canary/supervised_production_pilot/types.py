"""Supervised production pilot contracts (BUILD 33).

Derived operational pilot telemetry, provider selection, checkpoints, runbooks —
never competing sources of truth for portfolio, authorization, order state, or incidents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

SUPERVISED_PILOT_SCHEMA_VERSION = "1"
SUPERVISED_PILOT_IMPLEMENTATION_VERSION = "build33-v1"

BUILD33_KNOWN_LIMITATIONS = (
    "bounded supervised production pilot — not unrestricted production rollout",
    "no autonomous live trading authority added by BUILD 33",
    "human session authorization and per-order confirmation remain mandatory",
    "market-data provider failover is deterministic; live broker failover is NOT automatic",
    "fallback provider must independently satisfy freshness and health requirements",
    "pilot caps are additional ceilings and cannot increase from operational success",
    "runbook exercises use fixtures and isolated stores only",
    "long-duration evidence limited to deterministic virtual endurance in CI",
    "single-host local qualification only",
    "external alert delivery not configured by default (local/console adapter only)",
    "no alternate live broker certified for automatic failover",
    "provider redundancy may be fixture-tested when only one live provider available",
)

# Default cadences (nanoseconds)
DEFAULT_PILOT_DURATION_NS = 7 * 24 * 60 * 60 * 1_000_000_000
DEFAULT_CHECKPOINT_INTERVAL_NS = 15 * 60 * 1_000_000_000
DEFAULT_RECONCILIATION_INTERVAL_NS = 5 * 60 * 1_000_000_000
DEFAULT_BACKUP_FRESHNESS_NS = 24 * 60 * 60 * 1_000_000_000
DEFAULT_RESTORE_DRILL_AGE_NS = 30 * 24 * 60 * 60 * 1_000_000_000

# Pilot caps (additional ceilings over BUILD 29/30)
DEFAULT_MAX_PILOT_SESSIONS = 20
DEFAULT_MAX_PILOT_ORDERS = 40
DEFAULT_MAX_PILOT_FILLS = 40
DEFAULT_MAX_PILOT_SINGLE_ORDER_NOTIONAL_MINOR = 5_000
DEFAULT_MAX_PILOT_TOTAL_NOTIONAL_MINOR = 50_000
DEFAULT_MAX_PILOT_LIVE_EXPOSURE_MINOR = 25_000

# Provider redundancy defaults
DEFAULT_PROVIDER_FAILURE_DURATION_NS = 30_000_000_000
DEFAULT_PROVIDER_RECOVERY_DURATION_NS = 60_000_000_000
DEFAULT_PROVIDER_SWITCH_COOLDOWN_NS = 120_000_000_000
DEFAULT_PROVIDER_MAX_FRESHNESS_NS = 5_000_000_000


class PilotGovernanceState(StrEnum):
    PILOT_PREPARED = "PILOT_PREPARED"
    PILOT_READY = "PILOT_READY"
    PILOT_ACTIVE = "PILOT_ACTIVE"
    PILOT_DEGRADED = "PILOT_DEGRADED"
    PILOT_PAUSED = "PILOT_PAUSED"
    PILOT_HALTED = "PILOT_HALTED"
    PILOT_RECONCILING = "PILOT_RECONCILING"
    PILOT_COMPLETE = "PILOT_COMPLETE"
    PILOT_INVALID = "PILOT_INVALID"


class PilotDisposition(StrEnum):
    SUPERVISED_PRODUCTION_PILOT_QUALIFIED = "SUPERVISED_PRODUCTION_PILOT_QUALIFIED"
    SUPERVISED_PRODUCTION_PILOT_QUALIFIED_WITH_LIMITATIONS = (
        "SUPERVISED_PRODUCTION_PILOT_QUALIFIED_WITH_LIMITATIONS"
    )
    MORE_PILOT_DURATION_REQUIRED = "MORE_PILOT_DURATION_REQUIRED"
    PROVIDER_REDUNDANCY_INCOMPLETE = "PROVIDER_REDUNDANCY_INCOMPLETE"
    OPERATIONAL_RUNBOOKS_INCOMPLETE = "OPERATIONAL_RUNBOOKS_INCOMPLETE"
    PILOT_HALTED_SAFE = "PILOT_HALTED_SAFE"
    PILOT_INVALID_RECONCILIATION = "PILOT_INVALID_RECONCILIATION"
    PILOT_INVALID_OPERATIONAL_INTEGRITY = "PILOT_INVALID_OPERATIONAL_INTEGRITY"


class ProviderCapability(StrEnum):
    QUOTES = "QUOTES"
    TRADES = "TRADES"
    ORDER_BOOK = "ORDER_BOOK"


class ProviderHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ProviderSelectionReason(StrEnum):
    PRIMARY_HEALTHY = "PRIMARY_HEALTHY"
    PRIMARY_FAILURE_THRESHOLD_MET = "PRIMARY_FAILURE_THRESHOLD_MET"
    FALLBACK_SELECTED = "FALLBACK_SELECTED"
    BOTH_UNHEALTHY = "BOTH_UNHEALTHY"
    FALLBACK_STALE = "FALLBACK_STALE"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    PRIMARY_RECOVERED = "PRIMARY_RECOVERED"
    NO_CANDIDATE = "NO_CANDIDATE"


class ProviderDivergenceStatus(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class PilotReviewDisposition(StrEnum):
    CONTINUE_PILOT = "CONTINUE_PILOT"
    CONTINUE_DEGRADED = "CONTINUE_DEGRADED"
    PAUSE_FOR_REVIEW = "PAUSE_FOR_REVIEW"
    HALT_PILOT = "HALT_PILOT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RunbookExerciseResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class BrokerFailoverAuthorization(StrEnum):
    NOT_AUTHORIZED = "NOT_AUTHORIZED"


@dataclass(frozen=True)
class LiveSupervisedPilotPolicyV1:
    pilot_policy_id: str
    schema_version: str
    source_build32_ref: str
    pilot_start_ns: int
    pilot_end_ns: int
    allowed_market_sessions: tuple[str, ...]
    allowed_data_providers: tuple[str, ...]
    primary_provider_policy: dict[str, str]
    allowed_live_broker: str
    allowed_live_account_ref: str
    allowed_canary_program_policy_refs: tuple[str, ...]
    max_pilot_sessions: int
    max_pilot_orders: int
    max_pilot_fills: int
    max_pilot_single_order_notional_minor: int
    max_pilot_total_notional_minor: int
    max_pilot_live_exposure_minor: int
    provider_redundancy_policy_ref: str
    required_slo_policy_ref: str
    required_alert_policy_ref: str
    required_reconciliation_interval_ns: int
    required_operational_checkpoint_interval_ns: int
    required_backup_freshness_ns: int
    required_restore_drill_age_ns: int
    human_session_authorization_required: bool
    human_order_confirmation_required: bool
    manual_resume_required: bool
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveSupervisedPilotRunV1:
    pilot_run_id: str
    schema_version: str
    pilot_policy_ref: str
    build33_source_ref: str
    build25_release_candidate_ref: str
    build32_reliability_refs: tuple[str, ...]
    provider_redundancy_policy_ref: str
    slo_policy_ref: str
    alert_policy_ref: str
    broker_certification_ref: str
    live_account_ref: str
    start_ns: int
    end_ns: int | None
    initial_provider_health_snapshot: dict[str, Any]
    initial_broker_health_snapshot: dict[str, Any]
    initial_reconciliation_checkpoint_ref: str | None
    initial_kill_switch_state: str
    initial_backup_status: dict[str, Any]
    canary_program_refs: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRedundancyPolicyV1:
    provider_redundancy_policy_id: str
    schema_version: str
    scope: str
    capability: str
    instrument_class: str
    primary_provider: str
    fallback_providers: tuple[str, ...]
    minimum_primary_health: str
    minimum_fallback_health: str
    maximum_freshness_ns: int
    minimum_failure_duration_ns: int
    minimum_recovery_duration_ns: int
    switch_cooldown_ns: int
    divergence_warning_bps: float
    divergence_critical_bps: float
    fallback_for_observational_state: bool
    fallback_for_forecast_inputs: bool
    fallback_for_opportunity_inputs: bool
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCandidateHealthV1:
    provider: str
    health: str
    freshness_ns: int | None
    last_event_time_ns: int | None
    last_available_time_ns: int | None


@dataclass(frozen=True)
class ProviderSelectionDecisionV1:
    provider_selection_decision_id: str
    schema_version: str
    decision_time_ns: int
    scope: str
    capability: str
    primary_provider: str
    available_candidates: tuple[ProviderCandidateHealthV1, ...]
    selected_provider: str | None
    decision_reason: str
    previous_provider: str | None
    switch_state: str
    policy_ref: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderDivergenceAssessmentV1:
    assessment_id: str
    schema_version: str
    as_of_ns: int
    instrument: str
    capability: str
    provider_a: str
    provider_b: str
    provider_a_value: float | None
    provider_b_value: float | None
    provider_a_event_time_ns: int | None
    provider_b_event_time_ns: int | None
    absolute_difference: float | None
    relative_difference_bps: float | None
    freshness_difference_ns: int | None
    status: str
    reason_codes: tuple[str, ...]
    policy_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerRedundancyAssessmentV1:
    assessment_id: str
    schema_version: str
    brokers_assessed: tuple[str, ...]
    capability_overlap: dict[str, tuple[str, ...]]
    account_isolation: bool
    auto_failover_authorization: str
    limitations: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationalPilotCheckpointV1:
    checkpoint_id: str
    schema_version: str
    pilot_run_ref: str
    as_of_ns: int
    pilot_state: str
    provider_health_summary: dict[str, str]
    selected_provider_state: dict[str, str]
    divergence_state: str
    broker_health: str
    reconciliation_health: str
    persistence_health: str
    slo_summary: str
    alert_delivery_health: str
    kill_switch_state: str
    live_exposure_minor: int
    active_sessions: int
    open_orders: int
    backup_freshness_ns: int | None
    unresolved_incidents: int
    blocking_reasons: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PilotOperationalReviewV1:
    review_id: str
    schema_version: str
    pilot_run_ref: str
    review_window_start_ns: int
    review_window_end_ns: int
    slo_summary: dict[str, str]
    provider_failovers: int
    provider_divergences: int
    broker_reconciliation_summary: str
    sessions_count: int
    orders_count: int
    fills_count: int
    incidents_count: int
    alerts_count: int
    backup_restore_state: str
    resource_health: str
    policy_cap_compliance: bool
    unresolved_risks: tuple[str, ...]
    operator_review_disposition: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunbookExerciseSpecV1:
    exercise_spec_id: str
    schema_version: str
    runbook_id: str
    runbook_version: str
    trigger: str
    initial_state: dict[str, Any]
    injected_condition: dict[str, Any]
    required_detections: tuple[str, ...]
    required_safety_state: dict[str, Any]
    required_operator_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    completion_criteria: tuple[str, ...]
    implementation_version: str


@dataclass(frozen=True)
class RunbookExerciseReportV1:
    exercise_report_id: str
    schema_version: str
    exercise_spec_ref: str
    detected_condition: dict[str, Any]
    alerts_raised: tuple[str, ...]
    operator_path: tuple[str, ...]
    reconciliation_performed: bool
    errors_deviations: tuple[str, ...]
    unsafe_actions_attempted: tuple[str, ...]
    unsafe_actions_blocked: tuple[str, ...]
    final_state: dict[str, Any]
    duration_ns: int
    result: str
    real_broker_submits: int
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduledReliabilityReviewV1:
    review_id: str
    schema_version: str
    review_window_start_ns: int
    review_window_end_ns: int
    slo_summary: dict[str, str]
    error_budget_status: str
    incidents_summary: tuple[str, ...]
    failovers_summary: tuple[str, ...]
    data_quality_summary: str
    broker_health: str
    reconciliation_health: str
    alert_delivery_health: str
    backup_dr_status: str
    resource_stability: str
    open_limitations: tuple[str, ...]
    recommendation: str
    implementation_version: str


@dataclass(frozen=True)
class SustainedPilotQualificationSpecV1:
    qualification_spec_id: str
    schema_version: str
    pilot_policy_ref: str
    minimum_observation_duration_ns: int
    required_market_sessions: int
    required_provider_health_samples: int
    required_reconciliation_checkpoints: int
    required_operational_reviews: int
    required_runbook_exercises: tuple[str, ...]
    slo_acceptance_criteria: tuple[str, ...]
    maximum_critical_incidents: int
    required_backup_freshness_ns: int
    required_zero_autonomy_invariants: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PilotObservationSegmentV1:
    segment_id: str
    start_ns: int
    end_ns: int
    runtime_version: str
    provider_configuration: dict[str, Any]
    health_summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SustainedPilotQualificationReportV1:
    report_id: str
    schema_version: str
    qualification_spec_ref: str
    pilot_run_ref: str
    actual_observation_duration_ns: int
    virtual_observation_duration_ns: int
    market_sessions_observed: int
    observation_segments: tuple[PilotObservationSegmentV1, ...]
    provider_uptime_summary: dict[str, float]
    provider_failovers: int
    provider_divergences: int
    degraded_mode_intervals: int
    slo_results: dict[str, str]
    alerts_summary: dict[str, int]
    broker_reconciliation_summary: str
    canary_sessions: int
    orders_count: int
    fills_count: int
    incidents_count: int
    runbook_exercise_results: dict[str, str]
    backup_dr_freshness: dict[str, Any]
    maintenance_restart_results: dict[str, str]
    resource_observations: dict[str, Any]
    policy_cap_compliance: bool
    final_pilot_state: str
    disposition: str
    limitations: tuple[str, ...]
    real_broker_side_effects_observed: int
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
