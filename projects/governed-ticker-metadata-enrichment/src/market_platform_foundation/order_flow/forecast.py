"""Short-horizon microstructure forecasts from OF3–OF7 composites — Order Flow OF8.

Composes book flow (OFI), L1 pressure (microprice, QI), liquidity fragility (OF6),
and impact regimes (OF7) into continuation vs reversal probabilities.

Distinct from SHARED P2 multi-day physical P (EWMA/GARCH/HAR). This module answers
what is likely over the next snapshot / seconds-scale horizon on the book.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any

from .contracts import ImpactRegime, ForecastDirection
from .impact import AGGRESSION_THRESHOLD
from .l1 import compute_l1_state
from .ofi import _best_bid_ask, snapshot_book_state_valid

FORECAST_METHOD = "microstructure_heuristic_v1"
FORECAST_VERSION = "1"
DEFAULT_HORIZON_SECONDS = 1
DIRECTION_THRESHOLD = 0.12
CONTINUATION_THRESHOLD = 0.55
REVERSAL_THRESHOLD = 0.45
OFI_SCALE = 200.0
EXPECTED_MOVE_SPREAD_FRACTION = 0.5
MID_DELTA_HISTORY_MIN = 2


@dataclass(frozen=True, slots=True)
class MicrostructureForecastResult:
    forecast_horizon_seconds: int
    expected_mid_delta: float
    direction_bias: ForecastDirection
    continuation_probability: float
    reversal_probability: float
    volatility_proxy: float
    composite_bias: float
    model_confidence: float
    forecast_method: str
    forecast_version: str
    book_state_valid: bool
    quality_flags: tuple[str, ...] = ()


def _tanh_scale(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _volatility_proxy(
    *,
    relative_spread: float,
    recent_mid_deltas: Sequence[float] | None,
) -> float:
    if recent_mid_deltas and len(recent_mid_deltas) >= MID_DELTA_HISTORY_MIN:
        mean = sum(recent_mid_deltas) / len(recent_mid_deltas)
        variance = sum((delta - mean) ** 2 for delta in recent_mid_deltas) / len(recent_mid_deltas)
        stdev = math.sqrt(variance)
        return round(max(stdev, relative_spread), 8)
    return round(relative_spread, 8)


def _l1_from_snapshot(snapshot: dict[str, Any]) -> tuple[float, float, float, float] | None:
    bbo = _best_bid_ask(snapshot)
    if bbo is None:
        return None
    bid_price, bid_size, ask_price, ask_size = bbo
    l1 = compute_l1_state(
        best_bid=bid_price,
        best_ask=ask_price,
        bid_size=bid_size,
        ask_size=ask_size,
    )
    if l1 is None:
        return None
    return l1.spread, l1.relative_spread, l1.microprice_minus_mid, l1.queue_imbalance


def compute_microstructure_forecast(
    snapshot: dict[str, Any],
    *,
    ofi_value: float | None = None,
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    impact_regime: ImpactRegime | str | None = None,
    absorption_score: float | None = None,
    exhaustion_score: float | None = None,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    recent_mid_deltas: Sequence[float] | None = None,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
) -> MicrostructureForecastResult:
    """Heuristic v1 short-horizon forecast from microstructure stack."""
    valid = book_state_valid if book_state_valid is not None else snapshot_book_state_valid(snapshot)
    if not valid:
        return MicrostructureForecastResult(
            forecast_horizon_seconds=horizon_seconds,
            expected_mid_delta=0.0,
            direction_bias=ForecastDirection.NEUTRAL,
            continuation_probability=0.0,
            reversal_probability=0.0,
            volatility_proxy=0.0,
            composite_bias=0.0,
            model_confidence=0.0,
            forecast_method=FORECAST_METHOD,
            forecast_version=FORECAST_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    l1_metrics = _l1_from_snapshot(snapshot)
    if l1_metrics is None:
        return MicrostructureForecastResult(
            forecast_horizon_seconds=horizon_seconds,
            expected_mid_delta=0.0,
            direction_bias=ForecastDirection.NEUTRAL,
            continuation_probability=0.0,
            reversal_probability=0.0,
            volatility_proxy=0.0,
            composite_bias=0.0,
            model_confidence=0.0,
            forecast_method=FORECAST_METHOD,
            forecast_version=FORECAST_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    spread, relative_spread, microprice_minus_mid, queue_imbalance = l1_metrics
    quality_flags: list[str] = []

    ofi_signal = _tanh_scale(ofi_value or 0.0, OFI_SCALE)
    pressure_signal = 0.0
    if spread > 0:
        pressure_signal = _clamp01(abs(microprice_minus_mid) / spread) * (
            1.0 if microprice_minus_mid > 0 else -1.0 if microprice_minus_mid < 0 else 0.0
        )
    qi_signal = queue_imbalance

    trade_signal = 0.0
    if bar_delta is not None:
        trade_signal = _tanh_scale(bar_delta, AGGRESSION_THRESHOLD)
    elif cvd_slope is not None:
        trade_signal = _tanh_scale(cvd_slope, AGGRESSION_THRESHOLD)
    else:
        quality_flags.append("MISSING_TRADE_FLOW")

    composite_bias = round(
        0.35 * ofi_signal + 0.25 * pressure_signal + 0.20 * qi_signal + 0.20 * trade_signal,
        6,
    )

    continuation_probability = _clamp01(abs(composite_bias))
    if bar_delta is None and cvd_slope is None:
        continuation_probability *= 0.65

    reversal_probability = 0.0
    regime_value = (
        impact_regime.value if isinstance(impact_regime, ImpactRegime) else str(impact_regime or "NEUTRAL")
    )
    if exhaustion_score is not None and exhaustion_score > 0:
        reversal_probability = max(reversal_probability, exhaustion_score * 0.75)
    if regime_value in (ImpactRegime.BUY_EXHAUSTION.value, ImpactRegime.SELL_EXHAUSTION.value):
        reversal_probability = max(reversal_probability, 0.45)
    if fragility_score is not None and fragility_score >= 0.25:
        reversal_probability = max(reversal_probability, fragility_score * 0.6)

    if absorption_score is not None and absorption_score > 0:
        dampen = absorption_score * 0.5
        if composite_bias > 0 and regime_value == ImpactRegime.BUY_ABSORPTION.value:
            continuation_probability *= (1.0 - dampen)
        elif composite_bias < 0 and regime_value == ImpactRegime.SELL_ABSORPTION.value:
            continuation_probability *= (1.0 - dampen)

    reversal_probability = round(_clamp01(reversal_probability), 6)
    continuation_probability = round(_clamp01(continuation_probability), 6)

    model_confidence = 0.75
    if fragility_score is not None:
        model_confidence *= (1.0 - _clamp01(fragility_score))
    if resiliency_score is not None:
        model_confidence = 0.55 * model_confidence + 0.45 * _clamp01(resiliency_score)
    if "MISSING_TRADE_FLOW" in quality_flags:
        model_confidence *= 0.7
    if recent_mid_deltas is None or len(recent_mid_deltas) < MID_DELTA_HISTORY_MIN:
        quality_flags.append("INSUFFICIENT_HISTORY")
        model_confidence *= 0.85
    model_confidence = round(_clamp01(model_confidence), 6)

    direction_bias = ForecastDirection.NEUTRAL
    if composite_bias > DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.UP
    elif composite_bias < -DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.DOWN

    expected_mid_delta = round(composite_bias * spread * EXPECTED_MOVE_SPREAD_FRACTION, 8)
    volatility_proxy = _volatility_proxy(
        relative_spread=relative_spread,
        recent_mid_deltas=recent_mid_deltas,
    )

    return MicrostructureForecastResult(
        forecast_horizon_seconds=horizon_seconds,
        expected_mid_delta=expected_mid_delta,
        direction_bias=direction_bias,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        volatility_proxy=volatility_proxy,
        composite_bias=composite_bias,
        model_confidence=model_confidence,
        forecast_method=FORECAST_METHOD,
        forecast_version=FORECAST_VERSION,
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def microstructure_forecast_to_dict(result: MicrostructureForecastResult) -> dict[str, Any]:
    return {
        "forecast_horizon_seconds": result.forecast_horizon_seconds,
        "expected_mid_delta": result.expected_mid_delta,
        "direction_bias": result.direction_bias.value,
        "continuation_probability": result.continuation_probability,
        "reversal_probability": result.reversal_probability,
        "volatility_proxy": result.volatility_proxy,
        "composite_bias": result.composite_bias,
        "model_confidence": result.model_confidence,
        "forecast_method": result.forecast_method,
        "forecast_version": result.forecast_version,
        "book_state_valid": result.book_state_valid,
        "quality_flags": list(result.quality_flags),
    }


__all__ = [
    "CONTINUATION_THRESHOLD",
    "DEFAULT_HORIZON_SECONDS",
    "DIRECTION_THRESHOLD",
    "FORECAST_METHOD",
    "FORECAST_VERSION",
    "ForecastDirection",
    "MicrostructureForecastResult",
    "REVERSAL_THRESHOLD",
    "compute_microstructure_forecast",
    "microstructure_forecast_to_dict",
]
