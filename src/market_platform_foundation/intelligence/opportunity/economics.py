"""Probability edge and economic value helpers (BUILD 21).

Probability edge is dimensionless. Spread and friction are expressed in basis points.
Never subtract bps from probability.
"""

from __future__ import annotations

import math

from ..contracts.common import OpportunitySide
from ..contracts.forecast import ForecastV1
from .types import EconomicValueStatus


def probability_edge_for_side(p_up: float, side: OpportunitySide, reference: float = 0.5) -> float:
    if side == OpportunitySide.LONG:
        return p_up - reference
    if side == OpportunitySide.SHORT:
        return (1.0 - p_up) - reference
    return 0.0


def side_from_probability(p_up: float) -> OpportunitySide:
    if p_up > 0.5:
        return OpportunitySide.LONG
    if p_up < 0.5:
        return OpportunitySide.SHORT
    return OpportunitySide.NEUTRAL


def meets_edge_threshold(
    edge: float,
    *,
    minimum: float,
    strict: bool,
) -> bool:
    if strict:
        return edge > minimum
    return edge >= minimum


def extract_predictive_entropy(forecast: ForecastV1) -> float | None:
    uncertainty = forecast.uncertainty
    if "predictive_entropy" in uncertainty:
        value = uncertainty.get("predictive_entropy")
        if value is not None and math.isfinite(float(value)):
            return float(value)
    receipt = forecast.metadata.get("uncertainty_receipt")
    if isinstance(receipt, dict) and receipt.get("predictive_entropy") is not None:
        value = receipt["predictive_entropy"]
        if math.isfinite(float(value)):
            return float(value)
    return None


def extract_ood_reasons(forecast: ForecastV1) -> tuple[str, ...]:
    reasons: list[str] = []
    receipt = forecast.metadata.get("uncertainty_receipt")
    if isinstance(receipt, dict):
        for item in receipt.get("ood_reasons", []) or []:
            reasons.append(str(item))
    for item in forecast.uncertainty.get("ood_reasons", []) or []:
        reasons.append(str(item))
    return tuple(sorted(set(reasons)))


def assess_economic_value(
    forecast: ForecastV1,
    *,
    spread_bps: float | None,
) -> tuple[
    EconomicValueStatus,
    float | None,
    float | None,
    float | None,
]:
    estimate = forecast.estimate
    if estimate.expected_value is not None:
        gross_bps = estimate.expected_value
        friction_bps = spread_bps if spread_bps is not None else None
        if friction_bps is not None:
            net_bps = gross_bps - friction_bps
            return EconomicValueStatus.AVAILABLE, gross_bps, friction_bps, net_bps
        return EconomicValueStatus.AVAILABLE, gross_bps, None, None
    return EconomicValueStatus.UNAVAILABLE_DIRECTION_ONLY, None, None, None


# Explicit dimensional-integrity guard for audits.
_FORBIDDEN_ARITHMETIC = "probability_minus_spread_bps"


def assert_no_probability_bps_subtraction() -> None:
    """Static marker — opportunity core must never mix probability with bps arithmetically."""
    raise AssertionError(_FORBIDDEN_ARITHMETIC)


__all__ = [
    "assess_economic_value",
    "assert_no_probability_bps_subtraction",
    "extract_ood_reasons",
    "extract_predictive_entropy",
    "meets_edge_threshold",
    "probability_edge_for_side",
    "side_from_probability",
]
