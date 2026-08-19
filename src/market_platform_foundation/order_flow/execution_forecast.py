"""Book-aware execution forecasts from L2 depth + OF3–OF8 composites — Order Flow OF9.

Estimates fill probability, expected slippage, and adverse selection for aggressive
and passive orders against displayed depth. Distinct from Options O9 lifecycle sim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .contracts import ForecastDirection, ImpactRegime
from .l1 import compute_l1_state
from .liquidity import snapshot_side_depths
from .ofi import _best_bid_ask, snapshot_book_state_valid

EXECUTION_METHOD = "execution_book_aware_v1"
EXECUTION_VERSION = "1"
BOOK_MODEL_VERSION = "displayed_depth_l2_v1"
QUEUE_MODEL_VERSION = "none"
DEFAULT_ORDER_QTY = 100.0
PASSIVE_BASE_FILL_PROB = 0.72
SLIPPAGE_HALF_SPREAD = 0.5
DEPTH_PENALTY_SCALE = 0.12
FRAGILITY_SLIPPAGE_SCALE = 0.15

OrderSide = Literal["buy", "sell"]


@dataclass(frozen=True, slots=True)
class ExecutionForecastResult:
    aggressive_fill_probability: float
    passive_fill_probability: float
    expected_slippage_spread_fraction: float
    expected_slippage_absolute: float
    adverse_selection_risk: float
    touch_depth_bid: float
    touch_depth_ask: float
    displayed_depth_consumed_fraction: float
    execution_method: str
    execution_version: str
    book_model_version: str
    queue_model_version: str
    book_state_valid: bool
    quality_flags: tuple[str, ...] = ()


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def compute_execution_forecast(
    snapshot: dict[str, Any],
    *,
    order_qty: float = DEFAULT_ORDER_QTY,
    order_side: OrderSide = "buy",
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    continuation_probability: float | None = None,
    reversal_probability: float | None = None,
    direction_bias: ForecastDirection | str | None = None,
    exhaustion_score: float | None = None,
    impact_regime: ImpactRegime | str | None = None,
    level_count: int = 10,
) -> ExecutionForecastResult:
    """Heuristic v1 execution forecast from displayed L2 book and microstructure context."""
    valid = book_state_valid if book_state_valid is not None else snapshot_book_state_valid(snapshot)
    if not valid:
        return ExecutionForecastResult(
            aggressive_fill_probability=0.0,
            passive_fill_probability=0.0,
            expected_slippage_spread_fraction=0.0,
            expected_slippage_absolute=0.0,
            adverse_selection_risk=0.0,
            touch_depth_bid=0.0,
            touch_depth_ask=0.0,
            displayed_depth_consumed_fraction=0.0,
            execution_method=EXECUTION_METHOD,
            execution_version=EXECUTION_VERSION,
            book_model_version=BOOK_MODEL_VERSION,
            queue_model_version=QUEUE_MODEL_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    bbo = _best_bid_ask(snapshot)
    if bbo is None:
        return ExecutionForecastResult(
            aggressive_fill_probability=0.0,
            passive_fill_probability=0.0,
            expected_slippage_spread_fraction=0.0,
            expected_slippage_absolute=0.0,
            adverse_selection_risk=0.0,
            touch_depth_bid=0.0,
            touch_depth_ask=0.0,
            displayed_depth_consumed_fraction=0.0,
            execution_method=EXECUTION_METHOD,
            execution_version=EXECUTION_VERSION,
            book_model_version=BOOK_MODEL_VERSION,
            queue_model_version=QUEUE_MODEL_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    bid_price, bid_size, ask_price, ask_size = bbo
    touch_depth_bid = float(bid_size)
    touch_depth_ask = float(ask_size)
    l1 = compute_l1_state(
        best_bid=bid_price,
        best_ask=ask_price,
        bid_size=touch_depth_bid,
        ask_size=touch_depth_ask,
    )
    if l1 is None:
        return ExecutionForecastResult(
            aggressive_fill_probability=0.0,
            passive_fill_probability=0.0,
            expected_slippage_spread_fraction=0.0,
            expected_slippage_absolute=0.0,
            adverse_selection_risk=0.0,
            touch_depth_bid=touch_depth_bid,
            touch_depth_ask=touch_depth_ask,
            displayed_depth_consumed_fraction=0.0,
            execution_method=EXECUTION_METHOD,
            execution_version=EXECUTION_VERSION,
            book_model_version=BOOK_MODEL_VERSION,
            queue_model_version=QUEUE_MODEL_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    quality_flags: list[str] = []
    qty = max(float(order_qty), 1.0)
    side = str(order_side).lower()
    if side not in {"buy", "sell"}:
        side = "buy"
        quality_flags.append("INVALID_ORDER_SIDE_DEFAULT_BUY")

    touch_depth = touch_depth_ask if side == "buy" else touch_depth_bid
    side_depths = snapshot_side_depths(snapshot, level_count=level_count)
    sweep_depth = touch_depth
    if side_depths is not None:
        sweep_depth = side_depths[1] if side == "buy" else side_depths[0]

    aggressive_fill = _clamp01(touch_depth / qty)
    fragility = _clamp01(fragility_score if fragility_score is not None else 0.0)
    passive_fill = _clamp01(PASSIVE_BASE_FILL_PROB * (1.0 - 0.35 * fragility))
    if fragility >= 0.25:
        passive_fill *= 0.85

    consumed_fraction = _clamp01(qty / max(sweep_depth, 1.0))
    relative_spread = l1.relative_spread
    slippage_fraction = SLIPPAGE_HALF_SPREAD * relative_spread
    if qty > touch_depth:
        depth_gap = (qty - touch_depth) / max(touch_depth, 1.0)
        slippage_fraction += depth_gap * DEPTH_PENALTY_SCALE * relative_spread
    slippage_fraction += fragility * FRAGILITY_SLIPPAGE_SCALE * relative_spread
    slippage_fraction = round(_clamp01(slippage_fraction), 8)
    slippage_absolute = round(slippage_fraction * l1.mid, 8)

    bias_value = (
        direction_bias.value
        if isinstance(direction_bias, ForecastDirection)
        else str(direction_bias or ForecastDirection.NEUTRAL.value)
    )
    cont = continuation_probability if continuation_probability is not None else 0.0
    rev = reversal_probability if reversal_probability is not None else 0.0
    regime_value = (
        impact_regime.value if isinstance(impact_regime, ImpactRegime) else str(impact_regime or "NEUTRAL")
    )

    adverse_selection = 0.0
    if side == "buy":
        if bias_value == ForecastDirection.UP.value:
            adverse_selection = max(adverse_selection, cont * 0.85)
        if bias_value == ForecastDirection.DOWN.value:
            adverse_selection = max(adverse_selection, rev * 0.7)
        if regime_value == ImpactRegime.BUY_EXHAUSTION.value:
            adverse_selection = max(adverse_selection, 0.35)
    else:
        if bias_value == ForecastDirection.DOWN.value:
            adverse_selection = max(adverse_selection, cont * 0.85)
        if bias_value == ForecastDirection.UP.value:
            adverse_selection = max(adverse_selection, rev * 0.7)
        if regime_value == ImpactRegime.SELL_EXHAUSTION.value:
            adverse_selection = max(adverse_selection, 0.35)

    if exhaustion_score is not None and exhaustion_score > 0:
        adverse_selection = max(adverse_selection, exhaustion_score * 0.6)
    adverse_selection += fragility * 0.25
    adverse_selection = round(_clamp01(adverse_selection), 6)

    if sweep_depth <= 0:
        quality_flags.append("ZERO_DISPLAYED_DEPTH")

    return ExecutionForecastResult(
        aggressive_fill_probability=round(aggressive_fill, 6),
        passive_fill_probability=round(passive_fill, 6),
        expected_slippage_spread_fraction=slippage_fraction,
        expected_slippage_absolute=slippage_absolute,
        adverse_selection_risk=adverse_selection,
        touch_depth_bid=touch_depth_bid,
        touch_depth_ask=touch_depth_ask,
        displayed_depth_consumed_fraction=round(consumed_fraction, 6),
        execution_method=EXECUTION_METHOD,
        execution_version=EXECUTION_VERSION,
        book_model_version=BOOK_MODEL_VERSION,
        queue_model_version=QUEUE_MODEL_VERSION,
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def execution_forecast_to_dict(result: ExecutionForecastResult) -> dict[str, Any]:
    return {
        "aggressive_fill_probability": result.aggressive_fill_probability,
        "passive_fill_probability": result.passive_fill_probability,
        "expected_slippage_spread_fraction": result.expected_slippage_spread_fraction,
        "expected_slippage_absolute": result.expected_slippage_absolute,
        "adverse_selection_risk": result.adverse_selection_risk,
        "touch_depth_bid": result.touch_depth_bid,
        "touch_depth_ask": result.touch_depth_ask,
        "displayed_depth_consumed_fraction": result.displayed_depth_consumed_fraction,
        "execution_method": result.execution_method,
        "execution_version": result.execution_version,
        "book_model_version": result.book_model_version,
        "queue_model_version": result.queue_model_version,
        "book_state_valid": result.book_state_valid,
        "quality_flags": list(result.quality_flags),
    }


__all__ = [
    "BOOK_MODEL_VERSION",
    "DEFAULT_ORDER_QTY",
    "EXECUTION_METHOD",
    "EXECUTION_VERSION",
    "QUEUE_MODEL_VERSION",
    "ExecutionForecastResult",
    "compute_execution_forecast",
    "execution_forecast_to_dict",
]
