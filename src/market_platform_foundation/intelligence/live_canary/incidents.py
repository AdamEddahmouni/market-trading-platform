"""Live execution incident detection and response (BUILD 30)."""

from __future__ import annotations

from .identity import derive_incident_id, derive_resume_approval_id, derive_response_policy_id
from .types import (
    LIVE_CANARY_PROGRAM_IMPLEMENTATION_VERSION,
    LIVE_CANARY_SCHEMA_VERSION,
    HumanApprovalSource,
    IncidentAction,
    IncidentSeverity,
    IncidentState,
    IncidentType,
    LiveExecutionIncidentV1,
    LiveIncidentResponsePolicyV1,
    LiveOperationalResumeApprovalV1,
)


def build_default_incident_response_policy() -> LiveIncidentResponsePolicyV1:
    policy = LiveIncidentResponsePolicyV1(
        response_policy_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        info_actions=(IncidentAction.LOG_ONLY.value,),
        warning_actions=(
            IncidentAction.LOG_ONLY.value,
            IncidentAction.RECONCILE_REQUIRED.value,
        ),
        critical_actions=(
            IncidentAction.BLOCK_NEW_SUBMITS.value,
            IncidentAction.MANUAL_REVIEW_REQUIRED.value,
            IncidentAction.HALT_PROGRAM.value,
        ),
        implementation_version=LIVE_CANARY_PROGRAM_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(policy, "response_policy_id", derive_response_policy_id(policy))
    return policy


def actions_for_severity(
    policy: LiveIncidentResponsePolicyV1,
    severity: IncidentSeverity,
) -> tuple[str, ...]:
    if severity == IncidentSeverity.CRITICAL:
        return policy.critical_actions
    if severity == IncidentSeverity.WARNING:
        return policy.warning_actions
    return policy.info_actions


def create_incident(
    *,
    incident_type: IncidentType,
    severity: IncidentSeverity,
    detected_at_ns: int,
    description: str,
    session_ref: str | None = None,
    program_run_ref: str | None = None,
    response_policy: LiveIncidentResponsePolicyV1 | None = None,
) -> LiveExecutionIncidentV1:
    response_policy = response_policy or build_default_incident_response_policy()
    actions = actions_for_severity(response_policy, severity)
    incident = LiveExecutionIncidentV1(
        incident_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        incident_type=incident_type,
        severity=severity,
        state=IncidentState.OPEN,
        session_ref=session_ref,
        program_run_ref=program_run_ref,
        detected_at_ns=detected_at_ns,
        description=description,
        resolution_evidence_ref=None,
        resolved_at_ns=None,
        actions_taken=actions,
    )
    object.__setattr__(incident, "incident_id", derive_incident_id(incident))
    return incident


def resolve_incident(
    incident: LiveExecutionIncidentV1,
    *,
    resolution_evidence_ref: str,
    resolved_at_ns: int,
) -> LiveExecutionIncidentV1:
    return LiveExecutionIncidentV1(
        incident_id=incident.incident_id,
        schema_version=incident.schema_version,
        incident_type=incident.incident_type,
        severity=incident.severity,
        state=IncidentState.RESOLVED,
        session_ref=incident.session_ref,
        program_run_ref=incident.program_run_ref,
        detected_at_ns=incident.detected_at_ns,
        description=incident.description,
        resolution_evidence_ref=resolution_evidence_ref,
        resolved_at_ns=resolved_at_ns,
        actions_taken=incident.actions_taken,
        lineage=dict(incident.lineage),
        metadata=dict(incident.metadata),
    )


def record_resume_approval(
    *,
    incident_refs: tuple[str, ...],
    resolution_evidence_ref: str,
    reconciliation_checkpoint_ref: str,
    program_run_ref: str,
    approved_at_ns: int,
    approved_by: str,
    approval_source: HumanApprovalSource,
) -> LiveOperationalResumeApprovalV1:
    approval = LiveOperationalResumeApprovalV1(
        resume_approval_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        incident_refs=incident_refs,
        resolution_evidence_ref=resolution_evidence_ref,
        reconciliation_checkpoint_ref=reconciliation_checkpoint_ref,
        program_run_ref=program_run_ref,
        approved_at_ns=approved_at_ns,
        approved_by=approved_by,
        approval_source=approval_source,
    )
    object.__setattr__(approval, "resume_approval_id", derive_resume_approval_id(approval))
    return approval


def incident_blocks_submits(incident: LiveExecutionIncidentV1) -> bool:
    if incident.state != IncidentState.OPEN:
        return False
    return IncidentAction.BLOCK_NEW_SUBMITS.value in incident.actions_taken
