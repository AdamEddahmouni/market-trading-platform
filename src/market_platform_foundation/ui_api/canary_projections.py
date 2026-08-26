"""UI API projections for BUILD 31 operator control plane."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from ..intelligence.live_canary.operator_control import (
    OperatorControlContext,
    acknowledge_incident,
    activate_kill_switch,
    approve_resume,
    authorize_reviewed_session,
    build_audit_review_report,
    build_authorization_review_model,
    build_lineage_trace,
    build_operator_audit_timeline,
    build_operator_control_snapshot,
    build_order_review_model,
    confirm_reviewed_order,
    prepare_session_authorization,
    revoke_session_authorization,
    submit_resolution_evidence,
)
from ..intelligence.live_canary.policy import build_default_canary_policy
from ..intelligence.live_canary.program_policy import build_default_program_policy
from ..intelligence.live_canary.types import ProgramGovernanceState

# Module-level fixture context for local operator control plane API.
# Canonical trading state remains in live_canary modules; this is the UI bridge.
_OPERATOR_CTX: OperatorControlContext | None = None


def _now_ns() -> int:
    return time.time_ns()


def _get_or_init_context() -> OperatorControlContext:
    global _OPERATOR_CTX
    if _OPERATOR_CTX is None:
        t = _now_ns()
        _OPERATOR_CTX = OperatorControlContext(
            program_policy=build_default_program_policy(program_effective_from_ns=t),
            canary_policy=build_default_canary_policy(
                broker="tradier.paper", account_ref="fp-canary-local"
            ),
            governance_state=ProgramGovernanceState.PROGRAM_ACTIVE,
            session_ref="session-local-1",
            broker_health="HEALTHY",
            reconciliation_health="CLEAN",
        )
        _OPERATOR_CTX.kill_switch.permit_program("OPERATOR_CONTROL_PLANE_INIT")
    return _OPERATOR_CTX


def reset_operator_context_for_tests() -> None:
    global _OPERATOR_CTX
    _OPERATOR_CTX = None


def _snapshot_payload(ctx: OperatorControlContext, *, as_of_ns: int) -> dict[str, Any]:
    snap = build_operator_control_snapshot(ctx, as_of_ns=as_of_ns)
    return {
        "authority_boundary": "OPERATOR_CONTROL_PLANE",
        "execution_mode_label": "LIVE_CANARY",
        "paper_live_distinct": True,
        "real_money_warning": "LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED",
        "snapshot": _dataclass_to_dict(snap),
    }


def _dataclass_to_dict(obj: object) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        result: dict[str, Any] = {}
        for key, value in asdict(obj).items():
            if hasattr(value, "value"):
                result[key] = value.value
            elif isinstance(value, dict):
                result[key] = value
            elif isinstance(value, (list, tuple)):
                result[key] = list(value)
            else:
                result[key] = value
        return result
    return {"value": str(obj)}


def build_canary_snapshot_payload() -> dict[str, Any]:
    ctx = _get_or_init_context()
    return _snapshot_payload(ctx, as_of_ns=_now_ns())


def build_canary_authorization_preview_payload() -> dict[str, Any]:
    ctx = _get_or_init_context()
    as_of = _now_ns()
    receipt, preview = prepare_session_authorization(
        ctx, decision_time_ns=as_of, request_id=f"preview-{as_of}"
    )
    snap = build_operator_control_snapshot(ctx, as_of_ns=as_of)
    review = build_authorization_review_model(ctx, as_of_ns=as_of)
    return {
        "authority_boundary": "OPERATOR_CONTROL_PLANE",
        "receipt": _dataclass_to_dict(receipt),
        "authorization_review": review,
        "reviewed_snapshot_id": snap.snapshot_id,
    }


def build_canary_timeline_payload() -> dict[str, Any]:
    ctx = _get_or_init_context()
    timeline = build_operator_audit_timeline(ctx, as_of_ns=_now_ns())
    return {
        "authority_boundary": "OPERATOR_CONTROL_PLANE",
        "timeline": _dataclass_to_dict(timeline),
    }


def build_canary_reconciliation_payload() -> dict[str, Any]:
    ctx = _get_or_init_context()
    checkpoint = ctx.latest_checkpoint()
    return {
        "authority_boundary": "OPERATOR_CONTROL_PLANE",
        "reconciliation_health": ctx.reconciliation_health,
        "checkpoint": _dataclass_to_dict(checkpoint) if checkpoint else None,
        "local_open_orders": list(ctx.ledger.get_open_local_orders()),
        "ambiguous_states": list(ctx.ledger.ambiguous_client_order_ids),
    }


def build_canary_incidents_payload() -> dict[str, Any]:
    ctx = _get_or_init_context()
    return {
        "authority_boundary": "OPERATOR_CONTROL_PLANE",
        "incidents": [_dataclass_to_dict(i) for i in ctx.incidents],
        "open_critical": [i.incident_id for i in ctx.critical_open_incidents()],
    }


def handle_canary_command(body: dict[str, Any]) -> dict[str, Any]:
    ctx = _get_or_init_context()
    command = str(body.get("command", ""))
    request_id = str(body.get("request_id", f"cmd-{_now_ns()}"))
    as_of = int(body.get("decision_time_ns", _now_ns()))
    if command == "authorize_session":
        receipt, result = authorize_reviewed_session(
            ctx,
            preview_id=str(body["preview_id"]),
            preview_hash=str(body["preview_hash"]),
            reviewed_snapshot_id=str(body["reviewed_snapshot_id"]),
            approved_by=str(body.get("approved_by", "operator")),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    if command == "confirm_order":
        receipt, result = confirm_reviewed_order(
            ctx,
            confirmation_id=str(body["confirmation_id"]),
            reviewed_snapshot_id=str(body["reviewed_snapshot_id"]),
            confirmed_by=str(body.get("confirmed_by", "operator")),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    if command == "activate_kill_switch":
        receipt = activate_kill_switch(
            ctx,
            scope=str(body.get("scope", "PROGRAM")),
            reason=str(body.get("reason", "OPERATOR_ACTIVATED")),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt)}
    if command == "revoke_authorization":
        receipt, result = revoke_session_authorization(
            ctx, decision_time_ns=as_of, request_id=request_id
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    if command == "acknowledge_incident":
        receipt, result = acknowledge_incident(
            ctx,
            incident_id=str(body["incident_id"]),
            acknowledged_by=str(body.get("acknowledged_by", "operator")),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    if command == "submit_resolution_evidence":
        receipt, result = submit_resolution_evidence(
            ctx,
            incident_id=str(body["incident_id"]),
            resolution_evidence_ref=str(body["resolution_evidence_ref"]),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    if command == "approve_resume":
        receipt, result = approve_resume(
            ctx,
            incident_refs=tuple(body.get("incident_refs", [])),
            resolution_evidence_ref=str(body["resolution_evidence_ref"]),
            reconciliation_checkpoint_ref=str(body["reconciliation_checkpoint_ref"]),
            approved_by=str(body.get("approved_by", "operator")),
            decision_time_ns=as_of,
            request_id=request_id,
        )
        return {"receipt": _dataclass_to_dict(receipt), "result": _dataclass_to_dict(result) if result else None}
    return {"error": "UNKNOWN_COMMAND", "command": command}


def build_canary_action_inventory() -> dict[str, Any]:
    return {
        "actions": [
            {
                "action": "prepare_session_authorization",
                "backend_authority": "live_canary.authorization.prepare_canary_authorization_preview",
                "required_human_review": True,
                "idempotent": False,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "authorize_session",
                "backend_authority": "live_canary.authorization.authorize_canary_from_human_approval",
                "required_human_review": True,
                "idempotent": True,
                "increases_authority": True,
                "broker_side_effect": False,
            },
            {
                "action": "confirm_order",
                "backend_authority": "live_canary.confirmation.confirm_order",
                "required_human_review": True,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "activate_kill_switch",
                "backend_authority": "live_canary.kill_switch_store.KillSwitchStore",
                "required_human_review": False,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "revoke_authorization",
                "backend_authority": "live_canary.authorization.revoke_authorization",
                "required_human_review": False,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "acknowledge_incident",
                "backend_authority": "operator_control.commands.acknowledge_incident",
                "required_human_review": False,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "submit_resolution_evidence",
                "backend_authority": "live_canary.incidents.resolve_incident",
                "required_human_review": True,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
            {
                "action": "approve_resume",
                "backend_authority": "live_canary.incidents.record_resume_approval",
                "required_human_review": True,
                "idempotent": True,
                "increases_authority": False,
                "broker_side_effect": False,
            },
        ]
    }
