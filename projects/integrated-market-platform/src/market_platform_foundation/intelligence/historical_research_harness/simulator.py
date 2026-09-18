"""Paper simulator research path (HISTORICAL_DEVELOPMENT; not Item 9 calibration)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...risk.kill_switch import KillSwitchState
from ...risk_simulation.evaluation import (
    risk_simulation_root_hash,
    run_risk_simulation_from_signal_interpretations,
)
from .prediction_coupling import (
    PREDICTION_COUPLING_SCHEMA_VERSION,
    PredictionCoupledSimulatorError,
    assert_no_trade_baseline_invariant,
    build_signal_interpretations_from_predictions,
    summarize_risk_execution,
)

SIMULATOR_RESEARCH_RESULT_KIND = "SIMULATOR_RESEARCH_RESULT"
ITEM9_CALIBRATION_RESULT_KIND = "ITEM9_CALIBRATION_RESULT"


def _default_instrument_id(events: Sequence[Mapping[str, Any]]) -> str:
    for event in events:
        instrument_id = event.get("instrument_id")
        if instrument_id:
            return str(instrument_id)
    return "UNKNOWN"


def run_historical_development_simulator_research(
    events: list[dict[str, Any]],
    *,
    predictions: Sequence[Mapping[str, Any]],
    simulator_version: str,
    cost_slippage_bps: float,
    desired_quantity: int = 1,
    kill_switch: KillSwitchState | None = None,
    enable_squeeze_replay: bool = True,
    external_position_documented: bool = False,
) -> dict[str, Any]:
    """Prediction-conditioned historical simulator (research only; not Item 9 calibration)."""

    scoped_event_times_ns = sorted({int(event["available_time"]) for event in events})
    allowed_times = frozenset(scoped_event_times_ns)
    instrument_id = _default_instrument_id(events)
    interpretations, signals = build_signal_interpretations_from_predictions(
        predictions,
        instrument_id=instrument_id,
        allowed_decision_times_ns=allowed_times,
    )
    risk_result = run_risk_simulation_from_signal_interpretations(
        events,
        interpretations,
        desired_quantity=desired_quantity,
        kill_switch=kill_switch,
        enable_squeeze_replay=enable_squeeze_replay,
        strategy_result={
            "source": "prediction_coupled_simulator_research",
            "prediction_coupling_schema": PREDICTION_COUPLING_SCHEMA_VERSION,
            "prediction_count": len(predictions),
            "signal_count": len(interpretations),
        },
    )
    execution = summarize_risk_execution(risk_result)
    assert_no_trade_baseline_invariant(
        trade_intent_count=execution["trade_intents"],
        fill_count=execution["fills"],
        turnover=execution["turnover"],
        external_position_documented=external_position_documented,
    )
    estimated_costs = abs(execution["gross_pnl"]) * (cost_slippage_bps / 10_000.0)
    net_pnl = execution["gross_pnl"] - estimated_costs
    return {
        "result_kind": SIMULATOR_RESEARCH_RESULT_KIND,
        "not_result_kind": ITEM9_CALIBRATION_RESULT_KIND,
        "item9_calibration": False,
        "item9_calibration_authority": False,
        "historical_research_only": True,
        "prediction_coupling_schema": PREDICTION_COUPLING_SCHEMA_VERSION,
        "simulator_version": simulator_version,
        "cost_slippage_bps": cost_slippage_bps,
        "risk_simulation_root_hash": risk_simulation_root_hash(risk_result),
        "signals": signals,
        "signal_count": len(signals),
        "trade_intents": execution["trade_intents"],
        "accepted_intents": execution["accepted_intents"],
        "rejected_intents": execution["rejected_intents"],
        "fills": execution["fills"],
        "partial_fills": execution["partial_fills"],
        "fill_count": execution["fills"],
        "order_count": len(risk_result.get("orders") or []),
        "intent_count": execution["trade_intents"],
        "gross_pnl": execution["gross_pnl"],
        "net_pnl": net_pnl,
        "estimated_costs": estimated_costs,
        "turnover": execution["turnover"],
        "max_drawdown": risk_result.get("portfolio", {}).get("max_drawdown"),
        "exposure": execution["exposure"],
        "coverage": risk_result.get("portfolio", {}).get("coverage"),
        "scoped_event_times_ns": scoped_event_times_ns,
        "prediction_coupled": True,
        "independent_bar_replay_trading": False,
        "raw_risk_result_keys": sorted(risk_result.keys()),
    }


__all__ = [
    "ITEM9_CALIBRATION_RESULT_KIND",
    "PredictionCoupledSimulatorError",
    "SIMULATOR_RESEARCH_RESULT_KIND",
    "run_historical_development_simulator_research",
]
