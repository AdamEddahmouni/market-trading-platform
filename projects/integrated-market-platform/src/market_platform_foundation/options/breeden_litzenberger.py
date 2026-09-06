"""Discrete Breeden–Litzenberger Q from an IV-reconstructed call curve.

Fail-closed additive path. Default O3 remains the log-normal moment
approximation in ``risk_neutral.py``. Never fall back to average-IV log-normal.
"""

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
from .iv import bsm_price
from .surface import infer_underlying_price
from .surface_qa import evaluate_surface_qa

BL_MODEL_VERSION = "risk_neutral_breeden_litzenberger_v1"
Q_METHOD = "breeden_litzenberger"
MIN_UNIQUE_STRIKES = 5
DENSITY_MASS_MIN = 0.85
DENSITY_MASS_MAX = 1.15
TAIL_THRESHOLD = 0.05
_CALL_RECONSTRUCTION_ABS_TOL = 1e-6
_CALL_RECONSTRUCTION_REL_TOL = 1e-4
_NEGATIVE_DENSITY_EPS = 0.0

RATE_ASSUMPTION_MISSING = "RATE_ASSUMPTION_MISSING"
BL_DUPLICATE_STRIKE = "BL_DUPLICATE_STRIKE"
BL_INSUFFICIENT_STRIKES = "BL_INSUFFICIENT_STRIKES"
BL_NEGATIVE_DENSITY = "BL_NEGATIVE_DENSITY"
BL_DENSITY_MASS_INVALID = "BL_DENSITY_MASS_INVALID"
BL_INCONSISTENT_RECONSTRUCTED_CALL = "BL_INCONSISTENT_RECONSTRUCTED_CALL"
BL_POINT_INCOMPLETE = "BL_POINT_INCOMPLETE"


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


def _unavailable(reason: str, qa: dict[str, Any]) -> dict[str, Any]:
    return {"available": False, "reason": reason, "qa": qa, "q_method": Q_METHOD}


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _call_put(point: dict[str, Any]) -> str:
    raw = str(point.get("call_put") or point.get("option_type") or "call").lower()
    return "put" if raw == "put" else "call"


def _reconstruct_call(
    point: dict[str, Any],
    *,
    spot: float,
    rate: float,
    time_years: float,
) -> float | None:
    strike = _positive_float(point.get("strike"))
    sigma = _positive_float(point.get("sigma"))
    if strike is None or sigma is None:
        return None
    kind = _call_put(point)
    price = bsm_price(spot, strike, time_years, rate, sigma, kind)
    if kind == "call":
        return price
    return price + spot - strike * math.exp(-rate * time_years)


def _calls_inconsistent(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right), 1.0)
    tol = max(_CALL_RECONSTRUCTION_ABS_TOL, _CALL_RECONSTRUCTION_REL_TOL * scale)
    return abs(left - right) > tol


def _unique_call_curve(
    points: list[dict[str, Any]],
    *,
    spot: float,
    rate: float,
    time_years: float,
) -> tuple[list[tuple[float, float]] | None, str | None]:
    grouped: dict[float, list[dict[str, Any]]] = {}
    for point in points:
        strike = _positive_float(point.get("strike"))
        if strike is None or _positive_float(point.get("sigma")) is None:
            return None, BL_POINT_INCOMPLETE
        grouped.setdefault(strike, []).append(point)

    curve: list[tuple[float, float]] = []
    for strike in sorted(grouped):
        family = grouped[strike]
        calls = [p for p in family if _call_put(p) == "call"]
        puts = [p for p in family if _call_put(p) == "put"]
        if len(calls) > 1 or len(puts) > 1 or (not calls and not puts):
            return None, BL_DUPLICATE_STRIKE
        reconstructed: list[float] = []
        preferred: float | None = None
        if calls:
            value = _reconstruct_call(calls[0], spot=spot, rate=rate, time_years=time_years)
            if value is None:
                return None, BL_POINT_INCOMPLETE
            reconstructed.append(value)
            preferred = value
        if puts:
            value = _reconstruct_call(puts[0], spot=spot, rate=rate, time_years=time_years)
            if value is None:
                return None, BL_POINT_INCOMPLETE
            reconstructed.append(value)
            if preferred is None:
                preferred = value
        if preferred is None:
            return None, BL_POINT_INCOMPLETE
        if len(reconstructed) == 2 and _calls_inconsistent(reconstructed[0], reconstructed[1]):
            return None, BL_INCONSISTENT_RECONSTRUCTED_CALL
        curve.append((strike, preferred))
    return curve, None


def _second_derivative(c_prev: float, c_i: float, c_next: float, h1: float, h2: float) -> float:
    return (2.0 / (h1 + h2)) * ((c_next - c_i) / h2 - (c_i - c_prev) / h1)


def _trapezoid(nodes: list[tuple[float, float]]) -> float:
    if len(nodes) < 2:
        return 0.0
    total = 0.0
    for index in range(len(nodes) - 1):
        k0, q0 = nodes[index]
        k1, q1 = nodes[index + 1]
        total += 0.5 * (q0 + q1) * (k1 - k0)
    return total


def _horizon_from_expiry(
    points: list[dict[str, Any]],
    *,
    spot: float,
    rate: float,
) -> tuple[RiskNeutralHorizonForecast | None, float | None, str | None]:
    dte = max(int(points[0].get("dte", 1)), 1)
    time_years = dte / 365.0
    curve, reason = _unique_call_curve(points, spot=spot, rate=rate, time_years=time_years)
    if curve is None:
        return None, None, reason
    if len(curve) < MIN_UNIQUE_STRIKES:
        return None, None, BL_INSUFFICIENT_STRIKES

    densities: list[tuple[float, float]] = []
    for index in range(1, len(curve) - 1):
        k_prev, c_prev = curve[index - 1]
        k_i, c_i = curve[index]
        k_next, c_next = curve[index + 1]
        h1 = k_i - k_prev
        h2 = k_next - k_i
        if h1 <= 0.0 or h2 <= 0.0:
            return None, None, BL_DUPLICATE_STRIKE
        call_dd = _second_derivative(c_prev, c_i, c_next, h1, h2)
        density = math.exp(rate * time_years) * call_dd
        if density < _NEGATIVE_DENSITY_EPS:
            return None, None, BL_NEGATIVE_DENSITY
        densities.append((k_i, density))

    mass = _trapezoid(densities)
    if mass < DENSITY_MASS_MIN or mass > DENSITY_MASS_MAX:
        return None, None, BL_DENSITY_MASS_INVALID

    mean_acc = 0.0
    second_acc = 0.0
    third_acc = 0.0
    upside = 0.0
    downside = 0.0
    for index in range(len(densities) - 1):
        k0, q0 = densities[index]
        k1, q1 = densities[index + 1]
        width = k1 - k0
        r0 = k0 / spot - 1.0
        r1 = k1 / spot - 1.0
        weight = 0.5 * (q0 + q1) * width
        r_mid = 0.5 * (r0 + r1)
        mean_acc += r_mid * weight
        second_acc += (r0 * r0 * q0 + r1 * r1 * q1) * 0.5 * width
        third_acc += (r0 ** 3 * q0 + r1 ** 3 * q1) * 0.5 * width
        if r0 > TAIL_THRESHOLD and r1 > TAIL_THRESHOLD:
            upside += weight
        elif r0 < -TAIL_THRESHOLD and r1 < -TAIL_THRESHOLD:
            downside += weight
        else:
            for strike, density in ((k0, q0), (k1, q1)):
                simple = strike / spot - 1.0
                slice_mass = 0.25 * (q0 + q1) * width
                if simple > TAIL_THRESHOLD:
                    upside += slice_mass
                elif simple < -TAIL_THRESHOLD:
                    downside += slice_mass

    variance = max(second_acc - mean_acc * mean_acc, 0.0)
    std = math.sqrt(variance) if variance > 0.0 else 0.0
    centered_third = third_acc - 3.0 * mean_acc * second_acc + 2.0 * mean_acc ** 3
    skew = centered_third / (std ** 3) if std > 1e-12 else 0.0
    vol_annualized = math.sqrt(variance / time_years) if time_years > 0.0 else None
    horizon = RiskNeutralHorizonForecast(
        horizon_days=dte,
        mean_return=round(mean_acc, 8),
        variance=round(variance, 8),
        upside_tail_probability=round(upside, 6),
        downside_tail_probability=round(downside, 6),
        skew=round(skew, 8),
    )
    return horizon, vol_annualized, None


def infer_risk_neutral_breeden_litzenberger(
    surface: dict[str, Any],
    *,
    symbol: str = "",
    as_of_time: str = "",
    spot: float | None = None,
    rate: float | None = None,
) -> dict[str, Any]:
    """Discrete finite-difference Breeden–Litzenberger Q. Fail-closed, no log-normal fallback."""
    qa = evaluate_surface_qa(surface)
    if qa.get("blocked"):
        return _unavailable("SURFACE_QA_BLOCKED", qa)
    points = surface.get("points", [])
    if not isinstance(points, list) or not points:
        return _unavailable("SURFACE_EMPTY", qa)

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
        return _unavailable("UNDERLYING_PRICE_UNKNOWN", qa)

    typed_points = [point for point in points if isinstance(point, dict)]
    resolved_rate = _resolve_rate(typed_points, rate)
    if resolved_rate is None:
        return _unavailable(RATE_ASSUMPTION_MISSING, qa)

    by_expiry: dict[str, list[dict[str, Any]]] = {}
    for point in typed_points:
        expiry = str(point.get("expiration", ""))
        if expiry:
            by_expiry.setdefault(expiry, []).append(point)
    if not by_expiry:
        return _unavailable(BL_INSUFFICIENT_STRIKES, qa)

    horizons: list[RiskNeutralHorizonForecast] = []
    vols: list[float] = []
    for expiry_points in by_expiry.values():
        horizon, vol_annualized, reason = _horizon_from_expiry(
            expiry_points,
            spot=inferred_spot,
            rate=resolved_rate,
        )
        if reason is not None or horizon is None:
            return _unavailable(reason or BL_INSUFFICIENT_STRIKES, qa)
        horizons.append(horizon)
        if vol_annualized is not None:
            vols.append(vol_annualized)

    horizons.sort(key=lambda item: item.horizon_days)
    vol_implied = vols[0] if vols else None
    forecast = RiskNeutralDistributionForecast(
        symbol=symbol,
        as_of_time=as_of_time,
        model_version=BL_MODEL_VERSION,
        underlying_price=inferred_spot,
        vol_implied_annualized=vol_implied,
        horizons=tuple(horizons),
        methodology_tags=(
            "breeden_litzenberger_finite_difference",
            "iv_reconstructed_call_curve",
        ),
        quality_flags=tuple(qa.get("flags", [])),
        confidence="MEDIUM" if len(horizons) >= 2 else "LOW",
        provenance_ref="options:risk_neutral_breeden_litzenberger",
    )
    payload = risk_neutral_distribution_to_dict(forecast)
    payload["available"] = True
    payload["qa"] = qa
    payload["rate"] = resolved_rate
    payload["q_method"] = Q_METHOD
    payload["replay_hash"] = _replay_hash(payload)
    return payload


__all__ = [
    "BL_DENSITY_MASS_INVALID",
    "BL_DUPLICATE_STRIKE",
    "BL_INCONSISTENT_RECONSTRUCTED_CALL",
    "BL_INSUFFICIENT_STRIKES",
    "BL_MODEL_VERSION",
    "Q_METHOD",
    "BL_NEGATIVE_DENSITY",
    "BL_POINT_INCOMPLETE",
    "DENSITY_MASS_MAX",
    "DENSITY_MASS_MIN",
    "MIN_UNIQUE_STRIKES",
    "RATE_ASSUMPTION_MISSING",
    "TAIL_THRESHOLD",
    "infer_risk_neutral_breeden_litzenberger",
]
