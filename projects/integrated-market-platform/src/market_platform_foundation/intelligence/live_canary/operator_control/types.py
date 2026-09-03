"""Operator control plane contracts (BUILD 31).

Derived read models and audit artifacts — never competing sources of truth for
portfolio, authorization, order state, risk, or incident status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

OPERATOR_CONTROL_SCHEMA_VERSION = "1"
OPERATOR_CONTROL_IMPLEMENTATION_VERSION = "build31-v1"
BUILD31_KNOWN_LIMITATIONS = (
    "single-user/local operator control plane only",
    "incident drills use fixtures and mock transports only",
    "no mobile operator UI",
    "no external pager or push notification delivery",
    "replace-order controls intentionally absent (NOT CERTIFIED)",
    "no emergency liquidation automation",
    "role enforcement remains MODEL_ONLY_NOT_ENFORCED",
)


class OperatorActionType(StrEnum):
    PREPARE_SESSION_AUTHORIZATION = "PREPARE_SESSION_AUTHORIZATION"
    AUTHORIZE_SESSION = "AUTHORIZE_SESSION"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    ACTIVATE_KILL_SWITCH = "ACTIVATE_KILL_SWITCH"
    REVOKE_AUTHORIZATION = "REVOKE_AUTHORIZATION"
    ACKNOWLEDGE_INCIDENT = "ACKNOWLEDGE_INCIDENT"
    SUBMIT_RESOLUTION_EVIDENCE = "SUBMIT_RESOLUTION_EVIDENCE"
    REQUEST_RESUME_REVIEW = "REQUEST_RESUME_REVIEW"
    APPROVE_RESUME = "APPROVE_RESUME"


class OperatorNextAction(StrEnum):
    PREPARE_SESSION = "PREPARE_SESSION"
    AUTHORIZE_SESSION = "AUTHORIZE_SESSION"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    ACTIVATE_KILL_SWITCH = "ACTIVATE_KILL_SWITCH"
    REVOKE_AUTHORIZATION = "REVOKE_AUTHORIZATION"
    ACKNOWLEDGE_INCIDENT = "ACKNOWLEDGE_INCIDENT"
    BEGIN_RECONCILIATION = "BEGIN_RECONCILIATION"
    REQUEST_RESUME_REVIEW = "REQUEST_RESUME_REVIEW"
    APPROVE_RESUME = "APPROVE_RESUME"
    REVIEW_PROGRAM_HISTORY = "REVIEW_PROGRAM_HISTORY"


class ExecutionModeLabel(StrEnum):
    PAPER = "PAPER"
    LIVE_CANARY = "LIVE_CANARY"


class AuditReviewDisposition(StrEnum):
    CLEAN = "CLEAN"
    CLEAN_WITH_LIMITATIONS = "CLEAN_WITH_LIMITATIONS"
    REQUIRES_FOLLOWUP = "REQUIRES_FOLLOWUP"
    INVALID_RECONCILIATION = "INVALID_RECONCILIATION"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"


class OperatorQualificationDisposition(StrEnum):
    OPERATOR_CONTROL_PLANE_QUALIFIED = "OPERATOR_CONTROL_PLANE_QUALIFIED"
    OPERATOR_CONTROL_PLANE_QUALIFIED_WITH_LIMITATIONS = (
        "OPERATOR_CONTROL_PLANE_QUALIFIED_WITH_LIMITATIONS"
    )
    INCIDENT_WORKFLOW_INCOMPLETE = "INCIDENT_WORKFLOW_INCOMPLETE"
    RECONCILIATION_UI_INVALID = "RECONCILIATION_UI_INVALID"
    UNSAFE_OPERATOR_ACTION_PATH = "UNSAFE_OPERATOR_ACTION_PATH"


class DrillResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class OperatorControlSnapshotV1:
    snapshot_id: str
    schema_version: str
    as_of_ns: int
    execution_mode_label: str
    live_blocked: bool
    block_reasons: tuple[str, ...]
    runtime_governance_state: str
    program_state: str | None
    session_state: str | None
    program_run_ref: str | None
    session_ref: str | None
    broker: str | None
    account_environment: str | None
    account_fingerprint: str | None
    broker_health: str
    reconciliation_health: str
    kill_switch_global: str
    kill_switch_program: str
    kill_switch_session: str
    authorization_status: str | None
    authorization_expires_at_ns: int | None
    pending_confirmation_refs: tuple[str, ...]
    live_positions: tuple[dict[str, Any], ...]
    open_broker_orders: tuple[dict[str, Any], ...]
    ambiguous_states: tuple[str, ...]
    program_cap_usage: dict[str, int]
    program_cap_remaining: dict[str, int]
    session_cap_remaining: dict[str, int]
    incident_summary: dict[str, int]
    unresolved_critical_incidents: tuple[str, ...]
    allowed_next_actions: tuple[str, ...]
    action_queue: tuple[dict[str, Any], ...]
    source_refs: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorActionReceiptV1:
    action_receipt_id: str
    schema_version: str
    action_type: str
    target_refs: tuple[str, ...]
    operator_action_time_ns: int
    precondition_snapshot_ref: str
    result_refs: tuple[str, ...]
    success: bool
    reason_codes: tuple[str, ...]
    request_id: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorAuditTimelineEventV1:
    event_id: str
    schema_version: str
    event_family: str
    event_type: str
    event_time_ns: int
    recorded_at_ns: int
    source_ref: str
    summary: str
    blocking: bool
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorAuditTimelineV1:
    timeline_id: str
    schema_version: str
    as_of_ns: int
    program_run_ref: str | None
    session_ref: str | None
    events: tuple[OperatorAuditTimelineEventV1, ...]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditReviewReportV1:
    review_report_id: str
    schema_version: str
    program_run_ref: str | None
    session_ref: str | None
    window_start_ns: int
    window_end_ns: int
    authorization_summary: dict[str, Any]
    human_action_summary: tuple[dict[str, Any], ...]
    orders_fills_summary: dict[str, Any]
    incidents_summary: dict[str, Any]
    reconciliation_summary: dict[str, Any]
    kill_switch_summary: dict[str, Any]
    policy_cap_compliance: dict[str, Any]
    unexpected_events: tuple[str, ...]
    unresolved_items: tuple[str, ...]
    disposition: AuditReviewDisposition
    source_refs: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IncidentDrillSpecV1:
    drill_spec_id: str
    schema_version: str
    scenario: str
    initial_state: dict[str, Any]
    injected_incident: dict[str, Any]
    expected_alerts: tuple[str, ...]
    expected_blocked_actions: tuple[str, ...]
    expected_operator_workflow: tuple[str, ...]
    expected_final_state: dict[str, Any]
    timeout_expectation_ns: int | None
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IncidentDrillReportV1:
    drill_report_id: str
    schema_version: str
    drill_spec_ref: str
    initial_state: dict[str, Any]
    injected_fault: dict[str, Any]
    observed_alerts: tuple[str, ...]
    operator_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    final_state: dict[str, Any]
    deviations: tuple[str, ...]
    result: DrillResult
    real_broker_submits: int
    real_broker_cancels: int
    real_broker_replaces: int
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorControlPlaneQualificationReportV1:
    report_id: str
    schema_version: str
    build31_source_ref: str
    build30_source_ref: str
    read_model_results: dict[str, str]
    authorization_ux_results: dict[str, str]
    confirmation_safety_results: dict[str, str]
    kill_switch_results: dict[str, str]
    incident_workflow_results: dict[str, str]
    reconciliation_results: dict[str, str]
    audit_trace_results: dict[str, str]
    stale_view_results: dict[str, str]
    idempotency_results: dict[str, str]
    drill_results: dict[str, str]
    security_results: dict[str, str]
    real_broker_side_effects_observed: int
    disposition: OperatorQualificationDisposition
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
