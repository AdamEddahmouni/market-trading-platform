"""Build versioned OrderFlowEvidence for cross-lane publication."""

from __future__ import annotations

from typing import Any

from .contracts import (
    BookPressureEvidence,
    CVDState,
    ExecutionForecast,
    ForecastDirection,
    ImpactEvidence,
    ImpactRegime,
    L1QuoteState,
    LiquidityEvidence,
    MicrostructureCapabilityTier,
    MicrostructureForecast,
    OrderFlowEvidence,
    cvd_state_to_dict,
    execution_forecast_to_dict,
    impact_evidence_to_dict,
    l1_state_to_dict,
    liquidity_evidence_to_dict,
    microstructure_forecast_to_dict,
)
from .impact import (
    IMPACT_METHOD,
    IMPACT_VERSION,
    ImpactDynamicsResult,
    compute_impact_dynamics,
    impact_dynamics_to_dict,
)
from .cvd import compute_cvd_state
from .l1 import compute_book_pressure, compute_l1_state
from .liquidity import (
    compute_liquidity_dynamics,
    fragility_elevated,
    snapshot_total_depth,
    withdrawal_ratio,
)
from .ofi import OFI_METHOD_MULTILEVEL_CS, compute_ofi
from .forecast import (
    CONTINUATION_THRESHOLD,
    FORECAST_METHOD,
    FORECAST_VERSION,
    compute_microstructure_forecast,
    microstructure_forecast_to_dict,
)
from .execution_forecast import (
    EXECUTION_METHOD,
    EXECUTION_VERSION,
    compute_execution_forecast,
    execution_forecast_to_dict as execution_forecast_result_to_dict,
)

PRODUCER_VERSION = "order_flow.1.0.0"
OFI_METHOD_BBO_DELTA = "ofi_bbo_delta_v1"


def build_order_flow_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    bars: list[dict[str, object]] | None = None,
    snapshot: dict[str, Any] | None = None,
    prev_snapshot: dict[str, Any] | None = None,
    ofi_value: float | None = None,
    ofi_method: str | None = None,
    ofi_version: str | None = None,
    ofi_level_count: int = 10,
    horizon: str = "bar",
    data_confidence: float | None = None,
    quality_flags: tuple[str, ...] = (),
) -> OrderFlowEvidence | None:
    """Assemble microstructure evidence from trade bars and/or book snapshot."""
    cvd: CVDState | None = None
    if bars:
        cvd = compute_cvd_state(bars)

    l1: L1QuoteState | None = None
    book_pressure: BookPressureEvidence | None = None
    capability = MicrostructureCapabilityTier.L1

    if snapshot:
        bids = snapshot.get("bids", [])
        asks = snapshot.get("asks", [])
        if isinstance(bids, list) and isinstance(asks, list) and bids and asks:
            book_pressure = compute_book_pressure(bids, asks)
            best_bid = max(float(row["price"]) for row in bids)
            best_ask = min(float(row["price"]) for row in asks)
            top_bid = max(bids, key=lambda row: float(row["price"]))
            top_ask = min(asks, key=lambda row: float(row["price"]))
            l1 = compute_l1_state(
                best_bid=best_bid,
                best_ask=best_ask,
                bid_size=float(top_bid["size"]),
                ask_size=float(top_ask["size"]),
            )
            if len(bids) > 1 or len(asks) > 1:
                capability = MicrostructureCapabilityTier.L2_MBP

    if cvd is None and l1 is None:
        return None

    resolved_confidence = data_confidence
    if resolved_confidence is None and cvd is not None:
        resolved_confidence = cvd.cvd_confidence
    elif resolved_confidence is None and l1 is not None:
        resolved_confidence = 0.7

    supporting: list[str] = []
    counter: list[str] = []
    if cvd is not None:
        if cvd.session_cvd > 0:
            supporting.append(f"session CVD positive ({cvd.session_cvd:.0f})")
        elif cvd.session_cvd < 0:
            supporting.append(f"session CVD negative ({cvd.session_cvd:.0f})")
        if cvd.unknown_fraction > 0.25:
            counter.append(f"unknown aggressor fraction {cvd.unknown_fraction:.0%}")
    if book_pressure is not None:
        if book_pressure.queue_imbalance_l1 > 0.1:
            supporting.append(f"L1 queue imbalance bid-heavy ({book_pressure.queue_imbalance_l1:.2f})")
        elif book_pressure.queue_imbalance_l1 < -0.1:
            supporting.append(f"L1 queue imbalance ask-heavy ({book_pressure.queue_imbalance_l1:.2f})")

    resolved_ofi_value = ofi_value
    resolved_ofi_method = ofi_method
    resolved_ofi_version = ofi_version
    resolved_quality_flags = list(quality_flags)
    if prev_snapshot is not None and snapshot is not None:
        ofi_result = compute_ofi(
            prev_snapshot,
            snapshot,
            method=OFI_METHOD_MULTILEVEL_CS,
            level_count=ofi_level_count,
        )
        resolved_ofi_value = ofi_result.value
        resolved_ofi_method = ofi_result.ofi_method
        resolved_ofi_version = ofi_result.ofi_version
        if not ofi_result.book_state_valid:
            resolved_quality_flags.append("BOOK_STATE_INVALID")
    elif resolved_ofi_value is not None:
        resolved_ofi_method = resolved_ofi_method or OFI_METHOD_BBO_DELTA
        resolved_ofi_version = resolved_ofi_version or "1"

    return OrderFlowEvidence(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        data_confidence=resolved_confidence or 0.0,
        model_confidence=0.0,
        capability_tier=capability,
        cvd=cvd,
        l1=l1,
        book_pressure=book_pressure,
        ofi_value=resolved_ofi_value,
        ofi_method=resolved_ofi_method if resolved_ofi_value is not None else None,
        ofi_version=resolved_ofi_version if resolved_ofi_value is not None else None,
        quality_flags=tuple(resolved_quality_flags),
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


def order_flow_evidence_to_dict(evidence: OrderFlowEvidence) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrument": evidence.instrument,
        "venue": evidence.venue,
        "horizon": evidence.horizon,
        "event_time": evidence.event_time,
        "available_time": evidence.available_time,
        "producer_version": evidence.producer_version,
        "data_confidence": evidence.data_confidence,
        "model_confidence": evidence.model_confidence,
        "capability_tier": evidence.capability_tier.value,
        "quality_flags": list(evidence.quality_flags),
        "supporting_evidence": list(evidence.supporting_evidence),
        "counter_evidence": list(evidence.counter_evidence),
    }
    if evidence.cvd is not None:
        payload["cvd"] = cvd_state_to_dict(evidence.cvd)
    if evidence.l1 is not None:
        payload["l1"] = l1_state_to_dict(evidence.l1)
    if evidence.book_pressure is not None:
        bp = evidence.book_pressure
        payload["book_pressure"] = {
            "depth_imbalance_ratio": bp.depth_imbalance_ratio,
            "queue_imbalance_l1": bp.queue_imbalance_l1,
            "bid_depth": bp.bid_depth,
            "ask_depth": bp.ask_depth,
            "level_count": bp.level_count,
            "capability_tier": bp.capability_tier.value,
        }
    if evidence.ofi_value is not None:
        payload["ofi_value"] = evidence.ofi_value
        payload["ofi_method"] = evidence.ofi_method
        payload["ofi_version"] = evidence.ofi_version
    return payload


def build_liquidity_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    prev_snapshot: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    trajectory_resiliency: float | None = None,
    level_count: int = 10,
    horizon: str = "snapshot",
    data_confidence: float = 0.85,
    quality_flags: tuple[str, ...] = (),
) -> LiquidityEvidence | None:
    """Build OF6 liquidity evidence from consecutive book snapshots."""
    if prev_snapshot is None or snapshot is None:
        return None
    dynamics = compute_liquidity_dynamics(
        prev_snapshot,
        snapshot,
        level_count=level_count,
        trajectory_resiliency=trajectory_resiliency,
    )
    if not dynamics.book_state_valid:
        return None

    prev_total = snapshot_total_depth(prev_snapshot, level_count=level_count) or 0.0
    supporting: list[str] = []
    counter: list[str] = []
    resolved_flags = list(quality_flags)

    if dynamics.depth_withdrawal > 0:
        ratio = withdrawal_ratio(dynamics, prev_total)
        supporting.append(
            f"displayed depth withdrawal {dynamics.depth_withdrawal:.0f} "
            f"({ratio:.0%} of prior total depth)"
        )
    if dynamics.depth_replenishment > 0:
        supporting.append(f"displayed depth replenishment {dynamics.depth_replenishment:.0f}")
    if fragility_elevated(dynamics, prev_total_depth=prev_total):
        supporting.append(f"book fragility elevated ({dynamics.fragility_score:.2f})")
    if dynamics.resiliency_score is not None and dynamics.resiliency_score >= 0.5:
        supporting.append(f"trajectory resiliency {dynamics.resiliency_score:.2f}")

    return LiquidityEvidence(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        liquidity_method=dynamics.liquidity_method,
        liquidity_version=dynamics.liquidity_version,
        net_depth_delta=dynamics.net_depth_delta,
        depth_withdrawal=dynamics.depth_withdrawal,
        depth_replenishment=dynamics.depth_replenishment,
        fragility_score=dynamics.fragility_score,
        spread_delta=dynamics.spread_delta,
        total_depth=dynamics.total_depth,
        data_confidence=data_confidence,
        resiliency_score=dynamics.resiliency_score,
        capability_tier=MicrostructureCapabilityTier.L2_MBP,
        quality_flags=tuple(resolved_flags),
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


def build_impact_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    prev_snapshot: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    bar_delta: float | None = None,
    buying_volume: float | None = None,
    selling_volume: float | None = None,
    prev_bar_delta: float | None = None,
    level_count: int = 10,
    trajectory_resiliency: float | None = None,
    horizon: str = "snapshot",
    data_confidence: float = 0.85,
    quality_flags: tuple[str, ...] = (),
) -> ImpactEvidence | None:
    """Build OF7 impact evidence from consecutive book snapshots and optional bar flow."""
    if prev_snapshot is None or snapshot is None:
        return None
    dynamics = compute_impact_dynamics(
        prev_snapshot,
        snapshot,
        bar_delta=bar_delta,
        buying_volume=buying_volume,
        selling_volume=selling_volume,
        prev_bar_delta=prev_bar_delta,
        level_count=level_count,
        trajectory_resiliency=trajectory_resiliency,
    )
    if not dynamics.book_state_valid and "BOOK_STATE_INVALID" in dynamics.quality_flags:
        return None

    supporting: list[str] = []
    counter: list[str] = []
    resolved_flags = list(quality_flags) + list(dynamics.quality_flags)

    if dynamics.aggression_signed_volume is not None:
        supporting.append(f"signed aggression {dynamics.aggression_signed_volume:.0f}")
    if dynamics.mid_delta != 0:
        supporting.append(f"mid delta {dynamics.mid_delta:+.4f}")
    if dynamics.opposing_replenishment:
        supporting.append("opposing displayed-depth replenishment")
    if dynamics.impact_regime == ImpactRegime.BUY_ABSORPTION:
        supporting.append(
            "book flow buy absorption — high aggression with weak upward progress"
        )
    elif dynamics.impact_regime == ImpactRegime.SELL_ABSORPTION:
        supporting.append(
            "book flow sell absorption — high aggression with weak downward progress"
        )
    elif dynamics.impact_regime == ImpactRegime.BUY_EXHAUSTION:
        supporting.append(
            "book flow buy exhaustion — decaying buy aggression, progress stalling"
        )
    elif dynamics.impact_regime == ImpactRegime.SELL_EXHAUSTION:
        supporting.append(
            "book flow sell exhaustion — decaying sell aggression, progress stalling"
        )
    if "MISSING_TRADE_FLOW" in dynamics.quality_flags:
        counter.append("trade flow missing — absorption/exhaustion not asserted")

    return ImpactEvidence(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        impact_method=dynamics.impact_method,
        impact_version=dynamics.impact_version,
        impact_regime=dynamics.impact_regime,
        mid_delta=dynamics.mid_delta,
        aggression_signed_volume=dynamics.aggression_signed_volume,
        price_efficiency=dynamics.price_efficiency,
        absorption_score=dynamics.absorption_score,
        exhaustion_score=dynamics.exhaustion_score,
        opposing_replenishment=dynamics.opposing_replenishment,
        data_confidence=data_confidence,
        capability_tier=MicrostructureCapabilityTier.L2_MBP,
        quality_flags=tuple(resolved_flags),
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


def build_microstructure_forecast_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    snapshot: dict[str, Any] | None = None,
    ofi_value: float | None = None,
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    impact_regime: ImpactRegime | str | None = None,
    absorption_score: float | None = None,
    exhaustion_score: float | None = None,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    recent_mid_deltas: list[float] | None = None,
    horizon: str = "snapshot",
    horizon_seconds: int = 1,
    data_confidence: float = 0.85,
    quality_flags: tuple[str, ...] = (),
) -> MicrostructureForecast | None:
    """Build OF8 microstructure forecast evidence from composite inputs."""
    if snapshot is None:
        return None
    result = compute_microstructure_forecast(
        snapshot,
        ofi_value=ofi_value,
        book_state_valid=book_state_valid,
        fragility_score=fragility_score,
        resiliency_score=resiliency_score,
        impact_regime=impact_regime,
        absorption_score=absorption_score,
        exhaustion_score=exhaustion_score,
        bar_delta=bar_delta,
        cvd_slope=cvd_slope,
        recent_mid_deltas=recent_mid_deltas,
        horizon_seconds=horizon_seconds,
    )
    if not result.book_state_valid and "BOOK_STATE_INVALID" in result.quality_flags:
        return None

    supporting: list[str] = []
    counter: list[str] = []
    resolved_flags = list(quality_flags) + list(result.quality_flags)

    if ofi_value is not None:
        supporting.append(f"OFI {ofi_value:+.0f}")
    supporting.append(f"composite bias {result.composite_bias:+.3f}")
    supporting.append(
        f"continuation {result.continuation_probability:.2f}, "
        f"reversal {result.reversal_probability:.2f}"
    )
    if result.direction_bias != ForecastDirection.NEUTRAL:
        supporting.append(f"direction bias {result.direction_bias.value}")
    if fragility_score is not None and fragility_score >= 0.25:
        supporting.append(f"fragility {fragility_score:.2f} elevates reversal risk")
    if impact_regime is not None and str(impact_regime) != ImpactRegime.NEUTRAL.value:
        supporting.append(f"impact regime {impact_regime}")
    if "MISSING_TRADE_FLOW" in result.quality_flags:
        counter.append("trade flow missing — trade leg weight zeroed")
    if result.continuation_probability < CONTINUATION_THRESHOLD:
        counter.append("continuation below threshold — weak short-horizon edge")

    return MicrostructureForecast(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        forecast_method=result.forecast_method,
        forecast_version=result.forecast_version,
        forecast_horizon_seconds=result.forecast_horizon_seconds,
        expected_mid_delta=result.expected_mid_delta,
        direction_bias=result.direction_bias,
        continuation_probability=result.continuation_probability,
        reversal_probability=result.reversal_probability,
        volatility_proxy=result.volatility_proxy,
        composite_bias=result.composite_bias,
        data_confidence=data_confidence,
        model_confidence=result.model_confidence,
        capability_tier=MicrostructureCapabilityTier.L2_MBP,
        quality_flags=tuple(resolved_flags),
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


SLIPPAGE_ELEVATED_THRESHOLD = 0.0035
FILL_RISK_THRESHOLD = 0.55
ADVERSE_SELECTION_THRESHOLD = 0.45


def build_execution_forecast_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    snapshot: dict[str, Any] | None = None,
    order_qty: float | None = None,
    order_side: str = "buy",
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    continuation_probability: float | None = None,
    reversal_probability: float | None = None,
    direction_bias: ForecastDirection | str | None = None,
    exhaustion_score: float | None = None,
    impact_regime: ImpactRegime | str | None = None,
    horizon: str = "snapshot",
    level_count: int = 10,
    data_confidence: float = 0.85,
    quality_flags: tuple[str, ...] = (),
) -> ExecutionForecast | None:
    """Build OF9 execution forecast evidence from book snapshot and microstructure context."""
    if snapshot is None:
        return None
    qty = order_qty if order_qty is not None else 100.0
    result = compute_execution_forecast(
        snapshot,
        order_qty=qty,
        order_side=order_side if order_side in {"buy", "sell"} else "buy",
        book_state_valid=book_state_valid,
        fragility_score=fragility_score,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        direction_bias=direction_bias,
        exhaustion_score=exhaustion_score,
        impact_regime=impact_regime,
        level_count=level_count,
    )
    if not result.book_state_valid and "BOOK_STATE_INVALID" in result.quality_flags:
        return None

    supporting: list[str] = []
    counter: list[str] = []
    resolved_flags = list(quality_flags) + list(result.quality_flags)
    supporting.append(
        f"aggressive fill p={result.aggressive_fill_probability:.2f}, "
        f"passive p={result.passive_fill_probability:.2f}"
    )
    supporting.append(
        f"expected slippage {result.expected_slippage_spread_fraction:.4f} spread fraction"
    )
    supporting.append(f"adverse selection risk {result.adverse_selection_risk:.2f}")
    if result.displayed_depth_consumed_fraction > 1.0:
        counter.append(
            f"order size exceeds displayed depth ({result.displayed_depth_consumed_fraction:.2f}x)"
        )
    if result.aggressive_fill_probability < FILL_RISK_THRESHOLD:
        counter.append("aggressive fill probability below comfort threshold")
    if result.expected_slippage_spread_fraction >= SLIPPAGE_ELEVATED_THRESHOLD:
        counter.append("elevated expected slippage vs spread")

    model_confidence = 0.8
    if fragility_score is not None:
        model_confidence *= (1.0 - min(max(fragility_score, 0.0), 1.0) * 0.35)
    if continuation_probability is None:
        model_confidence *= 0.85
    model_confidence = round(min(max(model_confidence, 0.0), 1.0), 6)

    return ExecutionForecast(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        execution_method=result.execution_method,
        execution_version=result.execution_version,
        book_model_version=result.book_model_version,
        queue_model_version=result.queue_model_version,
        aggressive_fill_probability=result.aggressive_fill_probability,
        passive_fill_probability=result.passive_fill_probability,
        expected_slippage_spread_fraction=result.expected_slippage_spread_fraction,
        expected_slippage_absolute=result.expected_slippage_absolute,
        adverse_selection_risk=result.adverse_selection_risk,
        touch_depth_bid=result.touch_depth_bid,
        touch_depth_ask=result.touch_depth_ask,
        displayed_depth_consumed_fraction=result.displayed_depth_consumed_fraction,
        data_confidence=data_confidence,
        model_confidence=model_confidence,
        capability_tier=MicrostructureCapabilityTier.L2_MBP,
        quality_flags=tuple(resolved_flags),
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


__all__ = [
    "ADVERSE_SELECTION_THRESHOLD",
    "FILL_RISK_THRESHOLD",
    "OFI_METHOD_BBO_DELTA",
    "OFI_METHOD_MULTILEVEL_CS",
    "PRODUCER_VERSION",
    "SLIPPAGE_ELEVATED_THRESHOLD",
    "build_execution_forecast_evidence",
    "build_impact_evidence",
    "build_liquidity_evidence",
    "build_microstructure_forecast_evidence",
    "build_order_flow_evidence",
    "execution_forecast_result_to_dict",
    "impact_evidence_to_dict",
    "liquidity_evidence_to_dict",
    "microstructure_forecast_to_dict",
    "order_flow_evidence_to_dict",
]
