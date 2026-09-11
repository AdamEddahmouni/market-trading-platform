"""Anti-look-ahead guards for forward testing."""

from __future__ import annotations

from typing import Any


class ForwardTestTemporalError(ValueError):
    """Temporal integrity violation."""


def assert_source_time_at_or_before_decision(*, source_time_ns: int, decision_time_ns: int) -> None:
    if source_time_ns > decision_time_ns:
        raise ForwardTestTemporalError("FORWARD_TEST_FUTURE_SOURCE_TIME")


def assert_input_observable_at_decision(*, effective_time_ns: int, decision_time_ns: int) -> None:
    if effective_time_ns > decision_time_ns:
        raise ForwardTestTemporalError("FORWARD_TEST_FUTURE_INPUT_REJECTED")


def assert_observation_after_decision(*, observation_time_ns: int, decision_time_ns: int) -> None:
    if observation_time_ns < decision_time_ns:
        raise ForwardTestTemporalError("FORWARD_TEST_OBSERVATION_BEFORE_DECISION")


def assert_evaluation_horizon_reached(*, now_ns: int, decision_time_ns: int, horizon_ns: int) -> None:
    if now_ns < decision_time_ns + horizon_ns:
        raise ForwardTestTemporalError("FORWARD_TEST_HORIZON_NOT_REACHED")


def assert_decision_payload_immutable(
    *,
    original: dict[str, Any],
    proposed: dict[str, Any],
) -> None:
    if original != proposed:
        raise ForwardTestTemporalError("FORWARD_TEST_DECISION_PAYLOAD_MUTATION_FORBIDDEN")


def assert_run_kind_forward(*, run_kind: str) -> None:
    if run_kind != "FORWARD_TEST":
        raise ForwardTestTemporalError("FORWARD_TEST_BACKTEST_BOUNDARY_VIOLATION")
