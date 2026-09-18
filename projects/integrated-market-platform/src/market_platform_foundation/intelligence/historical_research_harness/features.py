"""Point-in-time bar feature reconstruction for historical research."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ...features.bar_features import BAR_FEATURE_IDS, SUPPORTED_CAPABILITY, derive_bar_features
from .types import FeatureSpec, HISTORICAL_RESEARCH_HARNESS_VERSION, MissingDataBehavior

HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION = "historical-research-bar-features/1.0.0"

DEFAULT_HISTORICAL_RESEARCH_FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec("log_return_1m", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 1),
    FeatureSpec("rolling_vol_5m", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 5),
    FeatureSpec("relative_volume_10m", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 10),
    FeatureSpec("session_gap", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 1),
    FeatureSpec("momentum_5m", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 5),
    FeatureSpec("short_window_range_3m", HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION, 3),
)


def _bar_close(bar: Mapping[str, Any]) -> float | None:
    payload = bar.get("bar_payload")
    if not isinstance(payload, Mapping):
        return None
    try:
        return float(payload.get("close"))
    except (TypeError, ValueError):
        return None


def _bar_volume(bar: Mapping[str, Any]) -> float | None:
    payload = bar.get("bar_payload")
    if not isinstance(payload, Mapping):
        return None
    try:
        return float(payload.get("volume", 0))
    except (TypeError, ValueError):
        return None


def _history_at_cutoff(
    bars: Sequence[Mapping[str, Any]],
    *,
    prediction_cutoff_ns: int,
) -> list[Mapping[str, Any]]:
    eligible = [
        bar
        for bar in bars
        if int(bar.get("available_time", 0)) <= prediction_cutoff_ns
    ]
    eligible.sort(key=lambda row: (int(row["available_time"]), str(row.get("normalized_event_id", ""))))
    return eligible


def reconstruct_historical_research_features(
    bars: Sequence[Mapping[str, Any]],
    *,
    prediction_cutoff_ns: int,
    feature_specs: Sequence[FeatureSpec] = DEFAULT_HISTORICAL_RESEARCH_FEATURES,
) -> dict[str, Any]:
    """Reconstruct research features with explicit cutoff; no future leakage."""

    history = _history_at_cutoff(bars, prediction_cutoff_ns=prediction_cutoff_ns)
    closes = [_bar_close(bar) for bar in history]
    volumes = [_bar_volume(bar) for bar in history]
    values: dict[str, Any] = {}
    warnings: list[str] = []
    for spec in feature_specs:
        key = spec.feature_id
        if len(history) <= spec.lookback_bars:
            if spec.missing_data_behavior == MissingDataBehavior.ZERO:
                values[key] = 0.0
            elif spec.missing_data_behavior == MissingDataBehavior.SKIP:
                values[key] = None
            else:
                values[key] = None
                warnings.append(f"ABSTAIN:{key}:INSUFFICIENT_LOOKBACK")
            continue
        if key == "log_return_1m":
            prev_close = closes[-2]
            last_close = closes[-1]
            if prev_close is None or last_close is None or prev_close <= 0:
                values[key] = None
                warnings.append(f"ABSTAIN:{key}:INVALID_CLOSE")
            else:
                values[key] = math.log(last_close / prev_close)
        elif key == "rolling_vol_5m":
            window = [c for c in closes[-(spec.lookback_bars + 1) :] if c is not None]
            if len(window) < 2:
                values[key] = None
            else:
                rets = [math.log(window[i] / window[i - 1]) for i in range(1, len(window)) if window[i - 1] > 0]
                if not rets:
                    values[key] = None
                else:
                    mean = sum(rets) / len(rets)
                    var = sum((r - mean) ** 2 for r in rets) / len(rets)
                    values[key] = math.sqrt(var)
        elif key == "relative_volume_10m":
            recent = [v for v in volumes[-spec.lookback_bars :] if v is not None]
            current = volumes[-1]
            if not recent or current is None:
                values[key] = None
            else:
                baseline = sum(recent) / len(recent)
                values[key] = (current / baseline) if baseline > 0 else None
        elif key == "session_gap":
            if len(history) < 2:
                values[key] = None
            else:
                prev_close = closes[-2]
                open_px = history[-1].get("bar_payload", {}).get("open")
                try:
                    open_f = float(open_px)
                except (TypeError, ValueError):
                    open_f = None
                if prev_close is None or open_f is None or prev_close <= 0:
                    values[key] = None
                else:
                    values[key] = (open_f - prev_close) / prev_close
        elif key == "momentum_5m":
            start = closes[-(spec.lookback_bars + 1)]
            end = closes[-1]
            if start is None or end is None or start <= 0:
                values[key] = None
            else:
                values[key] = end / start - 1.0
        elif key == "short_window_range_3m":
            highs = []
            lows = []
            for bar in history[-spec.lookback_bars :]:
                payload = bar.get("bar_payload", {})
                if not isinstance(payload, Mapping):
                    continue
                try:
                    highs.append(float(payload.get("high")))
                    lows.append(float(payload.get("low")))
                except (TypeError, ValueError):
                    continue
            if not highs or not lows:
                values[key] = None
            else:
                values[key] = max(highs) - min(lows)
        else:
            values[key] = None
            warnings.append(f"ABSTAIN:{key}:UNKNOWN_FEATURE")
    latest_bar = history[-1] if history else None
    pit_bar_features: list[dict[str, object]] = []
    pit_reasons: list[str] = []
    if latest_bar is not None:
        bars_by_instrument = {str(latest_bar.get("instrument_id", "")): dict(latest_bar)}
        pit_bar_features, pit_reasons = derive_bar_features(
            bars_by_instrument,
            prediction_cutoff=prediction_cutoff_ns,
        )
    return {
        "prediction_cutoff_ns": prediction_cutoff_ns,
        "feature_schema_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "harness_version": HISTORICAL_RESEARCH_HARNESS_VERSION,
        "supported_capability": SUPPORTED_CAPABILITY,
        "path_a_bar_feature_ids": tuple(BAR_FEATURE_IDS),
        "values": values,
        "feature_specs": [
            {
                "feature_id": spec.feature_id,
                "schema_version": spec.schema_version,
                "lookback_bars": spec.lookback_bars,
                "missing_data_behavior": spec.missing_data_behavior.value,
                "cutoff_ns": prediction_cutoff_ns,
            }
            for spec in feature_specs
        ],
        "path_a_bar_features": pit_bar_features,
        "pit_rejection_reasons": pit_reasons,
        "warnings": warnings,
    }


__all__ = [
    "DEFAULT_HISTORICAL_RESEARCH_FEATURES",
    "HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION",
    "reconstruct_historical_research_features",
]
