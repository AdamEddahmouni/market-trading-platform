"""Post-decision / post-trade learning records (analysis-only; no execution authority)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import ContractReference

TRADE_REVIEW_SCHEMA_VERSION = "intelligence/trade_review/1.0.0"
TRADE_REVIEW_IMPLEMENTATION_VERSION = "trade-review-foundation-v1"
TRADE_REVIEW_FOUNDATION_READY = "TRADE_REVIEW_FOUNDATION_READY"

_NON_EXECUTED_MODES = frozenset(
    {
        "REJECTED_OPPORTUNITY",
        "WATCHED_OPPORTUNITY",
    }
)
_EXECUTED_MODES = frozenset(
    {
        "PAPER_TRADE",
        "LIVE_TRADE",
    }
)


class TradeReviewMode(StrEnum):
    """How the reviewed subject relates to execution."""

    REJECTED_OPPORTUNITY = "REJECTED_OPPORTUNITY"
    WATCHED_OPPORTUNITY = "WATCHED_OPPORTUNITY"
    PAPER_TRADE = "PAPER_TRADE"
    LIVE_TRADE = "LIVE_TRADE"


@dataclass(frozen=True, slots=True)
class TradeExecutionAttribution:
    """Execution-linked metrics — only for PAPER_TRADE / LIVE_TRADE reviews."""

    order_refs: tuple[ContractReference, ...] = ()
    fill_refs: tuple[ContractReference, ...] = ()
    entry_price_minor: int | None = None
    exit_price_minor: int | None = None
    realized_pnl_minor: int | None = None
    mae_bps: float | None = None
    mfe_bps: float | None = None
    slippage_bps: float | None = None
    decision_to_submit_latency_ns: int | None = None
    exit_reason: str | None = None

    def __post_init__(self) -> None:
        if self.entry_price_minor is not None and self.entry_price_minor < 0:
            raise ValueError("TRADE_REVIEW_ENTRY_PRICE_INVALID")
        if self.exit_price_minor is not None and self.exit_price_minor < 0:
            raise ValueError("TRADE_REVIEW_EXIT_PRICE_INVALID")


@dataclass(frozen=True, slots=True)
class TradeReviewV1:
    """Canonical post-event learning record linking upstream intelligence by ID."""

    review_id: str
    schema_version: str
    review_mode: TradeReviewMode
    decision: str
    decision_time_ns: int
    created_at_ns: int
    opportunity_id: str | None = None
    strategy_id: str | None = None
    ftep_campaign: str | None = None
    ftep_session_id: str | None = None
    evidence_snapshot_refs: tuple[ContractReference, ...] = ()
    contradictions: tuple[str, ...] = ()
    risk_snapshot: dict[str, Any] | None = None
    preview_refs: tuple[ContractReference, ...] = ()
    execution_attribution: TradeExecutionAttribution | None = None
    execution_decision_trace_id: str | None = None
    tags: tuple[str, ...] = ()
    mistakes: tuple[str, ...] = ()
    notes: str = ""
    reflection: str = ""
    implementation_version: str = TRADE_REVIEW_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.review_id:
            raise ValueError("TRADE_REVIEW_ID_REQUIRED")
        if not self.decision or not str(self.decision).strip():
            raise ValueError("TRADE_REVIEW_DECISION_REQUIRED")
        if self.decision_time_ns < 0:
            raise ValueError("TRADE_REVIEW_DECISION_TIME_INVALID")
        if self.created_at_ns < 0:
            raise ValueError("TRADE_REVIEW_CREATED_AT_INVALID")
        mode = TradeReviewMode(str(self.review_mode))
        object.__setattr__(self, "review_mode", mode)
        if mode.value in _NON_EXECUTED_MODES:
            if self.execution_attribution is not None:
                raise ValueError("TRADE_REVIEW_EXECUTION_METRICS_NOT_APPLICABLE")
            if self.execution_decision_trace_id:
                raise ValueError("TRADE_REVIEW_EXECUTION_TRACE_NOT_APPLICABLE")
        if mode.value in _EXECUTED_MODES:
            if self.execution_attribution is None:
                raise ValueError("TRADE_REVIEW_EXECUTION_ATTRIBUTION_REQUIRED")
        if not str(self.schema_version).strip():
            raise ValueError("TRADE_REVIEW_SCHEMA_VERSION_INVALID")


def default_trade_review_schema_version() -> str:
    return TRADE_REVIEW_SCHEMA_VERSION


__all__ = [
    "TRADE_REVIEW_FOUNDATION_READY",
    "TRADE_REVIEW_IMPLEMENTATION_VERSION",
    "TRADE_REVIEW_SCHEMA_VERSION",
    "TradeExecutionAttribution",
    "TradeReviewMode",
    "TradeReviewV1",
    "default_trade_review_schema_version",
]
