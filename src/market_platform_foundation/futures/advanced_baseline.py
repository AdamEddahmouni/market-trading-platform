"""Futures F11 family-conditioned engineered baseline (M8) vs trend-only (M1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from .advanced_features import (
    FuturesFeatureVector,
    build_futures_feature_vector,
    futures_feature_vector_from_workspace,
)

FUTURES_ENGINEERED_METHOD = "futures_family_engineered_v1"
FUTURES_TREND_ONLY_METHOD = "futures_trend_only_v1"
FUTURES_BASELINE_VERSION = "1"
DIRECTION_THRESHOLD = 0.08

BaselineTier = Literal["M1", "M8"]


@dataclass(frozen=True, slots=True)
class FuturesBaselineForecast:
    futures_model_version: str
    futures_model_version_number: str
    baseline_tier: BaselineTier
    outright_up_probability: float
    curve_steepen_probability: float
    direction_bias: str
    family: str
    family_supported: bool
    composite_score: float
    model_confidence: float
    quality_flags: tuple[str, ...] = ()


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _direction_bias(composite: float) -> str:
    if composite > DIRECTION_THRESHOLD:
        return "UP"
    if composite < -DIRECTION_THRESHOLD:
        return "DOWN"
    return "NEUTRAL"


def _fail_closed(
    *,
    method: str,
    tier: BaselineTier,
    family: str,
    quality_flags: tuple[str, ...],
) -> FuturesBaselineForecast:
    return FuturesBaselineForecast(
        futures_model_version=method,
        futures_model_version_number=FUTURES_BASELINE_VERSION,
        baseline_tier=tier,
        outright_up_probability=0.5,
        curve_steepen_probability=0.5,
        direction_bias="NEUTRAL",
        family=family,
        family_supported=False,
        composite_score=0.0,
        model_confidence=0.0,
        quality_flags=quality_flags,
    )


def compute_trend_only_baseline(vector: FuturesFeatureVector) -> FuturesBaselineForecast:
    """M1 comparator — F5 trend-3m signal only."""
    if not vector.family_supported:
        return _fail_closed(
            method=FUTURES_TREND_ONLY_METHOD,
            tier="M1",
            family=vector.family,
            quality_flags=vector.quality_flags,
        )
    composite = round(vector.trend_signal, 6)
    probability = round(_clamp01(0.5 + 0.5 * math.tanh(composite * 1.2)), 6)
    curve_prob = round(_clamp01(0.5 + 0.5 * vector.curve_slope_signal), 6)
    confidence = 0.55
    if "TREND_HISTORY_INSUFFICIENT" in vector.quality_flags:
        confidence = 0.25
    return FuturesBaselineForecast(
        futures_model_version=FUTURES_TREND_ONLY_METHOD,
        futures_model_version_number=FUTURES_BASELINE_VERSION,
        baseline_tier="M1",
        outright_up_probability=probability,
        curve_steepen_probability=curve_prob,
        direction_bias=_direction_bias(composite),
        family=vector.family,
        family_supported=True,
        composite_score=composite,
        model_confidence=round(confidence, 6),
        quality_flags=vector.quality_flags,
    )


def compute_family_engineered_baseline(vector: FuturesFeatureVector) -> FuturesBaselineForecast:
    """M8 engineered EQUITY_INDEX baseline from F11 feature vector."""
    if not vector.family_supported:
        return _fail_closed(
            method=FUTURES_ENGINEERED_METHOD,
            tier="M8",
            family=vector.family,
            quality_flags=vector.quality_flags,
        )

    crowding_weight = 0.18 if vector.cot_available else 0.0
    base_weight = 1.0 - crowding_weight
    composite = base_weight * (
        0.58 * vector.trend_signal
        + 0.16 * vector.carry_signal
        + 0.14 * vector.curve_slope_signal
        - 0.12 * vector.leverage_dampener * abs(vector.trend_signal)
    ) + crowding_weight * vector.crowding_signal
    if vector.macro_uncertainty > 0:
        composite *= 0.92
    composite = round(composite, 6)

    probability = round(_clamp01(0.5 + 0.5 * math.tanh(composite * 1.35)), 6)
    curve_prob = round(_clamp01(0.5 + 0.5 * math.tanh(vector.curve_slope_signal * 1.2)), 6)

    confidence = 0.72
    if not vector.cot_available:
        confidence *= 0.88
    if vector.leverage_dampener >= 0.7:
        confidence *= 0.85
    if vector.macro_uncertainty > 0:
        confidence *= 0.9
    if "TREND_HISTORY_INSUFFICIENT" in vector.quality_flags:
        confidence *= 0.5

    return FuturesBaselineForecast(
        futures_model_version=FUTURES_ENGINEERED_METHOD,
        futures_model_version_number=FUTURES_BASELINE_VERSION,
        baseline_tier="M8",
        outright_up_probability=probability,
        curve_steepen_probability=curve_prob,
        direction_bias=_direction_bias(composite),
        family=vector.family,
        family_supported=True,
        composite_score=composite,
        model_confidence=round(_clamp01(confidence), 6),
        quality_flags=vector.quality_flags,
    )


def futures_baseline_forecast_to_dict(result: FuturesBaselineForecast) -> dict[str, Any]:
    return {
        "futures_model_version": result.futures_model_version,
        "futures_model_version_number": result.futures_model_version_number,
        "baseline_tier": result.baseline_tier,
        "outright_up_probability": result.outright_up_probability,
        "curve_steepen_probability": result.curve_steepen_probability,
        "direction_bias": result.direction_bias,
        "family": result.family,
        "family_supported": result.family_supported,
        "futures_composite_score": result.composite_score,
        "futures_model_confidence": result.model_confidence,
        "futures_quality_flags": list(result.quality_flags),
        "research_only": True,
        "experimental": True,
    }


def compute_futures_forecast_from_inputs(
    *,
    instrument_family: str = "ES",
    trend_3m: float | None = None,
    annualized_carry: float | None = None,
    curve_slope: float | None = None,
    curve_slope_change: float | None = None,
    net_percentile: float | None = None,
    crowding_regime: str | None = None,
    stress_score: float | None = None,
    event_window_active: bool = False,
    cot_available: bool = False,
    tier: BaselineTier = "M8",
) -> FuturesBaselineForecast:
    vector = build_futures_feature_vector(
        instrument_family=instrument_family,
        trend_3m=trend_3m,
        annualized_carry=annualized_carry,
        curve_slope=curve_slope,
        curve_slope_change=curve_slope_change,
        net_percentile=net_percentile,
        crowding_regime=crowding_regime,
        stress_score=stress_score,
        event_window_active=event_window_active,
        cot_available=cot_available,
    )
    if tier == "M1":
        return compute_trend_only_baseline(vector)
    return compute_family_engineered_baseline(vector)


def compute_futures_forecast_from_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapter helper — M8 forecast dict for ES workspace rows."""
    vector = futures_feature_vector_from_workspace(payload)
    result = compute_family_engineered_baseline(vector)
    return futures_baseline_forecast_to_dict(result)


__all__ = [
    "FUTURES_BASELINE_VERSION",
    "FUTURES_ENGINEERED_METHOD",
    "FUTURES_TREND_ONLY_METHOD",
    "FuturesBaselineForecast",
    "compute_family_engineered_baseline",
    "compute_futures_forecast_from_inputs",
    "compute_futures_forecast_from_workspace",
    "compute_trend_only_baseline",
    "futures_baseline_forecast_to_dict",
]
