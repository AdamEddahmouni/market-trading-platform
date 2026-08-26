"""Operational readiness gate integration (BUILD 32)."""

from __future__ import annotations

from ...live_execution_safety.gate import _blocked
from ...live_execution_safety.types import (
    AccountEnvironment,
    LiveExecutionGateDecisionV1,
    LiveGateDecisionKind,
    LiveGateReasonCode,
)
from ..operator_control.context import OperatorControlContext
from .health_matrix import build_operational_health_matrix


def evaluate_operational_readiness_blocks_live(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    persistence_healthy: bool = True,
    telemetry_evaluator_ok: bool = True,
    component_observations: dict[str, int | None] | None = None,
    recovered_runtime: bool = False,
    reconciliation_clean: bool = True,
    operator_approved_resume: bool = False,
) -> tuple[bool, tuple[str, ...]]:
    """Return whether operational dependencies block new live submissions."""
    reasons: list[str] = []
    matrix = build_operational_health_matrix(
        ctx,
        as_of_ns=as_of_ns,
        component_observations=component_observations,
        persistence_healthy=persistence_healthy,
        telemetry_evaluator_ok=telemetry_evaluator_ok,
    )
    if matrix.observability_state == "OBSERVABILITY_DEGRADED":
        reasons.append(LiveGateReasonCode.OBSERVABILITY_DEGRADED.value)
    if matrix.blocking_dependencies:
        reasons.append(LiveGateReasonCode.CRITICAL_HEARTBEAT_STALE.value)
    if not persistence_healthy:
        reasons.append(LiveGateReasonCode.PERSISTENCE_UNHEALTHY.value)
    if not telemetry_evaluator_ok:
        reasons.append(LiveGateReasonCode.OBSERVABILITY_DEGRADED.value)
    if recovered_runtime and (not reconciliation_clean or not operator_approved_resume):
        reasons.append(LiveGateReasonCode.RECOVERED_RUNTIME_BLOCKED.value)
    return bool(reasons), tuple(reasons)


def block_gate_for_operational_readiness(
    *,
    decision_time_ns: int,
    broker: str,
    account_environment: AccountEnvironment,
    kill_switch_ref: str,
    reasons: tuple[str, ...],
) -> LiveExecutionGateDecisionV1:
    mapped: list[LiveGateReasonCode] = []
    for code in reasons:
        try:
            mapped.append(LiveGateReasonCode(code))
        except ValueError:
            mapped.append(LiveGateReasonCode.OPERATIONAL_READINESS_UNKNOWN)
    return _blocked(
        decision_time_ns=decision_time_ns,
        broker=broker,
        account_environment=account_environment,
        reason_codes=tuple(mapped),
        kill_switch_ref=kill_switch_ref,
        decision=LiveGateDecisionKind.FAIL_CLOSED,
    )
