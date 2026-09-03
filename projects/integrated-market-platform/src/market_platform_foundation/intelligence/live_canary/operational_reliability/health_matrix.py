"""Operational health matrix builder (BUILD 32)."""

from __future__ import annotations

from ..operator_control.context import OperatorControlContext
from .heartbeats import CRITICAL_COMPONENTS, EXECUTION_CRITICAL, build_component_heartbeat
from .identity import derive_health_matrix_id
from .types import (
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    ComponentHeartbeatV1,
    ComponentSignalState,
    OperationalHealthMatrixEntryV1,
    OperationalHealthMatrixV1,
)
from .heartbeats import aggregate_observability_state


def _map_broker_health_label(label: str) -> bool | None:
    if label == "HEALTHY":
        return True
    if label in {"UNHEALTHY", "CRITICAL", "DEGRADED"}:
        return False
    return None


def collect_heartbeats_from_context(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    component_observations: dict[str, int | None] | None = None,
    persistence_healthy: bool = True,
    telemetry_evaluator_ok: bool = True,
) -> tuple[ComponentHeartbeatV1, ...]:
    """Collect heartbeats from operator context and optional observation timestamps."""
    observations = component_observations or {}
    broker_ok = _map_broker_health_label(ctx.broker_health)
    recon_ok = ctx.reconciliation_health == "CLEAN"

    heartbeats: list[ComponentHeartbeatV1] = []
    for component in CRITICAL_COMPONENTS:
        observed = observations.get(component, as_of_ns)
        if component == "broker_adapter":
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed,
                liveness_ok=True,
                readiness_ok=broker_ok,
                health_ok=broker_ok,
                current_issue=None if broker_ok else ctx.broker_health,
            )
        elif component == "broker_status_feed":
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed,
                liveness_ok=True,
                readiness_ok=broker_ok,
                health_ok=broker_ok,
            )
        elif component == "reconciliation_worker":
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed,
                liveness_ok=True,
                readiness_ok=recon_ok,
                health_ok=recon_ok,
                current_issue=None if recon_ok else ctx.reconciliation_health,
            )
        elif component == "canonical_persistence":
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed if persistence_healthy else None,
                liveness_ok=persistence_healthy,
                readiness_ok=persistence_healthy,
                health_ok=persistence_healthy,
                current_issue=None if persistence_healthy else "PERSISTENCE_UNHEALTHY",
            )
        elif component == "kill_switch_store":
            ks_ok = getattr(ctx.kill_switch, "state_known", True)
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed,
                liveness_ok=True,
                readiness_ok=ks_ok,
                health_ok=ks_ok,
                current_issue=None if ks_ok else "KILL_SWITCH_STATE_UNKNOWN",
            )
        elif component == "alert_evaluator":
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed if telemetry_evaluator_ok else None,
                liveness_ok=telemetry_evaluator_ok,
                readiness_ok=telemetry_evaluator_ok,
                health_ok=telemetry_evaluator_ok,
                current_issue=None if telemetry_evaluator_ok else "TELEMETRY_EVALUATOR_FAILED",
            )
        else:
            hb = build_component_heartbeat(
                component=component,
                as_of_ns=as_of_ns,
                observed_at_ns=observed,
                liveness_ok=True,
                readiness_ok=True,
                health_ok=True,
            )
        heartbeats.append(hb)
    return tuple(heartbeats)


def build_operational_health_matrix(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    component_observations: dict[str, int | None] | None = None,
    persistence_healthy: bool = True,
    telemetry_evaluator_ok: bool = True,
) -> OperationalHealthMatrixV1:
    heartbeats = collect_heartbeats_from_context(
        ctx,
        as_of_ns=as_of_ns,
        component_observations=component_observations,
        persistence_healthy=persistence_healthy,
        telemetry_evaluator_ok=telemetry_evaluator_ok,
    )
    observability = aggregate_observability_state(heartbeats)
    if not telemetry_evaluator_ok:
        observability = "OBSERVABILITY_DEGRADED"
    entries: list[OperationalHealthMatrixEntryV1] = []
    blocking: list[str] = []
    for hb in heartbeats:
        freshness = as_of_ns - hb.observed_at_ns if hb.observed_at_ns else None
        exec_crit = hb.component in EXECUTION_CRITICAL
        state = hb.health
        if hb.liveness == ComponentSignalState.STALE.value:
            state = ComponentSignalState.STALE.value
        elif hb.liveness == ComponentSignalState.NEVER_OBSERVED.value:
            state = ComponentSignalState.NEVER_OBSERVED.value
        entries.append(
            OperationalHealthMatrixEntryV1(
                component=hb.component,
                state=state,
                freshness_ns=freshness,
                last_success_at_ns=hb.last_success_at_ns,
                current_issue=hb.current_issue,
                blocking_live=hb.blocking_live,
                execution_critical=exec_crit,
                scientific_critical=False,
                operational_only=not exec_crit,
            )
        )
        if hb.blocking_live:
            blocking.append(hb.component)

    matrix = OperationalHealthMatrixV1(
        matrix_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        observability_state=observability,
        entries=tuple(entries),
        blocking_dependencies=tuple(blocking),
        source_refs=(f"operator_ctx:{ctx.session_ref}",),
    )
    return OperationalHealthMatrixV1(
        matrix_id=derive_health_matrix_id(matrix),
        schema_version=matrix.schema_version,
        as_of_ns=matrix.as_of_ns,
        observability_state=matrix.observability_state,
        entries=matrix.entries,
        blocking_dependencies=matrix.blocking_dependencies,
        source_refs=matrix.source_refs,
    )
