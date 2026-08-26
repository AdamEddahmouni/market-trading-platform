"""Environment promotion policy (BUILD 35)."""

from __future__ import annotations

from .identity import derive_environment_promotion_policy_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    EnvironmentPromotionPolicyV1,
    PromotionEdgeResult,
    ReleaseApprovalStatus,
)

ENVIRONMENT_GRAPH: tuple[tuple[str, str], ...] = (
    ("TEST", "QUALIFICATION"),
    ("QUALIFICATION", "SUPERVISED_PILOT"),
    ("SUPERVISED_PILOT", "SUPERVISED_LIVE"),
)

REQUIRED_EVIDENCE_PER_EDGE: dict[str, tuple[str, ...]] = {
    "TEST->QUALIFICATION": ("release_integrity", "dependency_lock", "targeted_tests"),
    "QUALIFICATION->SUPERVISED_PILOT": (
        "full_regression",
        "deployment_canary",
        "rollback_qualification",
        "reliability_prerequisites",
    ),
    "SUPERVISED_PILOT->SUPERVISED_LIVE": (
        "BUILD33_pilot_evidence",
        "BUILD34_deployment_evidence",
        "BUILD35_release_approval",
    ),
}


def build_environment_promotion_policy() -> EnvironmentPromotionPolicyV1:
    policy = EnvironmentPromotionPolicyV1(
        environment_promotion_policy_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        environment_graph=ENVIRONMENT_GRAPH,
        required_evidence_per_edge=REQUIRED_EVIDENCE_PER_EDGE,
        artifact_identity_requirement="same_executable_artifact_hash_across_promotion",
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return EnvironmentPromotionPolicyV1(
        environment_promotion_policy_id=derive_environment_promotion_policy_id(policy),
        schema_version=policy.schema_version,
        environment_graph=policy.environment_graph,
        required_evidence_per_edge=policy.required_evidence_per_edge,
        artifact_identity_requirement=policy.artifact_identity_requirement,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )


def validate_promotion_edge(
    *,
    policy: EnvironmentPromotionPolicyV1,
    from_environment: str,
    to_environment: str,
    source_artifact_hash: str,
    target_artifact_hash: str,
    evidence_refs: tuple[str, ...],
    release_approval_status: str | None = None,
) -> tuple[str, list[str]]:
    edge = f"{from_environment}->{to_environment}"
    violations: list[str] = []

    valid_edges = {f"{a}->{b}" for a, b in policy.environment_graph}
    if edge not in valid_edges:
        # Check for skipped stages
        if from_environment == "TEST" and to_environment == "SUPERVISED_LIVE":
            violations.append("skipped required intermediate environments")
            return PromotionEdgeResult.BLOCKED.value, violations
        violations.append(f"invalid promotion edge {edge}")
        return PromotionEdgeResult.INVALID.value, violations

    if source_artifact_hash != target_artifact_hash:
        violations.append("artifact hash mismatch — rebuild per environment prohibited")
        return PromotionEdgeResult.BLOCKED.value, violations

    required = policy.required_evidence_per_edge.get(edge, ())
    for req in required:
        if req not in evidence_refs and not any(req.lower() in e.lower() for e in evidence_refs):
            violations.append(f"missing required evidence: {req}")

    if edge == "SUPERVISED_PILOT->SUPERVISED_LIVE":
        if release_approval_status != ReleaseApprovalStatus.APPROVED_SUPERVISED_OPERATION.value:
            violations.append("BUILD35 release approval required for SUPERVISED_LIVE promotion")
        if release_approval_status == ReleaseApprovalStatus.REVOKED.value:
            violations.append("revoked release cannot be promoted")
            return PromotionEdgeResult.BLOCKED.value, violations

    if violations:
        return PromotionEdgeResult.BLOCKED.value, violations
    return PromotionEdgeResult.PROMOTED.value, []
