"""Volatility surface σ(K,T) builder (O2)."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from .iv import dual_track_iv


def infer_underlying_price(activity: dict[str, Any], strike: float, call_put: str) -> float:
    raw = activity.get("underlying_price")
    if isinstance(raw, (int, float)) and raw > 0:
        return float(raw)
    if call_put == "call":
        return strike * 1.02
    return strike * 0.98


def build_surface_point(
    activity: dict[str, Any],
    *,
    rate: float = 0.05,
) -> dict[str, Any] | None:
    bid = float(activity.get("bid", 0.0))
    ask = float(activity.get("ask", 0.0))
    if bid <= 0 or ask <= 0:
        return None
    mid = (bid + ask) / 2.0
    strike = float(activity.get("strike", 0.0))
    expiry = str(activity.get("expiry", ""))
    option_type = str(activity.get("option_type", "call")).lower()
    event_time = str(activity.get("event_time", ""))
    if not strike or not expiry or not event_time:
        return None
    from datetime import date

    event_date = date.fromisoformat(event_time[:10])
    expiry_date = date.fromisoformat(expiry[:10])
    dte = max((expiry_date - event_date).days, 1)
    time_years = dte / 365.0
    spot = infer_underlying_price(activity, strike, option_type)
    call_put = "call" if option_type == "call" else "put"
    provider_iv_raw = activity.get("provider_iv")
    provider_iv = float(provider_iv_raw) if isinstance(provider_iv_raw, (int, float)) else None
    iv_track = dual_track_iv(
        market_price=mid,
        spot=spot,
        strike=strike,
        time_years=time_years,
        rate=rate,
        call_put=call_put,
        provider_iv=provider_iv,
    )
    quality_flags: list[str] = []
    if iv_track["iv_invalid"]:
        quality_flags.append(OptionQualityFlag.IV_INVALID.value)
    return {
        "strike": strike,
        "expiration": expiry,
        "dte": dte,
        "call_put": call_put,
        "sigma": iv_track["internal_iv"],
        "internal_iv": iv_track["internal_iv"],
        "provider_iv": iv_track["provider_iv"],
        "solver_version": iv_track["solver_version"],
        "quality_flags": quality_flags,
    }


def build_volatility_surface(
    activities: list[dict[str, Any]],
    *,
    rate: float = 0.05,
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        point = build_surface_point(activity, rate=rate)
        if point is not None:
            points.append(point)
    return {
        "point_count": len(points),
        "points": points,
        "surface_version": "sigma_kt_v1",
    }


__all__ = ["build_surface_point", "build_volatility_surface", "infer_underlying_price"]
