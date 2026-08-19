"""Squeeze context features for Options P forecast conditioning (SHARED P3)."""

from __future__ import annotations

from typing import Any, Sequence


def build_squeeze_context_for_options(causal_intelligence: dict[str, Any] | None) -> dict[str, Any]:
    """Extract squeeze lane context for Options consumers — fail-closed when unavailable."""
    if not causal_intelligence or not isinstance(causal_intelligence, dict):
        return {
            "available": False,
            "reason": "SQUEEZE_CAUSAL_UNAVAILABLE",
        }
    state = causal_intelligence.get("state")
    if not state:
        return {
            "available": False,
            "reason": "SQUEEZE_STATE_MISSING",
        }
    ignition_strength = causal_intelligence.get("ignition_strength")
    if ignition_strength is None:
        ignition_strength = causal_intelligence.get("overall_confidence")
    structural = causal_intelligence.get("structural_vulnerability")
    if structural is None and str(state).upper() in {"VULNERABLE", "IGNITION_WATCH", "ACTIVE_SQUEEZE"}:
        structural = True
    return {
        "available": True,
        "squeeze_state": str(state),
        "ignition_strength": str(ignition_strength or "LOW"),
        "structural_vulnerability": bool(structural),
        "exhaustion_risk": causal_intelligence.get("exhaustion_risk"),
        "remaining_squeeze_fuel": causal_intelligence.get("remaining_fuel")
        if causal_intelligence.get("remaining_fuel") is not None
        else causal_intelligence.get("remaining_squeeze_fuel"),
        "model_version": causal_intelligence.get("model_version", ""),
        "provenance_ref": "squeeze:causal_intelligence",
    }


def augment_features_with_context(
    features: Sequence[float],
    *,
    squeeze_context: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
) -> list[float]:
    """Augment baseline feature vector with SHARED P2 magnitude and squeeze context."""
    augmented = list(features)
    if squeeze_context and squeeze_context.get("available"):
        state = str(squeeze_context.get("squeeze_state", "")).upper()
        state_boost = 0.0
        if state in {"VULNERABLE", "IGNITION_WATCH"}:
            state_boost = 0.15
        elif state == "ACTIVE_SQUEEZE":
            state_boost = 0.35
        augmented.append(state_boost)
        if squeeze_context.get("structural_vulnerability"):
            augmented.append(0.2)
    if physical_forecast and isinstance(physical_forecast, dict):
        vol = physical_forecast.get("vol_forecast_annualized")
        if isinstance(vol, (int, float)):
            augmented.append(float(vol))
        horizons = physical_forecast.get("horizons", [])
        if isinstance(horizons, list) and horizons:
            latest = horizons[-1]
            if isinstance(latest, dict):
                upside = latest.get("upside_tail_probability")
                if isinstance(upside, (int, float)):
                    augmented.append(float(upside))
    return augmented


__all__ = [
    "augment_features_with_context",
    "build_squeeze_context_for_options",
]
