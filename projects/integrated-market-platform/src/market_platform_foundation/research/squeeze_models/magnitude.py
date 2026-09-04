"""SS P7 squeeze magnitude baseline — separate from occurrence probability."""

from __future__ import annotations

from typing import Any, Sequence

MODEL_VERSION = "ss_magnitude_baseline_v1"
METHOD = "PHYSICAL_FORECAST_SQUEEZE_CONTEXT_V1"


def predict_squeeze_magnitude(
    features: Sequence[float],
    *,
    squeeze_context: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate conditional move magnitude — fail-closed without physical forecast."""
    if not physical_forecast or not isinstance(physical_forecast, dict):
        return {
            "expected_move_pct": None,
            "upside_tail_pct": None,
            "method": METHOD,
            "model_version": MODEL_VERSION,
            "status": "UNAVAILABLE",
            "note": "Physical distribution forecast required for magnitude estimate",
        }

    vol = physical_forecast.get("vol_forecast_annualized")
    if not isinstance(vol, (int, float)) or vol <= 0:
        return {
            "expected_move_pct": None,
            "upside_tail_pct": None,
            "method": METHOD,
            "model_version": MODEL_VERSION,
            "status": "UNAVAILABLE",
            "note": "vol_forecast_annualized missing or invalid",
        }

    horizons = physical_forecast.get("horizons", [])
    upside_tail = None
    if isinstance(horizons, list) and horizons:
        latest = horizons[-1]
        if isinstance(latest, dict):
            raw_upside = latest.get("upside_tail_probability")
            if isinstance(raw_upside, (int, float)):
                upside_tail = float(raw_upside)

    # Base expected move from annualized vol scaled to 5-day horizon
    daily_vol = float(vol) / (252 ** 0.5)
    expected_move = round(daily_vol * (5 ** 0.5) * 100.0, 4)

    state_boost = 0.0
    fuel_boost = 0.0
    if squeeze_context and squeeze_context.get("available"):
        state = str(squeeze_context.get("squeeze_state", "")).upper()
        if state == "ACTIVE_SQUEEZE":
            state_boost = 0.35
        elif state in {"VULNERABLE", "IGNITION_WATCH", "LIVE_CONFIRMATION"}:
            state_boost = 0.15
        remaining = squeeze_context.get("remaining_squeeze_fuel")
        if remaining is None:
            remaining = squeeze_context.get("remaining_fuel")
        if isinstance(remaining, (int, float)):
            fuel_boost = min(float(remaining) / 200.0, 0.25)

    feature_boost = float(features[0]) * 0.1 if features else 0.0
    adjusted_move = round(expected_move * (1.0 + state_boost + fuel_boost + feature_boost), 4)
    upside_tail_pct = None
    if upside_tail is not None:
        upside_tail_pct = round(upside_tail * 100.0 * (1.0 + state_boost), 4)

    return {
        "expected_move_pct": adjusted_move,
        "upside_tail_pct": upside_tail_pct,
        "method": METHOD,
        "model_version": MODEL_VERSION,
        "status": "RESEARCH_ONLY",
        "note": "Magnitude baseline uses physical forecast + squeeze context; not walk-forward calibrated",
    }


__all__ = ["METHOD", "MODEL_VERSION", "predict_squeeze_magnitude"]
