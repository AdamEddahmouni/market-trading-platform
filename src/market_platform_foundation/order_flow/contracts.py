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


class ImpactRegime(StrEnum):
    """Book-flow price-response regime — not Short Squeeze lifecycle exhaustion."""

    NEUTRAL = "NEUTRAL"
    BUY_ABSORPTION = "BUY_ABSORPTION"
    SELL_ABSORPTION = "SELL_ABSORPTION"
    BUY_EXHAUSTION = "BUY_EXHAUSTION"
    SELL_EXHAUSTION = "SELL_EXHAUSTION"


class ForecastDirection(StrEnum):
    """Short-horizon microstructure direction bias (OF8)."""

    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


class MboOrderSide(StrEnum):
    """Resting order side in MBO feed."""

    BID = "bid"
    ASK = "ask"


class MetaorderFlowState(StrEnum):
    """OF11 primitive flow state — not PI lifecycle."""

    FLOW_ACTIVE = "FLOW_ACTIVE"
    FLOW_WEAKENING = "FLOW_WEAKENING"
    FLOW_STALLED = "FLOW_STALLED"


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


@dataclass(frozen=True, slots=True)
class LiquidityEvidence:
    """Cross-lane liquidity dynamics evidence (OF6)."""

    instrument: str
    venue: str
    horizon: str
    event_time: str
    available_time: str
    producer_version: str
    liquidity_method: str
    liquidity_version: str
    net_depth_delta: float
    depth_withdrawal: float
    depth_replenishment: float
    fragility_score: float
    spread_delta: float
    total_depth: float
    data_confidence: float
    model_confidence: float = 0.0
    resiliency_score: float | None = None
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L2_MBP
    quality_flags: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpactEvidence:
    """Cross-lane absorption / exhaustion evidence (OF7)."""

    instrument: str
    venue: str
    horizon: str
    event_time: str
    available_time: str
    producer_version: str
    impact_method: str
    impact_version: str
    impact_regime: ImpactRegime
    mid_delta: float
    aggression_signed_volume: float | None
    price_efficiency: float | None
    absorption_score: float | None
    exhaustion_score: float | None
    opposing_replenishment: bool
    data_confidence: float
    model_confidence: float = 0.0
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L2_MBP
    quality_flags: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MicrostructureForecast:
    """Cross-lane short-horizon microstructure forecast (OF8)."""

    instrument: str
    venue: str
    horizon: str
    event_time: str
    available_time: str
    producer_version: str
    forecast_method: str
    forecast_version: str
    forecast_horizon_seconds: int
    expected_mid_delta: float
    direction_bias: ForecastDirection
    continuation_probability: float
    reversal_probability: float
    volatility_proxy: float
    composite_bias: float
    data_confidence: float
    model_confidence: float = 0.0
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L2_MBP
    quality_flags: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MboOrder:
    """Individual resting order from MBO feed — OF10."""

    order_id: str
    price: float
    size: float
    side: MboOrderSide
    sequence: int
    timestamp: str


@dataclass(frozen=True, slots=True)
class PriceLevelQueue:
    """FIFO queue at one price level."""

    price: float
    side: MboOrderSide
    orders: tuple[MboOrder, ...]
    total_size: float


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """MBO-derived queue state at one event time — OF10."""

    event_time: str
    bid_queues: tuple[PriceLevelQueue, ...]
    ask_queues: tuple[PriceLevelQueue, ...]
    queue_method: str
    queue_version: str
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.MBO
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QueuePositionEstimate:
    """Heuristic queue position for a hypothetical passive order."""

    price: float
    side: MboOrderSide
    hypothetical_size: float
    size_ahead: float
    size_at_level: float
    queue_method: str
    queue_version: str
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MetaorderPrimitive:
    """OF11 detection output — raw persistent-flow primitive, not PI evidence."""

    primitive_id: str
    instrument: str
    venue: str
    aggressor_side: AggressorSide
    signed_volume: float
    trade_count: int
    start_time: str
    end_time: str
    available_time: str
    flow_state: MetaorderFlowState
    detection_method: str
    detection_version: str
    mbo_corroborated: bool = False
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionForecast:
    """Cross-lane book-aware execution forecast (OF9)."""

    instrument: str
    venue: str
    horizon: str
    event_time: str
    available_time: str
    producer_version: str
    execution_method: str
    execution_version: str
    book_model_version: str
    queue_model_version: str
    aggressive_fill_probability: float
    passive_fill_probability: float
    expected_slippage_spread_fraction: float
    expected_slippage_absolute: float
    adverse_selection_risk: float
    touch_depth_bid: float
    touch_depth_ask: float
    displayed_depth_consumed_fraction: float
    data_confidence: float
    model_confidence: float = 0.0
    capability_tier: MicrostructureCapabilityTier = MicrostructureCapabilityTier.L2_MBP
    quality_flags: tuple[str, ...] = ()
    supporting_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()


def execution_forecast_to_dict(forecast: ExecutionForecast) -> dict[str, Any]:
    return {
        "instrument": forecast.instrument,
        "venue": forecast.venue,
        "horizon": forecast.horizon,
        "event_time": forecast.event_time,
        "available_time": forecast.available_time,
        "producer_version": forecast.producer_version,
        "execution_method": forecast.execution_method,
        "execution_version": forecast.execution_version,
        "book_model_version": forecast.book_model_version,
        "queue_model_version": forecast.queue_model_version,
        "aggressive_fill_probability": forecast.aggressive_fill_probability,
        "passive_fill_probability": forecast.passive_fill_probability,
        "expected_slippage_spread_fraction": forecast.expected_slippage_spread_fraction,
        "expected_slippage_absolute": forecast.expected_slippage_absolute,
        "adverse_selection_risk": forecast.adverse_selection_risk,
        "touch_depth_bid": forecast.touch_depth_bid,
        "touch_depth_ask": forecast.touch_depth_ask,
        "displayed_depth_consumed_fraction": forecast.displayed_depth_consumed_fraction,
        "data_confidence": forecast.data_confidence,
        "model_confidence": forecast.model_confidence,
        "capability_tier": forecast.capability_tier.value,
        "quality_flags": list(forecast.quality_flags),
        "supporting_evidence": list(forecast.supporting_evidence),
        "counter_evidence": list(forecast.counter_evidence),
    }


def microstructure_forecast_to_dict(forecast: MicrostructureForecast) -> dict[str, Any]:
    return {
        "instrument": forecast.instrument,
        "venue": forecast.venue,
        "horizon": forecast.horizon,
        "event_time": forecast.event_time,
        "available_time": forecast.available_time,
        "producer_version": forecast.producer_version,
        "forecast_method": forecast.forecast_method,
        "forecast_version": forecast.forecast_version,
        "forecast_horizon_seconds": forecast.forecast_horizon_seconds,
        "expected_mid_delta": forecast.expected_mid_delta,
        "direction_bias": forecast.direction_bias.value,
        "continuation_probability": forecast.continuation_probability,
        "reversal_probability": forecast.reversal_probability,
        "volatility_proxy": forecast.volatility_proxy,
        "composite_bias": forecast.composite_bias,
        "data_confidence": forecast.data_confidence,
        "model_confidence": forecast.model_confidence,
        "capability_tier": forecast.capability_tier.value,
        "quality_flags": list(forecast.quality_flags),
        "supporting_evidence": list(forecast.supporting_evidence),
        "counter_evidence": list(forecast.counter_evidence),
    }


def impact_evidence_to_dict(evidence: ImpactEvidence) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrument": evidence.instrument,
        "venue": evidence.venue,
        "horizon": evidence.horizon,
        "event_time": evidence.event_time,
        "available_time": evidence.available_time,
        "producer_version": evidence.producer_version,
        "impact_method": evidence.impact_method,
        "impact_version": evidence.impact_version,
        "impact_regime": evidence.impact_regime.value,
        "mid_delta": evidence.mid_delta,
        "opposing_replenishment": evidence.opposing_replenishment,
        "data_confidence": evidence.data_confidence,
        "model_confidence": evidence.model_confidence,
        "capability_tier": evidence.capability_tier.value,
        "quality_flags": list(evidence.quality_flags),
        "supporting_evidence": list(evidence.supporting_evidence),
        "counter_evidence": list(evidence.counter_evidence),
    }
    if evidence.aggression_signed_volume is not None:
        payload["aggression_signed_volume"] = evidence.aggression_signed_volume
    if evidence.price_efficiency is not None:
        payload["price_efficiency"] = evidence.price_efficiency
    if evidence.absorption_score is not None:
        payload["absorption_score"] = evidence.absorption_score
    if evidence.exhaustion_score is not None:
        payload["exhaustion_score"] = evidence.exhaustion_score
    return payload


def liquidity_evidence_to_dict(evidence: LiquidityEvidence) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrument": evidence.instrument,
        "venue": evidence.venue,
        "horizon": evidence.horizon,
        "event_time": evidence.event_time,
        "available_time": evidence.available_time,
        "producer_version": evidence.producer_version,
        "liquidity_method": evidence.liquidity_method,
        "liquidity_version": evidence.liquidity_version,
        "net_depth_delta": evidence.net_depth_delta,
        "depth_withdrawal": evidence.depth_withdrawal,
        "depth_replenishment": evidence.depth_replenishment,
        "fragility_score": evidence.fragility_score,
        "spread_delta": evidence.spread_delta,
        "total_depth": evidence.total_depth,
        "data_confidence": evidence.data_confidence,
        "model_confidence": evidence.model_confidence,
        "capability_tier": evidence.capability_tier.value,
        "quality_flags": list(evidence.quality_flags),
        "supporting_evidence": list(evidence.supporting_evidence),
        "counter_evidence": list(evidence.counter_evidence),
    }
    if evidence.resiliency_score is not None:
        payload["resiliency_score"] = evidence.resiliency_score
    return payload


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


def mbo_order_to_dict(order: MboOrder) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "price": order.price,
        "size": order.size,
        "side": order.side.value,
        "sequence": order.sequence,
        "timestamp": order.timestamp,
    }


def queue_snapshot_to_dict(snapshot: QueueSnapshot) -> dict[str, Any]:
    return {
        "event_time": snapshot.event_time,
        "bid_queues": [
            {
                "price": queue.price,
                "side": queue.side.value,
                "total_size": queue.total_size,
                "order_count": len(queue.orders),
            }
            for queue in snapshot.bid_queues
        ],
        "ask_queues": [
            {
                "price": queue.price,
                "side": queue.side.value,
                "total_size": queue.total_size,
                "order_count": len(queue.orders),
            }
            for queue in snapshot.ask_queues
        ],
        "queue_method": snapshot.queue_method,
        "queue_version": snapshot.queue_version,
        "capability_tier": snapshot.capability_tier.value,
        "quality_flags": list(snapshot.quality_flags),
    }


def queue_position_to_dict(estimate: QueuePositionEstimate) -> dict[str, Any]:
    return {
        "price": estimate.price,
        "side": estimate.side.value,
        "hypothetical_size": estimate.hypothetical_size,
        "size_ahead": estimate.size_ahead,
        "size_at_level": estimate.size_at_level,
        "queue_method": estimate.queue_method,
        "queue_version": estimate.queue_version,
        "quality_flags": list(estimate.quality_flags),
    }


def metaorder_primitive_to_dict(primitive: MetaorderPrimitive) -> dict[str, Any]:
    return {
        "primitive_id": primitive.primitive_id,
        "instrument": primitive.instrument,
        "venue": primitive.venue,
        "aggressor_side": primitive.aggressor_side.value,
        "signed_volume": primitive.signed_volume,
        "trade_count": primitive.trade_count,
        "start_time": primitive.start_time,
        "end_time": primitive.end_time,
        "available_time": primitive.available_time,
        "flow_state": primitive.flow_state.value,
        "detection_method": primitive.detection_method,
        "detection_version": primitive.detection_version,
        "mbo_corroborated": primitive.mbo_corroborated,
        "quality_flags": list(primitive.quality_flags),
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
