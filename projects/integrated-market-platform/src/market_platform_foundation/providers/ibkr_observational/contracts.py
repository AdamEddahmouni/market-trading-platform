"""Canonical IBKR observational contracts (G6).

Provider-agnostic-in-intent state vocabulary for the IBKR observational
adapter. These are IBKR-specific *lifecycle* contracts (connection,
subscription, entitlement, error categories); the *market-data* contracts stay
canonical (``order_flow.order_book.DepthUpdate`` / the store quote state).

Truthfulness rules enforced here:

- ``EntitlementState.UNKNOWN`` is never mapped to ``ENTITLED``.
- ``EntitlementState.DELAYED`` is never presented as real-time.
- ``sequence`` on a ``DepthUpdate`` is only ever a real provider sequence;
  IBKR supplies none, so the adapter emits ``None`` (engine → ``NO_SEQUENCE``).
- Subscription records serialize no credentials/account numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IbkrConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class IbkrSubscriptionState(StrEnum):
    CREATED = "CREATED"
    SUBSCRIBING = "SUBSCRIBING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    RESETTING = "RESETTING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class EntitlementState(StrEnum):
    UNKNOWN = "UNKNOWN"
    ENTITLED = "ENTITLED"
    DELAYED = "DELAYED"
    NOT_ENTITLED = "NOT_ENTITLED"
    ERROR = "ERROR"


class CapabilityKind(StrEnum):
    L1 = "L1"
    L2 = "L2"
    TRADES = "TRADES"


class IbkrErrorCategory(StrEnum):
    CONNECTION = "CONNECTION"
    ENTITLEMENT = "ENTITLEMENT"
    DELAYED_DATA = "DELAYED_DATA"
    PACING = "PACING"
    CONTRACT = "CONTRACT"
    SUBSCRIPTION = "SUBSCRIPTION"
    INTERNAL_PROVIDER = "INTERNAL_PROVIDER"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class DepthTranslationOutcome(StrEnum):
    """Outcome of translating one IB depth callback into canonical events."""

    APPLIED = "APPLIED"
    IGNORED = "IGNORED"  # benign (e.g. delete of unknown position after reset)
    REJECTED = "REJECTED"  # malformed / unknown reqId / invalid constants
    DEGRADED = "DEGRADED"  # fail-closed: rank disagreement → reset required


@dataclass(frozen=True, slots=True)
class IbkrProviderError:
    """Sanitized provider error fact (no secrets, no account data)."""

    code: int | None
    message: str
    category: IbkrErrorCategory
    req_id: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "code": self.code,
            "message": self.message,
            "req_id": self.req_id,
        }


@dataclass(frozen=True, slots=True)
class ContractQualification:
    """Provider-side contract resolution facts (provenance, not identity)."""

    con_id: int
    symbol: str = ""
    sec_type: str = ""
    exchange: str = ""
    currency: str = ""
    multiplier: str | None = None
    local_symbol: str | None = None
    last_trade_date: str | None = None
    strike: str | None = None
    right: str | None = None
    trading_class: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "con_id": self.con_id,
            "currency": self.currency,
            "exchange": self.exchange,
            "last_trade_date": self.last_trade_date,
            "local_symbol": self.local_symbol,
            "multiplier": self.multiplier,
            "right": self.right,
            "sec_type": self.sec_type,
            "strike": self.strike,
            "symbol": self.symbol,
            "trading_class": self.trading_class,
        }


@dataclass(slots=True)
class IbkrSubscriptionRecord:
    """One canonical IBKR observational subscription.

    Identity resolution is required before a record exists: ``instrument_id``
    is the canonical XA-01 id, never a bare provider symbol. Provider contract
    metadata is provenance, not identity.
    """

    subscription_id: str
    capability: CapabilityKind
    instrument_id: str
    req_id: int
    generation: int
    connection_identity: str
    con_id: int | None = None
    entitlement: EntitlementState = EntitlementState.UNKNOWN
    state: IbkrSubscriptionState = IbkrSubscriptionState.CREATED
    depth_levels: int = 20
    created_ns: int | None = None
    activated_ns: int | None = None
    last_source_time_ns: int | None = None
    last_received_time_ns: int | None = None
    last_error: IbkrProviderError | None = None
    delayed: bool = False
    reset_count: int = 0
    reason: str | None = None

    def mark_active(self, *, received_ns: int | None = None) -> None:
        self.state = IbkrSubscriptionState.ACTIVE
        self.activated_ns = self.activated_ns or received_ns
        self.reason = None

    def mark_degraded(self, reason: str, *, received_ns: int | None = None) -> None:
        self.state = IbkrSubscriptionState.DEGRADED
        self.reason = reason
        if received_ns is not None:
            self.last_received_time_ns = received_ns

    def mark_failed(self, reason: str, *, error: IbkrProviderError | None = None) -> None:
        self.state = IbkrSubscriptionState.FAILED
        self.reason = reason
        if error is not None:
            self.last_error = error

    def as_dict(self) -> dict[str, Any]:
        return {
            "activated_ns": self.activated_ns,
            "capability": self.capability.value,
            "con_id": self.con_id,
            "connection_identity": self.connection_identity,
            "created_ns": self.created_ns,
            "delayed": self.delayed,
            "depth_levels": self.depth_levels,
            "entitlement": self.entitlement.value,
            "generation": self.generation,
            "instrument_id": self.instrument_id,
            "last_error": None if self.last_error is None else self.last_error.as_dict(),
            "last_received_time_ns": self.last_received_time_ns,
            "last_source_time_ns": self.last_source_time_ns,
            "reason": self.reason,
            "req_id": self.req_id,
            "reset_count": self.reset_count,
            "state": self.state.value,
            "subscription_id": self.subscription_id,
        }


@dataclass(frozen=True, slots=True)
class L1QuoteFacts:
    """Truthful accumulated L1 facts for one subscription.

    Every field is either a real provider fact or ``None`` — unknown size is
    never coerced to 0, and a missing side is never fabricated.
    """

    instrument_id: str
    subscription_id: str
    generation: int
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    last_price: float | None = None
    last_size: float | None = None
    delayed: bool = False
    entitlement: EntitlementState = EntitlementState.UNKNOWN
    source_time_ns: int | None = None
    received_time_ns: int | None = None
    source: str = "IBKR"

    @property
    def has_any_fact(self) -> bool:
        return any(
            value is not None
            for value in (
                self.bid_price,
                self.ask_price,
                self.bid_size,
                self.ask_size,
                self.last_price,
                self.last_size,
            )
        )

    @property
    def has_full_top_of_book(self) -> bool:
        return self.bid_price is not None and self.ask_price is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ask_price": self.ask_price,
            "ask_size": self.ask_size,
            "bid_price": self.bid_price,
            "bid_size": self.bid_size,
            "delayed": self.delayed,
            "entitlement": self.entitlement.value,
            "generation": self.generation,
            "instrument_id": self.instrument_id,
            "last_price": self.last_price,
            "last_size": self.last_size,
            "received_time_ns": self.received_time_ns,
            "source": self.source,
            "source_time_ns": self.source_time_ns,
            "subscription_id": self.subscription_id,
        }


@dataclass(frozen=True, slots=True)
class RankLevel:
    """Adapter-local provider rank state for one side of one depth feed."""

    price: float
    size: float
    market_maker: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "market_maker": self.market_maker,
            "price": self.price,
            "size": self.size,
        }


@dataclass(frozen=True, slots=True)
class TradePrintFacts:
    """Canonical IBKR tick-by-tick trade observation (one print)."""

    instrument_id: str
    subscription_id: str
    req_id: int
    generation: int
    price: float
    size: float
    received_time_ns: int
    source_time_ns: int | None = None
    exchange: str | None = None
    special_conditions: str | None = None
    tick_type: int | None = None
    past_limit: bool | None = None
    unreported: bool | None = None
    provider_event_id: str | None = None
    schema_version: str = "ibkr_observational/trade_print/1.0.0"

    def as_dict(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange,
            "generation": self.generation,
            "instrument_id": self.instrument_id,
            "past_limit": self.past_limit,
            "price": self.price,
            "provider_event_id": self.provider_event_id,
            "received_time_ns": self.received_time_ns,
            "req_id": self.req_id,
            "schema_version": self.schema_version,
            "size": self.size,
            "source_time_ns": self.source_time_ns,
            "special_conditions": self.special_conditions,
            "subscription_id": self.subscription_id,
            "tick_type": self.tick_type,
            "unreported": self.unreported,
        }


@dataclass(frozen=True, slots=True)
class PacingReport:
    active_l1: int = 0
    active_l2: int = 0
    active_trades: int = 0
    configured_max_l1: int = 0
    configured_max_l2: int = 0
    configured_max_trades: int = 0
    rejected_reasons: tuple[str, ...] = ()
    cooldown_until_ns: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_l1": self.active_l1,
            "active_l2": self.active_l2,
            "active_trades": self.active_trades,
            "cooldown_until_ns": self.cooldown_until_ns,
            "configured_max_l1": self.configured_max_l1,
            "configured_max_l2": self.configured_max_l2,
            "configured_max_trades": self.configured_max_trades,
            "rejected_reasons": list(self.rejected_reasons),
        }


@dataclass(slots=True)
class AdapterDiagnostics:
    """Provider + subscription diagnostics (existing health vocabulary)."""

    provider: str = "IBKR_OBSERVATIONAL"
    connection_state: IbkrConnectionState = IbkrConnectionState.DISCONNECTED
    connection_generation: int = 0
    reconnect_count: int = 0
    reset_count: int = 0
    l1_subscription_count: int = 0
    l2_subscription_count: int = 0
    trades_subscription_count: int = 0
    subscriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    pacing: dict[str, Any] = field(default_factory=dict)
    entitlement_state: EntitlementState = EntitlementState.UNKNOWN
    last_error: dict[str, Any] | None = None
    last_received_ns: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "connection_generation": self.connection_generation,
            "connection_state": self.connection_state.value,
            "entitlement_state": self.entitlement_state.value,
            "l1_subscription_count": self.l1_subscription_count,
            "l2_subscription_count": self.l2_subscription_count,
            "trades_subscription_count": self.trades_subscription_count,
            "last_error": self.last_error,
            "last_received_ns": self.last_received_ns,
            "pacing": dict(self.pacing),
            "provider": self.provider,
            "reconnect_count": self.reconnect_count,
            "reset_count": self.reset_count,
            "subscriptions": dict(self.subscriptions),
        }


__all__ = [
    "AdapterDiagnostics",
    "CapabilityKind",
    "ContractQualification",
    "DepthTranslationOutcome",
    "EntitlementState",
    "IbkrConnectionState",
    "IbkrErrorCategory",
    "IbkrProviderError",
    "IbkrSubscriptionState",
    "IbkrSubscriptionRecord",
    "L1QuoteFacts",
    "PacingReport",
    "RankLevel",
    "TradePrintFacts",
]