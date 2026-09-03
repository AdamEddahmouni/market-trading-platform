"""SHARED P4 input extractors — map workspace/cross-lane snapshot dicts to fusion contracts."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from ..research.squeeze_models.logistic_hazard import predict_squeeze_probability
from .opportunity import (
    CostInput,
    FuturesInput,
    LiquidityInput,
    OpportunityQualityFlag,
    PayoffInput,
    ProbabilityInput,
    SQUEEZE_ALIGNED_TEMPLATES,
)


def _squeeze_state_boost(state: str | None) -> float:
    normalized = (state or "").upper()
    if normalized in {"VULNERABLE", "IGNITION_WATCH"}:
        return 0.15
    if normalized in {"ACTIVE_SQUEEZE", "LIVE_CONFIRMATION"}:
        return 0.35
    return 0.0


def _fuel_boost(remaining_fuel: float | None) -> float:
    if remaining_fuel is None:
        return 0.0
    return min(max(float(remaining_fuel) / 100.0, 0.0), 0.5)


def extract_probability_input(
    *,
    cross_lane_snapshot: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    payoff_dict: dict[str, Any] | None = None,
) -> ProbabilityInput:
    """Derive probability inputs from merged snapshots — no lane evaluator imports."""
    quality_flags: list[str] = []
    cross_lane = cross_lane_snapshot or {}
    squeeze_ctx = squeeze_context or {}

    squeeze_state = cross_lane.get("squeeze_state")
    if not squeeze_state and squeeze_ctx.get("available"):
        squeeze_state = squeeze_ctx.get("squeeze_state")

    remaining_fuel = cross_lane.get("remaining_fuel")
    if remaining_fuel is None and squeeze_ctx.get("available"):
        remaining_fuel = squeeze_ctx.get("remaining_squeeze_fuel")

    features = [
        _squeeze_state_boost(str(squeeze_state) if squeeze_state else None),
        _fuel_boost(remaining_fuel if isinstance(remaining_fuel, (int, float)) else None),
    ]
    vol = physical_forecast.get("vol_forecast_annualized") if isinstance(physical_forecast, dict) else None
    if isinstance(vol, (int, float)):
        features.append(float(vol))
    else:
        features.append(0.0)

    upside_tail: float | None = None
    downside_tail: float | None = None
    if isinstance(physical_forecast, dict):
        horizons = physical_forecast.get("horizons", [])
        if isinstance(horizons, list) and horizons:
            latest = horizons[-1]
            if isinstance(latest, dict):
                up = latest.get("upside_tail_probability")
                down = latest.get("downside_tail_probability")
                if isinstance(up, (int, float)):
                    upside_tail = float(up)
                if isinstance(down, (int, float)):
                    downside_tail = float(down)

    squeeze_pred = predict_squeeze_probability(features, horizon_days=5)

    scenario_win: float | None = None
    if isinstance(payoff_dict, dict):
        win = payoff_dict.get("win_probability")
        if isinstance(win, (int, float)):
            scenario_win = float(win)

    available = squeeze_state is not None or scenario_win is not None or upside_tail is not None
    if not available:
        quality_flags.append(OpportunityQualityFlag.FUSION_INPUTS_INCOMPLETE.value)
        return ProbabilityInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason="PROBABILITY_INPUTS_UNAVAILABLE",
        )

    return ProbabilityInput(
        available=True,
        squeeze_occurrence_probability=float(squeeze_pred["occurrence_probability"]),
        squeeze_hazard_probability=float(squeeze_pred["hazard_probability"]),
        scenario_win_probability=scenario_win,
        physical_upside_tail_probability=upside_tail,
        physical_downside_tail_probability=downside_tail,
        squeeze_state=str(squeeze_state) if squeeze_state else None,
        quality_flags=tuple(quality_flags),
    )


def extract_payoff_input(strategy_snapshot: dict[str, Any] | None) -> PayoffInput:
    """Extract payoff from Options O8 strategy snapshot best candidate."""
    quality_flags: list[str] = []
    if not strategy_snapshot or not strategy_snapshot.get("available"):
        quality_flags.append(OpportunityQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return PayoffInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason="STRATEGY_SNAPSHOT_UNAVAILABLE",
        )

    if strategy_snapshot.get("outcome") != "RANKED":
        return PayoffInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason=str(strategy_snapshot.get("reason", "STRATEGY_NOT_RANKED")),
        )

    best = strategy_snapshot.get("best_candidate")
    if not isinstance(best, dict):
        quality_flags.append(OpportunityQualityFlag.PAYOFF_UNAVAILABLE.value)
        return PayoffInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason="BEST_CANDIDATE_MISSING",
        )

    payoff = best.get("payoff")
    if not isinstance(payoff, dict) or not payoff.get("available"):
        quality_flags.append(OpportunityQualityFlag.PAYOFF_UNAVAILABLE.value)
        return PayoffInput(
            available=False,
            template=str(best.get("template") or ""),
            quality_flags=tuple(quality_flags),
            reason="PAYOFF_DECOMPOSITION_UNAVAILABLE",
        )

    expected_pnl = payoff.get("expected_pnl")
    net_expected_pnl = payoff.get("net_expected_pnl")
    if not isinstance(expected_pnl, (int, float)):
        quality_flags.append(OpportunityQualityFlag.PAYOFF_UNAVAILABLE.value)
        return PayoffInput(
            available=False,
            template=str(best.get("template") or ""),
            quality_flags=tuple(quality_flags),
            reason="EXPECTED_PNL_MISSING",
        )

    return PayoffInput(
        available=True,
        expected_pnl=float(expected_pnl),
        net_expected_pnl=float(net_expected_pnl) if isinstance(net_expected_pnl, (int, float)) else None,
        template=str(best.get("template") or best.get("edge_alignment") or ""),
        edge_alignment=str(best.get("edge_alignment") or best.get("template") or ""),
        max_loss=float(payoff["max_loss"]) if isinstance(payoff.get("max_loss"), (int, float)) else None,
        max_gain=float(payoff["max_gain"]) if isinstance(payoff.get("max_gain"), (int, float)) else None,
        quality_flags=tuple(quality_flags),
    )


def extract_cost_input(
    strategy_snapshot: dict[str, Any] | None,
    execution_snapshot: dict[str, Any] | None = None,
) -> CostInput:
    """Extract explicit cost decomposition from payoff and execution snapshots."""
    quality_flags: list[str] = []
    best = None
    payoff: dict[str, Any] | None = None
    if strategy_snapshot and strategy_snapshot.get("available"):
        candidate = strategy_snapshot.get("best_candidate")
        if isinstance(candidate, dict):
            best = candidate
            raw_payoff = candidate.get("payoff")
            payoff = raw_payoff if isinstance(raw_payoff, dict) else None

    if payoff is None or not payoff.get("available"):
        quality_flags.append(OpportunityQualityFlag.PAYOFF_UNAVAILABLE.value)
        return CostInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason="PAYOFF_COSTS_UNAVAILABLE",
        )

    friction_cost = payoff.get("friction_cost")
    entry_cost = payoff.get("entry_cost")
    execution_fill_cost: float | None = None
    if isinstance(execution_snapshot, dict) and execution_snapshot.get("available"):
        fill_summary = execution_snapshot.get("fill_summary")
        if isinstance(fill_summary, dict):
            total_slippage = fill_summary.get("total_slippage_cost")
            if isinstance(total_slippage, (int, float)):
                execution_fill_cost = float(total_slippage)

    return CostInput(
        available=True,
        friction_cost=float(friction_cost) if isinstance(friction_cost, (int, float)) else 0.0,
        entry_cost=float(entry_cost) if isinstance(entry_cost, (int, float)) else None,
        execution_fill_cost=execution_fill_cost,
        quality_flags=tuple(quality_flags),
    )


def extract_liquidity_input(
    *,
    strategy_snapshot: dict[str, Any] | None = None,
    cross_lane_snapshot: dict[str, Any] | None = None,
    order_flow_payload: dict[str, Any] | None = None,
    execution_friction: dict[str, Any] | None = None,
) -> LiquidityInput:
    """Extract liquidity gates and order-flow confidence."""
    quality_flags: list[str] = []
    cross_lane = cross_lane_snapshot or {}

    gates_passed = True
    if strategy_snapshot:
        flags = strategy_snapshot.get("quality_flags", [])
        if isinstance(flags, list):
            if OptionQualityFlag.STRATEGY_LIQUIDITY_BLOCKED.value in flags:
                gates_passed = False
                quality_flags.append(OpportunityQualityFlag.LIQUIDITY_BLOCKED.value)
        if strategy_snapshot.get("reason") == "ALL_CANDIDATES_LIQUIDITY_BLOCKED":
            gates_passed = False
            quality_flags.append(OpportunityQualityFlag.LIQUIDITY_BLOCKED.value)

    cvd_confidence: float | None = None
    if isinstance(order_flow_payload, dict) and order_flow_payload.get("available"):
        cvd_summary = order_flow_payload.get("cvd_summary")
        if isinstance(cvd_summary, dict):
            conf = cvd_summary.get("cvd_confidence")
            if isinstance(conf, (int, float)):
                cvd_confidence = float(conf)
    elif cross_lane.get("order_flow_available"):
        conf = cross_lane.get("order_flow_cvd_confidence")
        if isinstance(conf, (int, float)):
            cvd_confidence = float(conf)

    book_supports = bool(cross_lane.get("order_flow_aggressive_buy"))
    book_opposes = bool(cross_lane.get("order_flow_aggressive_sell"))

    depth_withdrawal: float | None = None
    depth_replenishment: float | None = None
    fragility_score: float | None = None
    resiliency_score: float | None = None
    book_fragility_elevated = False
    absorption_score: float | None = None
    exhaustion_score: float | None = None
    continuation_probability: float | None = None
    reversal_probability: float | None = None
    microstructure_direction_bias: str | None = None
    fill_probability: float | None = None
    expected_slippage_spread_fraction: float | None = None
    adverse_selection_risk: float | None = None

    liquidity_summary = None
    if isinstance(order_flow_payload, dict) and order_flow_payload.get("available"):
        liquidity_summary = order_flow_payload.get("latest_liquidity_summary")
    if isinstance(liquidity_summary, dict):
        w = liquidity_summary.get("depth_withdrawal")
        r = liquidity_summary.get("depth_replenishment")
        f = liquidity_summary.get("fragility_score")
        res = liquidity_summary.get("resiliency_score")
        if isinstance(w, (int, float)):
            depth_withdrawal = float(w)
        if isinstance(r, (int, float)):
            depth_replenishment = float(r)
        if isinstance(f, (int, float)):
            fragility_score = float(f)
            book_fragility_elevated = fragility_score >= 0.25
        if isinstance(res, (int, float)):
            resiliency_score = float(res)
    cross_absorption = cross_lane.get("order_book_absorption_score")
    cross_exhaustion = cross_lane.get("order_book_exhaustion_score")
    if isinstance(cross_absorption, (int, float)):
        absorption_score = float(cross_absorption)
    if isinstance(cross_exhaustion, (int, float)):
        exhaustion_score = float(cross_exhaustion)
    elif cross_lane.get("order_book_depth_withdrawal") is not None:
        w = cross_lane.get("order_book_depth_withdrawal")
        if isinstance(w, (int, float)):
            depth_withdrawal = float(w)
        r = cross_lane.get("order_book_depth_replenishment")
        if isinstance(r, (int, float)):
            depth_replenishment = float(r)
        f = cross_lane.get("order_book_fragility_score")
        if isinstance(f, (int, float)):
            fragility_score = float(f)
            book_fragility_elevated = fragility_score >= 0.25
        res = cross_lane.get("order_book_resiliency_score")
        if isinstance(res, (int, float)):
            resiliency_score = float(res)
    forecast_summary = None
    if isinstance(order_flow_payload, dict) and order_flow_payload.get("available"):
        forecast_summary = order_flow_payload.get("latest_microstructure_forecast")
    if isinstance(forecast_summary, dict):
        cont = forecast_summary.get("continuation_probability")
        rev = forecast_summary.get("reversal_probability")
        bias = forecast_summary.get("direction_bias")
        if isinstance(cont, (int, float)):
            continuation_probability = float(cont)
        if isinstance(rev, (int, float)):
            reversal_probability = float(rev)
        if isinstance(bias, str):
            microstructure_direction_bias = bias
    elif cross_lane.get("order_book_continuation_probability") is not None:
        cont = cross_lane.get("order_book_continuation_probability")
        if isinstance(cont, (int, float)):
            continuation_probability = float(cont)
        rev = cross_lane.get("order_book_reversal_probability")
        if isinstance(rev, (int, float)):
            reversal_probability = float(rev)
        bias = cross_lane.get("order_book_forecast_direction")
        if isinstance(bias, str):
            microstructure_direction_bias = bias

    execution_summary = None
    if isinstance(order_flow_payload, dict) and order_flow_payload.get("available"):
        execution_summary = order_flow_payload.get("latest_execution_forecast")
    if isinstance(execution_summary, dict):
        agg_fill = execution_summary.get("aggressive_fill_probability")
        slip = execution_summary.get("expected_slippage_spread_fraction")
        adverse = execution_summary.get("adverse_selection_risk")
        if isinstance(agg_fill, (int, float)):
            fill_probability = float(agg_fill)
        if isinstance(slip, (int, float)):
            expected_slippage_spread_fraction = float(slip)
        if isinstance(adverse, (int, float)):
            adverse_selection_risk = float(adverse)
    elif cross_lane.get("order_book_fill_probability") is not None:
        fp = cross_lane.get("order_book_fill_probability")
        if isinstance(fp, (int, float)):
            fill_probability = float(fp)
        slip = cross_lane.get("order_book_expected_slippage")
        if isinstance(slip, (int, float)):
            expected_slippage_spread_fraction = float(slip)
        adverse = cross_lane.get("order_book_adverse_selection_risk")
        if isinstance(adverse, (int, float)):
            adverse_selection_risk = float(adverse)

    liquidity_quality: str | None = None
    if isinstance(execution_friction, dict) and execution_friction.get("available"):
        liquidity_quality = str(execution_friction.get("liquidity_quality") or "")

    available = (
        gates_passed
        or cvd_confidence is not None
        or book_supports
        or book_opposes
        or depth_withdrawal is not None
        or fragility_score is not None
        or absorption_score is not None
        or exhaustion_score is not None
        or continuation_probability is not None
        or reversal_probability is not None
        or fill_probability is not None
        or expected_slippage_spread_fraction is not None
        or adverse_selection_risk is not None
    )
    return LiquidityInput(
        available=available or not quality_flags,
        gates_passed=gates_passed,
        cvd_confidence=cvd_confidence,
        book_imbalance_supports_trade=book_supports,
        book_imbalance_opposes_trade=book_opposes,
        depth_withdrawal=depth_withdrawal,
        depth_replenishment=depth_replenishment,
        fragility_score=fragility_score,
        resiliency_score=resiliency_score,
        book_fragility_elevated=book_fragility_elevated,
        absorption_score=absorption_score,
        exhaustion_score=exhaustion_score,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        microstructure_direction_bias=microstructure_direction_bias,
        fill_probability=fill_probability,
        expected_slippage_spread_fraction=expected_slippage_spread_fraction,
        adverse_selection_risk=adverse_selection_risk,
        liquidity_quality=liquidity_quality,
        quality_flags=tuple(quality_flags),
        reason=None if gates_passed else "LIQUIDITY_GATES_FAILED",
    )


def is_squeeze_aligned_template(template: str | None, squeeze_state: str | None) -> bool:
    """Whether template qualifies for SS occurrence conditioning."""
    if not template or template not in SQUEEZE_ALIGNED_TEMPLATES:
        return False
    state = (squeeze_state or "").upper()
    return state in {
        "VULNERABLE",
        "IGNITION_WATCH",
        "ACTIVE_SQUEEZE",
        "LIVE_CONFIRMATION",
    }


def extract_futures_input(futures_payload: dict[str, Any] | None) -> FuturesInput:
    """Extract futures outright/curve regime modifiers from workspace futures payload."""
    quality_flags: list[str] = []
    if not futures_payload or not futures_payload.get("available"):
        quality_flags.append(OpportunityQualityFlag.FUSION_INPUTS_INCOMPLETE.value)
        return FuturesInput(
            available=False,
            quality_flags=tuple(quality_flags),
            reason="FUTURES_WORKSPACE_UNAVAILABLE",
        )

    carry_baseline = futures_payload.get("carry_baseline")
    carry_percentile: float | None = None
    if isinstance(carry_baseline, dict):
        raw = carry_baseline.get("carry_percentile")
        if isinstance(raw, (int, float)):
            carry_percentile = float(raw)

    rv_snapshot = futures_payload.get("relative_value_snapshot")
    rv_spread_zscore: float | None = None
    curve_regime: str | None = None
    if isinstance(rv_snapshot, dict):
        z = rv_snapshot.get("spread_zscore")
        if isinstance(z, (int, float)):
            rv_spread_zscore = float(z)
        regime = rv_snapshot.get("curve_regime")
        if isinstance(regime, str):
            curve_regime = regime

    trend_regime = futures_payload.get("trend_regime")
    stress_snapshot = futures_payload.get("leverage_stress_snapshot")
    leverage_stress_regime: str | None = None
    if isinstance(stress_snapshot, dict):
        regime = stress_snapshot.get("stress_regime")
        if isinstance(regime, str):
            leverage_stress_regime = regime

    macro_snapshot = futures_payload.get("macro_event_snapshot")
    macro_event_risk = False
    if isinstance(macro_snapshot, dict) and macro_snapshot.get("macro_event_risk"):
        macro_event_risk = True

    return FuturesInput(
        available=True,
        carry_percentile=carry_percentile,
        rv_spread_zscore=rv_spread_zscore,
        trend_regime=str(trend_regime) if trend_regime else None,
        leverage_stress_regime=leverage_stress_regime,
        macro_event_risk=macro_event_risk,
        curve_regime=curve_regime,
        quality_flags=tuple(quality_flags),
    )


__all__ = [
    "extract_cost_input",
    "extract_futures_input",
    "extract_liquidity_input",
    "extract_payoff_input",
    "extract_probability_input",
    "is_squeeze_aligned_template",
]
