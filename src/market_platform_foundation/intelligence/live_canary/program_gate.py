"""Program and session gate evaluation (BUILD 30)."""

from __future__ import annotations

from ..live_execution_safety.types import LiveExecutionAuthorizationV1, LiveGateReasonCode
from .incidents import incident_blocks_submits
from .kill_switch_store import KillSwitchStore
from .program_accounting import ProgramAccounting
from .reconciliation_checkpoint import evaluate_checkpoint_clean
from .types import (
    IncidentSeverity,
    IncidentType,
    LiveCanaryProgramPolicyV1,
    LiveExecutionIncidentV1,
    LiveReconciliationCheckpointV1,
)


class GateResult:
    __slots__ = ("allowed", "reason_codes")

    def __init__(self, *, allowed: bool, reason_codes: tuple[str, ...]) -> None:
        self.allowed = allowed
        self.reason_codes = reason_codes


def evaluate_program_active(
    *,
    policy: LiveCanaryProgramPolicyV1,
    accounting: ProgramAccounting,
    decision_time_ns: int,
    kill_switch: KillSwitchStore,
    open_incidents: tuple[LiveExecutionIncidentV1, ...] = (),
    resume_approval_present: bool = False,
) -> GateResult:
    reasons: list[str] = []
    if decision_time_ns < policy.program_effective_from_ns:
        reasons.append("PROGRAM_NOT_STARTED")
    if decision_time_ns >= policy.program_effective_until_ns:
        reasons.append(LiveGateReasonCode.PROGRAM_EXPIRED.value)
    if kill_switch.any_block_active() and kill_switch.program_state.value == "ACTIVE_BLOCK":
        reasons.append(LiveGateReasonCode.KILL_SWITCH_ACTIVE.value)
    exceeded, cap_reason = accounting.program_cap_exceeded(policy)
    if exceeded and cap_reason:
        reasons.append(LiveGateReasonCode.PROGRAM_CAP_EXCEEDED.value)
    if accounting.sessions_completed >= policy.max_sessions:
        reasons.append(LiveGateReasonCode.PROGRAM_SESSION_LIMIT.value)
    for incident in open_incidents:
        if incident_blocks_submits(incident):
            reasons.append(LiveGateReasonCode.PROGRAM_HALTED.value)
            break
    if (
        accounting.consecutive_incidents >= policy.max_consecutive_incidents
        and policy.manual_resume_required
        and not resume_approval_present
    ):
        reasons.append(LiveGateReasonCode.MANUAL_RESUME_REQUIRED.value)
    return GateResult(allowed=len(reasons) == 0, reason_codes=tuple(reasons))


def evaluate_session_start_gate(
    *,
    policy: LiveCanaryProgramPolicyV1,
    accounting: ProgramAccounting,
    decision_time_ns: int,
    kill_switch: KillSwitchStore,
    checkpoint: LiveReconciliationCheckpointV1 | None,
    broker_healthy: bool,
    account_matched: bool,
    authorization: LiveExecutionAuthorizationV1 | None,
    prior_authorization_ref: str | None = None,
    status_feed_as_of_ns: int | None = None,
    open_incidents: tuple[LiveExecutionIncidentV1, ...] = (),
    resume_approval_present: bool = False,
) -> GateResult:
    program_gate = evaluate_program_active(
        policy=policy,
        accounting=accounting,
        decision_time_ns=decision_time_ns,
        kill_switch=kill_switch,
        open_incidents=open_incidents,
        resume_approval_present=resume_approval_present,
    )
    reasons = list(program_gate.reason_codes)
    if not accounting.cooldown_satisfied(policy, decision_time_ns):
        reasons.append(LiveGateReasonCode.PROGRAM_COOLDOWN_ACTIVE.value)
    if kill_switch.session_state.value == "ACTIVE_BLOCK":
        reasons.append(LiveGateReasonCode.KILL_SWITCH_ACTIVE.value)
    if not broker_healthy:
        reasons.append(LiveGateReasonCode.BROKER_UNHEALTHY.value)
    if not account_matched:
        reasons.append(LiveGateReasonCode.ACCOUNT_MISMATCH.value)
    if policy.require_clean_reconciliation_before_session:
        if checkpoint is None:
            reasons.append(LiveGateReasonCode.PROGRAM_RECONCILIATION_REQUIRED.value)
        else:
            eval_result = evaluate_checkpoint_clean(checkpoint)
            if not eval_result.passed:
                reasons.extend(eval_result.reason_codes)
    if authorization is None:
        reasons.append(LiveGateReasonCode.LIVE_AUTHORIZATION_MISSING.value)
    elif prior_authorization_ref and authorization.authorization_id == prior_authorization_ref:
        reasons.append(LiveGateReasonCode.SESSION_AUTHORIZATION_MISMATCH.value)
    if status_feed_as_of_ns is not None:
        stale_threshold = policy.status_feed_stale_threshold_ns
        if decision_time_ns - status_feed_as_of_ns > stale_threshold:
            reasons.append(LiveGateReasonCode.STATUS_FEED_STALE.value)
    return GateResult(allowed=len(reasons) == 0, reason_codes=tuple(reasons))


def evaluate_session_end_gate(
    *,
    policy: LiveCanaryProgramPolicyV1,
    checkpoint: LiveReconciliationCheckpointV1 | None,
) -> GateResult:
    if not policy.require_clean_reconciliation_after_session:
        return GateResult(allowed=True, reason_codes=())
    if checkpoint is None:
        return GateResult(
            allowed=False,
            reason_codes=(LiveGateReasonCode.PROGRAM_RECONCILIATION_REQUIRED.value,),
        )
    eval_result = evaluate_checkpoint_clean(checkpoint)
    return GateResult(allowed=eval_result.passed, reason_codes=eval_result.reason_codes)


def detect_external_broker_activity(
    *,
    checkpoint: LiveReconciliationCheckpointV1,
    known_platform_orders: frozenset[str],
) -> tuple[bool, IncidentType | None]:
    external = [
        o for o in checkpoint.broker_only
        if o not in known_platform_orders
    ]
    if external:
        return True, IncidentType.EXTERNAL_ACCOUNT_ACTIVITY
    if checkpoint.broker_only:
        return True, IncidentType.BROKER_ONLY_ORDER
    return False, None
