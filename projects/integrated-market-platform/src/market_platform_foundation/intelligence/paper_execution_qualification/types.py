"""Prospective paper execution qualification contracts (BUILD 27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION = "1"
PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION = "build27-v1"

DEFAULT_INSTRUMENT_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "NVDA",
    "MSFT",
    "AMD",
    "TSLA",
    "SPY",
    "QQQ",
)

DEFAULT_TARGET_KIND = "direction_up_down"
DEFAULT_HORIZON_NS = 5 * 60 * 1_000_000_000
DEFAULT_MINIMUM_OPPORTUNITIES = 1
DEFAULT_MINIMUM_RISK_DECISIONS = 1
DEFAULT_MINIMUM_ORDERS = 1
DEFAULT_MINIMUM_FILLS = 1
DEFAULT_MINIMUM_DURATION_NS = 60 * 60 * 1_000_000_000
DEFAULT_INITIAL_CASH_MINOR = 100_000_00


class QualificationKind(StrEnum):
    PROSPECTIVE_PAPER_EXECUTION = "PROSPECTIVE_PAPER_EXECUTION"


class PaperEvidenceClass(StrEnum):
    FORWARD_PAPER = "FORWARD_PAPER"
    REPLAY_PAPER = "REPLAY_PAPER"
    COUNTERFACTUAL_PAPER = "COUNTERFACTUAL_PAPER"


class ExecutionIntegrityStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    PENDING = "PENDING"


class ExecutionIntegrityFailureCode(StrEnum):
    REPLAY_MASQUERADING_AS_FORWARD = "REPLAY_MASQUERADING_AS_FORWARD"
    COUNTERFACTUAL_MASQUERADING_AS_FORWARD = "COUNTERFACTUAL_MASQUERADING_AS_FORWARD"
    NO_FORWARD_LINEAGE = "NO_FORWARD_LINEAGE"
    EXPIRED_OPPORTUNITY_ORDER = "EXPIRED_OPPORTUNITY_ORDER"
    FUTURE_QUOTE_FILL = "FUTURE_QUOTE_FILL"
    TERMINAL_PRICE_AS_FILL = "TERMINAL_PRICE_AS_FILL"
    OPTIMISTIC_MID_FILL = "OPTIMISTIC_MID_FILL"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    RISK_WITHOUT_DECISION = "RISK_WITHOUT_DECISION"
    LIVE_EXECUTION_DETECTED = "LIVE_EXECUTION_DETECTED"
    POLICY_CHANGED_MID_RUN = "POLICY_CHANGED_MID_RUN"
    BUILD26_LINEAGE_BROKEN = "BUILD26_LINEAGE_BROKEN"


class PaperQualificationDisposition(StrEnum):
    PAPER_EXECUTION_QUALIFIED = "PAPER_EXECUTION_QUALIFIED"
    PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS = "PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS"
    INSUFFICIENT_PAPER_EXECUTION_EVIDENCE = "INSUFFICIENT_PAPER_EXECUTION_EVIDENCE"
    INVALID_EXECUTION_INTEGRITY = "INVALID_EXECUTION_INTEGRITY"
    INVALID_RISK_INTEGRITY = "INVALID_RISK_INTEGRITY"
    INVALID_FILL_REALISM = "INVALID_FILL_REALISM"
    INVALID_ACCOUNTING_INTEGRITY = "INVALID_ACCOUNTING_INTEGRITY"


class FillRealismLimitation(StrEnum):
    QUEUE_POSITION_UNMODELED = "QUEUE_POSITION_UNMODELED"
    PARTIAL_FILLS_MODELED = "PARTIAL_FILLS_MODELED"
    MARKET_IMPACT_UNMODELED = "MARKET_IMPACT_UNMODELED"
    ZERO_FEES = "ZERO_FEES"
    FIXED_SLIPPAGE = "FIXED_SLIPPAGE"
    BAR_CONSERVATIVE_FILL = "BAR_CONSERVATIVE_FILL"
    LIMITED_DEPTH = "LIMITED_DEPTH"


@dataclass(frozen=True)
class InitialPaperPortfolioStateV1:
    state_id: str
    schema_version: str
    initial_cash_minor: int
    initial_equity_minor: int
    currency: str
    price_scale: int
    allow_short: bool
    margin_policy: str
    initial_positions: tuple[dict[str, Any], ...] = ()
    initial_open_orders: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionQualificationSpecV1:
    qualification_spec_id: str
    schema_version: str
    source_build26_ref: str
    source_release_candidate_ref: str
    source_head: str
    contract_inventory_hash: str
    qualification_kind: QualificationKind
    allowed_forward_qualification_runs: tuple[str, ...]
    instrument_universe: tuple[str, ...]
    target_kind: str
    horizon_ns: int
    opportunity_policy_ref: str
    execution_policy_ref: str
    fill_policy_ref: str
    fee_policy_ref: str
    initial_portfolio_state_ref: str
    minimum_opportunities: int
    minimum_risk_decisions: int
    minimum_orders: int
    minimum_fills: int
    minimum_duration_ns: int
    required_data_mode: str
    required_execution_mode: str
    required_execution_authority: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionQualificationRunV1:
    qualification_run_id: str
    schema_version: str
    qualification_spec_ref: str
    source_build26_ref: str
    source_release_candidate_ref: str
    source_head: str
    forward_qualification_run_ref: str | None
    runtime_activation_ref: str | None
    champion_assignment_ref: str | None
    opportunity_policy_ref: str
    execution_policy_ref: str
    fill_policy_ref: str
    initial_portfolio_state_ref: str
    provider_capability_snapshot: tuple[Any, ...]
    instrument_universe: tuple[str, ...]
    run_start_ns: int
    run_end_ns: int | None
    data_mode: str
    execution_mode: str
    execution_authority: str
    implementation_version: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionReceiptV1:
    receipt_id: str
    schema_version: str
    opportunity_id: str
    forecast_id: str
    forward_receipt_ref: str | None
    trade_proposal_id: str
    risk_decision_id: str
    paper_order_id: str | None
    fill_id: str | None
    decision_time_ns: int
    fill_time_ns: int | None
    qualification_run_ref: str
    evidence_class: PaperEvidenceClass
    execution_integrity_status: ExecutionIntegrityStatus
    integrity_failure_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionFunnelCountsV1:
    forecasts_evaluated: int = 0
    opportunity_assessments: int = 0
    opportunities_emitted: int = 0
    trade_proposals: int = 0
    risk_approvals: int = 0
    risk_reductions: int = 0
    risk_rejections: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    orders_expired: int = 0
    no_fill_count: int = 0
    attrition_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionQualificationReportV1:
    qualification_report_id: str
    schema_version: str
    qualification_spec_ref: str
    qualification_run_ref: str
    source_forward_qualification_refs: tuple[str, ...]
    source_release_candidate_ref: str
    evaluation_as_of_ns: int
    funnel_counts: ExecutionFunnelCountsV1
    execution_realism_assessment: dict[str, Any]
    accounting_integrity_assessment: dict[str, Any]
    risk_integrity_assessment: dict[str, Any]
    idempotency_assessment: dict[str, Any]
    paper_pnl_diagnostics: dict[str, Any]
    provider_data_quality_summary: dict[str, Any]
    governance_incident_summary: dict[str, Any]
    execution_integrity_status: ExecutionIntegrityStatus
    execution_integrity_failures: tuple[str, ...]
    qualification_disposition: PaperQualificationDisposition
    disposition_reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    lineage: dict[str, Any]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
