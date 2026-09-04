"""Pilot telemetry snapshots for operator visibility (BUILD 33)."""

from __future__ import annotations

from typing import Any

from ..operator_control.context import OperatorControlContext
from .accounting import PilotAccounting
from .policy import build_default_pilot_policy, build_default_provider_redundancy_policy
from .types import PilotGovernanceState


def build_pilot_snapshot(
    *,
    ctx: OperatorControlContext,
    pilot_accounting: PilotAccounting,
    as_of_ns: int,
    pilot_state: str = PilotGovernanceState.PILOT_ACTIVE.value,
    build32_ref: str = "ce49004c1388afc4895dd6d595ccb1b063757441",
) -> dict[str, Any]:
    policy = build_default_pilot_policy(
        source_build32_ref=build32_ref,
        pilot_start_ns=as_of_ns - 3_600_000_000_000,
    )
    redundancy = build_default_provider_redundancy_policy()
    exceeded, cap_reason = pilot_accounting.pilot_cap_exceeded(policy)
    return {
        "authority_boundary": "SUPERVISED_PRODUCTION_PILOT_READ_ONLY",
        "pilot_state": pilot_state,
        "pilot_policy_id": policy.pilot_policy_id,
        "provider_redundancy_policy_id": redundancy.provider_redundancy_policy_id,
        "human_session_authorization_required": policy.human_session_authorization_required,
        "human_order_confirmation_required": policy.human_order_confirmation_required,
        "pilot_cap_exceeded": exceeded,
        "pilot_cap_reason": cap_reason,
        "sessions_completed": pilot_accounting.sessions_completed,
        "orders_submitted": pilot_accounting.orders_submitted,
        "broker_health": ctx.broker_health,
        "reconciliation_health": ctx.reconciliation_health,
        "auto_broker_failover": "NOT_AUTHORIZED",
    }
