"""Audit review report builder (BUILD 31)."""

from __future__ import annotations

from .context import OperatorControlContext
from .identity import derive_review_report_id
from .timeline import build_operator_audit_timeline
from .types import OPERATOR_CONTROL_SCHEMA_VERSION, AuditReviewDisposition, AuditReviewReportV1


def build_audit_review_report(
    ctx: OperatorControlContext,
    *,
    window_start_ns: int,
    window_end_ns: int,
) -> AuditReviewReportV1:
    timeline = build_operator_audit_timeline(ctx, as_of_ns=window_end_ns)
    unresolved: list[str] = []
    for incident in ctx.open_incidents():
        unresolved.append(f"incident:{incident.incident_id}")
    if ctx.reconciliation_health not in ("CLEAN", "UNKNOWN"):
        unresolved.append(f"reconciliation:{ctx.reconciliation_health}")
    disposition = AuditReviewDisposition.CLEAN
    if unresolved:
        disposition = AuditReviewDisposition.REQUIRES_FOLLOWUP
    if ctx.reconciliation_health == "CONFLICT":
        disposition = AuditReviewDisposition.INVALID_RECONCILIATION
    report = AuditReviewReportV1(
        review_report_id="",
        schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
        program_run_ref=ctx.program_run.program_run_id if ctx.program_run else None,
        session_ref=ctx.session_ref,
        window_start_ns=window_start_ns,
        window_end_ns=window_end_ns,
        authorization_summary={
            "authorization_id": ctx.authorization.authorization_id if ctx.authorization else None,
            "state": (
                ctx.authorization.authorization_state.value if ctx.authorization else None
            ),
        },
        human_action_summary=tuple(
            {
                "action_type": r.action_type,
                "success": r.success,
                "request_id": r.request_id,
            }
            for r in ctx.action_receipts
        ),
        orders_fills_summary={
            "submit_attempts": ctx.accounting.total_submit_attempts,
            "fills": ctx.accounting.total_fills,
            "confirmed_orders": len(ctx.confirmed_orders),
        },
        incidents_summary={
            "open": len(ctx.open_incidents()),
            "resolved": sum(1 for i in ctx.incidents if i.state.value == "RESOLVED"),
        },
        reconciliation_summary={
            "health": ctx.reconciliation_health,
            "checkpoint": (
                ctx.latest_checkpoint().checkpoint_id if ctx.latest_checkpoint() else None
            ),
        },
        kill_switch_summary=ctx.kill_switch.to_persistence_dict(),
        policy_cap_compliance={
            "sessions_completed": ctx.accounting.sessions_completed,
            "max_sessions": ctx.program_policy.max_sessions,
            "orders_submitted": ctx.accounting.total_submit_attempts,
            "max_program_orders": ctx.program_policy.max_program_order_count,
        },
        unexpected_events=(),
        unresolved_items=tuple(unresolved),
        disposition=disposition,
        source_refs=tuple(e.source_ref for e in timeline.events),
    )
    object.__setattr__(report, "review_report_id", derive_review_report_id(report))
    return report
