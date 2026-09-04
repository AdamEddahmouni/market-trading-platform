"""Component heartbeat evaluation (BUILD 32)."""

from __future__ import annotations

from .types import (
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    ComponentHeartbeatV1,
    ComponentSignalState,
)

# Default intervals for critical supervised-live components (nanoseconds).
DEFAULT_HEARTBEAT_INTERVAL_NS = 30_000_000_000  # 30s
DEFAULT_STALE_AFTER_NS = 90_000_000_000  # 3x interval

CRITICAL_COMPONENTS = (
    "broker_adapter",
    "broker_status_feed",
    "reconciliation_worker",
    "canonical_persistence",
    "live_execution_gate",
    "operator_api",
    "alert_evaluator",
    "alert_delivery",
    "kill_switch_store",
)

EXECUTION_CRITICAL = frozenset(
    {
        "broker_adapter",
        "broker_status_feed",
        "reconciliation_worker",
        "canonical_persistence",
        "live_execution_gate",
        "kill_switch_store",
    }
)


def evaluate_heartbeat_staleness(
    *,
    observed_at_ns: int | None,
    as_of_ns: int,
    expected_interval_ns: int = DEFAULT_HEARTBEAT_INTERVAL_NS,
    stale_after_ns: int = DEFAULT_STALE_AFTER_NS,
) -> ComponentSignalState:
    """Evaluate heartbeat freshness; never-observed is not healthy."""
    if observed_at_ns is None:
        return ComponentSignalState.NEVER_OBSERVED
    age_ns = as_of_ns - observed_at_ns
    if age_ns >= stale_after_ns:
        return ComponentSignalState.STALE
    if age_ns >= expected_interval_ns * 2:
        return ComponentSignalState.WARNING
    return ComponentSignalState.HEALTHY


def build_component_heartbeat(
    *,
    component: str,
    as_of_ns: int,
    observed_at_ns: int | None,
    liveness_ok: bool | None = None,
    readiness_ok: bool | None = None,
    health_ok: bool | None = None,
    last_success_at_ns: int | None = None,
    current_issue: str | None = None,
    expected_interval_ns: int = DEFAULT_HEARTBEAT_INTERVAL_NS,
    stale_after_ns: int = DEFAULT_STALE_AFTER_NS,
    source_refs: tuple[str, ...] = (),
) -> ComponentHeartbeatV1:
    freshness = evaluate_heartbeat_staleness(
        observed_at_ns=observed_at_ns,
        as_of_ns=as_of_ns,
        expected_interval_ns=expected_interval_ns,
        stale_after_ns=stale_after_ns,
    )

    if freshness == ComponentSignalState.NEVER_OBSERVED:
        liveness = ComponentSignalState.NEVER_OBSERVED.value
        readiness = ComponentSignalState.UNKNOWN.value
        health = ComponentSignalState.UNKNOWN.value
        blocking = component in EXECUTION_CRITICAL
    elif freshness == ComponentSignalState.STALE:
        liveness = ComponentSignalState.STALE.value
        readiness = ComponentSignalState.UNKNOWN.value
        health = ComponentSignalState.UNKNOWN.value
        blocking = component in EXECUTION_CRITICAL
    else:
        liveness = (
            ComponentSignalState.HEALTHY.value
            if liveness_ok is not False
            else ComponentSignalState.CRITICAL.value
        )
        if readiness_ok is None:
            readiness = ComponentSignalState.UNKNOWN.value
        else:
            readiness = (
                ComponentSignalState.HEALTHY.value
                if readiness_ok
                else ComponentSignalState.CRITICAL.value
            )
        if health_ok is None:
            health = ComponentSignalState.UNKNOWN.value
        elif health_ok:
            health = ComponentSignalState.HEALTHY.value
        else:
            health = ComponentSignalState.CRITICAL.value
        blocking = (
            component in EXECUTION_CRITICAL
            and (
                freshness != ComponentSignalState.HEALTHY
                or liveness != ComponentSignalState.HEALTHY.value
                or readiness == ComponentSignalState.UNKNOWN.value
                or readiness == ComponentSignalState.CRITICAL.value
                or health == ComponentSignalState.UNKNOWN.value
                or health == ComponentSignalState.CRITICAL.value
            )
        )

    return ComponentHeartbeatV1(
        component=component,
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        observed_at_ns=observed_at_ns or 0,
        expected_interval_ns=expected_interval_ns,
        stale_after_ns=stale_after_ns,
        liveness=liveness,
        readiness=readiness,
        health=health,
        blocking_live=blocking,
        last_success_at_ns=last_success_at_ns,
        current_issue=current_issue,
        source_refs=source_refs,
    )


def aggregate_observability_state(heartbeats: tuple[ComponentHeartbeatV1, ...]) -> str:
    """Unknown/stale critical state cannot aggregate to healthy."""
    if not heartbeats:
        return ComponentSignalState.UNKNOWN.value
    states = {hb.health for hb in heartbeats if hb.component in EXECUTION_CRITICAL}
    if ComponentSignalState.NEVER_OBSERVED.value in states:
        return "OBSERVABILITY_DEGRADED"
    if ComponentSignalState.STALE.value in {hb.liveness for hb in heartbeats if hb.blocking_live}:
        return "OBSERVABILITY_DEGRADED"
    if ComponentSignalState.UNKNOWN.value in states:
        return "OBSERVABILITY_DEGRADED"
    if ComponentSignalState.CRITICAL.value in states:
        return ComponentSignalState.CRITICAL.value
    if ComponentSignalState.WARNING.value in states:
        return ComponentSignalState.WARNING.value
    return ComponentSignalState.HEALTHY.value
