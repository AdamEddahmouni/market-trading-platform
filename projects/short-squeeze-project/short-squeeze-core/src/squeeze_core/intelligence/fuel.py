"""SS P5/P6 fuel / reflexivity / exhaustion proxies — fixture-first, fail-closed."""

from __future__ import annotations

FUEL_VERSION = "squeeze_fuel_proxy_v2"
FUEL_METHOD = "STRUCTURAL_CVD_GAMMA_BORROW_PROXY_V2"

HEDGING_PRESSURE_THRESHOLD = 1.0
REFLEXIVITY_CAP = 100.0
EXHAUSTION_FUEL_DEPLETION_THRESHOLD = 25.0
EXHAUSTION_PRIOR_FUEL_THRESHOLD = 50.0
BORROW_UTIL_DECLINE_MODERATE = 10.0
BORROW_UTIL_DECLINE_HIGH = 20.0
BORROW_FEE_DECLINE_MODERATE = 2.0
BORROW_FEE_DECLINE_HIGH = 5.0

FUEL_ASSUMPTIONS = (
    "Reflexivity combines order-flow aggression, CVD slope, and O6 gamma/hedging proxies.",
    "Covering pressure is an order-flow imbalance proxy — not published SI delta.",
    "Remaining fuel subtracts covering consumption from structural vulnerability.",
    "Exhaustion uses temporal fuel decline, CVD divergence history, borrow normalization, and O5/O6 reversal proxies.",
)


def estimate_reflexivity_strength(
    *,
    order_flow_available: bool,
    aggressive_buy: bool | None,
    cvd_slope: float | None,
    options_gamma_amplification: bool | None,
    hedging_pressure: float | None,
) -> float | None:
    """Estimate live feedback-loop strength from cross-lane inputs."""
    if not order_flow_available and not options_gamma_amplification:
        return None

    score = 0.0
    if aggressive_buy:
        score = 50.0
    if cvd_slope is not None and cvd_slope > 0:
        score += 10.0
    if options_gamma_amplification:
        score += 15.0
    if isinstance(hedging_pressure, (int, float)) and hedging_pressure >= HEDGING_PRESSURE_THRESHOLD:
        score += 10.0

    if score <= 0:
        return None
    return min(REFLEXIVITY_CAP, round(score, 1))


def estimate_covering_pressure(
    *,
    order_flow_available: bool,
    cvd_slope: float | None,
    aggressive_buy: bool | None,
    aggressive_sell: bool | None,
) -> float | None:
    """Order-flow covering proxy — not a claim about published short-interest delta."""
    if not order_flow_available:
        return None

    score = 0.0
    if aggressive_buy:
        score += 40.0
    if aggressive_sell:
        score -= 20.0
    if cvd_slope is not None:
        if cvd_slope > 0:
            score += min(40.0, cvd_slope / 10.0)
        elif cvd_slope < 0:
            score += max(-30.0, cvd_slope / 10.0)

    if score <= 0:
        return None
    return min(REFLEXIVITY_CAP, round(score, 1))


def estimate_remaining_fuel(
    *,
    vulnerability: float | None,
    covering_pressure: float | None,
    structural_fuel: float | None = None,
) -> float | None:
    """Structural fuel minus order-flow covering consumption."""
    if vulnerability is None:
        return None
    base = structural_fuel if structural_fuel is not None else vulnerability
    consumption = (covering_pressure or 0.0) * 0.4
    return max(0.0, round(base - consumption, 1))


def detect_cvd_divergence(
    *,
    cvd_slope: float | None,
    previous_cvd_slope: float | None,
    aggressive_buy: bool | None,
) -> bool:
    """True when buy regime shows CVD slope flip from positive to negative."""
    if not aggressive_buy:
        return False
    if cvd_slope is None or previous_cvd_slope is None:
        return False
    return previous_cvd_slope > 0 and cvd_slope < 0


def estimate_borrow_normalization(
    *,
    current_utilization: float | None,
    prior_utilization: float | None,
    current_fee: float | None,
    prior_fee: float | None,
) -> float | None:
    """Borrow normalization proxy — utilization/fee decline from squeeze peak."""
    if current_utilization is None or prior_utilization is None:
        return None

    score = 0.0
    util_decline = prior_utilization - current_utilization
    if util_decline >= BORROW_UTIL_DECLINE_HIGH:
        score += 50.0
    elif util_decline >= BORROW_UTIL_DECLINE_MODERATE:
        score += 30.0

    if current_fee is not None and prior_fee is not None:
        fee_decline = prior_fee - current_fee
        if fee_decline >= BORROW_FEE_DECLINE_HIGH:
            score += 35.0
        elif fee_decline >= BORROW_FEE_DECLINE_MODERATE:
            score += 20.0

    if score <= 0:
        return None
    return min(REFLEXIVITY_CAP, round(score, 1))


def estimate_exhaustion_risk(
    *,
    covering_pressure: float | None,
    cvd_slope: float | None,
    remaining_fuel: float | None,
    previous_fuel: float | None = None,
    aggressive_buy: bool | None = None,
    cvd_divergence: bool = False,
    borrow_normalization: float | None = None,
    options_flow_reversal: bool | None = None,
    options_gamma_decay: bool | None = None,
) -> float | None:
    """Exhaustion proxy from divergence, fuel depletion, borrow, and options reversal."""
    risk = 0.0
    if aggressive_buy and cvd_slope is not None and cvd_slope < 0:
        risk += 45.0
    if cvd_divergence:
        risk += 20.0
    if remaining_fuel is not None and remaining_fuel < EXHAUSTION_FUEL_DEPLETION_THRESHOLD:
        if previous_fuel is not None and previous_fuel >= EXHAUSTION_PRIOR_FUEL_THRESHOLD:
            risk += 35.0
        elif remaining_fuel < 15.0:
            risk += 25.0
    if isinstance(covering_pressure, (int, float)) and covering_pressure >= 70.0:
        risk += 15.0
    if isinstance(borrow_normalization, (int, float)) and borrow_normalization >= 50.0:
        risk += 15.0
    if options_flow_reversal:
        risk += 20.0
    if options_gamma_decay:
        risk += 15.0

    if risk <= 0:
        return None
    return min(REFLEXIVITY_CAP, round(risk, 1))
