"""Volatility surface σ(K,T) builder (O2)."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from .edge import infer_underlying_price_from_activities
from .flow import _resolve_rate
from .iv import dual_track_iv

SURFACE_VERSION = "sigma_kt_v3"


def infer_underlying_price(activity: dict[str, Any]) -> float | None:
    """First positive underlying_price on the row or nested canonical_contract."""
    return infer_underlying_price_from_activities([activity])


def build_surface_point(
    activity: dict[str, Any],
    *,
    rate: float | None = None,
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
    spot = infer_underlying_price(activity)
    if spot is None:
        return None
    resolved_rate = _resolve_rate([activity], rate)
    if resolved_rate is None:
        return None
    call_put = "call" if option_type == "call" else "put"
    provider_iv_raw = activity.get("provider_iv")
    provider_iv = float(provider_iv_raw) if isinstance(provider_iv_raw, (int, float)) else None
    iv_track = dual_track_iv(
        market_price=mid,
        spot=spot,
        strike=strike,
        time_years=time_years,
        rate=resolved_rate,
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
        "underlying_price": spot,
        "rate": resolved_rate,
        "sigma": iv_track["internal_iv"],
        "internal_iv": iv_track["internal_iv"],
        "provider_iv": iv_track["provider_iv"],
        "solver_version": iv_track["solver_version"],
        "quality_flags": quality_flags,
    }


def build_volatility_surface(
    activities: list[dict[str, Any]],
    *,
    rate: float | None = None,
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
        "surface_version": SURFACE_VERSION,
    }


__all__ = [
    "SURFACE_VERSION",
    "build_surface_point",
    "build_volatility_surface",
    "infer_underlying_price",
]
