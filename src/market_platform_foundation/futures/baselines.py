"""Futures trend + carry baselines (F5) — empirical features, not directional forecasts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from ..contracts.futures import (
    FuturesCarryBaseline,
    FuturesCurveMomentum,
    FuturesCurveSnapshot,
    FuturesTrendBaselineSnapshot,
    carry_baseline_to_dict,
    curve_momentum_to_dict,
    trend_baseline_to_dict,
)
from ..contracts.futures_quality import (
    FuturesQualityFlag,
    quality_blocks_baseline_interpretation,
    quality_blocks_curve_analytics,
)
from ..providers.contracts import ProviderResult
from ..research.distribution.ewma import ewma_volatility_forecast


BASELINES_VERSION = "futures_baselines_v1"

TREND_LOOKBACK_1M = 21
TREND_LOOKBACK_3M = 63
TREND_LOOKBACK_6M = 126
TREND_LOOKBACK_12M = 252

TREND_UP_THRESHOLD = 0.5
TREND_DOWN_THRESHOLD = -0.5

MIN_BARS_FOR_BASELINES = TREND_LOOKBACK_3M


class TrendRegime(StrEnum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class CalendarSpreadMomentum:
    """Label for curve slope change — context only."""

    label: str
    disclaimer: str = "Curve momentum ≠ directional forecast"


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _decision_time_iso(decision_time: int | str) -> str:
    if isinstance(decision_time, int):
        secs = decision_time // 1_000_000_000
        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    return str(decision_time)


def _bar_event_time(bar: dict[str, Any]) -> str:
    return str(bar.get("event_time") or bar.get("date") or bar.get("available_time", ""))


def _bar_close(bar: dict[str, Any]) -> float | None:
    close = bar.get("close") or bar.get("settlement_price") or bar.get("price")
    if close is None:
        return None
    return float(close)


def extract_bars_and_sidecar(events: tuple[dict[str, Any], ...]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    sidecar: dict[str, Any] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("_meta"):
            sidecar = event
        else:
            bars.append(event)
    return bars, sidecar


def filter_pit_bars(
    bars: list[dict[str, Any]],
    decision_time: int | str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return PIT-valid settlement bars and accumulated quality flags."""
    decision_iso = _decision_time_iso(decision_time)
    dec_dt = _parse_date(decision_iso)
    quality_flags: list[str] = []
    pit_valid: list[dict[str, Any]] = []

    for bar in bars:
        event_time = _bar_event_time(bar)
        if not event_time:
            continue
        bar_dt = _parse_date(event_time)
        if dec_dt is not None and bar_dt is not None and bar_dt > dec_dt:
            continue
        pit_valid.append(bar)

    pit_valid.sort(key=_bar_event_time)
    if len(pit_valid) < MIN_BARS_FOR_BASELINES:
        quality_flags.append(FuturesQualityFlag.TREND_HISTORY_INSUFFICIENT.value)

    return pit_valid, quality_flags


def compute_vol_scaled_trend(
    closes: list[float],
    lookback: int,
    vol: float | None,
) -> float | None:
    """Vol-scaled return over lookback — fail-closed when vol missing."""
    if vol is None or vol <= 0 or len(closes) < lookback + 1:
        return None
    current = closes[-1]
    prior = closes[-1 - lookback]
    if prior <= 0:
        return None
    raw_return = (current / prior) - 1.0
    return raw_return / vol


def compute_trend_features(closes: list[float], vol: float | None) -> tuple[dict[str, float | None], dict[str, int]]:
    """Compute trend_1m/3m/6m/12m with fixture-bounded lookbacks when history sparse."""
    lookbacks = {
        "trend_1m": TREND_LOOKBACK_1M,
        "trend_3m": TREND_LOOKBACK_3M,
        "trend_6m": TREND_LOOKBACK_6M,
        "trend_12m": TREND_LOOKBACK_12M,
    }
    features: dict[str, float | None] = {}
    bars_used: dict[str, int] = {}
    for key, target_lookback in lookbacks.items():
        effective_lookback = min(target_lookback, len(closes) - 1)
        if effective_lookback < 1:
            features[key] = None
            bars_used[key] = 0
            continue
        features[key] = compute_vol_scaled_trend(closes, effective_lookback, vol)
        bars_used[key] = effective_lookback
    return features, bars_used


def trend_regime(features: dict[str, float | None]) -> TrendRegime:
    """Classify trend from 3m vol-scaled feature — label only."""
    trend_3m = features.get("trend_3m")
    if trend_3m is None:
        return TrendRegime.NEUTRAL
    if trend_3m >= TREND_UP_THRESHOLD:
        return TrendRegime.TREND_UP
    if trend_3m <= TREND_DOWN_THRESHOLD:
        return TrendRegime.TREND_DOWN
    return TrendRegime.NEUTRAL


def compute_carry_percentile(current_carry: float, history_carries: list[float]) -> float | None:
    if not history_carries:
        return None
    sorted_carries = sorted(history_carries)
    rank = sum(1 for value in sorted_carries if value <= current_carry)
    return rank / len(sorted_carries)


def compute_carry_zscore(current_carry: float, history_carries: list[float]) -> float | None:
    if len(history_carries) < 2:
        return None
    mean = sum(history_carries) / len(history_carries)
    variance = sum((value - mean) ** 2 for value in history_carries) / len(history_carries)
    if variance <= 0:
        return 0.0
    return (current_carry - mean) / math.sqrt(variance)


def compute_carry_change(current_carry: float, prior_carry: float | None) -> float | None:
    if prior_carry is None:
        return None
    return current_carry - prior_carry


def compute_curve_slope(snapshot: FuturesCurveSnapshot) -> float | None:
    if quality_blocks_curve_analytics(snapshot.quality_flags):
        return None
    if len(snapshot.prices) < 2:
        return None
    front = float(snapshot.prices[0])
    back = float(snapshot.prices[-1])
    if front <= 0:
        return None
    return (back - front) / front


def compute_curve_momentum(
    current_slope: float | None,
    history_slopes: list[float],
) -> FuturesCurveMomentum:
    if current_slope is None:
        return FuturesCurveMomentum(
            quality_flags=(FuturesQualityFlag.CURVE_SPARSE.value,),
        )

    slope_change: float | None = None
    momentum_label = "FLAT"
    if history_slopes:
        prior_slope = history_slopes[-1]
        slope_change = current_slope - prior_slope
        if slope_change > 0.0001:
            momentum_label = "STEEPENING"
        elif slope_change < -0.0001:
            momentum_label = "FLATTENING"
        else:
            momentum_label = "STABLE"

    regime = "contango" if current_slope > 0 else "backwardation" if current_slope < 0 else "flat"

    return FuturesCurveMomentum(
        curve_slope=current_slope,
        slope_change=slope_change,
        calendar_spread_momentum=momentum_label,
        regime=regime,
    )


def build_trend_baseline_snapshot(
    bars: list[dict[str, Any]],
    *,
    instrument_family: str,
    quality_flags: tuple[str, ...] = (),
) -> FuturesTrendBaselineSnapshot | None:
    closes = [_bar_close(bar) for bar in bars]
    closes = [value for value in closes if value is not None]
    if len(closes) < MIN_BARS_FOR_BASELINES:
        return None

    vol = ewma_volatility_forecast(closes)
    features, bars_used = compute_trend_features(closes, vol)
    observation_time = _bar_event_time(bars[-1]) if bars else ""

    return FuturesTrendBaselineSnapshot(
        instrument_family=instrument_family,
        trend_1m=features.get("trend_1m"),
        trend_3m=features.get("trend_3m"),
        trend_6m=features.get("trend_6m"),
        trend_12m=features.get("trend_12m"),
        vol_estimate=vol,
        lookback_bars_used=tuple((key, bars_used[key]) for key in sorted(bars_used.keys())),
        observation_time=observation_time,
        quality_flags=quality_flags,
        provenance_ref="bars.fixture.futures_settlement",
    )


def build_carry_baseline(
    carry_observation: dict[str, Any],
    carry_history: list[dict[str, Any]],
) -> FuturesCarryBaseline | None:
    if not carry_observation.get("available"):
        return None
    annualized_carry = carry_observation.get("annualized_carry")
    if annualized_carry is None:
        return None
    current = float(annualized_carry)
    history_values: list[float] = []
    for row in carry_history:
        if not isinstance(row, dict):
            continue
        value = row.get("annualized_carry")
        if value is not None:
            history_values.append(float(value))

    percentile = compute_carry_percentile(current, history_values) if history_values else None
    zscore = compute_carry_zscore(current, history_values) if history_values else None
    prior = history_values[-1] if history_values else None
    change = compute_carry_change(current, prior)

    return FuturesCarryBaseline(
        annualized_carry=current,
        carry_percentile=percentile,
        carry_change=change,
        carry_zscore=round(zscore, 6) if zscore is not None else None,
        formula_tag=str(carry_observation.get("formula_tag", "")),
    )


def baselines_payload(
    bars_result: ProviderResult,
    curve_snapshot: FuturesCurveSnapshot | None,
    carry_observation: dict[str, Any],
    *,
    decision_time: int | str,
) -> dict[str, Any]:
    """Build workspace baselines payload with fail-closed semantics."""
    quality_flags: list[str] = []

    if bars_result.status != "available" or not bars_result.events:
        return {
            "available": False,
            "reason": bars_result.reason_code or "BARS_UNAVAILABLE",
            "futures_baselines_available": False,
            "baselines_version": BASELINES_VERSION,
        }

    raw_bars, sidecar = extract_bars_and_sidecar(bars_result.events)
    pit_bars, pit_flags = filter_pit_bars(raw_bars, decision_time)
    quality_flags.extend(pit_flags)

    instrument_family = str(sidecar.get("instrument_family", "ES"))
    trend_snapshot = build_trend_baseline_snapshot(
        pit_bars,
        instrument_family=instrument_family,
        quality_flags=tuple(quality_flags),
    )

    if trend_snapshot is None:
        quality_flags.append(FuturesQualityFlag.TREND_HISTORY_INSUFFICIENT.value)

    carry_history = sidecar.get("carry_history", [])
    if not isinstance(carry_history, list):
        carry_history = []
    carry_baseline = build_carry_baseline(carry_observation, carry_history)

    curve_slope_history = sidecar.get("curve_slope_history", [])
    if not isinstance(curve_slope_history, list):
        curve_slope_history = []
    history_slopes = [
        float(row["slope"])
        for row in curve_slope_history
        if isinstance(row, dict) and row.get("slope") is not None
    ]
    current_slope = compute_curve_slope(curve_snapshot) if curve_snapshot is not None else None
    curve_momentum = compute_curve_momentum(current_slope, history_slopes)

    combined_flags = tuple(dict.fromkeys(quality_flags))
    blocked = quality_blocks_baseline_interpretation(combined_flags)

    trend_dict: dict[str, Any] | None = None
    regime = TrendRegime.NEUTRAL
    if trend_snapshot is not None:
        trend_dict = trend_baseline_to_dict(trend_snapshot)
        trend_dict["baselines_version"] = BASELINES_VERSION
        regime = trend_regime(
            {
                "trend_1m": trend_snapshot.trend_1m,
                "trend_3m": trend_snapshot.trend_3m,
                "trend_6m": trend_snapshot.trend_6m,
                "trend_12m": trend_snapshot.trend_12m,
            }
        )

    carry_dict = carry_baseline_to_dict(carry_baseline) if carry_baseline is not None else None
    momentum_dict = curve_momentum_to_dict(curve_momentum)

    available = (
        not blocked
        and trend_snapshot is not None
        and trend_snapshot.vol_estimate is not None
        and trend_snapshot.trend_3m is not None
    )

    return {
        "available": available,
        "futures_baselines_available": available,
        "trend_baseline_snapshot": trend_dict,
        "carry_baseline": carry_dict,
        "curve_momentum": momentum_dict,
        "trend_regime": regime.value,
        "quality_flags": list(combined_flags),
        "baselines_version": BASELINES_VERSION,
    }


__all__ = [
    "BASELINES_VERSION",
    "MIN_BARS_FOR_BASELINES",
    "TREND_DOWN_THRESHOLD",
    "TREND_LOOKBACK_1M",
    "TREND_LOOKBACK_3M",
    "TREND_LOOKBACK_6M",
    "TREND_LOOKBACK_12M",
    "TREND_UP_THRESHOLD",
    "CalendarSpreadMomentum",
    "TrendRegime",
    "baselines_payload",
    "build_carry_baseline",
    "build_trend_baseline_snapshot",
    "compute_carry_change",
    "compute_carry_percentile",
    "compute_carry_zscore",
    "compute_curve_momentum",
    "compute_curve_slope",
    "compute_trend_features",
    "compute_vol_scaled_trend",
    "extract_bars_and_sidecar",
    "filter_pit_bars",
    "trend_regime",
]
