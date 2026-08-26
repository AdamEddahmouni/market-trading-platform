"""Read-only program operational status (BUILD 30)."""

from __future__ import annotations

from dataclasses import dataclass

from ..live_execution_safety.types import LiveAuthorizationState
from .kill_switch_store import KillSwitchStore
from .program_accounting import ProgramAccounting
from .types import LiveCanaryProgramPolicyV1, LiveExecutionIncidentV1, ProgramGovernanceState


@dataclass(frozen=True)
class ProgramOperationalStatus:
    program_state: str
    session_state: str | None
    authorization_status: str | None
    broker_health: str
    reconciliation_health: str
    current_live_exposure_minor: int
    orders_submitted: int
    fills: int
    open_incidents: int
    kill_switch_global: str
    kill_switch_program: str
    kill_switch_session: str
    remaining_program_sessions: int
    remaining_program_orders: int
    remaining_program_notional_minor: int
    cooldown_active: bool


def get_program_operational_status(
    *,
    governance_state: ProgramGovernanceState,
    policy: LiveCanaryProgramPolicyV1,
    accounting: ProgramAccounting,
    kill_switch: KillSwitchStore,
    incidents: tuple[LiveExecutionIncidentV1, ...] = (),
    authorization_state: LiveAuthorizationState | None = None,
    reconciliation_health: str = "UNKNOWN",
    broker_health: str = "UNKNOWN",
    decision_time_ns: int = 0,
    session_state: str | None = None,
) -> ProgramOperationalStatus:
    open_incidents = sum(1 for i in incidents if i.state.value == "OPEN")
    cooldown_active = not accounting.cooldown_satisfied(policy, decision_time_ns)
    return ProgramOperationalStatus(
        program_state=governance_state.value,
        session_state=session_state,
        authorization_status=(
            authorization_state.value if authorization_state else None
        ),
        broker_health=broker_health,
        reconciliation_health=reconciliation_health,
        current_live_exposure_minor=accounting.open_residual_exposure_minor,
        orders_submitted=accounting.total_submit_attempts,
        fills=accounting.total_fills,
        open_incidents=open_incidents,
        kill_switch_global=kill_switch.global_state.value,
        kill_switch_program=kill_switch.program_state.value,
        kill_switch_session=kill_switch.session_state.value,
        remaining_program_sessions=max(0, policy.max_sessions - accounting.sessions_completed),
        remaining_program_orders=max(
            0, policy.max_program_order_count - accounting.total_submit_attempts
        ),
        remaining_program_notional_minor=max(
            0,
            policy.max_program_live_notional_minor - accounting.filled_notional_minor,
        ),
        cooldown_active=cooldown_active,
    )
