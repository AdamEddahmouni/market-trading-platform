"""Futures F11 engineered feature vector (EQUITY_INDEX + ENERGY)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..contracts.futures_quality import FuturesQualityFlag
from .families.registry import resolve_family_for_symbol, resolve_family_model
from .positioning import CrowdingRegime

FEATURE_METHOD = "futures_feature_vector_v1"
FEATURE_VERSION = "1"
TREND_SCALE = 2.0
CARRY_SCALE = 0.05
CURVE_SLOPE_SCALE = 0.002
CURVE_CHANGE_SCALE = 0.0005


@dataclass(frozen=True, slots=True)
class FuturesFeatureVector:
    trend_signal: float
    carry_signal: float
    curve_slope_signal: float
    crowding_signal: float
    leverage_dampener: float
    macro_uncertainty: float
    cot_available: bool
    family: str
    family_supported: bool
    feature_method: str
    feature_version: str
    quality_flags: tuple[str, ...] = ()


def _tanh_scale(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _family_supported(instrument_family: str) -> tuple[bool, str]:
    family = resolve_family_for_symbol(instrument_family)
    model = resolve_family_model(family)
    return model is not None, family.value


def build_futures_feature_vector(
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
) -> FuturesFeatureVector:
    """Assemble normalized F3/F4/F5/F7/F8 features for F11 scoring."""
    supported, family_name = _family_supported(instrument_family)
    quality_flags: list[str] = []
    if not supported:
        quality_flags.append("FAMILY_MODEL_UNIMPLEMENTED")
        return FuturesFeatureVector(
            trend_signal=0.0,
            carry_signal=0.0,
            curve_slope_signal=0.0,
            crowding_signal=0.0,
            leverage_dampener=0.0,
            macro_uncertainty=0.0,
            cot_available=False,
            family=family_name,
            family_supported=False,
            feature_method=FEATURE_METHOD,
            feature_version=FEATURE_VERSION,
            quality_flags=tuple(quality_flags),
        )

    if trend_3m is None:
        quality_flags.append(FuturesQualityFlag.TREND_HISTORY_INSUFFICIENT.value)
        trend_signal = 0.0
    else:
        trend_signal = _tanh_scale(float(trend_3m), TREND_SCALE)

    if annualized_carry is None:
        quality_flags.append("CARRY_UNAVAILABLE")
        carry_signal = 0.0
    else:
        carry_signal = _tanh_scale(float(annualized_carry), CARRY_SCALE)

    curve_signal = 0.0
    if curve_slope_change is not None:
        curve_signal = _tanh_scale(float(curve_slope_change), CURVE_CHANGE_SCALE)
    elif curve_slope is not None:
        curve_signal = _tanh_scale(float(curve_slope), CURVE_SLOPE_SCALE)
    else:
        quality_flags.append(FuturesQualityFlag.CURVE_SPARSE.value)

    crowding_signal = 0.0
    if not cot_available or net_percentile is None:
        quality_flags.append(FuturesQualityFlag.POSITIONING_UNKNOWN.value)
        cot_ok = False
    else:
        cot_ok = True
        crowding_signal = 2.0 * (float(net_percentile) - 0.5)
        regime = str(crowding_regime or "").upper()
        if regime == CrowdingRegime.CROWDED_LONG.value:
            crowding_signal = max(crowding_signal, 0.6)
        elif regime == CrowdingRegime.CROWDED_SHORT.value:
            crowding_signal = min(crowding_signal, -0.6)

    if stress_score is None:
        quality_flags.append(FuturesQualityFlag.MARGIN_STALE.value)
        leverage_dampener = 0.0
    else:
        leverage_dampener = _clamp01(float(stress_score))

    macro_uncertainty = 1.0 if event_window_active else 0.0
    if event_window_active:
        quality_flags.append("MACRO_EVENT_WINDOW")

    return FuturesFeatureVector(
        trend_signal=round(trend_signal, 6),
        carry_signal=round(carry_signal, 6),
        curve_slope_signal=round(curve_signal, 6),
        crowding_signal=round(crowding_signal, 6),
        leverage_dampener=round(leverage_dampener, 6),
        macro_uncertainty=round(macro_uncertainty, 6),
        cot_available=cot_ok,
        family=family_name,
        family_supported=True,
        feature_method=FEATURE_METHOD,
        feature_version=FEATURE_VERSION,
        quality_flags=tuple(quality_flags),
    )


def futures_feature_vector_from_workspace(payload: dict[str, Any]) -> FuturesFeatureVector:
    """Build a vector from an ES futures workspace payload."""
    symbol = str(payload.get("symbol") or payload.get("instrument_family") or "ES")
    trend = payload.get("trend_baseline_snapshot")
    trend_3m = None
    if isinstance(trend, dict) and trend.get("trend_3m") is not None:
        trend_3m = float(trend["trend_3m"])

    carry = payload.get("carry_observation") or payload.get("carry_baseline")
    annualized_carry = None
    if isinstance(carry, dict) and carry.get("annualized_carry") is not None:
        annualized_carry = float(carry["annualized_carry"])

    momentum = payload.get("curve_momentum")
    curve_slope = None
    curve_slope_change = None
    if isinstance(momentum, dict):
        if momentum.get("curve_slope") is not None:
            curve_slope = float(momentum["curve_slope"])
        if momentum.get("slope_change") is not None:
            curve_slope_change = float(momentum["slope_change"])

    positioning = payload.get("positioning_snapshot")
    net_percentile = None
    crowding_regime = payload.get("crowding_regime")
    cot_available = bool(payload.get("futures_positioning_available"))
    if isinstance(positioning, dict):
        if positioning.get("net_percentile") is not None:
            net_percentile = float(positioning["net_percentile"])
        if positioning.get("crowding_regime"):
            crowding_regime = positioning.get("crowding_regime")
        if positioning.get("available") is False:
            cot_available = False

    leverage = payload.get("leverage_stress_snapshot")
    stress_score = None
    if isinstance(leverage, dict) and leverage.get("stress_score") is not None:
        stress_score = float(leverage["stress_score"])

    macro = payload.get("macro_event_snapshot")
    event_window = bool(payload.get("event_window_active"))
    if isinstance(macro, dict) and macro.get("event_window_active"):
        event_window = True

    return build_futures_feature_vector(
        instrument_family=symbol,
        trend_3m=trend_3m,
        annualized_carry=annualized_carry,
        curve_slope=curve_slope,
        curve_slope_change=curve_slope_change,
        net_percentile=net_percentile,
        crowding_regime=str(crowding_regime) if crowding_regime else None,
        stress_score=stress_score,
        event_window_active=event_window,
        cot_available=cot_available,
    )


def futures_feature_vector_to_dict(vector: FuturesFeatureVector) -> dict[str, Any]:
    return {
        "feature_method": vector.feature_method,
        "feature_version": vector.feature_version,
        "trend_signal": vector.trend_signal,
        "carry_signal": vector.carry_signal,
        "curve_slope_signal": vector.curve_slope_signal,
        "crowding_signal": vector.crowding_signal,
        "leverage_dampener": vector.leverage_dampener,
        "macro_uncertainty": vector.macro_uncertainty,
        "cot_available": vector.cot_available,
        "family": vector.family,
        "family_supported": vector.family_supported,
        "quality_flags": list(vector.quality_flags),
    }


__all__ = [
    "FEATURE_METHOD",
    "FEATURE_VERSION",
    "FuturesFeatureVector",
    "build_futures_feature_vector",
    "futures_feature_vector_from_workspace",
    "futures_feature_vector_to_dict",
]
