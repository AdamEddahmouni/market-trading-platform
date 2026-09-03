"""Deterministic operator audit timeline (BUILD 31)."""

from __future__ import annotations

from .context import OperatorControlContext
from .identity import derive_timeline_event_id, derive_timeline_id
from .types import OPERATOR_CONTROL_SCHEMA_VERSION, OperatorAuditTimelineEventV1, OperatorAuditTimelineV1


def _event_sort_key(event: OperatorAuditTimelineEventV1) -> tuple[int, str, str]:
    return (event.event_time_ns, event.recorded_at_ns, event.event_id)


def build_operator_audit_timeline(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    program_run_ref: str | None = None,
    session_ref: str | None = None,
    event_type_filter: str | None = None,
) -> OperatorAuditTimelineV1:
    events: list[OperatorAuditTimelineEventV1] = []
    for receipt in ctx.action_receipts:
        if event_type_filter and receipt.action_type != event_type_filter:
            continue
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="operator_action",
                    event_type=receipt.action_type,
                    event_time_ns=receipt.operator_action_time_ns,
                    source_ref=receipt.action_receipt_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="operator_action",
                event_type=receipt.action_type,
                event_time_ns=receipt.operator_action_time_ns,
                recorded_at_ns=receipt.operator_action_time_ns,
                source_ref=receipt.action_receipt_id,
                summary=f"{receipt.action_type} success={receipt.success}",
                blocking=not receipt.success,
                metadata={"reason_codes": list(receipt.reason_codes)},
            )
        )
    for incident in ctx.incidents:
        if event_type_filter and incident.incident_type.value != event_type_filter:
            continue
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="incident",
                    event_type=incident.incident_type.value,
                    event_time_ns=incident.detected_at_ns,
                    source_ref=incident.incident_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="incident",
                event_type=incident.incident_type.value,
                event_time_ns=incident.detected_at_ns,
                recorded_at_ns=incident.detected_at_ns,
                source_ref=incident.incident_id,
                summary=f"{incident.severity.value} {incident.state.value}",
                blocking=incident.state.value == "OPEN" and incident.severity.value == "CRITICAL",
                metadata={"description": incident.description},
            )
        )
    if ctx.authorization:
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="authorization",
                    event_type="SESSION_AUTHORIZED",
                    event_time_ns=ctx.authorization.effective_from_ns,
                    source_ref=ctx.authorization.authorization_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="authorization",
                event_type="SESSION_AUTHORIZED",
                event_time_ns=ctx.authorization.effective_from_ns,
                recorded_at_ns=ctx.authorization.effective_from_ns,
                source_ref=ctx.authorization.authorization_id,
                summary=ctx.authorization.authorization_state.value,
                blocking=False,
            )
        )
    for conf_id, confirmed in ctx.confirmed_orders.items():
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="order_confirmation",
                    event_type="ORDER_CONFIRMED",
                    event_time_ns=confirmed.confirmation_time_ns,
                    source_ref=conf_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="order_confirmation",
                event_type="ORDER_CONFIRMED",
                event_time_ns=confirmed.confirmation_time_ns,
                recorded_at_ns=confirmed.confirmation_time_ns,
                source_ref=conf_id,
                summary=f"{confirmed.side} {confirmed.quantity} {confirmed.instrument_id}",
                blocking=False,
            )
        )
    for submission in ctx.ledger.submission_receipts:
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="submit_attempt",
                    event_type=submission.submission_state.value,
                    event_time_ns=submission.submit_attempt_time_ns,
                    source_ref=submission.submission_receipt_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="submit_attempt",
                event_type=submission.submission_state.value,
                event_time_ns=submission.submit_attempt_time_ns,
                recorded_at_ns=submission.submit_attempt_time_ns,
                source_ref=submission.submission_receipt_id,
                summary=submission.transport_result,
                blocking=submission.submission_state.value == "SUBMISSION_STATUS_UNKNOWN",
            )
        )
    for fill in ctx.ledger.fill_receipts:
        events.append(
            OperatorAuditTimelineEventV1(
                event_id=derive_timeline_event_id(
                    event_family="fill",
                    event_type="FILL",
                    event_time_ns=fill.fill_time_ns,
                    source_ref=fill.fill_receipt_id,
                ),
                schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
                event_family="fill",
                event_type="FILL",
                event_time_ns=fill.fill_time_ns,
                recorded_at_ns=fill.fill_time_ns,
                source_ref=fill.fill_receipt_id,
                summary=f"qty={fill.quantity} price={fill.price_minor}",
                blocking=False,
            )
        )
    events.sort(key=_event_sort_key)
    seen: set[str] = set()
    deduped: list[OperatorAuditTimelineEventV1] = []
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        deduped.append(event)
    timeline = OperatorAuditTimelineV1(
        timeline_id="",
        schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        program_run_ref=program_run_ref or (ctx.program_run.program_run_id if ctx.program_run else None),
        session_ref=session_ref or ctx.session_ref,
        events=tuple(deduped),
    )
    object.__setattr__(timeline, "timeline_id", derive_timeline_id(timeline))
    return timeline
