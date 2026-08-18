"""Canonical Order Flow / microstructure contracts (OF1 foundation).

CVD measures net aggressive executed flow — not 'more buyers than sellers'.
Every executed trade has both a buyer and a seller; aggressor side indicates
which party demanded immediacy (liquidity taking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AggressorSide(StrEnum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class AggressorSource(StrEnum):
    """Provenance for aggressor classification — never mislabel inferred as native."""

    EXCHANGE_NATIVE = "EXCHANGE_NATIVE"
    PROVIDER_NATIVE = "PROVIDER_NATIVE"
    QUOTE_MATCH = "QUOTE_MATCH"
    TICK_RULE = "TICK_RULE"
    LEE_READY = "LEE_READY"
    BVC = "BVC"
    OTHER_INFERENCE = "OTHER_INFERENCE"
    UNKNOWN = "UNKNOWN"


class MicrostructureCapabilityTier(StrEnum):
    """Highest data tier supporting a feature — degrade gracefully below MBO."""

    L1 = "L1"
    L2_MBP = "L2_MBP"
    MBO = "MBO"


@dataclass(frozen=True, slots=True)
class ClassifiedTrade:
    """Normalized trade with aggressor semantics and provenance."""

    trade_id: str
    price: float
    quantity: float
    aggressor_side: AggressorSide
    signed_volume: float
    aggressor_source: AggressorSource
    classification_method: str
    classification_confidence: float
    trade_timestamp: str
    quote_timestamp: str | None = None
    provider: str = ""
    venue: str = ""


@dataclass(frozen=True, slots=True)
class L1QuoteState:
    """Top-of-book state and derived L1 microstructure features."""

    best_bid: float
    best_ask: float
    bid_size: float
    ask_size: float
    spread: float
    relative_spread: float
    mid: float
    queue_imbalance: float
    microprice: float
    microprice_minus_mid: float
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L1


@dataclass(frozen=True, slots=True)
class CVDState:
    """Cumulative volume delta with classification-quality awareness."""

    session_cvd: float
    rolling_cvd: float | None = None
    cvd_slope: float | None = None
    cvd_acceleration: float | None = None
    native_classification_fraction: float = 0.0
    inferred_classification_fraction: float = 0.0
    unknown_fraction: float = 0.0
    cvd_confidence: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0


@dataclass(frozen=True, slots=True)
class BookPressureEvidence:
    """Resting-book pressure without domain directional interpretation.

    High bid/ask size ratio indicates bid-heavy *resting* liquidity — not
    aggressive buying. Domain lanes apply their own interpretation policies.
    """

    depth_imbalance_ratio: float
    queue_imbalance_l1: float
    bid_depth: float
    ask_depth: float
    level_count: int
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L2_MBP


@dataclass(frozen=True, slots=True)
class OrderFlowEvidence:
    """Cross-lane evidence contract for microstructure primitives."""

    instrument: str
    venue: str
    horizon: str
    event_time: str
    available_time: str
    producer_version: str
    data_confidence: float
    model_confidence: float
    capability_tier: MicrostructureCapabilityTier
    cvd: CVDState | None = None
    l1: L1QuoteState | None = None
    book_pressure: BookPressureEvidence | None = None
    ofi_value: float | None = None
    ofi_method: str | None = None
    ofi_version: str | None = None
    quality_flags: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()


def classified_trade_to_dict(trade: ClassifiedTrade) -> dict[str, Any]:
    return {
        "trade_id": trade.trade_id,
        "price": trade.price,
        "quantity": trade.quantity,
        "aggressor_side": trade.aggressor_side.value,
        "signed_volume": trade.signed_volume,
        "aggressor_source": trade.aggressor_source.value,
        "classification_method": trade.classification_method,
        "classification_confidence": trade.classification_confidence,
        "trade_timestamp": trade.trade_timestamp,
        "quote_timestamp": trade.quote_timestamp,
        "provider": trade.provider,
        "venue": trade.venue,
    }


def l1_state_to_dict(state: L1QuoteState) -> dict[str, Any]:
    return {
        "best_bid": state.best_bid,
        "best_ask": state.best_ask,
        "bid_size": state.bid_size,
        "ask_size": state.ask_size,
        "spread": state.spread,
        "relative_spread": state.relative_spread,
        "mid": state.mid,
        "queue_imbalance": state.queue_imbalance,
        "microprice": state.microprice,
        "microprice_minus_mid": state.microprice_minus_mid,
        "capability_tier": state.capability_tier.value,
    }


def cvd_state_to_dict(state: CVDState) -> dict[str, Any]:
    return {
        "session_cvd": state.session_cvd,
        "rolling_cvd": state.rolling_cvd,
        "cvd_slope": state.cvd_slope,
        "cvd_acceleration": state.cvd_acceleration,
        "native_classification_fraction": state.native_classification_fraction,
        "inferred_classification_fraction": state.inferred_classification_fraction,
        "unknown_fraction": state.unknown_fraction,
        "cvd_confidence": state.cvd_confidence,
        "aggressive_buy_volume": state.aggressive_buy_volume,
        "aggressive_sell_volume": state.aggressive_sell_volume,
    }
