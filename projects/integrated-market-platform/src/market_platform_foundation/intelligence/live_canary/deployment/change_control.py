"""Deployment change control (BUILD 34)."""

from __future__ import annotations

from .identity import derive_change_request_id
from .promotion import floating_latest_prohibited
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    ChangeApprovalState,
    ChangeType,
    DeploymentChangeRequestV1,
)

T = 1_700_000_000_000_000_000


def build_change_request(
    *,
    change_type: str,
    release_ref: str,
    target_environment: str,
    reason: str,
    rollback_target: str,
    configuration_diff: dict | None = None,
    migration_diff: dict | None = None,
    qualification_refs: tuple[str, ...] = (),
    approval_state: str = ChangeApprovalState.PENDING_APPROVAL.value,
) -> DeploymentChangeRequestV1:
    if floating_latest_prohibited(release_ref):
        approval_state = ChangeApprovalState.REJECTED.value
    request = DeploymentChangeRequestV1(
        change_request_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        change_type=change_type,
        release_ref=release_ref,
        configuration_diff=configuration_diff or {},
        migration_diff=migration_diff or {},
        target_environment=target_environment,
        reason=reason,
        risk_classification="MEDIUM" if change_type == ChangeType.CODE_RELEASE.value else "LOW",
        required_qualification_refs=qualification_refs,
        rollback_target=rollback_target,
        planned_window_ns=(T, T + 3600_000_000_000),
        approval_state=approval_state,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentChangeRequestV1(
        change_request_id=derive_change_request_id(request),
        schema_version=request.schema_version,
        change_type=request.change_type,
        release_ref=request.release_ref,
        configuration_diff=request.configuration_diff,
        migration_diff=request.migration_diff,
        target_environment=request.target_environment,
        reason=request.reason,
        risk_classification=request.risk_classification,
        required_qualification_refs=request.required_qualification_refs,
        rollback_target=request.rollback_target,
        planned_window_ns=request.planned_window_ns,
        approval_state=request.approval_state,
        implementation_version=request.implementation_version,
        metadata=request.metadata,
    )


def deployment_requires_approved_change_request(
    request: DeploymentChangeRequestV1 | None,
) -> tuple[bool, str]:
    if request is None:
        return False, "no change request"
    if request.approval_state != ChangeApprovalState.APPROVED.value:
        return False, f"change request not approved: {request.approval_state}"
    if floating_latest_prohibited(request.release_ref):
        return False, "floating latest release prohibited"
    return True, "OK"
