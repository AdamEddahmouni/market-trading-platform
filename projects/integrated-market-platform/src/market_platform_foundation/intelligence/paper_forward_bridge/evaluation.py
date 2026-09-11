"""Forward-test outcome evaluation."""

from __future__ import annotations

from dataclasses import replace

from .temporal import assert_evaluation_horizon_reached, assert_observation_after_decision
from .types import (
    EvaluationState,
    ExecutionOutcomeMetrics,
    ForwardTestDecision,
    ForwardTestMode,
    ForwardTestObservation,
    ForwardTestState,
    SignalOutcomeMetrics,
)


def _direction_sign(direction: str) -> int:
    normalized = direction.upper()
    if normalized in {"BUY", "POSITIVE_DIRECTIONAL_BIAS", "UP", "LONG"}:
        return 1
    if normalized in {"SELL", "NEGATIVE_DIRECTIONAL_BIAS", "DOWN", "SHORT"}:
        return -1
    return 0


def compute_signal_outcome(
    *,
    decision: ForwardTestDecision,
    entry_price: float | None,
    exit_price: float | None,
) -> SignalOutcomeMetrics:
    warnings: list[str] = []
    if entry_price is None or exit_price is None:
        return SignalOutcomeMetrics(
            entry_reference_price=entry_price,
            exit_reference_price=exit_price,
            absolute_return=None,
            percentage_return=None,
            directional_correct=None,
            quality="INSUFFICIENT_DATA",
            warnings=tuple(warnings),
        )
    absolute_return = exit_price - entry_price
    percentage_return = absolute_return / entry_price if entry_price else None
    sign = _direction_sign(decision.direction)
    directional_correct = None
    if sign != 0 and absolute_return != 0:
        directional_correct = (absolute_return > 0 and sign > 0) or (absolute_return < 0 and sign < 0)
    elif sign == 0:
        warnings.append("NEUTRAL_DIRECTION_NO_DIRECTIONAL_SCORE")
    return SignalOutcomeMetrics(
        entry_reference_price=entry_price,
        exit_reference_price=exit_price,
        absolute_return=absolute_return,
        percentage_return=percentage_return,
        directional_correct=directional_correct,
        quality="COMPLETE",
        warnings=tuple(warnings),
    )


def compute_execution_outcome(
    *,
    decision: ForwardTestDecision,
    realized_pnl_minor: int | None,
    unrealized_pnl_minor: int | None,
    fill_count: int,
) -> ExecutionOutcomeMetrics:
    if decision.test_mode != ForwardTestMode.EXECUTION:
        return ExecutionOutcomeMetrics(
            paper_order_id=decision.paper_order_id,
            paper_intent_id=decision.paper_intent_id,
            realized_pnl_minor=None,
            unrealized_pnl_minor=None,
            fill_count=0,
            quality="NOT_APPLICABLE",
        )
    quality = "COMPLETE" if fill_count > 0 or realized_pnl_minor is not None else "PENDING"
    return ExecutionOutcomeMetrics(
        paper_order_id=decision.paper_order_id,
        paper_intent_id=decision.paper_intent_id,
        realized_pnl_minor=realized_pnl_minor,
        unrealized_pnl_minor=unrealized_pnl_minor,
        fill_count=fill_count,
        quality=quality,
    )


def extract_prices_from_observations(
    observations: tuple[ForwardTestObservation, ...],
) -> tuple[float | None, float | None]:
    if not observations:
        return None, None
    first = observations[0].payload
    last = observations[-1].payload
    entry = first.get("reference_price") or first.get("price") or first.get("close_price")
    exit_price = last.get("close_price") or last.get("reference_price") or last.get("price")
    entry_val = float(entry) if isinstance(entry, (int, float)) else None
    exit_val = float(exit_price) if isinstance(exit_price, (int, float)) else None
    return entry_val, exit_val


def evaluate_forward_test(
    *,
    decision: ForwardTestDecision,
    now_ns: int,
) -> ForwardTestDecision:
    assert_observation_after_decision(
        observation_time_ns=now_ns,
        decision_time_ns=decision.decision_time_ns,
    )
    try:
        assert_evaluation_horizon_reached(
            now_ns=now_ns,
            decision_time_ns=decision.decision_time_ns,
            horizon_ns=decision.evaluation_horizon_ns,
        )
    except ValueError as exc:
        if "HORIZON_NOT_REACHED" in str(exc):
            return replace(
                decision,
                evaluation_state=EvaluationState.PENDING,
            )
        raise

    entry_price, exit_price = extract_prices_from_observations(decision.observations)
    signal_outcome = compute_signal_outcome(
        decision=decision,
        entry_price=entry_price,
        exit_price=exit_price,
    )
    execution_outcome = compute_execution_outcome(
        decision=decision,
        realized_pnl_minor=None,
        unrealized_pnl_minor=None,
        fill_count=1 if decision.paper_order_id else 0,
    )
    evaluation_state = (
        EvaluationState.INSUFFICIENT_DATA
        if signal_outcome.quality == "INSUFFICIENT_DATA"
        else EvaluationState.EVALUATED
    )
    target_state = (
        ForwardTestState.INSUFFICIENT_DATA
        if evaluation_state == EvaluationState.INSUFFICIENT_DATA
        else ForwardTestState.EVALUATED
    )
    return replace(
        decision,
        signal_outcome=signal_outcome,
        execution_outcome=execution_outcome,
        evaluation_state=evaluation_state,
        state=target_state,
    )


def refresh_evaluability(*, decision: ForwardTestDecision, now_ns: int) -> ForwardTestDecision:
    if decision.state in {ForwardTestState.EVALUATED, ForwardTestState.REJECTED, ForwardTestState.CANCELLED}:
        return decision
    horizon_end = decision.decision_time_ns + decision.evaluation_horizon_ns
    if now_ns >= horizon_end and decision.state == ForwardTestState.OBSERVING:
        return replace(
            decision,
            state=ForwardTestState.EVALUABLE,
            evaluation_state=EvaluationState.EVALUABLE,
        )
    return decision
