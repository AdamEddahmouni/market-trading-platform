"""Production release eligibility assessment (BUILD 35)."""

from __future__ import annotations

from market_platform_foundation.intelligence.live_canary.deployment.source_provenance import (
    dirty_tree_blocks_release,
    is_source_tree_clean,
)

from .evidence import DEFAULT_DISPOSITIONS, load_build_dispositions_from_artifacts, verify_evidence_lineage
from .identity import derive_eligibility_assessment_id
from .policy import ACCEPTED_BUILD_DISPOSITIONS, BLOCKING_BUILD_DISPOSITIONS
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    EligibilityDisposition,
    EligibilityReasonV1,
    ProductionReleaseCandidateV1,
    ProductionReleaseEligibilityAssessmentV1,
    ProductionReleaseGovernancePolicyV1,
    ReleaseEvidenceBundleV1,
)


def assess_release_eligibility(
    *,
    policy: ProductionReleaseGovernancePolicyV1,
    candidate: ProductionReleaseCandidateV1,
    evidence_bundle: ReleaseEvidenceBundleV1,
    source_clean: bool | None = None,
) -> ProductionReleaseEligibilityAssessmentV1:
    reasons: list[EligibilityReasonV1] = []
    blocking: list[str] = []
    missing: list[str] = []
    incompatible: list[str] = []
    limitations: list[str] = []

    if source_clean is None:
        source_clean = is_source_tree_clean()

    if policy.required_source_cleanliness and not source_clean:
        blocked, reason = dirty_tree_blocks_release()
        blocking.append("DIRTY_SOURCE")
        reasons.append(
            EligibilityReasonV1(
                reason_code="DIRTY_SOURCE",
                description=reason or "source tree is not clean",
                blocking=True,
            )
        )

    dispositions = load_build_dispositions_from_artifacts()
    for build in policy.required_build_evidence:
        disp = dispositions.get(build)
        if not disp:
            missing.append(build)
            blocking.append(f"MISSING_EVIDENCE_{build}")
            reasons.append(
                EligibilityReasonV1(
                    reason_code=f"MISSING_EVIDENCE_{build}",
                    description=f"No qualification disposition for {build}",
                    blocking=True,
                )
            )
            continue
        accepted = policy.required_qualification_dispositions.get(build, ())
        if disp not in accepted:
            blocking.append(f"INVALID_DISPOSITION_{build}")
            reasons.append(
                EligibilityReasonV1(
                    reason_code=f"INVALID_DISPOSITION_{build}",
                    description=f"{build} disposition {disp} not in accepted {accepted}",
                    blocking=True,
                )
            )
        blocking_disps = BLOCKING_BUILD_DISPOSITIONS.get(build, ())
        if disp in blocking_disps:
            blocking.append(f"BLOCKING_DISPOSITION_{build}")
            reasons.append(
                EligibilityReasonV1(
                    reason_code=f"BLOCKING_DISPOSITION_{build}",
                    description=f"{build} disposition {disp} is blocking",
                    blocking=True,
                )
            )
        # Nonblocking limitations
        if build == "BUILD26" and disp == "INSUFFICIENT_FORWARD_EVIDENCE":
            limitations.append("BUILD26: insufficient forward evidence — nonblocking")
        if build == "BUILD29" and disp == "CANARY_NOT_EXECUTED":
            limitations.append("BUILD29: canary not executed — nonblocking for supervised operation with limitations")

    lineage_ok, lineage_violations = verify_evidence_lineage(
        {
            "BUILD25": evidence_bundle.build25_acceptance_ref,
            "BUILD34": evidence_bundle.build34_deployment_qualification_ref,
        },
        release_source_sha=candidate.exact_source_sha,
    )
    if not lineage_ok:
        for v in lineage_violations:
            incompatible.append(v)
            blocking.append("INCOMPATIBLE_EVIDENCE_LINEAGE")
            reasons.append(
                EligibilityReasonV1(
                    reason_code="INCOMPATIBLE_EVIDENCE_LINEAGE",
                    description=v,
                    blocking=True,
                )
            )

    if evidence_bundle.release_manifest_ref != candidate.release_manifest_ref:
        blocking.append("MANIFEST_REF_MISMATCH")
        incompatible.append("evidence bundle release manifest ref does not match candidate")
        reasons.append(
            EligibilityReasonV1(
                reason_code="MANIFEST_REF_MISMATCH",
                description="evidence bundle and candidate release manifest refs differ",
                blocking=True,
            )
        )

    if evidence_bundle.artifact_hashes != candidate.artifact_hashes:
        blocking.append("ARTIFACT_HASH_MISMATCH")
        incompatible.append("evidence bundle artifact hashes do not match candidate")
        reasons.append(
            EligibilityReasonV1(
                reason_code="ARTIFACT_HASH_MISMATCH",
                description="artifact hash mismatch between evidence bundle and candidate",
                blocking=True,
            )
        )

    if blocking:
        disposition = EligibilityDisposition.INELIGIBLE.value
    elif limitations:
        disposition = EligibilityDisposition.ELIGIBLE.value
    else:
        disposition = EligibilityDisposition.ELIGIBLE.value

    assessment = ProductionReleaseEligibilityAssessmentV1(
        eligibility_assessment_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        candidate_ref=candidate.production_release_candidate_id,
        governance_policy_ref=policy.release_governance_policy_id,
        evidence_bundle_ref=evidence_bundle.release_evidence_bundle_id,
        disposition=disposition,
        reasons=tuple(reasons),
        blocking_reasons=tuple(blocking),
        missing_evidence=tuple(missing),
        incompatible_evidence=tuple(incompatible),
        limitations=tuple(limitations),
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return ProductionReleaseEligibilityAssessmentV1(
        eligibility_assessment_id=derive_eligibility_assessment_id(assessment),
        schema_version=assessment.schema_version,
        candidate_ref=assessment.candidate_ref,
        governance_policy_ref=assessment.governance_policy_ref,
        evidence_bundle_ref=assessment.evidence_bundle_ref,
        disposition=assessment.disposition,
        reasons=assessment.reasons,
        blocking_reasons=assessment.blocking_reasons,
        missing_evidence=assessment.missing_evidence,
        incompatible_evidence=assessment.incompatible_evidence,
        limitations=assessment.limitations,
        implementation_version=assessment.implementation_version,
        metadata=assessment.metadata,
    )


def release_approval_creates_live_authority() -> bool:
    """Release approval never creates live execution authority."""
    return False
