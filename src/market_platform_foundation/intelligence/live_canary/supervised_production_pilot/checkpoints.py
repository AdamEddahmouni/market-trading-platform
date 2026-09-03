"""Operational pilot checkpoints (BUILD 33)."""

from __future__ import annotations

from .identity import derive_pilot_checkpoint_id
from .types import (
    LiveSupervisedPilotPolicyV1,
    OperationalPilotCheckpointV1,
    PilotGovernanceState,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)


def build_operational_pilot_checkpoint(
    *,
    pilot_run_ref: str,
    as_of_ns: int,
    pilot_state: str,
    provider_health_summary: dict[str, str],
    selected_provider_state: dict[str, str],
    divergence_state: str,
    broker_health: str,
    reconciliation_health: str,
    persistence_health: str = "HEALTHY",
    slo_summary: str = "HEALTHY",
    alert_delivery_health: str = "HEALTHY",
    kill_switch_state: str = "PERMIT",
    live_exposure_minor: int = 0,
    active_sessions: int = 0,
    open_orders: int = 0,
    backup_freshness_ns: int | None = None,
    unresolved_incidents: int = 0,
    blocking_reasons: tuple[str, ...] = (),
) -> OperationalPilotCheckpointV1:
    checkpoint = OperationalPilotCheckpointV1(
        checkpoint_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        pilot_run_ref=pilot_run_ref,
        as_of_ns=as_of_ns,
        pilot_state=pilot_state,
        provider_health_summary=provider_health_summary,
        selected_provider_state=selected_provider_state,
        divergence_state=divergence_state,
        broker_health=broker_health,
        reconciliation_health=reconciliation_health,
        persistence_health=persistence_health,
        slo_summary=slo_summary,
        alert_delivery_health=alert_delivery_health,
        kill_switch_state=kill_switch_state,
        live_exposure_minor=live_exposure_minor,
        active_sessions=active_sessions,
        open_orders=open_orders,
        backup_freshness_ns=backup_freshness_ns,
        unresolved_incidents=unresolved_incidents,
        blocking_reasons=blocking_reasons,
    )
    object.__setattr__(checkpoint, "checkpoint_id", derive_pilot_checkpoint_id(checkpoint))
    return checkpoint


def checkpoint_due(
    *,
    policy: LiveSupervisedPilotPolicyV1,
    last_checkpoint_ns: int | None,
    as_of_ns: int,
) -> bool:
    if last_checkpoint_ns is None:
        return True
    return as_of_ns - last_checkpoint_ns >= policy.required_operational_checkpoint_interval_ns


def missed_checkpoint_detected(
    *,
    policy: LiveSupervisedPilotPolicyV1,
    last_checkpoint_ns: int | None,
    as_of_ns: int,
    evaluator_ok: bool,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if not evaluator_ok:
        reasons.append("CHECKPOINT_EVALUATOR_FAILED")
    if last_checkpoint_ns is not None:
        overdue = as_of_ns - last_checkpoint_ns
        if overdue > policy.required_operational_checkpoint_interval_ns * 2:
            reasons.append("CHECKPOINT_MISSED")
    elif not evaluator_ok:
        reasons.append("CHECKPOINT_NEVER_PRODUCED")
    return bool(reasons), tuple(reasons)


def pilot_expired_blocks_session(
    *,
    policy: LiveSupervisedPilotPolicyV1,
    decision_time_ns: int,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if decision_time_ns < policy.pilot_start_ns:
        reasons.append("PILOT_NOT_STARTED")
    if decision_time_ns >= policy.pilot_end_ns:
        reasons.append("PILOT_EXPIRED")
    return bool(reasons), tuple(reasons)
