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
