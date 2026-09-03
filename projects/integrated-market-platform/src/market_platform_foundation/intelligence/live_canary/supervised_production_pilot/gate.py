"""Pilot gate integration — extends program gates without removing human controls (BUILD 33)."""

from __future__ import annotations

from ...live_execution_safety.types import LiveExecutionAuthorizationV1
from ..program_gate import GateResult, evaluate_session_start_gate
from ..program_accounting import ProgramAccounting
from ..kill_switch_store import KillSwitchStore
from ..types import LiveCanaryProgramPolicyV1, LiveExecutionIncidentV1, LiveReconciliationCheckpointV1
from .accounting import PilotAccounting
from .checkpoints import missed_checkpoint_detected, pilot_expired_blocks_session
from .provider_divergence import critical_divergence_blocks_opportunity
from .types import LiveSupervisedPilotPolicyV1, ProviderDivergenceAssessmentV1


def evaluate_pilot_active(
    *,
    policy: LiveSupervisedPilotPolicyV1,
    accounting: PilotAccounting,
    decision_time_ns: int,
    pilot_state: str,
    backup_age_ns: int | None = None,
    restore_drill_age_ns: int | None = None,
    checkpoint_evaluator_ok: bool = True,
    last_checkpoint_ns: int | None = None,
) -> GateResult:
    reasons: list[str] = []
    expired, expiry_reasons = pilot_expired_blocks_session(
        policy=policy, decision_time_ns=decision_time_ns
    )
    reasons.extend(expiry_reasons)
    if pilot_state in ("PILOT_HALTED", "PILOT_INVALID", "PILOT_COMPLETE"):
        reasons.append("PILOT_NOT_ACTIVE")
    exceeded, cap_reason = accounting.pilot_cap_exceeded(policy)
    if exceeded and cap_reason:
        reasons.append(cap_reason)
    if backup_age_ns is not None and backup_age_ns > policy.required_backup_freshness_ns:
        reasons.append("BACKUP_STALE")
    if restore_drill_age_ns is not None and restore_drill_age_ns > policy.required_restore_drill_age_ns:
        reasons.append("DR_READINESS_STALE")
    missed, missed_reasons = missed_checkpoint_detected(
        policy=policy,
        last_checkpoint_ns=last_checkpoint_ns,
        as_of_ns=decision_time_ns,
        evaluator_ok=checkpoint_evaluator_ok,
    )
    if missed:
        reasons.extend(missed_reasons)
    return GateResult(allowed=len(reasons) == 0, reason_codes=tuple(reasons))


def evaluate_pilot_session_gate(
    *,
    pilot_policy: LiveSupervisedPilotPolicyV1,
    program_policy: LiveCanaryProgramPolicyV1,
    pilot_accounting: PilotAccounting,
    program_accounting: ProgramAccounting,
    decision_time_ns: int,
    kill_switch: KillSwitchStore,
    checkpoint: LiveReconciliationCheckpointV1 | None,
    broker_healthy: bool,
    account_matched: bool,
    authorization: LiveExecutionAuthorizationV1 | None = None,
    pilot_state: str = "PILOT_ACTIVE",
    open_incidents: tuple[LiveExecutionIncidentV1, ...] = (),
    resume_approval_present: bool = False,
    divergence_assessment: ProviderDivergenceAssessmentV1 | None = None,
) -> GateResult:
    """Pilot envelope + program gate; still requires BUILD 29/30 authorization."""
    pilot_gate = evaluate_pilot_active(
        policy=pilot_policy,
        accounting=pilot_accounting,
        decision_time_ns=decision_time_ns,
        pilot_state=pilot_state,
    )
    reasons = list(pilot_gate.reason_codes)
    if not pilot_policy.human_session_authorization_required:
        reasons.append("HUMAN_SESSION_AUTHORIZATION_REQUIRED")
    if divergence_assessment and critical_divergence_blocks_opportunity(divergence_assessment):
        reasons.append("PROVIDER_DIVERGENCE_CRITICAL")
    program_gate = evaluate_session_start_gate(
        policy=program_policy,
        accounting=program_accounting,
        decision_time_ns=decision_time_ns,
        kill_switch=kill_switch,
        checkpoint=checkpoint,
        broker_healthy=broker_healthy,
        account_matched=account_matched,
        authorization=authorization,
        open_incidents=open_incidents,
        resume_approval_present=resume_approval_present,
    )
    reasons.extend(program_gate.reason_codes)
    return GateResult(allowed=len(reasons) == 0, reason_codes=tuple(dict.fromkeys(reasons)))


def pilot_policy_authorizes_order() -> bool:
    return False
