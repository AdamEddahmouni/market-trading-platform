"""Delta-hedged return research primitive (O10) — vol edge isolation, not a trade signal."""

from __future__ import annotations

from typing import Any, Literal

from .greeks import CallPut, bsm_greeks
from .iv import bsm_price

DELTA_HEDGED_VERSION = "delta_hedged_research_v1"
DEFAULT_REBALANCE_COST_BPS = 1.0


def compute_delta_hedged_period_return(
    *,
    option_value_start: float,
    option_value_end: float,
    spot_start: float,
    spot_end: float,
    delta_at_start: float,
    hedge_rebalance_cost: float = 0.0,
) -> dict[str, Any]:
    """One-period delta-hedged option return with explicit hedge P&L decomposition."""
    if option_value_start < 0 or option_value_end < 0:
        return {
            "available": False,
            "reason": "INVALID_OPTION_MARKS",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }
    if spot_start <= 0 or spot_end <= 0:
        return {
            "available": False,
            "reason": "INVALID_SPOT",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }

    option_pnl = option_value_end - option_value_start
    stock_hedge_pnl = -delta_at_start * (spot_end - spot_start)
    net_return = option_pnl + stock_hedge_pnl - hedge_rebalance_cost
    denominator = option_value_start if option_value_start > 0 else None
    net_return_pct = (net_return / denominator) if denominator else None

    return {
        "available": True,
        "delta_hedged_version": DELTA_HEDGED_VERSION,
        "option_pnl": round(option_pnl, 8),
        "stock_hedge_pnl": round(stock_hedge_pnl, 8),
        "hedge_rebalance_cost": round(hedge_rebalance_cost, 8),
        "delta_hedged_pnl": round(net_return, 8),
        "delta_hedged_return_pct": (
            round(net_return_pct, 8) if net_return_pct is not None else None
        ),
        "delta_at_start": round(delta_at_start, 8),
        "not_trade_signal": True,
        "interpretation": (
            "Delta-hedged return isolates vol/convexity exposure from directional delta; "
            "research primitive only — not execution advice"
        ),
    }


def simulate_delta_hedged_path(
    spot_path: list[float],
    *,
    strike: float,
    rate: float,
    volatility: float,
    call_put: CallPut,
    maturity_days_start: int,
    rebalance_cost_bps: float = DEFAULT_REBALANCE_COST_BPS,
) -> dict[str, Any]:
    """Discrete daily-rebalance delta-hedged path using BSM marks (fixture/research scope)."""
    if len(spot_path) < 2:
        return {
            "available": False,
            "reason": "SPOT_PATH_TOO_SHORT",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }
    if strike <= 0 or volatility <= 0 or maturity_days_start <= 0:
        return {
            "available": False,
            "reason": "INVALID_CONTRACT_INPUTS",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }

    periods: list[dict[str, Any]] = []
    cumulative_pnl = 0.0
    initial_option_value: float | None = None

    for index in range(len(spot_path) - 1):
        spot_start = spot_path[index]
        spot_end = spot_path[index + 1]
        days_remaining = max(maturity_days_start - index, 1)
        time_years = days_remaining / 365.0
        option_start = bsm_price(
            spot_start, strike, time_years, rate, volatility, call_put
        )
        days_remaining_end = max(maturity_days_start - index - 1, 1)
        time_years_end = days_remaining_end / 365.0
        option_end = bsm_price(
            spot_end, strike, time_years_end, rate, volatility, call_put
        )
        greeks = bsm_greeks(
            spot_start, strike, time_years, rate, volatility, call_put
        )
        delta = greeks.get("delta")
        if delta is None:
            return {
                "available": False,
                "reason": "DELTA_UNAVAILABLE",
                "delta_hedged_version": DELTA_HEDGED_VERSION,
            }

        hedge_cost = abs(spot_start * float(delta)) * (rebalance_cost_bps / 10_000.0)
        period = compute_delta_hedged_period_return(
            option_value_start=option_start,
            option_value_end=option_end,
            spot_start=spot_start,
            spot_end=spot_end,
            delta_at_start=float(delta),
            hedge_rebalance_cost=hedge_cost,
        )
        if not period.get("available"):
            return period

        if initial_option_value is None:
            initial_option_value = option_start

        cumulative_pnl += float(period["delta_hedged_pnl"])
        periods.append(
            {
                "period_index": index,
                "spot_start": spot_start,
                "spot_end": spot_end,
                **period,
            }
        )

    cumulative_return_pct = None
    if initial_option_value and initial_option_value > 0:
        cumulative_return_pct = cumulative_pnl / initial_option_value

    return {
        "available": True,
        "delta_hedged_version": DELTA_HEDGED_VERSION,
        "rebalance_frequency": "daily",
        "period_count": len(periods),
        "cumulative_delta_hedged_pnl": round(cumulative_pnl, 8),
        "cumulative_delta_hedged_return_pct": (
            round(cumulative_return_pct, 8) if cumulative_return_pct is not None else None
        ),
        "initial_option_value": round(initial_option_value or 0.0, 8),
        "periods": periods,
        "not_trade_signal": True,
        "research_only": True,
    }


def delta_hedged_research_snapshot(
  physical_p: dict[str, Any] | None,
  risk_neutral_q: dict[str, Any] | None,
  *,
  spot_path: list[float] | None = None,
  strike: float | None = None,
  rate: float = 0.05,
  call_put: CallPut = "call",
  maturity_days: int = 30,
) -> dict[str, Any]:
    """Compose O10 delta-hedged research from P/Q context plus optional spot path."""
    if not spot_path or strike is None:
        return {
            "available": False,
            "reason": "SPOT_PATH_OR_STRIKE_MISSING",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }

    implied_vol = None
    if risk_neutral_q and risk_neutral_q.get("available"):
        implied_vol = risk_neutral_q.get("vol_implied_annualized")

    forecast_rv = None
    if physical_p:
        forecast_rv = physical_p.get("vol_forecast_annualized")

    if not isinstance(implied_vol, (int, float)) or implied_vol <= 0:
        return {
            "available": False,
            "reason": "IMPLIED_VOL_UNAVAILABLE",
            "delta_hedged_version": DELTA_HEDGED_VERSION,
        }

    path_result = simulate_delta_hedged_path(
        spot_path,
        strike=strike,
        rate=rate,
        volatility=float(implied_vol),
        call_put=call_put,
        maturity_days_start=maturity_days,
    )
    if not path_result.get("available"):
        return path_result

    vrp_context = None
    if isinstance(forecast_rv, (int, float)) and forecast_rv >= 0:
        vrp_context = round(float(implied_vol) - float(forecast_rv), 6)

    return {
        **path_result,
        "vol_implied_annualized": round(float(implied_vol), 6),
        "vol_forecast_annualized": (
            round(float(forecast_rv), 6) if isinstance(forecast_rv, (int, float)) else None
        ),
        "vrp_context": vrp_context,
        "target_id": "T-DH",
        "gate_milestone": "R-O6",
        "interpretation": (
            "Delta-hedged path uses risk-neutral IV for marks; compare cumulative DH return "
            "against P vs Q edge forecasts (R-O6) — research gate only"
        ),
    }


__all__ = [
    "DEFAULT_REBALANCE_COST_BPS",
    "DELTA_HEDGED_VERSION",
    "compute_delta_hedged_period_return",
    "delta_hedged_research_snapshot",
    "simulate_delta_hedged_path",
]
