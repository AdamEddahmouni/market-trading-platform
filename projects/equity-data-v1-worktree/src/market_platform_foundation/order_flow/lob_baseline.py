"""Advanced LOB engineered baseline forecaster — Order Flow OF12 (M8)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from .contracts import ForecastDirection
from .forecast import _l1_from_snapshot
from .impact import AGGRESSION_THRESHOLD
from .lob_features import build_lob_feature_vector
from .ofi import snapshot_book_state_valid

LOB_BASELINE_METHOD = "lob_engineered_baseline_v1"
LOB_BASELINE_VERSION = "1"
LOB_M1_METHOD = "lob_cvd_only_v1"
DEFAULT_SIGNAL_HALF_LIFE_MS = 100
DIRECTION_THRESHOLD = 0.08
EXPECTED_MOVE_SPREAD_FRACTION = 0.45

BaselineTier = Literal["M1", "M8"]


@dataclass(frozen=True, slots=True)
class LobBaselineForecast:
    lob_model_version: str
    lob_model_version_number: str
    baseline_tier: BaselineTier
    mid_up_probability: float
    expected_mid_delta: float
    direction_bias: ForecastDirection
    signal_half_life_ms: int
    composite_score: float
    model_confidence: float
    book_state_valid: bool
    quality_flags: tuple[str, ...] = ()


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _tanh_scale(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def _score_from_trade_signal(trade_signal: float) -> float:
    return round(trade_signal, 6)


def compute_m1_cvd_baseline(
    snapshot: dict[str, Any],
    *,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    book_state_valid: bool | None = None,
    signal_half_life_ms: int = DEFAULT_SIGNAL_HALF_LIFE_MS,
) -> LobBaselineForecast:
    """M1 comparator — CVD / bar delta direction only."""
    valid = book_state_valid if book_state_valid is not None else snapshot_book_state_valid(snapshot)
    quality_flags: list[str] = []
    if not valid:
        return LobBaselineForecast(
            lob_model_version=LOB_M1_METHOD,
            lob_model_version_number=LOB_BASELINE_VERSION,
            baseline_tier="M1",
            mid_up_probability=0.5,
            expected_mid_delta=0.0,
            direction_bias=ForecastDirection.NEUTRAL,
            signal_half_life_ms=signal_half_life_ms,
            composite_score=0.0,
            model_confidence=0.0,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    trade_signal = 0.0
    if bar_delta is not None:
        trade_signal = _tanh_scale(bar_delta, AGGRESSION_THRESHOLD)
    elif cvd_slope is not None:
        trade_signal = _tanh_scale(cvd_slope, AGGRESSION_THRESHOLD)
    else:
        quality_flags.append("MISSING_TRADE_FLOW")

    composite = _score_from_trade_signal(trade_signal)
    mid_up_probability = round(_clamp01(0.5 + 0.5 * composite), 6)
    direction_bias = ForecastDirection.NEUTRAL
    if composite > DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.UP
    elif composite < -DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.DOWN

    l1_metrics = _l1_from_snapshot(snapshot)
    spread = l1_metrics[0] if l1_metrics is not None else 0.0
    expected_mid_delta = round(composite * spread * EXPECTED_MOVE_SPREAD_FRACTION, 8)
    model_confidence = 0.55 if "MISSING_TRADE_FLOW" not in quality_flags else 0.25

    return LobBaselineForecast(
        lob_model_version=LOB_M1_METHOD,
        lob_model_version_number=LOB_BASELINE_VERSION,
        baseline_tier="M1",
        mid_up_probability=mid_up_probability,
        expected_mid_delta=expected_mid_delta,
        direction_bias=direction_bias,
        signal_half_life_ms=signal_half_life_ms,
        composite_score=composite,
        model_confidence=round(model_confidence, 6),
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def compute_lob_baseline_forecast(
    snapshot: dict[str, Any],
    *,
    ofi_value: float | None = None,
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    absorption_score: float | None = None,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    queue_ahead_fraction: float | None = None,
    signal_half_life_ms: int = DEFAULT_SIGNAL_HALF_LIFE_MS,
) -> LobBaselineForecast:
    """M8 engineered LOB baseline from M7 feature vector."""
    vector = build_lob_feature_vector(
        snapshot,
        ofi_value=ofi_value,
        book_state_valid=book_state_valid,
        fragility_score=fragility_score,
        absorption_score=absorption_score,
        bar_delta=bar_delta,
        cvd_slope=cvd_slope,
        queue_ahead_fraction=queue_ahead_fraction,
    )
    if not vector.book_state_valid:
        return LobBaselineForecast(
            lob_model_version=LOB_BASELINE_METHOD,
            lob_model_version_number=LOB_BASELINE_VERSION,
            baseline_tier="M8",
            mid_up_probability=0.5,
            expected_mid_delta=0.0,
            direction_bias=ForecastDirection.NEUTRAL,
            signal_half_life_ms=signal_half_life_ms,
            composite_score=0.0,
            model_confidence=0.0,
            book_state_valid=False,
            quality_flags=vector.quality_flags,
        )

    queue_term = vector.queue_ahead_fraction if vector.queue_ahead_fraction is not None else 0.0
    queue_weight = 0.10 if vector.queue_ahead_fraction is not None else 0.0
    base_weight = 0.90

    composite = (
        base_weight
        * (
            0.32 * vector.ofi_signal
            + 0.22 * vector.pressure_signal
            + 0.18 * vector.queue_imbalance_signal
            + 0.18 * vector.trade_signal
            - 0.10 * vector.fragility_signal * vector.trade_signal
            - 0.08 * vector.absorption_dampener * abs(vector.trade_signal)
        )
        + queue_weight * queue_term * (1.0 if vector.trade_signal >= 0 else -1.0)
    )
    composite = round(composite, 6)

    mid_up_probability = round(_clamp01(0.5 + 0.5 * math.tanh(composite * 1.35)), 6)
    direction_bias = ForecastDirection.NEUTRAL
    if composite > DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.UP
    elif composite < -DIRECTION_THRESHOLD:
        direction_bias = ForecastDirection.DOWN

    l1_metrics = _l1_from_snapshot(snapshot)
    spread = l1_metrics[0] if l1_metrics is not None else 0.0
    expected_mid_delta = round(composite * spread * EXPECTED_MOVE_SPREAD_FRACTION, 8)

    model_confidence = 0.72
    if resiliency_score is not None:
        model_confidence = 0.55 * model_confidence + 0.45 * _clamp01(resiliency_score)
    if fragility_score is not None:
        model_confidence *= 1.0 - 0.35 * _clamp01(fragility_score)
    if "MISSING_TRADE_FLOW" in vector.quality_flags:
        model_confidence *= 0.75
    if "MBO_UNAVAILABLE" in vector.quality_flags:
        model_confidence *= 0.92

    quality_flags = list(vector.quality_flags)
    return LobBaselineForecast(
        lob_model_version=LOB_BASELINE_METHOD,
        lob_model_version_number=LOB_BASELINE_VERSION,
        baseline_tier="M8",
        mid_up_probability=mid_up_probability,
        expected_mid_delta=expected_mid_delta,
        direction_bias=direction_bias,
        signal_half_life_ms=signal_half_life_ms,
        composite_score=composite,
        model_confidence=round(_clamp01(model_confidence), 6),
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def lob_baseline_forecast_to_dict(result: LobBaselineForecast) -> dict[str, Any]:
    return {
        "lob_model_version": result.lob_model_version,
        "lob_model_version_number": result.lob_model_version_number,
        "baseline_tier": result.baseline_tier,
        "lob_mid_up_probability": result.mid_up_probability,
        "lob_expected_mid_delta": result.expected_mid_delta,
        "lob_direction_bias": result.direction_bias.value,
        "signal_half_life_ms": result.signal_half_life_ms,
        "lob_composite_score": result.composite_score,
        "lob_model_confidence": result.model_confidence,
        "lob_quality_flags": list(result.quality_flags),
        "research_only": True,
        "experimental": True,
    }


def queue_ahead_fraction_from_snapshot(
    snapshot: dict[str, Any],
    mbo_queue_snapshot: Any | None,
    *,
    hypothetical_size: float = 10.0,
) -> float | None:
    """Derive normalized queue-ahead fraction from MBO snapshot when aligned."""
    if mbo_queue_snapshot is None:
        return None
    from ..donor_patterns.order_book_lane import best_bid_ask
    from .contracts import MboOrderSide
    from .queue import estimate_queue_position

    bbo = best_bid_ask(snapshot)
    if bbo is None:
        return None
    estimate = estimate_queue_position(
        mbo_queue_snapshot,
        price=float(bbo["bid_price"]),
        side=MboOrderSide.BID,
        hypothetical_size=hypothetical_size,
    )
    if estimate.size_at_level <= 0:
        return None
    total = estimate.size_ahead + hypothetical_size
    if total <= 0:
        return None
    return estimate.size_ahead / total


def compute_lob_forecast_for_snapshot(
    snapshot: dict[str, Any],
    *,
    ofi_value: float | None = None,
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    absorption_score: float | None = None,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    mbo_queue_snapshot: Any | None = None,
) -> dict[str, Any]:
    """Adapter helper — M8 LOB baseline dict for ledger/workspace rows."""
    queue_ahead = queue_ahead_fraction_from_snapshot(snapshot, mbo_queue_snapshot)
    result = compute_lob_baseline_forecast(
        snapshot,
        ofi_value=ofi_value,
        book_state_valid=book_state_valid,
        fragility_score=fragility_score,
        resiliency_score=resiliency_score,
        absorption_score=absorption_score,
        bar_delta=bar_delta,
        cvd_slope=cvd_slope,
        queue_ahead_fraction=queue_ahead,
    )
    return lob_baseline_forecast_to_dict(result)


__all__ = [
    "DEFAULT_SIGNAL_HALF_LIFE_MS",
    "LOB_BASELINE_METHOD",
    "LOB_BASELINE_VERSION",
    "LOB_M1_METHOD",
    "LobBaselineForecast",
    "compute_lob_baseline_forecast",
    "compute_lob_forecast_for_snapshot",
    "compute_m1_cvd_baseline",
    "lob_baseline_forecast_to_dict",
    "queue_ahead_fraction_from_snapshot",
]
