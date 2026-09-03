"""Default release governance policies (BUILD 35)."""

from __future__ import annotations

from .identity import derive_governance_policy_id
from .types import (
    FORBIDDEN_AUTONOMY_EXPANSIONS,
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ProductionReleaseGovernancePolicyV1,
)

# Accepted qualification dispositions per build (minimum acceptable)
ACCEPTED_BUILD_DISPOSITIONS: dict[str, tuple[str, ...]] = {
    "BUILD25": ("ACCEPTED", "ACCEPTED_WITH_LIMITATIONS"),
    "BUILD26": (
        "FORWARD_QUALIFIED",
        "FORWARD_QUALIFIED_WITH_LIMITATIONS",
        "INSUFFICIENT_FORWARD_EVIDENCE",
    ),
    "BUILD27": ("PAPER_EXECUTION_QUALIFIED", "PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS"),
    "BUILD28": ("PRELIVE_SAFETY_GATE_COMPLETE", "PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS"),
    "BUILD29": ("CANARY_QUALIFIED", "CANARY_QUALIFIED_WITH_LIMITATIONS", "CANARY_NOT_EXECUTED"),
    "BUILD30": ("SUPERVISED_CANARY_PROGRAM_COMPLETE",),
    "BUILD31": ("OPERATOR_CONTROL_PLANE_QUALIFIED", "OPERATOR_CONTROL_PLANE_QUALIFIED_WITH_LIMITATIONS"),
    "BUILD32": (
        "OPERATIONAL_RELIABILITY_QUALIFIED",
        "OPERATIONAL_RELIABILITY_QUALIFIED_WITH_LIMITATIONS",
    ),
    "BUILD33": (
        "SUPERVISED_PRODUCTION_PILOT_QUALIFIED",
        "SUPERVISED_PRODUCTION_PILOT_QUALIFIED_WITH_LIMITATIONS",
    ),
    "BUILD34": ("DEPLOYMENT_QUALIFIED", "DEPLOYMENT_QUALIFIED_WITH_LIMITATIONS"),
}

# Dispositions that block supervised-live release approval
BLOCKING_BUILD_DISPOSITIONS: dict[str, tuple[str, ...]] = {
    "BUILD26": (),  # INSUFFICIENT_FORWARD_EVIDENCE is nonblocking limitation
    "BUILD29": (),  # CANARY_NOT_EXECUTED is nonblocking for supervised operation with limitations
}

REQUIRED_BUILD_EVIDENCE = (
    "BUILD25",
    "BUILD26",
    "BUILD27",
    "BUILD28",
    "BUILD29",
    "BUILD30",
    "BUILD31",
    "BUILD32",
    "BUILD33",
    "BUILD34",
)


def build_default_release_governance_policy(
    *,
    environment_promotion_policy_ref: str,
    change_window_policy_ref: str,
    rollback_policy_ref: str = "BUILD34-ROLLBACK-POLICY",
    release_expiry_policy_ref: str = "REQUALIFY-ON-MATERIAL-CHANGE",
) -> ProductionReleaseGovernancePolicyV1:
    policy = ProductionReleaseGovernancePolicyV1(
        release_governance_policy_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        eligible_source_branches=(
            "cloud/build-34-deployment-change-control",
            "cloud/build-35-release-governance-operational-acceptance",
        ),
        required_build_evidence=REQUIRED_BUILD_EVIDENCE,
        required_test_suites=(
            "intelligence",
            "deployment_change_control",
            "release_governance",
            "system_acceptance",
        ),
        required_qualification_dispositions=ACCEPTED_BUILD_DISPOSITIONS,
        required_source_cleanliness=True,
        required_release_manifest=True,
        required_deployment_qualification_report=True,
        required_operational_pilot_evidence=True,
        minimum_provider_qualification_states=("FIXTURE_QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"),
        required_unresolved_limitation_classifications=("NONBLOCKING_LIMITATION",),
        environment_promotion_policy_ref=environment_promotion_policy_ref,
        change_window_policy_ref=change_window_policy_ref,
        rollback_policy_ref=rollback_policy_ref,
        approval_requirements=(
            "eligibility_assessment_ELIGIBLE",
            "full_system_acceptance_pass",
            "human_governed_approval",
            "environment_scope_explicit",
        ),
        release_expiry_policy_ref=release_expiry_policy_ref,
        revocation_conditions=(
            "critical_safety_defect",
            "artifact_integrity_violation",
            "security_vulnerability",
            "reconciliation_defect",
            "invalidated_qualification_evidence",
            "deployment_drift",
            "schema_corruption",
            "critical_broker_adapter_defect",
            "temporal_leakage_discovery",
        ),
        forbidden_authority_expansions=tuple(sorted(FORBIDDEN_AUTONOMY_EXPANSIONS)),
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return ProductionReleaseGovernancePolicyV1(
        release_governance_policy_id=derive_governance_policy_id(policy),
        schema_version=policy.schema_version,
        eligible_source_branches=policy.eligible_source_branches,
        required_build_evidence=policy.required_build_evidence,
        required_test_suites=policy.required_test_suites,
        required_qualification_dispositions=policy.required_qualification_dispositions,
        required_source_cleanliness=policy.required_source_cleanliness,
        required_release_manifest=policy.required_release_manifest,
        required_deployment_qualification_report=policy.required_deployment_qualification_report,
        required_operational_pilot_evidence=policy.required_operational_pilot_evidence,
        minimum_provider_qualification_states=policy.minimum_provider_qualification_states,
        required_unresolved_limitation_classifications=policy.required_unresolved_limitation_classifications,
        environment_promotion_policy_ref=policy.environment_promotion_policy_ref,
        change_window_policy_ref=policy.change_window_policy_ref,
        rollback_policy_ref=policy.rollback_policy_ref,
        approval_requirements=policy.approval_requirements,
        release_expiry_policy_ref=policy.release_expiry_policy_ref,
        revocation_conditions=policy.revocation_conditions,
        forbidden_authority_expansions=policy.forbidden_authority_expansions,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )
