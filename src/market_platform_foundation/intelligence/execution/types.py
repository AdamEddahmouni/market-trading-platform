"""Execution policy, portfolio snapshot, and risk decision contracts (BUILD 22)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference, validate_id, validate_schema_version, validate_timestamp_ns

EXECUTION_IMPLEMENTATION_VERSION = "deterministic-paper-execution-risk-v1"


class ExecutionMode(StrEnum):
    PAPER = "PAPER"


class SizingPolicyKind(StrEnum):
    FIXED_FRACTION_NAV_WITH_CAPS = "FIXED_FRACTION_NAV_WITH_CAPS"


class RiskDecisionKind(StrEnum):
    APPROVE = "APPROVE"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    FAIL_CLOSED = "FAIL_CLOSED"


class RiskReasonCode(StrEnum):
    RISK_APPROVED = "RISK_APPROVED"
    SIZE_REDUCED = "SIZE_REDUCED"
    RISK_REJECTED = "RISK_REJECTED"
    FAIL_CLOSED = "FAIL_CLOSED"
    OPPORTUNITY_EXPIRED = "OPPORTUNITY_EXPIRED"
    OPPORTUNITY_MODE_NOT_ALLOWED = "OPPORTUNITY_MODE_NOT_ALLOWED"
    OPPORTUNITY_SIDE_INVALID = "OPPORTUNITY_SIDE_INVALID"
    PORTFOLIO_STATE_STALE = "PORTFOLIO_STATE_STALE"
    PORTFOLIO_INVALID = "PORTFOLIO_INVALID"
    REQUESTED_SIZE_TOO_SMALL = "REQUESTED_SIZE_TOO_SMALL"
    INSUFFICIENT_PAPER_CASH = "INSUFFICIENT_PAPER_CASH"
    MAX_TRADE_NOTIONAL = "MAX_TRADE_NOTIONAL"
    MAX_POSITION_NOTIONAL = "MAX_POSITION_NOTIONAL"
    MAX_SYMBOL_CONCENTRATION = "MAX_SYMBOL_CONCENTRATION"
    MAX_GROSS_EXPOSURE = "MAX_GROSS_EXPOSURE"
    MAX_NET_EXPOSURE = "MAX_NET_EXPOSURE"
    MAX_OPEN_ORDERS = "MAX_OPEN_ORDERS"
    DUPLICATE_OPPORTUNITY = "DUPLICATE_OPPORTUNITY"
    POSITION_REVERSAL_NOT_ALLOWED = "POSITION_REVERSAL_NOT_ALLOWED"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    SHORT_NOT_ALLOWED = "SHORT_NOT_ALLOWED"
    QUALITY_NOT_ELIGIBLE = "QUALITY_NOT_ELIGIBLE"
    EXECUTION_AUTHORITY_LIVE = "EXECUTION_AUTHORITY_LIVE"
    LIVE_POLICY_REJECTED = "LIVE_POLICY_REJECTED"
    RUNTIME_GOVERNANCE_DISABLED = "RUNTIME_GOVERNANCE_DISABLED"


@dataclass(frozen=True, slots=True)
class PaperPositionSnapshot:
    instrument_id: str
    symbol: str
    quantity: int
    market_value_minor: int

    def __post_init__(self) -> None:
        validate_id(self.instrument_id, field_name="instrument_id")
        if self.quantity == 0:
            raise ValueError("POSITION_QUANTITY_ZERO")


@dataclass(frozen=True, slots=True)
class PaperOpenOrderSnapshot:
    order_id: str
    instrument_id: str
    side: str
    quantity: int
    opportunity_id: str | None = None

    def __post_init__(self) -> None:
        validate_id(self.order_id, field_name="order_id")
        validate_id(self.instrument_id, field_name="instrument_id")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("OPEN_ORDER_SIDE_INVALID")
        if self.quantity <= 0:
            raise ValueError("OPEN_ORDER_QUANTITY_INVALID")


@dataclass(frozen=True, slots=True)
class ExposureSnapshot:
    gross_exposure_minor: int
    net_exposure_minor: int

    def __post_init__(self) -> None:
        if self.gross_exposure_minor < 0:
            raise ValueError("GROSS_EXPOSURE_INVALID")
        if self.gross_exposure_minor < abs(self.net_exposure_minor):
            raise ValueError("NET_EXCEEDS_GROSS")


@dataclass(frozen=True, slots=True)
class PaperPortfolioSnapshotV1:
    snapshot_id: str
    schema_version: str
    captured_at_ns: int
    cash_minor: int
    equity_minor: int
    currency: str
    price_scale: int
    positions: tuple[PaperPositionSnapshot, ...] = ()
    open_orders: tuple[PaperOpenOrderSnapshot, ...] = ()
    reserved_cash_minor: int = 0
    exposure: ExposureSnapshot | None = None
    realized_pnl_minor: int = 0
    unrealized_pnl_minor: int = 0
    start_of_day_equity_minor: int | None = None
    peak_equity_minor: int | None = None
    scenario_id: str | None = None
    mode: str = "ACTUAL_LIVE"
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.snapshot_id, field_name="snapshot_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.captured_at_ns, field_name="captured_at_ns")
        if self.equity_minor <= 0:
            raise ValueError("PORTFOLIO_EQUITY_INVALID")
        if self.cash_minor < 0:
            raise ValueError("PORTFOLIO_CASH_INVALID")


@dataclass(frozen=True, slots=True)
class ExecutionPolicyV1:
    execution_policy_id: str
    schema_version: str
    mode: ExecutionMode = ExecutionMode.PAPER
    sizing_policy: SizingPolicyKind = SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS
    trade_fraction_nav: float = 0.01
    max_trade_notional_minor: int | None = None
    max_trade_fraction_nav: float | None = None
    max_position_notional_minor: int | None = None
    max_position_fraction_nav: float | None = None
    max_symbol_concentration_fraction: float = 0.25
    max_gross_exposure_fraction: float = 1.0
    max_net_exposure_fraction: float = 1.0
    max_open_orders_per_symbol: int = 3
    max_total_open_orders: int = 10
    minimum_trade_notional_minor: int = 100
    minimum_quantity: int = 1
    daily_loss_limit_fraction: float | None = None
    allow_short: bool = False
    allow_position_reversal: bool = False
    allow_size_reduction: bool = True
    max_portfolio_snapshot_age_ns: int | None = None
    allowed_order_types: tuple[str, ...] = ("MARKET",)
    price_scale: int = 100
    currency: str = "USD"
    implementation_version: str = EXECUTION_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.execution_policy_id, field_name="execution_policy_id")
        validate_schema_version(self.schema_version)
        if self.mode != ExecutionMode.PAPER:
            raise ValueError("EXECUTION_POLICY_MODE_INVALID")
        if not 0.0 < self.trade_fraction_nav <= 1.0:
            raise ValueError("TRADE_FRACTION_NAV_INVALID")
        if not 0.0 < self.max_symbol_concentration_fraction <= 1.0:
            raise ValueError("MAX_SYMBOL_CONCENTRATION_INVALID")
        if not 0.0 < self.max_gross_exposure_fraction:
            raise ValueError("MAX_GROSS_EXPOSURE_FRACTION_INVALID")
        if not 0.0 < self.max_net_exposure_fraction:
            raise ValueError("MAX_NET_EXPOSURE_FRACTION_INVALID")
        if self.minimum_quantity <= 0:
            raise ValueError("MINIMUM_QUANTITY_INVALID")
        if self.minimum_trade_notional_minor < 0:
            raise ValueError("MINIMUM_TRADE_NOTIONAL_INVALID")


@dataclass(frozen=True, slots=True)
class RiskDecisionV1:
    risk_decision_id: str
    schema_version: str
    trade_proposal_id: str
    opportunity_id: str
    execution_policy_id: str
    portfolio_snapshot_id: str
    decision_time_ns: int
    requested_quantity: int
    requested_notional_minor: int
    approved_quantity: int
    approved_notional_minor: int
    decision: RiskDecisionKind
    reason_codes: tuple[RiskReasonCode, ...] = ()
    pre_trade_exposure: ExposureSnapshot | None = None
    post_trade_exposure: ExposureSnapshot | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.risk_decision_id, field_name="risk_decision_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.approved_quantity < 0 or self.approved_quantity > self.requested_quantity:
            raise ValueError("APPROVED_QUANTITY_INVALID")


@dataclass(frozen=True, slots=True)
class MarketQuoteV1:
    """Point-in-time quote for sizing and paper fill context."""

    instrument_id: str
    bid_minor: int
    ask_minor: int
    available_time_ns: int

    def __post_init__(self) -> None:
        validate_id(self.instrument_id, field_name="instrument_id")
        validate_timestamp_ns(self.available_time_ns, field_name="available_time_ns")
        if self.bid_minor <= 0 or self.ask_minor <= 0 or self.ask_minor < self.bid_minor:
            raise ValueError("MARKET_QUOTE_INVALID")

    @property
    def mid_minor(self) -> int:
        return (self.bid_minor + self.ask_minor) // 2


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
  proposal: "TradeProposalV1 | None"
  risk_decision: RiskDecisionV1 | None
  paper_submit: dict[str, Any] | None = None


__all__ = [
    "EXECUTION_IMPLEMENTATION_VERSION",
    "ExecutionMode",
    "ExecutionPolicyV1",
    "ExposureSnapshot",
    "MarketQuoteV1",
    "PaperExecutionResult",
    "PaperOpenOrderSnapshot",
    "PaperPortfolioSnapshotV1",
    "PaperPositionSnapshot",
    "RiskDecisionKind",
    "RiskDecisionV1",
    "RiskReasonCode",
    "SizingPolicyKind",
]
