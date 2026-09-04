"""Deterministic release governance identities (BUILD 35)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    CanonicalAuthorityMapV1,
    ChangeImpactPolicyV1,
    ChangeWindowPolicyV1,
    EnvironmentPromotionPolicyV1,
    FullSystemOperationalAcceptanceReportV1,
    FullSystemOperationalAcceptanceSpecV1,
    ProductionReleaseApprovalV1,
    ProductionReleaseCandidateV1,
    ProductionReleaseEligibilityAssessmentV1,
    ProductionReleaseGovernancePolicyV1,
    ReleaseEvidenceBundleV1,
    ReleaseHistoryEventV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_governance_policy_id(policy: ProductionReleaseGovernancePolicyV1) -> str:
    payload = {
        "eligible_source_branches": list(policy.eligible_source_branches),
        "required_build_evidence": list(policy.required_build_evidence),
        "required_qualification_dispositions": dict(
            sorted((k, list(v)) for k, v in policy.required_qualification_dispositions.items())
        ),
        "forbidden_authority_expansions": list(policy.forbidden_authority_expansions),
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("RELGOV", payload)


def derive_evidence_bundle_id(bundle: ReleaseEvidenceBundleV1) -> str:
    payload = {
        "release_manifest_ref": bundle.release_manifest_ref,
        "build25_acceptance_ref": bundle.build25_acceptance_ref,
        "build26_forward_qualification_ref": bundle.build26_forward_qualification_ref,
        "build27_execution_qualification_ref": bundle.build27_execution_qualification_ref,
        "build28_live_safety_qualification_ref": bundle.build28_live_safety_qualification_ref,
        "build29_canary_evidence_ref": bundle.build29_canary_evidence_ref,
        "build30_supervised_operations_ref": bundle.build30_supervised_operations_ref,
        "build31_operator_qualification_ref": bundle.build31_operator_qualification_ref,
        "build32_reliability_qualification_ref": bundle.build32_reliability_qualification_ref,
        "build33_production_pilot_ref": bundle.build33_production_pilot_ref,
        "build34_deployment_qualification_ref": bundle.build34_deployment_qualification_ref,
        "source_hashes": dict(sorted(bundle.source_hashes.items())),
        "artifact_hashes": dict(sorted(bundle.artifact_hashes.items())),
        "implementation_version": bundle.implementation_version,
    }
    return _sha256_prefix("RELEV", payload)


def derive_release_candidate_id(candidate: ProductionReleaseCandidateV1) -> str:
    payload = {
        "release_manifest_ref": candidate.release_manifest_ref,
        "release_evidence_bundle_ref": candidate.release_evidence_bundle_ref,
        "release_governance_policy_ref": candidate.release_governance_policy_ref,
        "exact_source_sha": candidate.exact_source_sha,
        "artifact_hashes": dict(sorted(candidate.artifact_hashes.items())),
        "allowed_environment_kinds": list(candidate.allowed_environment_kinds),
        "implementation_version": candidate.implementation_version,
    }
    return _sha256_prefix("RELCAND", payload)


def derive_eligibility_assessment_id(assessment: ProductionReleaseEligibilityAssessmentV1) -> str:
    payload = {
        "candidate_ref": assessment.candidate_ref,
        "governance_policy_ref": assessment.governance_policy_ref,
        "evidence_bundle_ref": assessment.evidence_bundle_ref,
        "disposition": assessment.disposition,
        "blocking_reasons": list(assessment.blocking_reasons),
        "implementation_version": assessment.implementation_version,
    }
    return _sha256_prefix("RELIG", payload)


def derive_release_approval_id(approval: ProductionReleaseApprovalV1) -> str:
    payload = {
        "candidate_ref": approval.candidate_ref,
        "eligibility_assessment_ref": approval.eligibility_assessment_ref,
        "approved_environment_scope": list(approval.approved_environment_scope),
        "approval_status": approval.approval_status,
        "implementation_version": approval.implementation_version,
    }
    return _sha256_prefix("RELAPR", payload)


def derive_change_impact_policy_id(policy: ChangeImpactPolicyV1) -> str:
    payload = {
        "path_surface_classifications": dict(sorted(policy.path_surface_classifications.items())),
        "impact_domains": dict(sorted((k, list(v)) for k, v in policy.impact_domains.items())),
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("CHGIMP", payload)


def derive_change_window_policy_id(policy: ChangeWindowPolicyV1) -> str:
    payload = {
        "environment_scope": list(policy.environment_scope),
        "active_order_behavior": policy.active_order_behavior,
        "required_pre_change_reconciliation": policy.required_pre_change_reconciliation,
        "required_pre_change_backup": policy.required_pre_change_backup,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("CHGWND", payload)


def derive_environment_promotion_policy_id(policy: EnvironmentPromotionPolicyV1) -> str:
    payload = {
        "environment_graph": [list(e) for e in policy.environment_graph],
        "required_evidence_per_edge": dict(
            sorted((k, list(v)) for k, v in policy.required_evidence_per_edge.items())
        ),
        "artifact_identity_requirement": policy.artifact_identity_requirement,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("ENVPROM", payload)


def derive_history_event_id(event: ReleaseHistoryEventV1) -> str:
    payload = {
        "event_type": event.event_type,
        "event_time_ns": event.event_time_ns,
        "release_candidate_ref": event.release_candidate_ref,
        "release_approval_ref": event.release_approval_ref,
        "environment_kind": event.environment_kind,
        "implementation_version": event.implementation_version,
    }
    return _sha256_prefix("RELHIST", payload)


def derive_acceptance_spec_id(spec: FullSystemOperationalAcceptanceSpecV1) -> str:
    payload = {
        "required_build_range": list(spec.required_build_range),
        "required_domains": list(spec.required_domains),
        "blocking_requirement_ids": list(spec.blocking_requirement_ids),
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("FSASPEC", payload)


def derive_acceptance_report_id(report: FullSystemOperationalAcceptanceReportV1) -> str:
    payload = {
        "acceptance_spec_ref": report.acceptance_spec_ref,
        "release_candidate_ref": report.release_candidate_ref,
        "accepted_source_sha": report.accepted_source_sha,
        "final_disposition": report.final_disposition,
        "implementation_version": report.implementation_version,
    }
    return _sha256_prefix("FSAREP", payload)


def derive_authority_map_id(auth_map: CanonicalAuthorityMapV1) -> str:
    payload = {
        "entries": [
            {
                "decision_artifact": e.decision_artifact,
                "canonical_authority": e.canonical_authority,
                "authority_build": e.authority_build,
            }
            for e in auth_map.entries
        ],
        "forbidden_paths": [list(p) for p in auth_map.forbidden_paths],
        "implementation_version": auth_map.implementation_version,
    }
    return _sha256_prefix("AUTHMAP", payload)
