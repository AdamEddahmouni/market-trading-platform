"""Production release approval (BUILD 35)."""

from __future__ import annotations

from .identity import derive_release_approval_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    EligibilityDisposition,
    ProductionReleaseApprovalV1,
    ProductionReleaseEligibilityAssessmentV1,
    ReleaseApprovalStatus,
)


def build_release_approval(
    *,
    candidate_ref: str,
    eligibility: ProductionReleaseEligibilityAssessmentV1,
    approved_environment_scope: tuple[str, ...],
    approval_time_ns: int,
    governance_reason: str = "BUILD35 full-system acceptance qualified supervised operation",
    limitations_accepted: tuple[str, ...] = (),
) -> ProductionReleaseApprovalV1:
    if eligibility.disposition != EligibilityDisposition.ELIGIBLE.value:
        status = ReleaseApprovalStatus.REJECTED.value
    elif eligibility.blocking_reasons:
        status = ReleaseApprovalStatus.REJECTED.value
    else:
        status = ReleaseApprovalStatus.APPROVED_SUPERVISED_OPERATION.value

    approval = ProductionReleaseApprovalV1(
        release_approval_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        candidate_ref=candidate_ref,
        eligibility_assessment_ref=eligibility.eligibility_assessment_id,
        approved_environment_scope=approved_environment_scope,
        approval_time_ns=approval_time_ns,
        approval_status=status,
        limitations_accepted=limitations_accepted or eligibility.limitations,
        blocking_limitations_rejected=eligibility.blocking_reasons,
        release_expiry_ns=None,
        governance_reason=governance_reason,
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        lineage={"eligibility_ref": eligibility.eligibility_assessment_id},
    )
    return ProductionReleaseApprovalV1(
        release_approval_id=derive_release_approval_id(approval),
        schema_version=approval.schema_version,
        candidate_ref=approval.candidate_ref,
        eligibility_assessment_ref=approval.eligibility_assessment_ref,
        approved_environment_scope=approval.approved_environment_scope,
        approval_time_ns=approval.approval_time_ns,
        approval_status=approval.approval_status,
        limitations_accepted=approval.limitations_accepted,
        blocking_limitations_rejected=approval.blocking_limitations_rejected,
        release_expiry_ns=approval.release_expiry_ns,
        governance_reason=approval.governance_reason,
        implementation_version=approval.implementation_version,
        lineage=approval.lineage,
        metadata=approval.metadata,
    )


def revoke_release_approval(
    approval: ProductionReleaseApprovalV1,
    *,
    reason: str,
    revocation_time_ns: int,
) -> ProductionReleaseApprovalV1:
    return ProductionReleaseApprovalV1(
        release_approval_id=approval.release_approval_id,
        schema_version=approval.schema_version,
        candidate_ref=approval.candidate_ref,
        eligibility_assessment_ref=approval.eligibility_assessment_ref,
        approved_environment_scope=approval.approved_environment_scope,
        approval_time_ns=approval.approval_time_ns,
        approval_status=ReleaseApprovalStatus.REVOKED.value,
        limitations_accepted=approval.limitations_accepted,
        blocking_limitations_rejected=approval.blocking_limitations_rejected,
        release_expiry_ns=approval.release_expiry_ns,
        governance_reason=f"REVOKED: {reason}",
        implementation_version=approval.implementation_version,
        lineage={**approval.lineage, "revocation_time_ns": str(revocation_time_ns)},
        metadata={**approval.metadata, "revocation_reason": reason},
    )


def approval_authorizes_live_session() -> bool:
    return False


def approval_confirms_order() -> bool:
    return False
