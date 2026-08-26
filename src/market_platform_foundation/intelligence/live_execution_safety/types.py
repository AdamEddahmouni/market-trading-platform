"""Live execution safety gate contracts (BUILD 28).

BUILD 28 certifies the pre-live execution boundary with zero real order
submissions. No enabled live authorization may be produced in production
configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

LIVE_EXECUTION_SAFETY_SCHEMA_VERSION = "1"
LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION = "build28-v1"

# Certified US cash equities only in BUILD 28 scope.
CERTIFIED_ASSET_CLASSES: tuple[str, ...] = ("US_EQUITY",)
CERTIFIED_ORDER_TYPES: tuple[str, ...] = ("MARKET", "LIMIT")


class AccountEnvironment(StrEnum):
    SIMULATED = "SIMULATED"
    PAPER = "PAPER"
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"


class BrokerCapabilityStatus(StrEnum):
    MARKET_DATA_ONLY = "MARKET_DATA_ONLY"
    PAPER_ONLY = "PAPER_ONLY"
    LIVE_CAPABLE_BUT_DISABLED = "LIVE_CAPABLE_BUT_DISABLED"
    LIVE_UNCERTIFIED = "LIVE_UNCERTIFIED"
    LIVE_CERTIFIABLE_DRY_RUN = "LIVE_CERTIFIABLE_DRY_RUN"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"


class CertificationMode(StrEnum):
    ZERO_SUBMIT = "ZERO_SUBMIT"


class BrokerCertificationDisposition(StrEnum):
    ZERO_SUBMIT_SAFETY_CERTIFIED = "ZERO_SUBMIT_SAFETY_CERTIFIED"
    ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS = "ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS"
    INSUFFICIENT_BROKER_CAPABILITY = "INSUFFICIENT_BROKER_CAPABILITY"
    INVALID_EXECUTION_GATE = "INVALID_EXECUTION_GATE"
    INVALID_RECONCILIATION = "INVALID_RECONCILIATION"


class LiveAuthorizationState(StrEnum):
    DISABLED = "DISABLED"
    DESIGN_ONLY = "DESIGN_ONLY"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    # Exists for contract completeness; BUILD 28 must never create ENABLED.
    ENABLED = "ENABLED"


class LiveGateDecisionKind(StrEnum):
    ALLOW_DRY_RUN = "ALLOW_DRY_RUN"
    BLOCK = "BLOCK"
    FAIL_CLOSED = "FAIL_CLOSED"
    # Future value — unreachable in BUILD 28 production configuration.
    ALLOW_LIVE_SUBMIT = "ALLOW_LIVE_SUBMIT"


class LiveGateReasonCode(StrEnum):
    DRY_RUN_ALLOWED = "DRY_RUN_ALLOWED"
    LIVE_AUTHORIZATION_MISSING = "LIVE_AUTHORIZATION_MISSING"
    LIVE_AUTHORIZATION_DISABLED = "LIVE_AUTHORIZATION_DISABLED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    AUTHORIZATION_SCOPE_MISMATCH = "AUTHORIZATION_SCOPE_MISMATCH"
    BROKER_NOT_CERTIFIED = "BROKER_NOT_CERTIFIED"
    BROKER_ENVIRONMENT_UNKNOWN = "BROKER_ENVIRONMENT_UNKNOWN"
    BROKER_ENVIRONMENT_LIVE_BLOCKED_BY_BUILD28 = "BROKER_ENVIRONMENT_LIVE_BLOCKED_BY_BUILD28"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    RUNTIME_NOT_LIVE_AUTHORIZED = "RUNTIME_NOT_LIVE_AUTHORIZED"
    RISK_NOT_APPROVED = "RISK_NOT_APPROVED"
    OPPORTUNITY_EXPIRED = "OPPORTUNITY_EXPIRED"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"
    ORDER_TYPE_NOT_ALLOWED = "ORDER_TYPE_NOT_ALLOWED"
    INSTRUMENT_NOT_ALLOWED = "INSTRUMENT_NOT_ALLOWED"
    SIDE_NOT_ALLOWED = "SIDE_NOT_ALLOWED"
    NOTIONAL_LIMIT_EXCEEDED = "NOTIONAL_LIMIT_EXCEEDED"
    BROKER_UNHEALTHY = "BROKER_UNHEALTHY"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    RECONCILIATION_UNHEALTHY = "RECONCILIATION_UNHEALTHY"
    DUPLICATE_CLIENT_ORDER_ID = "DUPLICATE_CLIENT_ORDER_ID"
    RUNTIME_GOVERNANCE_DISABLED = "RUNTIME_GOVERNANCE_DISABLED"
    BUILD28_LIVE_SUBMIT_FORBIDDEN = "BUILD28_LIVE_SUBMIT_FORBIDDEN"


class KillSwitchState(StrEnum):
    ACTIVE_BLOCK = "ACTIVE_BLOCK"
    INACTIVE = "INACTIVE"


class BrokerOrderStateKind(StrEnum):
    CREATED = "CREATED"
    DRY_RUN_VALIDATED = "DRY_RUN_VALIDATED"
    SUBMISSION_PENDING = "SUBMISSION_PENDING"
    SUBMISSION_STATUS_UNKNOWN = "SUBMISSION_STATUS_UNKNOWN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ReconciliationHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class LiveSafetyDisposition(StrEnum):
    PRELIVE_SAFETY_GATE_COMPLETE = "PRELIVE_SAFETY_GATE_COMPLETE"
    PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS = "PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS"
    NOT_READY_FOR_LIVE_AUTHORIZATION = "NOT_READY_FOR_LIVE_AUTHORIZATION"
    INVALID = "INVALID"


class LiveAuditEventKind(StrEnum):
    GATE_EVALUATED = "GATE_EVALUATED"
    DRY_RUN_TRANSLATED = "DRY_RUN_TRANSLATED"
    PREVIEW_REQUESTED = "PREVIEW_REQUESTED"
    PREVIEW_RESULT = "PREVIEW_RESULT"
    SUBMIT_BLOCKED = "SUBMIT_BLOCKED"
    KILL_SWITCH_BLOCKED = "KILL_SWITCH_BLOCKED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    AMBIGUOUS_SUBMISSION = "AMBIGUOUS_SUBMISSION"
    CANCEL_DRY_RUN = "CANCEL_DRY_RUN"


@dataclass(frozen=True)
class LiveExecutionAuthorizationV1:
    """Future live authorization contract — BUILD 28 never creates ENABLED."""

    authorization_id: str
    schema_version: str
    scope: str
    broker: str
    account_ref: str
    allowed_instruments: tuple[str, ...]
    allowed_asset_classes: tuple[str, ...]
    allowed_sides: tuple[str, ...]
    allowed_order_types: tuple[str, ...]
    max_order_notional_minor: int
    max_daily_notional_minor: int
    max_position_notional_minor: int
    max_open_orders: int
    effective_from_ns: int
    effective_until_ns: int
    required_runtime_activation_ref: str
    required_execution_policy_ref: str
    required_risk_policy_ref: str
    authorization_state: LiveAuthorizationState
    issued_by: str
    reason: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionKillSwitchV1:
    kill_switch_id: str
    schema_version: str
    scope: str
    state: KillSwitchState
    reason: str
    effective_from_ns: int
    source: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerCapabilityCertificationV1:
    certification_id: str
    schema_version: str
    broker: str
    adapter_version: str
    asset_classes: tuple[str, ...]
    supports_market_data: bool
    supports_order_preview: bool
    supports_what_if: bool
    supports_paper: bool
    supports_live_transport: bool
    supports_cancel: bool
    supports_replace: bool
    account_environment: AccountEnvironment
    account_identity_available: bool
    client_order_id_support: bool
    idempotency_support: bool
    certification_mode: CertificationMode
    tested_capabilities: tuple[str, ...]
    untested_capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    disposition: BrokerCertificationDisposition
    implementation_version: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerOrderIntentV1:
    broker_order_intent_id: str
    schema_version: str
    trade_proposal_ref: str
    risk_decision_ref: str
    execution_policy_ref: str
    instrument_id: str
    side: str
    quantity: int
    order_type: str
    limit_price_minor: int | None
    stop_price_minor: int | None
    time_in_force: str
    client_order_id: str
    expires_at_ns: int
    mode: str
    broker_target: str
    account_environment: AccountEnvironment
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerExecutionHealthV1:
    health_id: str
    schema_version: str
    broker: str
    account_environment: AccountEnvironment
    adapter_loaded: bool
    connection_available: bool
    environment_identified: bool
    account_resolved: bool
    permissions_observable: bool
    preview_endpoint_available: bool
    order_status_feed_available: bool
    reconciliation_healthy: bool
    disposition: ReconciliationHealthState
    as_of_ns: int
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerReconciliationSnapshotV1:
    snapshot_id: str
    schema_version: str
    broker: str
    account_environment: AccountEnvironment
    as_of_ns: int
    local_open_intents: tuple[str, ...]
    broker_open_orders: tuple[str, ...]
    local_known_fills: tuple[str, ...]
    broker_fills: tuple[str, ...]
    matched: tuple[str, ...]
    local_only: tuple[str, ...]
    broker_only: tuple[str, ...]
    conflicts: tuple[str, ...]
    health_state: ReconciliationHealthState
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionGateDecisionV1:
    gate_decision_id: str
    schema_version: str
    decision_time_ns: int
    runtime_activation_ref: str | None
    authorization_ref: str | None
    broker_certification_ref: str | None
    opportunity_ref: str | None
    trade_proposal_ref: str | None
    risk_decision_ref: str | None
    broker_health_ref: str | None
    kill_switch_ref: str | None
    broker: str
    account_environment: AccountEnvironment
    requested_order_intent_hash: str | None
    decision: LiveGateDecisionKind
    reason_codes: tuple[LiveGateReasonCode, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DryRunTransportResultV1:
    result_id: str
    schema_version: str
    broker: str
    client_order_id: str
    payload_hash: str
    provider_payload: dict[str, Any]
    network_submit_performed: bool
    real_submit_count: int
    broker_order_state: BrokerOrderStateKind
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionAuditEventV1:
    event_id: str
    schema_version: str
    event_kind: LiveAuditEventKind
    event_time_ns: int
    broker: str
    account_environment: AccountEnvironment
    subject_ref: str | None
    reason_codes: tuple[str, ...] = ()
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerDryRunCertificationReportV1:
    report_id: str
    schema_version: str
    broker_certification_ref: str
    execution_gate_policy_ref: str
    adapter_version: str
    supported_instruments: tuple[str, ...]
    supported_order_types: tuple[str, ...]
    translation_tests_passed: int
    pre_submit_validation_tests_passed: int
    idempotency_tests_passed: int
    transport_failure_tests_passed: int
    reconciliation_tests_passed: int
    kill_switch_tests_passed: int
    restart_tests_passed: int
    real_submit_count: int
    real_cancel_count: int
    real_replace_count: int
    disposition: BrokerCertificationDisposition
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionSafetyReportV1:
    report_id: str
    schema_version: str
    source_build27_ref: str
    source_build26_ref: str
    source_release_candidate_ref: str
    source_head: str
    broker_certification_refs: tuple[str, ...]
    dry_run_report_refs: tuple[str, ...]
    evaluation_as_of_ns: int
    system_disposition: LiveSafetyDisposition
    real_submit_count: int
    real_cancel_count: int
    real_replace_count: int
    limitations: tuple[str, ...]
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveExecutionSafetySpecV1:
    spec_id: str
    schema_version: str
    source_build27_ref: str
    source_build26_ref: str
    source_release_candidate_ref: str
    source_head: str
    contract_inventory_hash: str
    certification_mode: CertificationMode
    certified_asset_classes: tuple[str, ...]
    certified_order_types: tuple[str, ...]
    required_brokers: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
