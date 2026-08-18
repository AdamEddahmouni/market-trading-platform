"""Volatility risk premium research (O4) — informative, not a trade signal."""

from __future__ import annotations

from typing import Any

VRP_VERSION = "vrp_research_v1"


def estimate_vrp(
    implied_vol: float,
    forecast_rv: float,
    *,
    regime_tags: tuple[str, ...] = (),
    maturity_days: int | None = None,
    event_state: str = "NO_EVENT",
) -> dict[str, Any]:
    """Estimate VRP = IV - forecast RV with explicit research disclaimers."""
    if implied_vol <= 0 or forecast_rv < 0:
        return {
            "available": False,
            "reason": "INVALID_VOL_INPUTS",
            "vrp_version": VRP_VERSION,
        }
    vrp = round(implied_vol - forecast_rv, 6)
    return {
        "available": True,
        "vrp_version": VRP_VERSION,
        "vrp": vrp,
        "implied_vol": round(implied_vol, 6),
        "forecast_rv": round(forecast_rv, 6),
        "regime_tags": list(regime_tags),
        "maturity_days": maturity_days,
        "event_state": event_state,
        "iv_not_unbiased_rv_forecast": True,
        "not_trade_signal": True,
        "interpretation": (
            "VRP = implied vol minus physical vol forecast; "
            "positive VRP does not imply sell-vol is optimal"
        ),
    }


def vrp_research_snapshot(
    physical_p: dict[str, Any] | None,
    risk_neutral_q: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compose VRP research from SHARED P2 physical forecast and O3 risk-neutral Q."""
    if not physical_p or not risk_neutral_q:
        return {
            "available": False,
            "reason": "P_OR_Q_UNAVAILABLE",
            "vrp_version": VRP_VERSION,
        }
    if not risk_neutral_q.get("available"):
        return {
            "available": False,
            "reason": risk_neutral_q.get("reason", "Q_UNAVAILABLE"),
            "vrp_version": VRP_VERSION,
        }
    p_vol = physical_p.get("vol_forecast_annualized")
    q_vol = risk_neutral_q.get("vol_implied_annualized")
    if not isinstance(p_vol, (int, float)) or not isinstance(q_vol, (int, float)):
        return {
            "available": False,
            "reason": "VOL_INPUTS_MISSING",
            "vrp_version": VRP_VERSION,
        }

    methodology_tags = physical_p.get("methodology_tags", [])
    regime_tags: tuple[str, ...] = ()
    if isinstance(methodology_tags, list):
        regime_tags = tuple(str(tag) for tag in methodology_tags)

    horizons = risk_neutral_q.get("horizons", [])
    maturity_days = None
    if isinstance(horizons, list) and horizons:
        latest = horizons[-1]
        if isinstance(latest, dict) and latest.get("horizon_days") is not None:
            maturity_days = int(latest["horizon_days"])

    event_state = "EVENT_WINDOW" if physical_p.get("event_window_active") else "NO_EVENT"
    estimate = estimate_vrp(
        float(q_vol),
        float(p_vol),
        regime_tags=regime_tags,
        maturity_days=maturity_days,
        event_state=event_state,
    )
    estimate["model_confidence"] = physical_p.get("confidence", "LOW")
    estimate["data_confidence"] = risk_neutral_q.get("confidence", "LOW")
    return estimate


__all__ = [
    "VRP_VERSION",
    "estimate_vrp",
    "vrp_research_snapshot",
]
