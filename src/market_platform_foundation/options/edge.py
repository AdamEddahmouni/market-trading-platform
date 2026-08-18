"""P vs Q edge decomposition (O4) — no universal score."""

from __future__ import annotations

import hashlib
import json
from typing import Any


EDGE_VERSION = "p_vs_q_edge_v1"


def _latest_horizon(forecast: dict[str, Any]) -> dict[str, Any] | None:
    horizons = forecast.get("horizons", [])
    if not isinstance(horizons, list) or not horizons:
        return None
    latest = horizons[-1]
    return latest if isinstance(latest, dict) else None


def compare_physical_vs_risk_neutral(
    physical_p: dict[str, Any] | None,
    risk_neutral_q: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decompose disagreement between physical P and risk-neutral Q."""
    if not physical_p or not risk_neutral_q:
        return {
            "available": False,
            "reason": "P_OR_Q_UNAVAILABLE",
            "edge_version": EDGE_VERSION,
        }
    if not risk_neutral_q.get("available"):
        return {
            "available": False,
            "reason": risk_neutral_q.get("reason", "Q_UNAVAILABLE"),
            "edge_version": EDGE_VERSION,
        }
    p_horizon = _latest_horizon(physical_p)
    q_horizon = _latest_horizon(risk_neutral_q)
    if not p_horizon or not q_horizon:
        return {
            "available": False,
            "reason": "HORIZON_MISMATCH",
            "edge_version": EDGE_VERSION,
        }
    p_mean = float(p_horizon.get("mean_return", 0.0))
    q_mean = float(q_horizon.get("mean_return", 0.0))
    p_var = float(p_horizon.get("variance", 0.0))
    q_var = float(q_horizon.get("variance", 0.0))
    p_up = float(p_horizon.get("upside_tail_probability", 0.0))
    q_up = float(q_horizon.get("upside_tail_probability", 0.0))
    p_down = float(p_horizon.get("downside_tail_probability", 0.0))
    q_down = float(q_horizon.get("downside_tail_probability", 0.0))
    p_skew = float(p_horizon.get("skew", 0.0))
    q_skew = float(q_horizon.get("skew", 0.0))
    p_vol = physical_p.get("vol_forecast_annualized")
    q_vol = risk_neutral_q.get("vol_implied_annualized")
    vol_edge = None
    if isinstance(p_vol, (int, float)) and isinstance(q_vol, (int, float)):
        vol_edge = float(q_vol) - float(p_vol)
    components = {
        "directional_edge": round(p_mean - q_mean, 6),
        "volatility_edge": round(vol_edge, 6) if vol_edge is not None else None,
        "skew_edge": round(p_skew - q_skew, 6),
        "tail_edge": round(p_up - q_up, 6),
        "downside_tail_edge": round(p_down - q_down, 6),
        "model_confidence": physical_p.get("confidence", "LOW"),
        "data_confidence": risk_neutral_q.get("confidence", "LOW"),
    }
    result = {
        "available": True,
        "edge_version": EDGE_VERSION,
        "components": components,
        "interpretation_hints": _interpretation_hints(components),
    }
    result["replay_hash"] = _replay_hash(result)
    return result


def _interpretation_hints(components: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    directional = components.get("directional_edge")
    if isinstance(directional, (int, float)) and abs(directional) > 0.01:
        if directional > 0:
            hints.append("Physical P forecasts greater mean return than risk-neutral Q")
        else:
            hints.append("Risk-neutral Q prices greater mean return than physical P")
    vol_edge = components.get("volatility_edge")
    if isinstance(vol_edge, (int, float)) and abs(vol_edge) > 0.02:
        hints.append("Implied vol differs from physical vol forecast (VRP context, not trade signal)")
    tail = components.get("tail_edge")
    if isinstance(tail, (int, float)) and abs(tail) > 0.03:
        if tail > 0:
            hints.append("Physical upside tail exceeds market-implied upside tail")
        else:
            hints.append("Market-implied upside tail exceeds physical forecast")
    return hints


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = [
    "EDGE_VERSION",
    "compare_physical_vs_risk_neutral",
]
