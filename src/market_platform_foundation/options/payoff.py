"""Options O8 payoff engine — expiry P&L and expected P&L under physical P."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from ..contracts.options_quality import OptionQualityFlag

PAYOFF_VERSION = "options_payoff_v1"
PAYOFF_METHOD = "PHYSICAL_P_QUANTILE_V1"

CallPut = Literal["call", "put"]
LegSide = Literal["long", "short"]


@dataclass(frozen=True, slots=True)
class OptionLeg:
    """Single option leg for payoff and strategy ranking."""

    call_put: CallPut
    strike: float
    expiry: str
    side: LegSide
    quantity: int = 1
    entry_premium: float = 0.0
    multiplier: float = 100.0


def leg_to_dict(leg: OptionLeg) -> dict[str, Any]:
    return {
        "call_put": leg.call_put,
        "strike": leg.strike,
        "expiry": leg.expiry,
        "side": leg.side,
        "quantity": leg.quantity,
        "entry_premium": leg.entry_premium,
        "multiplier": leg.multiplier,
    }


def _leg_intrinsic(spot: float, leg: OptionLeg) -> float:
    if leg.call_put == "call":
        return max(0.0, spot - leg.strike)
    return max(0.0, leg.strike - spot)


def _leg_payoff_at_spot(spot: float, leg: OptionLeg) -> float:
    intrinsic = _leg_intrinsic(spot, leg)
    sign = 1.0 if leg.side == "long" else -1.0
    per_share = sign * (intrinsic - leg.entry_premium)
    return per_share * leg.multiplier * leg.quantity


def payoff_at_spot(spot: float, legs: Sequence[OptionLeg]) -> float:
    """Expiry P&L for arbitrary leg composition at a given spot."""
    return round(sum(_leg_payoff_at_spot(spot, leg) for leg in legs), 6)


def _friction_dollars(
    friction: dict[str, Any] | None,
    *,
    spot: float,
    legs: Sequence[OptionLeg],
) -> float:
    if not friction or not friction.get("executable_available"):
        return 0.0
    if spot <= 0 or not legs:
        return 0.0
    contract_count = sum(max(leg.quantity, 0) for leg in legs)
    multiplier = legs[0].multiplier
    half_spread = float(friction.get("half_spread_return_equiv", 0.0))
    commission = float(friction.get("commission_return_equiv", 0.0))
    spread_cost = half_spread * spot * multiplier * contract_count
    commission_cost = commission * spot * contract_count
    return round(spread_cost + commission_cost, 6)


def entry_cost(
    legs: Sequence[OptionLeg],
    friction: dict[str, Any] | None,
    *,
    spot: float,
) -> float:
    """Net premium outlay plus execution friction."""
    premium = 0.0
    for leg in legs:
        leg_premium = leg.entry_premium * leg.multiplier * leg.quantity
        if leg.side == "long":
            premium += leg_premium
        else:
            premium -= leg_premium
    friction_cost = _friction_dollars(friction, spot=spot, legs=legs)
    return round(premium + friction_cost, 6)


def _select_horizon(physical_p: dict[str, Any]) -> dict[str, Any] | None:
    horizons = physical_p.get("horizons", [])
    if not isinstance(horizons, list) or not horizons:
        return None
    for row in reversed(horizons):
        if isinstance(row, dict) and row.get("quantiles"):
            return row
    latest = horizons[-1]
    return latest if isinstance(latest, dict) else None


def expected_pnl_under_physical_p(
    physical_p: dict[str, Any] | None,
    legs: Sequence[OptionLeg],
    *,
    spot: float,
    friction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map physical P horizon quantiles to spot scenarios and aggregate leg payoffs."""
    quality_flags: list[str] = []
    if not physical_p or not legs or spot <= 0:
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "reason": "PAYOFF_INPUTS_INCOMPLETE",
            "quality_flags": quality_flags,
            "method": PAYOFF_METHOD,
            "model_version": PAYOFF_VERSION,
        }

    horizon = _select_horizon(physical_p)
    if horizon is None:
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "reason": "PHYSICAL_P_HORIZON_UNAVAILABLE",
            "quality_flags": quality_flags,
            "method": PAYOFF_METHOD,
            "model_version": PAYOFF_VERSION,
        }

    quantiles = horizon.get("quantiles", {})
    if not isinstance(quantiles, dict) or not quantiles:
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "reason": "PHYSICAL_P_QUANTILES_UNAVAILABLE",
            "quality_flags": quality_flags,
            "method": PAYOFF_METHOD,
            "model_version": PAYOFF_VERSION,
        }

    scenarios: list[float] = []
    for ret in quantiles.values():
        try:
            scenario_return = float(ret)
        except (TypeError, ValueError):
            continue
        scenario_spot = spot * (1.0 + scenario_return)
        scenarios.append(payoff_at_spot(scenario_spot, legs))

    if not scenarios:
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "reason": "NO_VALID_PNL_SCENARIOS",
            "quality_flags": quality_flags,
            "method": PAYOFF_METHOD,
            "model_version": PAYOFF_VERSION,
        }

    expected_pnl = sum(scenarios) / len(scenarios)
    sorted_scenarios = sorted(scenarios)
    median_idx = len(sorted_scenarios) // 2
    pnl_median = sorted_scenarios[median_idx]
    win_probability = sum(1 for value in scenarios if value > 0) / len(scenarios)
    friction_cost = _friction_dollars(friction, spot=spot, legs=legs)
    net_expected_pnl = expected_pnl - friction_cost

    return {
        "available": True,
        "expected_pnl": round(expected_pnl, 6),
        "pnl_median": round(pnl_median, 6),
        "win_probability": round(win_probability, 6),
        "max_loss": round(min(scenarios), 6),
        "max_gain": round(max(scenarios), 6),
        "entry_cost": entry_cost(legs, friction, spot=spot),
        "friction_cost": friction_cost,
        "net_expected_pnl": round(net_expected_pnl, 6),
        "scenario_count": len(scenarios),
        "method": PAYOFF_METHOD,
        "model_version": PAYOFF_VERSION,
        "quality_flags": quality_flags,
    }


__all__ = [
    "OptionLeg",
    "PAYOFF_METHOD",
    "PAYOFF_VERSION",
    "entry_cost",
    "expected_pnl_under_physical_p",
    "leg_to_dict",
    "payoff_at_spot",
]
