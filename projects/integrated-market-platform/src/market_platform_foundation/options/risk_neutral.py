"""Risk-neutral Q inference from volatility surface (O3)."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from ..contracts.risk_neutral_distribution import (
    RiskNeutralDistributionForecast,
    RiskNeutralHorizonForecast,
    risk_neutral_distribution_to_dict,
)
from .breeden_litzenberger import (
    BL_MODEL_VERSION,
    infer_risk_neutral_breeden_litzenberger,
)
from .surface import infer_underlying_price
from .surface_qa import evaluate_surface_qa

# Honest name: this is a log-normal moment approximation from average IVs,
# not a Breeden–Litzenberger density recovered from a strike continuum.
MODEL_VERSION = "risk_neutral_log_normal_moment_approx_v1"
Q_METHOD = "log_normal_moment_approx"
RATE_ASSUMPTION_MISSING = "RATE_ASSUMPTION_MISSING"
_TAIL_THRESHOLD = 0.05


def _positive_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)
    return None


def _resolve_rate(points: list[dict[str, Any]], rate: float | None) -> float | None:
    for point in points:
        if not isinstance(point, dict):
            continue
        stamped = _positive_float(point.get("rate"))
        if stamped is not None:
            return stamped
    return _positive_float(rate)


def _normal_tail_probability(z: float, tail: str) -> float:
    """Standard normal tail probability using error function."""
    if tail == "up":
        return 0.5 * (1.0 - math.erf(z / math.sqrt(2.0)))
    return 0.5 * (1.0 + math.erf(-z / math.sqrt(2.0)))


def _horizon_from_surface(
    points: list[dict[str, Any]],
    *,
    spot: float,
    rate: float,
) -> RiskNeutralHorizonForecast | None:
    if not points:
        return None
    dte = max(int(points[0].get("dte", 1)), 1)
    sigmas = [
        float(point.get("sigma", 0.0) or 0.0)
        for point in points
        if isinstance(point, dict) and point.get("sigma") is not None
    ]
    if not sigmas:
        return None
    sigma = sum(sigmas) / len(sigmas)
    time_years = dte / 365.0
    variance = sigma ** 2 * time_years
    mean_return = rate * time_years - 0.5 * variance
    std = math.sqrt(max(variance, 1e-12))
    upside_z = (_TAIL_THRESHOLD - mean_return) / std
    downside_z = (-_TAIL_THRESHOLD - mean_return) / std
    upside_tail = _normal_tail_probability(upside_z, "up")
    downside_tail = _normal_tail_probability(downside_z, "down")
    skew = 0.0
    return RiskNeutralHorizonForecast(
        horizon_days=dte,
        mean_return=round(mean_return, 8),
        variance=round(variance, 8),
        upside_tail_probability=round(upside_tail, 6),
        downside_tail_probability=round(downside_tail, 6),
        skew=skew,
    )


def _stamp_q_method(payload: dict[str, Any]) -> dict[str, Any]:
    payload["q_method"] = Q_METHOD
    return payload


def infer_risk_neutral_distribution(
    surface: dict[str, Any],
    *,
    symbol: str = "",
    as_of_time: str = "",
    spot: float | None = None,
    rate: float | None = None,
) -> dict[str, Any]:
    """Infer risk-neutral Q from O2 surface — fail-closed when QA blocks."""
    qa = evaluate_surface_qa(surface)
    if qa.get("blocked"):
        return _stamp_q_method({
            "available": False,
            "reason": "SURFACE_QA_BLOCKED",
            "qa": qa,
        })
    points = surface.get("points", [])
    if not isinstance(points, list) or not points:
        return _stamp_q_method({
            "available": False,
            "reason": "SURFACE_EMPTY",
            "qa": qa,
        })
    inferred_spot: float | None = None
    first = points[0]
    if isinstance(first, dict):
        stamped = first.get("underlying_price")
        if isinstance(stamped, (int, float)) and float(stamped) > 0:
            inferred_spot = float(stamped)
        else:
            inferred_spot = infer_underlying_price(first)
    if inferred_spot is None and isinstance(spot, (int, float)) and float(spot) > 0:
        inferred_spot = float(spot)
    if inferred_spot is None or inferred_spot <= 0:
        return _stamp_q_method({
            "available": False,
            "reason": "UNDERLYING_PRICE_UNKNOWN",
            "qa": qa,
        })
    typed_points = [point for point in points if isinstance(point, dict)]
    resolved_rate = _resolve_rate(typed_points, rate)
    if resolved_rate is None:
        return _stamp_q_method({
            "available": False,
            "reason": RATE_ASSUMPTION_MISSING,
            "qa": qa,
        })
    # Group by expiration for multi-horizon Q
    by_expiry: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        expiry = str(point.get("expiration", ""))
        if expiry:
            by_expiry.setdefault(expiry, []).append(point)
    horizons: list[RiskNeutralHorizonForecast] = []
    for expiry_points in by_expiry.values():
        horizon = _horizon_from_surface(expiry_points, spot=inferred_spot, rate=resolved_rate)
        if horizon is not None:
            horizons.append(horizon)
    if not horizons:
        return _stamp_q_method({
            "available": False,
            "reason": "Q_HORIZON_EXTRACTION_FAILED",
            "qa": qa,
        })
    horizons.sort(key=lambda h: h.horizon_days)
    sigmas = [
        float(point.get("sigma", 0.0) or 0.0)
        for point in points
        if isinstance(point, dict) and point.get("sigma") is not None
    ]
    vol_annualized = sum(sigmas) / len(sigmas) if sigmas else None
    forecast = RiskNeutralDistributionForecast(
        symbol=symbol,
        as_of_time=as_of_time,
        model_version=MODEL_VERSION,
        underlying_price=inferred_spot,
        vol_implied_annualized=vol_annualized,
        horizons=tuple(horizons),
        methodology_tags=(
            "log_normal_moment_approximation",
            "average_iv_not_strike_density",
        ),
        quality_flags=tuple(qa.get("flags", [])),
        confidence="MEDIUM" if len(horizons) >= 2 else "LOW",
        provenance_ref="options:risk_neutral_surface",
    )
    payload = risk_neutral_distribution_to_dict(forecast)
    payload["available"] = True
    payload["qa"] = qa
    _stamp_q_method(payload)
    payload["replay_hash"] = _replay_hash(payload)
    return payload


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = [
    "BL_MODEL_VERSION",
    "MODEL_VERSION",
    "Q_METHOD",
    "RATE_ASSUMPTION_MISSING",
    "infer_risk_neutral_breeden_litzenberger",
    "infer_risk_neutral_distribution",
]
