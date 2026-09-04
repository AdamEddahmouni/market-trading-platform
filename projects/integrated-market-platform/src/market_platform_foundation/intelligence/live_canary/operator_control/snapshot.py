"""Operator control snapshot read model (BUILD 31)."""

from __future__ import annotations

from ..incidents import incident_blocks_submits
from ..program_status import get_program_operational_status
from ...live_execution_safety.types import KillSwitchState, LiveAuthorizationState
from .context import OperatorControlContext
from .identity import derive_snapshot_id
from .types import (
    OPERATOR_CONTROL_SCHEMA_VERSION,
    ExecutionModeLabel,
    OperatorControlSnapshotV1,
    OperatorNextAction,
)


class OperatorControlError(ValueError):
    pass


def _authorization_expiry(ctx: OperatorControlContext) -> int | None:
    if ctx.authorization is None:
        return None
    return ctx.authorization.effective_until_ns


def _derive_block_reasons(ctx: OperatorControlContext, *, as_of_ns: int) -> tuple[str, ...]:
    reasons: list[str] = []
    if ctx.kill_switch.any_block_active():
        if ctx.kill_switch.global_state.value == "ACTIVE_BLOCK":
            reasons.append("GLOBAL_KILL_SWITCH")
        if ctx.kill_switch.program_state.value == "ACTIVE_BLOCK":
            reasons.append("PROGRAM_KILL_SWITCH")
        if ctx.kill_switch.session_state.value == "ACTIVE_BLOCK":
            reasons.append("SESSION_KILL_SWITCH")
    for incident in ctx.open_incidents():
        if incident_blocks_submits(incident):
            reasons.append(f"INCIDENT:{incident.incident_id}")
    if ctx.authorization is None and ctx.governance_state.value in (
        "SESSION_PREPARED",
        "SESSION_AUTHORIZED",
        "SESSION_ACTIVE",
    ):
        reasons.append("NO_AUTHORIZATION")
    elif ctx.authorization is not None:
        if ctx.authorization.authorization_state not in (
            LiveAuthorizationState.AUTHORIZED,
            LiveAuthorizationState.ENABLED,
        ):
            reasons.append(f"AUTHORIZATION_{ctx.authorization.authorization_state.value}")
        elif as_of_ns >= ctx.authorization.effective_until_ns:
            reasons.append("AUTHORIZATION_EXPIRED")
    if ctx.reconciliation_health not in ("CLEAN", "UNKNOWN"):
        reasons.append(f"RECONCILIATION_{ctx.reconciliation_health}")
    if ctx.broker_health not in ("HEALTHY", "UNKNOWN"):
        reasons.append(f"BROKER_{ctx.broker_health}")
    exceeded, cap_reason = ctx.accounting.program_cap_exceeded(ctx.program_policy)
    if exceeded:
        reasons.append(f"PROGRAM_CAP_{cap_reason}")
    if ctx.governance_state.value in ("PROGRAM_HALTED", "PROGRAM_COMPLETE", "PROGRAM_PAUSED"):
        reasons.append(f"PROGRAM_{ctx.governance_state.value}")
    return tuple(reasons)


def _derive_allowed_actions(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
    live_blocked: bool,
) -> tuple[str, ...]:
    actions: list[str] = []
    if ctx.governance_state.value == "PROGRAM_PREPARED":
        actions.append(OperatorNextAction.PREPARE_SESSION.value)
    if ctx.authorization_preview is not None and ctx.authorization is None:
        if not live_blocked or ctx.kill_switch.any_block_active() is False:
            actions.append(OperatorNextAction.AUTHORIZE_SESSION.value)
    if ctx.pending_order_reviews and not live_blocked:
        actions.append(OperatorNextAction.CONFIRM_ORDER.value)
    actions.append(OperatorNextAction.ACTIVATE_KILL_SWITCH.value)
    if ctx.authorization is not None and ctx.authorization.authorization_state in (
        LiveAuthorizationState.AUTHORIZED,
        LiveAuthorizationState.ENABLED,
    ):
        actions.append(OperatorNextAction.REVOKE_AUTHORIZATION.value)
    for incident in ctx.open_incidents():
        if not incident.metadata.get("acknowledged"):
            actions.append(OperatorNextAction.ACKNOWLEDGE_INCIDENT.value)
        if incident.state.value == "OPEN" and incident.severity.value == "CRITICAL":
            actions.append(OperatorNextAction.BEGIN_RECONCILIATION.value)
            actions.append(OperatorNextAction.REQUEST_RESUME_REVIEW.value)
    if ctx.governance_state.value == "PROGRAM_COMPLETE":
        actions.append(OperatorNextAction.REVIEW_PROGRAM_HISTORY.value)
    return tuple(dict.fromkeys(actions))


def _build_action_queue(ctx: OperatorControlContext) -> tuple[dict[str, object], ...]:
    queue: list[dict[str, object]] = []
    if ctx.authorization_preview and ctx.authorization is None:
        queue.append(
            {
                "item_type": "AUTHORIZATION_PREVIEW",
                "preview_id": ctx.authorization_preview.preview_id,
                "requires_explicit_review": True,
            }
        )
    for conf_id, pending in ctx.pending_order_reviews.items():
        queue.append(
            {
                "item_type": "ORDER_CONFIRMATION",
                "confirmation_id": conf_id,
                "instrument_id": pending.confirmation_preview.instrument_id,
                "side": pending.confirmation_preview.side,
                "quantity": pending.confirmation_preview.quantity,
                "requires_explicit_review": True,
            }
        )
    for incident in ctx.critical_open_incidents():
        queue.append(
            {
                "item_type": "CRITICAL_INCIDENT",
                "incident_id": incident.incident_id,
                "incident_type": incident.incident_type.value,
                "acknowledged": bool(incident.metadata.get("acknowledged")),
                "requires_explicit_review": True,
            }
        )
    return tuple(queue)


def build_operator_control_snapshot(
    ctx: OperatorControlContext,
    *,
    as_of_ns: int,
) -> OperatorControlSnapshotV1:
    """Deterministic read-only operator snapshot — explicitly as-of."""
    block_reasons = _derive_block_reasons(ctx, as_of_ns=as_of_ns)
    live_blocked = len(block_reasons) > 0
    status = get_program_operational_status(
        governance_state=ctx.governance_state,
        policy=ctx.program_policy,
        accounting=ctx.accounting,
        kill_switch=ctx.kill_switch,
        incidents=tuple(ctx.incidents),
        authorization_state=ctx.authorization.authorization_state if ctx.authorization else None,
        reconciliation_health=ctx.reconciliation_health,
        broker_health=ctx.broker_health,
        decision_time_ns=as_of_ns,
        session_state=ctx.session_state,
    )
    checkpoint = ctx.latest_checkpoint()
    positions: tuple[dict[str, object], ...] = ()
    open_orders: tuple[dict[str, object], ...] = ()
    if checkpoint is not None:
        positions = checkpoint.broker_positions
        open_orders = tuple({"order_id": oid} for oid in checkpoint.broker_open_orders)
    incident_summary = {
        "open": sum(1 for i in ctx.incidents if i.state.value == "OPEN"),
        "critical_open": len(ctx.critical_open_incidents()),
        "resolved": sum(1 for i in ctx.incidents if i.state.value == "RESOLVED"),
        "warning": sum(
            1 for i in ctx.incidents if i.severity.value == "WARNING" and i.state.value == "OPEN"
        ),
    }
    snapshot = OperatorControlSnapshotV1(
        snapshot_id="",
        schema_version=OPERATOR_CONTROL_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        execution_mode_label=ExecutionModeLabel.LIVE_CANARY.value,
        live_blocked=live_blocked,
        block_reasons=block_reasons,
        runtime_governance_state="BUILD23_ACTIVE",
        program_state=status.program_state,
        session_state=status.session_state,
        program_run_ref=ctx.program_run.program_run_id if ctx.program_run else None,
        session_ref=ctx.session_ref,
        broker=ctx.canary_policy.broker,
        account_environment=ctx.canary_policy.account_environment,
        account_fingerprint=(
            ctx.authorization_preview.account_fingerprint if ctx.authorization_preview else None
        ),
        broker_health=status.broker_health,
        reconciliation_health=status.reconciliation_health,
        kill_switch_global=status.kill_switch_global,
        kill_switch_program=status.kill_switch_program,
        kill_switch_session=status.kill_switch_session,
        authorization_status=status.authorization_status,
        authorization_expires_at_ns=_authorization_expiry(ctx),
        pending_confirmation_refs=tuple(ctx.pending_order_reviews.keys()),
        live_positions=positions,
        open_broker_orders=open_orders,
        ambiguous_states=tuple(ctx.ledger.ambiguous_client_order_ids),
        program_cap_usage={
            "sessions_completed": ctx.accounting.sessions_completed,
            "orders_submitted": ctx.accounting.total_submit_attempts,
            "notional_minor": ctx.accounting.filled_notional_minor,
        },
        program_cap_remaining={
            "sessions": status.remaining_program_sessions,
            "orders": status.remaining_program_orders,
            "notional_minor": status.remaining_program_notional_minor,
        },
        session_cap_remaining={
            "orders": max(
                0,
                ctx.canary_policy.max_order_count - ctx.accounting.total_submit_attempts,
            ),
            "notional_minor": max(
                0,
                ctx.canary_policy.max_total_canary_notional_minor
                - ctx.accounting.filled_notional_minor,
            ),
        },
        incident_summary=incident_summary,
        unresolved_critical_incidents=tuple(i.incident_id for i in ctx.critical_open_incidents()),
        allowed_next_actions=_derive_allowed_actions(ctx, as_of_ns=as_of_ns, live_blocked=live_blocked),
        action_queue=_build_action_queue(ctx),
        source_refs=tuple(
            ref
            for ref in (
                ctx.program_run.program_run_id if ctx.program_run else None,
                ctx.session_ref,
                ctx.authorization.authorization_id if ctx.authorization else None,
                checkpoint.checkpoint_id if checkpoint else None,
            )
            if ref
        ),
        metadata={
            "real_money_warning": "LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED",
            "paper_live_distinct": True,
        },
    )
    object.__setattr__(snapshot, "snapshot_id", derive_snapshot_id(snapshot))
    ctx.snapshot_versions[snapshot.snapshot_id] = snapshot.snapshot_id
    ctx.frozen_snapshots[snapshot.snapshot_id] = snapshot
    return snapshot


def validate_snapshot_binding(
    ctx: OperatorControlContext,
    *,
    reviewed_snapshot_id: str,
    reviewed_snapshot_hash: str | None = None,
    as_of_ns: int,
    max_staleness_ns: int = 60_000_000_000,
) -> tuple[bool, str | None]:
    """Reject operator mutations when reviewed snapshot is stale."""
    frozen = ctx.frozen_snapshots.get(reviewed_snapshot_id)
    if frozen is None:
        return False, "STALE_OPERATOR_VIEW"
    current = build_operator_control_snapshot(ctx, as_of_ns=as_of_ns)
    if frozen.program_state != current.program_state:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.authorization_status != current.authorization_status:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.kill_switch_global != current.kill_switch_global:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.kill_switch_program != current.kill_switch_program:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.kill_switch_session != current.kill_switch_session:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.unresolved_critical_incidents != current.unresolved_critical_incidents:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.reconciliation_health != current.reconciliation_health:
        return False, "STALE_OPERATOR_VIEW"
    if frozen.broker_health != current.broker_health:
        return False, "STALE_OPERATOR_VIEW"
    if as_of_ns - frozen.as_of_ns > max_staleness_ns:
        return False, "STALE_OPERATOR_VIEW"
    return True, None
