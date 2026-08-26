"""Operator mutation commands with idempotency and stale-view protection (BUILD 31)."""

from __future__ import annotations

from dataclasses import replace

from ..authorization import (
    AuthorizationError,
    authorize_canary_from_human_approval,
    prepare_canary_authorization_preview,
    record_human_canary_approval,
    revoke_authorization,
)
from ..confirmation import ConfirmationError, confirm_order
from ..identity import derive_account_fingerprint, derive_preview_hash
from ..incidents import create_incident, record_resume_approval, resolve_incident
from ..types import HumanApprovalSource, IncidentSeverity, IncidentType, ProgramGovernanceState
from ...live_execution_safety.types import KillSwitchState, LiveAuthorizationState
from .context import OperatorControlContext, PendingOrderReview
from .identity import derive_action_receipt_id
from .snapshot import build_operator_control_snapshot, validate_snapshot_binding
from .types import OPERATOR_CONTROL_SCHEMA_VERSION, OperatorActionReceiptV1, OperatorActionType


class OperatorCommandError(ValueError):
    pass


def _record_receipt(
    ctx: OperatorControlContext,
    *,
    action_type: str,
    target_refs: tuple[str, ...],
    operator_action_time_ns: int,
    precondition_snapshot_ref: str,
    result_refs: tuple[str, ...],
    success: bool,
    reason_codes: tuple[str, ...],
    request_id: str,
) -> OperatorActionReceiptV1:
    if request_id in ctx.idempotency_keys:
        return ctx.idempotency_keys[request_id]
    receipt = OperatorActionReceiptV1(
        action_receipt_id="",
        schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
        action_type=action_type,
        target_refs=target_refs,
        operator_action_time_ns=operator_action_time_ns,
        precondition_snapshot_ref=precondition_snapshot_ref,
        result_refs=result_refs,
        success=success,
        reason_codes=reason_codes,
        request_id=request_id,
    )
    object.__setattr__(receipt, "action_receipt_id", derive_action_receipt_id(receipt))
    ctx.action_receipts.append(receipt)
    ctx.idempotency_keys[request_id] = receipt
    return receipt


def prepare_session_authorization(
    ctx: OperatorControlContext,
    *,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object]:
    """Phase 1: create authorization preview for operator review — no authorization granted."""
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    if ctx.governance_state == ProgramGovernanceState.PROGRAM_COMPLETE:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.PREPARE_SESSION_AUTHORIZATION.value,
            target_refs=(),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=snapshot.snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("PROGRAM_COMPLETE",),
            request_id=request_id,
        )
        return receipt, snapshot
    fingerprint = derive_account_fingerprint(ctx.canary_policy.account_ref)
    preview = prepare_canary_authorization_preview(
        policy=ctx.canary_policy,
        broker=ctx.canary_policy.broker,
        account_ref=ctx.canary_policy.account_ref,
        account_fingerprint=fingerprint,
        generated_at_ns=decision_time_ns,
        kill_switch_state=ctx.kill_switch.program_state.value,
    )
    ctx.authorization_preview = preview
    ctx.session_state = "SESSION_PREPARED"
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.PREPARE_SESSION_AUTHORIZATION.value,
        target_refs=(preview.preview_id,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(preview.preview_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, preview


def authorize_reviewed_session(
    ctx: OperatorControlContext,
    *,
    preview_id: str,
    preview_hash: str,
    reviewed_snapshot_id: str,
    approved_by: str,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    """Phase 2: authorize session after explicit human review of exact preview."""
    ok, reason = validate_snapshot_binding(
        ctx, reviewed_snapshot_id=reviewed_snapshot_id, as_of_ns=decision_time_ns
    )
    if not ok:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.AUTHORIZE_SESSION.value,
            target_refs=(preview_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=(reason or "STALE_OPERATOR_VIEW",),
            request_id=request_id,
        )
        return receipt, None
    if ctx.authorization_preview is None or ctx.authorization_preview.preview_id != preview_id:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.AUTHORIZE_SESSION.value,
            target_refs=(preview_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("PREVIEW_NOT_FOUND",),
            request_id=request_id,
        )
        return receipt, None
    if derive_preview_hash(ctx.authorization_preview) != preview_hash:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.AUTHORIZE_SESSION.value,
            target_refs=(preview_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("STALE_OPERATOR_VIEW",),
            request_id=request_id,
        )
        return receipt, None
    for incident in ctx.critical_open_incidents():
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.AUTHORIZE_SESSION.value,
            target_refs=(preview_id, incident.incident_id),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=(f"INCIDENT_BLOCK:{incident.incident_id}",),
            request_id=request_id,
        )
        return receipt, None
    try:
        approval = record_human_canary_approval(
            preview=ctx.authorization_preview,
            approved_at_ns=decision_time_ns,
            approved_by=approved_by,
            approval_source=HumanApprovalSource.OPERATOR_CONSOLE,
        )
        auth = authorize_canary_from_human_approval(
            policy=ctx.canary_policy,
            preview=ctx.authorization_preview,
            human_approval=approval,
            effective_from_ns=decision_time_ns,
            effective_until_ns=decision_time_ns + ctx.canary_policy.authorization_duration_ns,
        )
    except AuthorizationError as exc:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.AUTHORIZE_SESSION.value,
            target_refs=(preview_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=(str(exc),),
            request_id=request_id,
        )
        return receipt, None
    ctx.authorization = auth
    ctx.session_state = "SESSION_AUTHORIZED"
    ctx.governance_state = ProgramGovernanceState.SESSION_AUTHORIZED
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.AUTHORIZE_SESSION.value,
        target_refs=(preview_id,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=reviewed_snapshot_id,
        result_refs=(auth.authorization_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, auth


def confirm_reviewed_order(
    ctx: OperatorControlContext,
    *,
    confirmation_id: str,
    reviewed_snapshot_id: str,
    confirmed_by: str,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    """Confirm exact reviewed order — binds reviewed snapshot; never trusts UI alone."""
    if ctx.kill_switch.any_block_active():
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.CONFIRM_ORDER.value,
            target_refs=(confirmation_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("KILL_SWITCH_ACTIVE",),
            request_id=request_id,
        )
        return receipt, None
    ok, reason = validate_snapshot_binding(
        ctx, reviewed_snapshot_id=reviewed_snapshot_id, as_of_ns=decision_time_ns
    )
    if not ok:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.CONFIRM_ORDER.value,
            target_refs=(confirmation_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=(reason or "STALE_OPERATOR_VIEW",),
            request_id=request_id,
        )
        return receipt, None
    pending = ctx.pending_order_reviews.get(confirmation_id)
    if pending is None:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.CONFIRM_ORDER.value,
            target_refs=(confirmation_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("CONFIRMATION_NOT_FOUND",),
            request_id=request_id,
        )
        return receipt, None
    if ctx.session_state in ("SESSION_COMPLETE", None) and ctx.governance_state == ProgramGovernanceState.PROGRAM_COMPLETE:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.CONFIRM_ORDER.value,
            target_refs=(confirmation_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("SESSION_CLOSED",),
            request_id=request_id,
        )
        return receipt, None
    for incident in ctx.open_incidents():
        if incident.severity == IncidentSeverity.CRITICAL and incident.state.value == "OPEN":
            receipt = _record_receipt(
                ctx,
                action_type=OperatorActionType.CONFIRM_ORDER.value,
                target_refs=(confirmation_id, incident.incident_id),
                operator_action_time_ns=decision_time_ns,
                precondition_snapshot_ref=reviewed_snapshot_id,
                result_refs=(),
                success=False,
                reason_codes=(f"INCIDENT_BLOCK:{incident.incident_id}",),
                request_id=request_id,
            )
            return receipt, None
    try:
        confirmed = confirm_order(
            pending.confirmation_preview,
            confirmed_by=confirmed_by,
            confirmation_source=HumanApprovalSource.OPERATOR_CONSOLE,
            confirmation_time_ns=decision_time_ns,
        )
    except ConfirmationError as exc:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.CONFIRM_ORDER.value,
            target_refs=(confirmation_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=reviewed_snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=(str(exc),),
            request_id=request_id,
        )
        return receipt, None
    ctx.confirmed_orders[confirmation_id] = confirmed
    del ctx.pending_order_reviews[confirmation_id]
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.CONFIRM_ORDER.value,
        target_refs=(confirmation_id,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=reviewed_snapshot_id,
        result_refs=(confirmed.confirmation_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, confirmed


def activate_kill_switch(
    ctx: OperatorControlContext,
    *,
    scope: str,
    reason: str,
    decision_time_ns: int,
    request_id: str,
) -> OperatorActionReceiptV1:
    """Easy stop path — blocks new submissions; does not liquidate."""
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    if scope == "GLOBAL":
        ctx.kill_switch.global_state = KillSwitchState.ACTIVE_BLOCK
        ctx.kill_switch.global_reason = reason
    elif scope == "PROGRAM":
        ctx.kill_switch.activate_program_block(reason)
    elif scope == "SESSION":
        ctx.kill_switch.activate_session_block(reason)
    else:
        return _record_receipt(
            ctx,
            action_type=OperatorActionType.ACTIVATE_KILL_SWITCH.value,
            target_refs=(scope,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=snapshot.snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("INVALID_SCOPE",),
            request_id=request_id,
        )
    return _record_receipt(
        ctx,
        action_type=OperatorActionType.ACTIVATE_KILL_SWITCH.value,
        target_refs=(scope,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(scope,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )


def revoke_session_authorization(
    ctx: OperatorControlContext,
    *,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    if ctx.authorization is None:
        return _record_receipt(
            ctx,
            action_type=OperatorActionType.REVOKE_AUTHORIZATION.value,
            target_refs=(),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=snapshot.snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("NO_AUTHORIZATION",),
            request_id=request_id,
        ), None
    revoked = revoke_authorization(ctx.authorization)
    ctx.authorization = revoked
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.REVOKE_AUTHORIZATION.value,
        target_refs=(revoked.authorization_id,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(revoked.authorization_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, revoked


def acknowledge_incident(
    ctx: OperatorControlContext,
    *,
    incident_id: str,
    acknowledged_by: str,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    """Acknowledge ≠ resolve — does not unblock trading."""
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    incident = next((i for i in ctx.incidents if i.incident_id == incident_id), None)
    if incident is None:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.ACKNOWLEDGE_INCIDENT.value,
            target_refs=(incident_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=snapshot.snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("INCIDENT_NOT_FOUND",),
            request_id=request_id,
        )
        return receipt, None
    updated = replace(
        incident,
        metadata={
            **dict(incident.metadata),
            "acknowledged": True,
            "acknowledged_by": acknowledged_by,
            "acknowledged_at_ns": decision_time_ns,
        },
    )
    ctx.incidents = [updated if i.incident_id == incident_id else i for i in ctx.incidents]
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.ACKNOWLEDGE_INCIDENT.value,
        target_refs=(incident_id,),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(incident_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, updated


def submit_resolution_evidence(
    ctx: OperatorControlContext,
    *,
    incident_id: str,
    resolution_evidence_ref: str,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    incident = next((i for i in ctx.incidents if i.incident_id == incident_id), None)
    if incident is None:
        receipt = _record_receipt(
            ctx,
            action_type=OperatorActionType.SUBMIT_RESOLUTION_EVIDENCE.value,
            target_refs=(incident_id,),
            operator_action_time_ns=decision_time_ns,
            precondition_snapshot_ref=snapshot.snapshot_id,
            result_refs=(),
            success=False,
            reason_codes=("INCIDENT_NOT_FOUND",),
            request_id=request_id,
        )
        return receipt, None
    resolved = resolve_incident(
        incident,
        resolution_evidence_ref=resolution_evidence_ref,
        resolved_at_ns=decision_time_ns,
    )
    ctx.incidents = [resolved if i.incident_id == incident_id else i for i in ctx.incidents]
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.SUBMIT_RESOLUTION_EVIDENCE.value,
        target_refs=(incident_id, resolution_evidence_ref),
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(incident_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, resolved


def approve_resume(
    ctx: OperatorControlContext,
    *,
    incident_refs: tuple[str, ...],
    resolution_evidence_ref: str,
    reconciliation_checkpoint_ref: str,
    approved_by: str,
    decision_time_ns: int,
    request_id: str,
) -> tuple[OperatorActionReceiptV1, object | None]:
    """Manual resume approval — fresh session authorization still required afterward."""
    snapshot = build_operator_control_snapshot(ctx, as_of_ns=decision_time_ns)
    program_ref = ctx.program_run.program_run_id if ctx.program_run else "UNKNOWN"
    approval = record_resume_approval(
        incident_refs=incident_refs,
        resolution_evidence_ref=resolution_evidence_ref,
        reconciliation_checkpoint_ref=reconciliation_checkpoint_ref,
        program_run_ref=program_ref,
        approved_at_ns=decision_time_ns,
        approved_by=approved_by,
        approval_source=HumanApprovalSource.OPERATOR_CONSOLE,
    )
    ctx.resume_approvals.append(approval)
    ctx.kill_switch.permit_program("RESUME_APPROVED")
    receipt = _record_receipt(
        ctx,
        action_type=OperatorActionType.APPROVE_RESUME.value,
        target_refs=incident_refs,
        operator_action_time_ns=decision_time_ns,
        precondition_snapshot_ref=snapshot.snapshot_id,
        result_refs=(approval.resume_approval_id,),
        success=True,
        reason_codes=(),
        request_id=request_id,
    )
    return receipt, approval


def register_pending_order_review(
    ctx: OperatorControlContext,
    pending: PendingOrderReview,
) -> str:
    conf_id = pending.confirmation_preview.confirmation_id
    ctx.pending_order_reviews[conf_id] = pending
    return conf_id


def inject_incident(
    ctx: OperatorControlContext,
    *,
    incident_type: IncidentType,
    severity: IncidentSeverity,
    description: str,
    detected_at_ns: int,
) -> object:
    incident = create_incident(
        incident_type=incident_type,
        severity=severity,
        detected_at_ns=detected_at_ns,
        description=description,
        session_ref=ctx.session_ref,
        program_run_ref=ctx.program_run.program_run_id if ctx.program_run else None,
    )
    ctx.incidents.append(incident)
    if severity == IncidentSeverity.CRITICAL:
        ctx.kill_switch.activate_program_block(f"INCIDENT:{incident.incident_id}")
    return incident
