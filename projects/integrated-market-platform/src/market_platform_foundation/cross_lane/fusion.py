"""SHARED P4 opportunity fusion engine."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .extractors import (
    extract_cost_input,
    extract_futures_input,
    extract_liquidity_input,
    extract_payoff_input,
    extract_probability_input,
    is_squeeze_aligned_template,
)
from .opportunity import (
    FUSION_METHOD,
    OPPORTUNITY_VERSION,
    OpportunityQualityFlag,
    FuturesInput,
    cost_input_to_dict,
    fused_opportunity_to_dict,
    futures_input_to_dict,
    liquidity_input_to_dict,
    payoff_input_to_dict,
    probability_input_to_dict,
)

# Q-H1 pinned liquidity scalars — unfitted, ledger fusion.liquidity_factor.
LIQUIDITY_BOOK_IMBALANCE_SUPPORTS = 1.05
LIQUIDITY_BOOK_IMBALANCE_OPPOSES = 0.85
LIQUIDITY_BOOK_FRAGILITY_ELEVATED = 0.8
LIQUIDITY_DEPTH_WITHDRAWAL_GT_0 = 0.9
LIQUIDITY_DEPTH_REPLENISHMENT_GT_0 = 1.02
LIQUIDITY_RESILIENCY_BOOST_CAP = 1.05
LIQUIDITY_RESILIENCY_BOOST_SCALE = 0.05
LIQUIDITY_RESILIENCY_SCORE_THRESHOLD = 0.5
LIQUIDITY_FILL_PROBABILITY_LT_0_55 = 0.88
LIQUIDITY_FILL_PROBABILITY_THRESHOLD = 0.55
LIQUIDITY_EXPECTED_SLIPPAGE_SPREAD_FRACTION_GE_0_0035 = 0.9
LIQUIDITY_SLIPPAGE_THRESHOLD = 0.0035
LIQUIDITY_ADVERSE_SELECTION_RISK_GE_0_45 = 0.88
LIQUIDITY_ADVERSE_SELECTION_THRESHOLD = 0.45
LIQUIDITY_CVD_CONFIDENCE_FLOOR = 0.5
LIQUIDITY_CVD_CONFIDENCE_SPAN = 0.5
PAYOFF_ALREADY_NET_TOLERANCE = 1e-9
OCCURRENCE_UNAVAILABLE = "OCCURRENCE_UNAVAILABLE"

# Q-H1 pinned futures-regime scalars — unfitted, ledger fusion.futures_regime_factor.
FUTURES_LEVERAGE_STRESS_ELEVATED = 0.85
FUTURES_MACRO_EVENT_RISK = 0.9
FUTURES_RV_SPREAD_ABS_Z_GT_2 = 0.92
FUTURES_RV_SPREAD_Z_THRESHOLD = 2.0
FUTURES_TREND_UP = 1.03
FUTURES_TREND_DOWN = 0.97

NVDA_OPPORTUNITY_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "opportunity"
    / "nvda_opportunity_fusion_expected.json"
)


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _liquidity_factor(liquidity: Any) -> float:
    if not liquidity.gates_passed:
        return 0.0
    factor = 1.0
    if liquidity.cvd_confidence is not None:
        factor *= LIQUIDITY_CVD_CONFIDENCE_FLOOR + LIQUIDITY_CVD_CONFIDENCE_SPAN * min(
            max(liquidity.cvd_confidence, 0.0), 1.0
        )
    if liquidity.book_imbalance_supports_trade:
        factor *= LIQUIDITY_BOOK_IMBALANCE_SUPPORTS
    if liquidity.book_imbalance_opposes_trade:
        factor *= LIQUIDITY_BOOK_IMBALANCE_OPPOSES
    if liquidity.book_fragility_elevated:
        factor *= LIQUIDITY_BOOK_FRAGILITY_ELEVATED
    if liquidity.depth_withdrawal is not None and liquidity.depth_withdrawal > 0:
        factor *= LIQUIDITY_DEPTH_WITHDRAWAL_GT_0
    if liquidity.depth_replenishment is not None and liquidity.depth_replenishment > 0:
        factor *= LIQUIDITY_DEPTH_REPLENISHMENT_GT_0
    if liquidity.resiliency_score is not None and liquidity.resiliency_score >= LIQUIDITY_RESILIENCY_SCORE_THRESHOLD:
        factor *= min(
            1.0 + LIQUIDITY_RESILIENCY_BOOST_SCALE * liquidity.resiliency_score,
            LIQUIDITY_RESILIENCY_BOOST_CAP,
        )
    if liquidity.fill_probability is not None and liquidity.fill_probability < LIQUIDITY_FILL_PROBABILITY_THRESHOLD:
        factor *= LIQUIDITY_FILL_PROBABILITY_LT_0_55
    if (
        liquidity.expected_slippage_spread_fraction is not None
        and liquidity.expected_slippage_spread_fraction >= LIQUIDITY_SLIPPAGE_THRESHOLD
    ):
        factor *= LIQUIDITY_EXPECTED_SLIPPAGE_SPREAD_FRACTION_GE_0_0035
    if (
        liquidity.adverse_selection_risk is not None
        and liquidity.adverse_selection_risk >= LIQUIDITY_ADVERSE_SELECTION_THRESHOLD
    ):
        factor *= LIQUIDITY_ADVERSE_SELECTION_RISK_GE_0_45
    return round(min(max(factor, 0.0), 1.0), 6)


def _futures_regime_factor(futures: FuturesInput | None) -> float:
    if futures is None or not futures.available:
        return 1.0
    factor = 1.0
    if futures.leverage_stress_regime and str(futures.leverage_stress_regime).upper() == "ELEVATED":
        factor *= FUTURES_LEVERAGE_STRESS_ELEVATED
    if futures.macro_event_risk:
        factor *= FUTURES_MACRO_EVENT_RISK
    if futures.rv_spread_zscore is not None and abs(futures.rv_spread_zscore) > FUTURES_RV_SPREAD_Z_THRESHOLD:
        factor *= FUTURES_RV_SPREAD_ABS_Z_GT_2
    if futures.trend_regime == "TREND_UP":
        factor *= FUTURES_TREND_UP
    elif futures.trend_regime == "TREND_DOWN":
        factor *= FUTURES_TREND_DOWN
    return round(min(max(factor, 0.0), 1.0), 6)


def _occurrence_weight(
    probability: Any, template: str | None, squeeze_aligned: bool
) -> tuple[float | None, str | None]:
    """Return (weight, fail_reason). Missing/non-squeeze must not look like full occurrence."""
    del template
    if not squeeze_aligned:
        return None, OCCURRENCE_UNAVAILABLE
    if probability.squeeze_hazard_probability is not None:
        return min(max(float(probability.squeeze_hazard_probability), 0.0), 1.0), None
    if probability.squeeze_occurrence_probability is not None:
        return min(max(float(probability.squeeze_occurrence_probability), 0.0), 1.0), None
    return None, OCCURRENCE_UNAVAILABLE


def fuse_opportunity_v1(
    probability: Any,
    payoff: Any,
    costs: Any,
    liquidity: Any,
    futures: FuturesInput | None = None,
) -> dict[str, Any]:
    """Fuse lane inputs: (gross expected_pnl - friction_cost) × occurrence_weight × liquidity_factor.

    Payoff EV must be gross of friction. If expected_pnl already equals net_expected_pnl
    while friction is positive, friction is not subtracted again.
    """
    quality_flags: list[str] = list(payoff.quality_flags) + list(liquidity.quality_flags)
    quality_flags.extend(probability.quality_flags)
    quality_flags.extend(costs.quality_flags)

    if not payoff.available or payoff.expected_pnl is None:
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "reason": payoff.reason or "PAYOFF_UNAVAILABLE",
            "quality_flags": list(dict.fromkeys(quality_flags)),
            "fusion": None,
        }
    if liquidity.reason == "STALE_ORDER_FLOW":
        quality_flags.append(OpportunityQualityFlag.FUSION_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "reason": "STALE_ORDER_FLOW",
            "quality_flags": list(dict.fromkeys(quality_flags)),
            "fusion": None,
        }

    friction = costs.friction_cost if costs.available and costs.friction_cost is not None else 0.0
    expected_gross = payoff.expected_pnl
    already_net = (
        payoff.net_expected_pnl is not None
        and friction > 0
        and abs(float(expected_gross) - float(payoff.net_expected_pnl)) < PAYOFF_ALREADY_NET_TOLERANCE
    )
    if already_net:
        gross_ev = float(expected_gross)
        quality_flags.append("PAYOFF_EV_ALREADY_NET_OF_FRICTION")
    else:
        gross_ev = float(expected_gross) - friction
    squeeze_aligned = is_squeeze_aligned_template(
        payoff.template,
        probability.squeeze_state,
    )
    occurrence_weight, occurrence_reason = _occurrence_weight(
        probability, payoff.template, squeeze_aligned
    )
    if squeeze_aligned and occurrence_reason == OCCURRENCE_UNAVAILABLE:
        quality_flags.append(OpportunityQualityFlag.OCCURRENCE_UNAVAILABLE.value)
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "reason": OCCURRENCE_UNAVAILABLE,
            "quality_flags": list(dict.fromkeys(quality_flags)),
            "fusion": None,
        }
    if occurrence_weight is None:
        quality_flags.append(OpportunityQualityFlag.OCCURRENCE_UNAVAILABLE.value)
    liquidity_factor = _liquidity_factor(liquidity)
    futures_regime_factor = _futures_regime_factor(futures)
    combined_liquidity_factor = round(liquidity_factor * futures_regime_factor, 6)
    occurrence_factor = 1.0 if occurrence_weight is None else occurrence_weight
    fused_net_ev = round(gross_ev * occurrence_factor * combined_liquidity_factor, 6)

    from .opportunity import FusedOpportunity

    fusion = FusedOpportunity(
        fused_net_ev=fused_net_ev,
        occurrence_weight=occurrence_weight,
        liquidity_factor=combined_liquidity_factor,
        gross_ev_before_weights=gross_ev,
        template=payoff.template,
        squeeze_aligned=squeeze_aligned,
    )

    if liquidity_factor == 0.0 or combined_liquidity_factor == 0.0:
        outcome = "NO_ACTIONABLE_EDGE"
        status = "NO_ACTIONABLE_EDGE"
        reason = "LIQUIDITY_BLOCKED"
        quality_flags.append(OpportunityQualityFlag.LIQUIDITY_BLOCKED.value)
    elif fused_net_ev > 0.0:
        outcome = "RANKED"
        status = "RANKED"
        reason = None
    else:
        outcome = "NO_ACTIONABLE_EDGE"
        status = "NO_ACTIONABLE_EDGE"
        reason = "FUSED_NET_EV_NOT_POSITIVE"

    return {
        "available": True,
        "status": status,
        "outcome": outcome,
        "reason": reason,
        "fused_net_ev": fusion.fused_net_ev,
        "fusion": fused_opportunity_to_dict(fusion),
        "futures_regime_factor": futures_regime_factor,
        "liquidity_factor_base": liquidity_factor,
        "quality_flags": list(dict.fromkeys(quality_flags)),
    }


def build_opportunity_snapshot(
    symbol: str,
    as_of_time: str,
    *,
    strategy_snapshot: dict[str, Any] | None = None,
    execution_snapshot: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    cross_lane_snapshot: dict[str, Any] | None = None,
    order_flow_payload: dict[str, Any] | None = None,
    execution_friction: dict[str, Any] | None = None,
    futures_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Top-level SHARED P4 snapshot for workspace payloads."""
    payoff_dict = None
    if strategy_snapshot and isinstance(strategy_snapshot.get("best_candidate"), dict):
        raw_payoff = strategy_snapshot["best_candidate"].get("payoff")
        payoff_dict = raw_payoff if isinstance(raw_payoff, dict) else None

    probability = extract_probability_input(
        cross_lane_snapshot=cross_lane_snapshot,
        physical_forecast=physical_forecast,
        squeeze_context=squeeze_context,
        payoff_dict=payoff_dict,
    )
    payoff = extract_payoff_input(strategy_snapshot)
    costs = extract_cost_input(strategy_snapshot, execution_snapshot)
    liquidity = extract_liquidity_input(
        strategy_snapshot=strategy_snapshot,
        cross_lane_snapshot=cross_lane_snapshot,
        order_flow_payload=order_flow_payload,
        execution_friction=execution_friction,
    )
    futures = extract_futures_input(futures_payload)

    fused = fuse_opportunity_v1(probability, payoff, costs, liquidity, futures)

    if not fused.get("available"):
        result = {
            "available": False,
            "status": fused.get("status", "UNAVAILABLE"),
            "outcome": fused.get("outcome", "UNAVAILABLE"),
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": fused.get("reason", "FUSION_UNAVAILABLE"),
            "probability": probability_input_to_dict(probability),
            "payoff": payoff_input_to_dict(payoff),
            "costs": cost_input_to_dict(costs),
            "liquidity": liquidity_input_to_dict(liquidity),
            "futures": futures_input_to_dict(futures),
            "futures_regime_factor": fused.get("futures_regime_factor"),
            "liquidity_factor_base": fused.get("liquidity_factor_base"),
            "fusion": fused.get("fusion"),
            "fused_net_ev": None,
            "method": FUSION_METHOD,
            "model_version": OPPORTUNITY_VERSION,
            "quality_flags": fused.get("quality_flags", []),
            "disclaimer": "Cross-lane EV fusion — research decomposition, not a trade recommendation.",
        }
        result["replay_hash"] = _replay_hash(result)
        return result

    result = {
        "available": True,
        "status": fused["status"],
        "outcome": fused["outcome"],
        "symbol": symbol,
        "as_of_time": as_of_time,
        "reason": fused.get("reason"),
        "probability": probability_input_to_dict(probability),
        "payoff": payoff_input_to_dict(payoff),
        "costs": cost_input_to_dict(costs),
        "liquidity": liquidity_input_to_dict(liquidity),
        "futures": futures_input_to_dict(futures),
        "futures_regime_factor": fused.get("futures_regime_factor"),
        "liquidity_factor_base": fused.get("liquidity_factor_base"),
        "fusion": fused.get("fusion"),
        "fused_net_ev": fused.get("fused_net_ev"),
        "method": FUSION_METHOD,
        "model_version": OPPORTUNITY_VERSION,
        "quality_flags": fused.get("quality_flags", []),
        "disclaimer": "Cross-lane EV fusion — research decomposition, not a trade recommendation.",
    }
    result["replay_hash"] = _replay_hash(result)
    return result


def load_opportunity_fixture(symbol: str) -> dict[str, Any] | None:
    """Load golden opportunity fusion expectations when symbol matches fixture scope."""
    if symbol.upper() != "NVDA" or not NVDA_OPPORTUNITY_FIXTURE.is_file():
        return None
    payload = json.loads(NVDA_OPPORTUNITY_FIXTURE.read_text(encoding="utf-8"))
    if str(payload.get("symbol", "")).upper() != symbol.upper():
        return None
    return payload


__all__ = [
    "FUSION_METHOD",
    "OPPORTUNITY_VERSION",
    "build_opportunity_snapshot",
    "fuse_opportunity_v1",
    "load_opportunity_fixture",
]
