"""P vs Q edge decomposition (O4) — no universal score."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from ..contracts.options_quality import OptionQualityFlag

EDGE_VERSION = "p_vs_q_edge_v2"

DEFAULT_EXECUTION_POLICY: dict[str, Any] = {
    "commission_per_contract": 0.65,
    "wide_spread_threshold_bps": 500.0,
    "underlying_price_assumption": 100.0,
}


@dataclass(frozen=True, slots=True)
class ExecutionFrictionInput:
    """Conservative friction estimate from option quote quality."""

    spread_bps: float
    half_spread_return_equiv: float
    commission_return_equiv: float
    total_friction_return_equiv: float
    liquidity_quality: str
    quality_flags: tuple[str, ...] = ()
    sample_count: int = 0


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


def _activity_bid_ask(activity: dict[str, Any]) -> tuple[float, float] | None:
    bid_raw = activity.get("bid")
    ask_raw = activity.get("ask")
    if bid_raw is None or ask_raw is None:
        contract = activity.get("canonical_contract")
        if isinstance(contract, dict):
            bid_raw = contract.get("bid")
            ask_raw = contract.get("ask")
    if bid_raw is None or ask_raw is None:
        return None
    bid = float(bid_raw)
    ask = float(ask_raw)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return bid, ask


def estimate_execution_friction(
    activities: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate spread + commission friction from option activities — fail-closed without quotes."""
    effective_policy = {**DEFAULT_EXECUTION_POLICY, **(policy or {})}
    spread_samples: list[float] = []
    quality_flags: list[str] = []
    for row in activities:
        if not isinstance(row, dict):
            continue
        quotes = _activity_bid_ask(row)
        if quotes is None:
            continue
        bid, ask = quotes
        mid = (bid + ask) / 2.0
        if mid <= 0:
            continue
        spread_bps = ((ask - bid) / mid) * 10000.0
        spread_samples.append(spread_bps)
        if spread_bps > float(effective_policy["wide_spread_threshold_bps"]):
            quality_flags.append(OptionQualityFlag.WIDE_OPTION_SPREAD.value)

    if not spread_samples:
        return {
            "available": False,
            "reason": "NO_TWO_SIDED_QUOTES",
            "executable_available": False,
        }

    avg_spread_bps = sum(spread_samples) / len(spread_samples)
    half_spread_return_equiv = avg_spread_bps / 10000.0
    underlying = float(effective_policy["underlying_price_assumption"])
    commission = float(effective_policy["commission_per_contract"])
    commission_return_equiv = commission / underlying if underlying > 0 else 0.0
    total_friction = half_spread_return_equiv + commission_return_equiv
    liquidity_quality = "LOW"
    if avg_spread_bps <= 200:
        liquidity_quality = "HIGH"
    elif avg_spread_bps <= float(effective_policy["wide_spread_threshold_bps"]):
        liquidity_quality = "MEDIUM"

    friction = ExecutionFrictionInput(
        spread_bps=round(avg_spread_bps, 4),
        half_spread_return_equiv=round(half_spread_return_equiv, 8),
        commission_return_equiv=round(commission_return_equiv, 8),
        total_friction_return_equiv=round(total_friction, 8),
        liquidity_quality=liquidity_quality,
        quality_flags=tuple(sorted(set(quality_flags))),
        sample_count=len(spread_samples),
    )
    return {
        "available": True,
        "executable_available": True,
        "spread_bps": friction.spread_bps,
        "half_spread_return_equiv": friction.half_spread_return_equiv,
        "commission_return_equiv": friction.commission_return_equiv,
        "total_friction_return_equiv": friction.total_friction_return_equiv,
        "liquidity_quality": friction.liquidity_quality,
        "quality_flags": list(friction.quality_flags),
        "sample_count": friction.sample_count,
    }


def apply_executable_edge(
    theoretical_edge: dict[str, Any],
    friction: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply execution friction to theoretical P vs Q components — no universal score."""
    if not theoretical_edge.get("available"):
        return {
            "available": False,
            "reason": theoretical_edge.get("reason", "THEORETICAL_EDGE_UNAVAILABLE"),
            "theoretical_edge": theoretical_edge,
            "executable_available": False,
            "edge_version": EDGE_VERSION,
        }
    if not friction or not friction.get("executable_available"):
        return {
            "available": False,
            "reason": friction.get("reason", "EXECUTION_FRICTION_UNAVAILABLE") if friction else "EXECUTION_FRICTION_UNAVAILABLE",
            "theoretical_edge": theoretical_edge,
            "executable_available": False,
            "edge_version": EDGE_VERSION,
        }

    friction_amount = float(friction["total_friction_return_equiv"])
    theoretical_components = theoretical_edge.get("components", {})
    if not isinstance(theoretical_components, dict):
        theoretical_components = {}

    directional = theoretical_components.get("directional_edge")
    vol_edge = theoretical_components.get("volatility_edge")
    net_directional = None
    net_volatility = None
    if isinstance(directional, (int, float)):
        net_directional = round(float(directional) - friction_amount, 6)
    if isinstance(vol_edge, (int, float)):
        net_volatility = round(float(vol_edge) - friction_amount, 6)

    executable_components = {
        "net_directional_edge": net_directional,
        "net_volatility_edge": net_volatility,
        "skew_edge": theoretical_components.get("skew_edge"),
        "tail_edge": theoretical_components.get("tail_edge"),
        "downside_tail_edge": theoretical_components.get("downside_tail_edge"),
        "model_confidence": theoretical_components.get("model_confidence"),
        "data_confidence": theoretical_components.get("data_confidence"),
    }
    execution_quality = {
        "spread_bps": friction.get("spread_bps"),
        "friction_applied": friction_amount,
        "liquidity_quality": friction.get("liquidity_quality"),
        "quality_flags": friction.get("quality_flags", []),
        "sample_count": friction.get("sample_count", 0),
    }
    result = {
        "available": True,
        "executable_available": True,
        "edge_version": EDGE_VERSION,
        "theoretical_edge": theoretical_edge,
        "executable_edge": {
            "components": executable_components,
            "execution_quality": execution_quality,
        },
    }
    result["replay_hash"] = _replay_hash(result)
    return result


__all__ = [
    "DEFAULT_EXECUTION_POLICY",
    "EDGE_VERSION",
    "ExecutionFrictionInput",
    "apply_executable_edge",
    "compare_physical_vs_risk_neutral",
    "estimate_execution_friction",
]
