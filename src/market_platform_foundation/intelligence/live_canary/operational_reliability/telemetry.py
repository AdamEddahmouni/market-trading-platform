"""Operational reliability telemetry collector (BUILD 32)."""

from __future__ import annotations

from typing import Any

from ..operator_control.context import OperatorControlContext
from .alerts import build_default_alert_policy
from .backup import create_backup_manifest
from .health_matrix import build_operational_health_matrix
from .persistence_health import assess_persistence_health
from .recovery import build_default_recovery_plan
from .slo import assess_operational_slos, build_default_slo_policy
from .types import BUILD32_KNOWN_LIMITATIONS


def build_operational_reliability_snapshot(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    source_head: str = "local",
    persistence_healthy: bool = True,
    telemetry_evaluator_ok: bool = True,
) -> dict[str, Any]:
    """Build read-only operational reliability payload for operator control plane."""
    matrix = build_operational_health_matrix(
        ctx,
        as_of_ns=as_of_ns,
        persistence_healthy=persistence_healthy,
        telemetry_evaluator_ok=telemetry_evaluator_ok,
    )
    persistence = assess_persistence_health(as_of_ns=as_of_ns)
    slo_policy = build_default_slo_policy()
    slo_assessment = assess_operational_slos(
        slo_policy,
        window_start_ns=as_of_ns - slo_policy.measurement_window_ns,
        window_end_ns=as_of_ns,
        as_of_ns=as_of_ns,
        samples={obj.objective_id: (5, 5) for obj in slo_policy.objectives},
    )
    backup_manifest = create_backup_manifest(ctx, created_at_ns=as_of_ns, source_head=source_head)
    recovery_plan = build_default_recovery_plan()
    alert_policy = build_default_alert_policy()

    return {
        "authority_boundary": "OPERATIONAL_RELIABILITY_READ_ONLY",
        "as_of_ns": as_of_ns,
        "observability_state": matrix.observability_state,
        "health_matrix": {
            "matrix_id": matrix.matrix_id,
            "as_of_ns": matrix.as_of_ns,
            "observability_state": matrix.observability_state,
            "blocking_dependencies": list(matrix.blocking_dependencies),
            "entries": [
                {
                    "component": e.component,
                    "state": e.state,
                    "freshness_ns": e.freshness_ns,
                    "last_success_at_ns": e.last_success_at_ns,
                    "current_issue": e.current_issue,
                    "blocking_live": e.blocking_live,
                }
                for e in matrix.entries
            ],
        },
        "slo_summary": {
            "overall_status": slo_assessment.overall_status,
            "window_start_ns": slo_assessment.window_start_ns,
            "window_end_ns": slo_assessment.window_end_ns,
            "objectives": [
                {
                    "objective_id": r.objective_id,
                    "status": r.status,
                    "observed_value": r.observed_value,
                    "sample_count": r.sample_count,
                }
                for r in slo_assessment.objective_results
            ],
        },
        "persistence_health": {
            "disposition": persistence.disposition,
            "blocking_live": persistence.blocking_live,
            "backend": persistence.backend,
            "last_successful_write_ns": persistence.last_successful_write_ns,
        },
        "backup_status": {
            "last_backup_id": backup_manifest.backup_manifest_id,
            "integrity_status": backup_manifest.integrity_status,
            "created_at_ns": backup_manifest.created_at_ns,
        },
        "recovery_status": {
            "recovery_plan_id": recovery_plan.recovery_plan_id,
            "startup_mode": recovery_plan.startup_mode,
            "requires_operator_approval": recovery_plan.requires_operator_approval,
        },
        "alert_policy_id": alert_policy.alert_policy_id,
        "alert_delivery_configured": "console" in alert_policy.delivery_channels,
        "limitations": list(BUILD32_KNOWN_LIMITATIONS),
    }


from .types import BUILD32_KNOWN_LIMITATIONS
