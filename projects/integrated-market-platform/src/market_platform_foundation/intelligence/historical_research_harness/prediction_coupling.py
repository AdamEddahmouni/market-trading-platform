"""Map strategy predictions to trade intents for prediction-conditioned simulator research."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PREDICTION_COUPLING_SCHEMA_VERSION = "prediction-coupled-simulator/1.0.0"
RESEARCH_PREDICTION_STRATEGY_IDENTITY = "historical_research_prediction_coupled_v1"


class PredictionCoupledSimulatorError(RuntimeError):
    """Research simulator run failed closed on coupling or no-trade invariants."""


def predicted_direction_to_signal_direction(predicted_direction: int) -> str | None:
    if predicted_direction == 0:
        return None
    if predicted_direction == 1:
        return "long"
    if predicted_direction == -1:
        return "short"
    return None


def prediction_to_signal_interpretation(
    prediction: Mapping[str, Any],
    *,
    instrument_id: str,
) -> dict[str, Any] | None:
    direction = predicted_direction_to_signal_direction(int(prediction.get("predicted_direction", 0)))
    if direction is None:
        return None
    decision_time_ns = int(prediction["decision_time_ns"])
    return {
        "outcome": "signal",
        "direction": direction,
        "prediction_cutoff": decision_time_ns,
        "observation_time": decision_time_ns,
        "strategy_identity_hash": RESEARCH_PREDICTION_STRATEGY_IDENTITY,
        "predicted_direction": int(prediction.get("predicted_direction", 0)),
    }


def build_signal_interpretations_from_predictions(
    predictions: Sequence[Mapping[str, Any]],
    *,
    instrument_id: str,
    allowed_decision_times_ns: frozenset[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return signal interpretations and audit records (one row per prediction)."""

    signals_audit: list[dict[str, Any]] = []
    interpretations: list[dict[str, Any]] = []
    for prediction in sorted(predictions, key=lambda row: int(row["decision_time_ns"])):
        decision_time_ns = int(prediction["decision_time_ns"])
        if allowed_decision_times_ns is not None and decision_time_ns not in allowed_decision_times_ns:
            continue
        predicted_direction = int(prediction.get("predicted_direction", 0))
        direction = predicted_direction_to_signal_direction(predicted_direction)
        audit_row = {
            "decision_time_ns": decision_time_ns,
            "predicted_direction": predicted_direction,
            "signal_direction": direction,
            "abstained": direction is None,
        }
        signals_audit.append(audit_row)
        if direction is None:
            continue
        interpretation = prediction_to_signal_interpretation(
            prediction,
            instrument_id=instrument_id,
        )
        if interpretation is not None:
            interpretations.append(interpretation)
    return interpretations, signals_audit


def assert_no_trade_baseline_invariant(
    *,
    trade_intent_count: int,
    fill_count: int,
    turnover: int,
    external_position_documented: bool = False,
) -> None:
    if external_position_documented:
        return
    if trade_intent_count == 0 and fill_count == 0 and turnover == 0:
        return
    if trade_intent_count == 0 and (fill_count > 0 or turnover > 0):
        raise PredictionCoupledSimulatorError("NO_TRADE_BASELINE_FILLS_FORBIDDEN")


def summarize_risk_execution(
    risk_result: Mapping[str, Any],
    *,
    events: Sequence[Mapping[str, Any]] | None = None,
    cost_slippage_bps: float = 0.0,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    intents = list(risk_result.get("intents") or [])
    risk_decisions = list(risk_result.get("risk_decisions") or [])
    fills = list(risk_result.get("fills") or [])
    orders = list(risk_result.get("orders") or [])
    accepted = [
        decision
        for decision in risk_decisions
        if isinstance(decision, dict) and decision.get("decision") in {"APPROVE", "RESIZE"}
    ]
    rejected = [
        decision
        for decision in risk_decisions
        if isinstance(decision, dict) and decision.get("decision") == "REJECT"
    ]
    partial_fills = sum(
        1 for order in orders if isinstance(order, dict) and order.get("state") == "PARTIALLY_FILLED"
    )
    from .fill_economics import aggregate_fill_economics

    policy = risk_result.get("risk_policy")
    economics = aggregate_fill_economics(
        fills,
        events=events or [],
        policy=policy if isinstance(policy, dict) else None,
        cost_slippage_bps=cost_slippage_bps,
        instrument_id=instrument_id,
    )
    return {
        "trade_intents": len(intents),
        "accepted_intents": len(accepted),
        "rejected_intents": len(rejected),
        "fills": economics["fill_count"],
        "partial_fills": partial_fills,
        **economics,
    }


__all__ = [
    "PREDICTION_COUPLING_SCHEMA_VERSION",
    "PredictionCoupledSimulatorError",
    "RESEARCH_PREDICTION_STRATEGY_IDENTITY",
    "assert_no_trade_baseline_invariant",
    "build_signal_interpretations_from_predictions",
    "prediction_to_signal_interpretation",
    "predicted_direction_to_signal_direction",
    "summarize_risk_execution",
]
