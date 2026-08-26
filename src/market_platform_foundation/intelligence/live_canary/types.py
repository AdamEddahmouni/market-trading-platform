"""Live canary contracts (BUILD 29).

BUILD 29 authorizes only a temporary, explicitly human-approved micro-notional
live canary. It does not enable autonomous or generally available live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

LIVE_CANARY_SCHEMA_VERSION = "1"
LIVE_CANARY_IMPLEMENTATION_VERSION = "build29-v1"
LIVE_CANARY_PROGRAM_IMPLEMENTATION_VERSION = "build30-v1"

# Program defaults — frozen operational envelope, not sizing authority.
DEFAULT_MAX_PROGRAM_SESSIONS = 3
DEFAULT_MAX_PROGRAM_ORDER_COUNT = 3
DEFAULT_MAX_PROGRAM_NOTIONAL_MINOR = 75_00
DEFAULT_MAX_PROGRAM_REALIZED_LOSS_MINOR = 50_00
DEFAULT_PROGRAM_COOLDOWN_NS = 60_000_000_000
DEFAULT_PROGRAM_DURATION_NS = 86_400_000_000_000
DEFAULT_SESSION_MAX_DURATION_NS = 3_600_000_000_000
DEFAULT_STATUS_FEED_STALE_THRESHOLD_NS = 300_000_000_000

# Absolute micro-notional caps for first canary — not NAV-scaled.
DEFAULT_MAX_SINGLE_ORDER_NOTIONAL_MINOR = 25_00  # $25.00
DEFAULT_MAX_TOTAL_CANARY_NOTIONAL_MINOR = 25_00
DEFAULT_MAX_ORDER_COUNT = 1
DEFAULT_MAX_FILL_COUNT = 1
DEFAULT_AUTHORIZATION_DURATION_NS = 3_600_000_000_000  # 1 hour
DEFAULT_ORDER_CONFIRMATION_EXPIRY_NS = 300_000_000_000  # 5 minutes


class CanaryGovernanceState(StrEnum):
    LIVE_DISABLED = "LIVE_DISABLED"
    CANARY_PREPARED = "CANARY_PREPARED"
    CANARY_AUTHORIZED = "CANARY_AUTHORIZED"
    CANARY_ACTIVE = "CANARY_ACTIVE"
    CANARY_HALTED = "CANARY_HALTED"
    CANARY_COMPLETE = "CANARY_COMPLETE"


class CanaryDisposition(StrEnum):
    CANARY_NOT_EXECUTED = "CANARY_NOT_EXECUTED"
    CANARY_EXECUTED_CLEAN = "CANARY_EXECUTED_CLEAN"
    CANARY_EXECUTED_WITH_LIMITATIONS = "CANARY_EXECUTED_WITH_LIMITATIONS"
    CANARY_HALTED_SAFE = "CANARY_HALTED_SAFE"
    CANARY_INVALID_RECONCILIATION = "CANARY_INVALID_RECONCILIATION"
    CANARY_INVALID_EXECUTION_INTEGRITY = "CANARY_INVALID_EXECUTION_INTEGRITY"


class ProgramGovernanceState(StrEnum):
    PROGRAM_PREPARED = "PROGRAM_PREPARED"
    PROGRAM_ACTIVE = "PROGRAM_ACTIVE"
    SESSION_PREPARED = "SESSION_PREPARED"
    SESSION_AUTHORIZED = "SESSION_AUTHORIZED"
    SESSION_ACTIVE = "SESSION_ACTIVE"
    SESSION_RECONCILING = "SESSION_RECONCILING"
    SESSION_COMPLETE = "SESSION_COMPLETE"
    PROGRAM_PAUSED = "PROGRAM_PAUSED"
    PROGRAM_HALTED = "PROGRAM_HALTED"
    PROGRAM_COMPLETE = "PROGRAM_COMPLETE"


class ProgramDisposition(StrEnum):
    SUPERVISED_CANARY_PROGRAM_COMPLETE = "SUPERVISED_CANARY_PROGRAM_COMPLETE"
    SUPERVISED_CANARY_PROGRAM_COMPLETE_WITH_LIMITATIONS = (
        "SUPERVISED_CANARY_PROGRAM_COMPLETE_WITH_LIMITATIONS"
    )
    MORE_SUPERVISED_EVIDENCE_REQUIRED = "MORE_SUPERVISED_EVIDENCE_REQUIRED"
    PROGRAM_HALTED_SAFE = "PROGRAM_HALTED_SAFE"
    PROGRAM_INVALID_RECONCILIATION = "PROGRAM_INVALID_RECONCILIATION"
    PROGRAM_INVALID_EXECUTION_INTEGRITY = "PROGRAM_INVALID_EXECUTION_INTEGRITY"


class SessionDisposition(StrEnum):
    SESSION_NOT_EXECUTED = "SESSION_NOT_EXECUTED"
    SESSION_EXECUTED_CLEAN = "SESSION_EXECUTED_CLEAN"
    SESSION_EXECUTED_WITH_LIMITATIONS = "SESSION_EXECUTED_WITH_LIMITATIONS"
    SESSION_HALTED_SAFE = "SESSION_HALTED_SAFE"
    SESSION_INVALID_RECONCILIATION = "SESSION_INVALID_RECONCILIATION"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"


class IncidentSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentType(StrEnum):
    BROKER_DISCONNECT = "BROKER_DISCONNECT"
    ACCOUNT_ENVIRONMENT_CHANGED = "ACCOUNT_ENVIRONMENT_CHANGED"
    ACCOUNT_IDENTITY_MISMATCH = "ACCOUNT_IDENTITY_MISMATCH"
    AMBIGUOUS_SUBMISSION = "AMBIGUOUS_SUBMISSION"
    BROKER_ONLY_ORDER = "BROKER_ONLY_ORDER"
    LOCAL_ONLY_ORDER = "LOCAL_ONLY_ORDER"
    UNEXPECTED_FILL = "UNEXPECTED_FILL"
    UNKNOWN_POSITION = "UNKNOWN_POSITION"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    ORDER_STATE_MISMATCH = "ORDER_STATE_MISMATCH"
    DUPLICATE_ACK = "DUPLICATE_ACK"
    STATUS_FEED_STALE = "STATUS_FEED_STALE"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    AUTHORIZATION_VIOLATION_ATTEMPT = "AUTHORIZATION_VIOLATION_ATTEMPT"
    CAP_VIOLATION_ATTEMPT = "CAP_VIOLATION_ATTEMPT"
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    EXTERNAL_ACCOUNT_ACTIVITY = "EXTERNAL_ACCOUNT_ACTIVITY"


class IncidentState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    HALTED = "HALTED"


class IncidentAction(StrEnum):
    LOG_ONLY = "LOG_ONLY"
    PAUSE_PROGRAM = "PAUSE_PROGRAM"
    HALT_PROGRAM = "HALT_PROGRAM"
    BLOCK_NEW_SUBMITS = "BLOCK_NEW_SUBMITS"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class SubmissionState(StrEnum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMIT_ATTEMPTED = "SUBMIT_ATTEMPTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SUBMISSION_STATUS_UNKNOWN = "SUBMISSION_STATUS_UNKNOWN"
    REJECTED = "REJECTED"


class HumanApprovalSource(StrEnum):
    OPERATOR_CONSOLE = "OPERATOR_CONSOLE"
    GOVERNANCE_ARTIFACT = "GOVERNANCE_ARTIFACT"
    TEST_FIXTURE = "TEST_FIXTURE"


@dataclass(frozen=True)
class LiveCanaryPolicyV1:
    canary_policy_id: str
    schema_version: str
    broker: str
    account_ref: str
    account_environment: str
    allowed_asset_classes: tuple[str, ...]
    allowed_instruments: tuple[str, ...]
    allowed_sides: tuple[str, ...]
    allowed_order_types: tuple[str, ...]
    max_single_order_notional_minor: int
    max_total_canary_notional_minor: int
    max_net_live_exposure_minor: int
    max_gross_live_exposure_minor: int
    max_order_count: int
    max_fill_count: int
    allow_fractional: bool
    allow_margin: bool
    allow_short: bool
    allow_outside_rth: bool
    authorization_duration_ns: int
    max_order_lifetime_ns: int
    require_flat_start: bool
    require_flat_end: bool
    require_manual_authorization: bool
    require_manual_order_confirmation: bool
    required_broker_certification_ref: str
    required_execution_policy_ref: str
    required_runtime_activation_ref: str
    kill_switch_default: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanaryAuthorizationPreviewV1:
    preview_id: str
    schema_version: str
    canary_policy_ref: str
    broker: str
    account_environment: str
    account_fingerprint: str
    symbol_universe: tuple[str, ...]
    allowed_sides: tuple[str, ...]
    allowed_order_types: tuple[str, ...]
    max_single_order_notional_minor: int
    max_total_canary_notional_minor: int
    max_order_count: int
    authorization_duration_ns: int
    starting_positions_summary: tuple[dict[str, Any], ...]
    starting_open_orders_summary: tuple[dict[str, Any], ...]
    execution_policy_ref: str
    risk_policy_ref: str
    broker_certification_ref: str
    kill_switch_state: str
    known_limitations: tuple[str, ...]
    generated_at_ns: int
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HumanCanaryApprovalV1:
    approval_id: str
    schema_version: str
    preview_id: str
    preview_hash: str
    approved_at_ns: int
    approved_by: str
    approval_source: HumanApprovalSource
    approval_statement: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveOrderConfirmationV1:
    confirmation_id: str
    schema_version: str
    authorization_ref: str
    broker_order_intent_ref: str
    risk_decision_ref: str
    instrument_id: str
    side: str
    quantity: int
    order_type: str
    limit_price_minor: int | None
    estimated_max_notional_minor: int
    confirmation_time_ns: int
    expires_at_ns: int
    confirmed_by: str
    confirmation_source: HumanApprovalSource
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LivePortfolioSnapshotV1:
    snapshot_id: str
    schema_version: str
    as_of_ns: int
    broker: str
    account_ref: str
    account_fingerprint: str
    cash_minor: int
    positions: tuple[dict[str, Any], ...]
    open_orders: tuple[dict[str, Any], ...]
    known_fills: tuple[dict[str, Any], ...]
    gross_exposure_minor: int
    net_exposure_minor: int
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerSubmissionReceiptV1:
    submission_receipt_id: str
    schema_version: str
    order_intent_ref: str
    authorization_ref: str
    confirmation_ref: str
    client_order_id: str
    broker: str
    account_ref: str
    submit_attempt_time_ns: int
    payload_hash: str
    transport_result: str
    broker_order_id: str | None
    ack_time_ns: int | None
    raw_response_hash: str | None
    submission_state: SubmissionState
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveFillReceiptV1:
    fill_receipt_id: str
    schema_version: str
    broker_order_id: str
    client_order_id: str
    broker_fill_id: str
    fill_time_ns: int
    quantity: int
    price_minor: int
    fees_minor: int | None
    liquidity_metadata: dict[str, Any]
    source: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanaryRunV1:
    canary_run_id: str
    schema_version: str
    source_build28_ref: str
    source_build27_ref: str
    source_head: str
    canary_policy_ref: str
    authorization_ref: str | None
    broker: str
    account_ref: str
    start_time_ns: int
    end_time_ns: int | None
    allowed_order_count: int
    allowed_notional_minor: int
    initial_reconciliation_ref: str | None
    initial_portfolio_ref: str | None
    runtime_activation_ref: str
    execution_policy_ref: str
    champion_ref: str | None
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanaryQualificationReportV1:
    report_id: str
    schema_version: str
    canary_run_ref: str
    authorization_ref: str | None
    opportunities_observed: int
    orders_confirmed: int
    submit_attempts: int
    acks: int
    fills: int
    cancels: int
    rejections: int
    real_notional_minor: int
    max_exposure_minor: int
    reconciliation_health: str
    broker_health: str
    kill_switch_events: tuple[str, ...]
    authorization_lifecycle: tuple[str, ...]
    unexpected_broker_activity: tuple[str, ...]
    errors: tuple[str, ...]
    final_portfolio_ref: str | None
    final_reconciliation_ref: str | None
    flat_end_status: str
    disposition: CanaryDisposition
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanaryProgramPolicyV1:
    program_policy_id: str
    schema_version: str
    allowed_brokers: tuple[str, ...]
    allowed_accounts: tuple[str, ...]
    allowed_asset_classes: tuple[str, ...]
    allowed_canary_policy_refs: tuple[str, ...]
    max_sessions: int
    max_program_order_count: int
    max_program_live_notional_minor: int
    max_program_realized_loss_minor: int
    max_consecutive_incidents: int
    require_fresh_authorization_per_session: bool
    require_order_confirmation: bool
    require_clean_reconciliation_before_session: bool
    require_clean_reconciliation_after_session: bool
    minimum_cooldown_between_sessions_ns: int
    incident_halt_rules: tuple[str, ...]
    program_effective_from_ns: int
    program_effective_until_ns: int
    manual_resume_required: bool
    session_max_duration_ns: int
    status_feed_stale_threshold_ns: int
    invalidate_confirmation_on_restart: bool
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanaryProgramRunV1:
    program_run_id: str
    schema_version: str
    source_build29_ref: str
    source_build28_ref: str
    source_head: str
    program_policy_ref: str
    broker_certification_refs: tuple[str, ...]
    starting_reconciliation_ref: str | None
    starting_portfolio_ref: str | None
    program_start_ns: int
    program_end_ns: int | None
    allowed_session_count: int
    session_refs: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionIncidentV1:
    incident_id: str
    schema_version: str
    incident_type: IncidentType
    severity: IncidentSeverity
    state: IncidentState
    session_ref: str | None
    program_run_ref: str | None
    detected_at_ns: int
    description: str
    resolution_evidence_ref: str | None
    resolved_at_ns: int | None
    actions_taken: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveIncidentResponsePolicyV1:
    response_policy_id: str
    schema_version: str
    info_actions: tuple[str, ...]
    warning_actions: tuple[str, ...]
    critical_actions: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveOperationalResumeApprovalV1:
    resume_approval_id: str
    schema_version: str
    incident_refs: tuple[str, ...]
    resolution_evidence_ref: str
    reconciliation_checkpoint_ref: str
    program_run_ref: str
    approved_at_ns: int
    approved_by: str
    approval_source: HumanApprovalSource
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveReconciliationCheckpointV1:
    checkpoint_id: str
    schema_version: str
    as_of_ns: int
    broker: str
    account_ref: str
    known_local_orders: tuple[str, ...]
    broker_open_orders: tuple[str, ...]
    known_local_fills: tuple[str, ...]
    broker_fills: tuple[str, ...]
    local_positions: tuple[dict[str, Any], ...]
    broker_positions: tuple[dict[str, Any], ...]
    matched: tuple[str, ...]
    local_only: tuple[str, ...]
    broker_only: tuple[str, ...]
    conflicts: tuple[str, ...]
    health: str
    incident_refs: tuple[str, ...]
    session_ref: str | None
    program_run_ref: str | None
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanarySessionReportV1:
    session_report_id: str
    schema_version: str
    session_ref: str
    program_run_ref: str
    authorization_ref: str | None
    confirmations: tuple[str, ...]
    submit_attempts: int
    acks: int
    fills: int
    rejections: int
    cancels: int
    max_exposure_minor: int
    fees_minor: int
    incident_refs: tuple[str, ...]
    reconciliation_checkpoint_ref: str | None
    final_authorization_state: str
    disposition: SessionDisposition
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveCanaryProgramReportV1:
    program_report_id: str
    schema_version: str
    program_run_ref: str
    program_policy_ref: str
    session_refs: tuple[str, ...]
    sessions_prepared: int
    sessions_authorized: int
    sessions_executed: int
    sessions_clean: int
    sessions_halted: int
    total_orders: int
    total_fills: int
    aggregate_notional_minor: int
    fees_minor: int
    incident_counts: dict[str, int]
    reconciliation_outcomes: tuple[str, ...]
    restart_events: int
    external_activity_detected: bool
    program_cap_usage: dict[str, int]
    final_kill_switch_state: str
    disposition: ProgramDisposition
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
