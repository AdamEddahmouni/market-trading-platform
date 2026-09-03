"""Production release candidate assembly (BUILD 35)."""

from __future__ import annotations

from .identity import derive_release_candidate_id
from .types import (
    BUILD35_KNOWN_LIMITATIONS,
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ProductionReleaseCandidateV1,
    ReleaseCandidateStatus,
)


def build_production_release_candidate(
    *,
    release_manifest_ref: str,
    release_evidence_bundle_ref: str,
    release_governance_policy_ref: str,
    exact_source_sha: str,
    artifact_hashes: dict[str, str],
    allowed_environment_kinds: tuple[str, ...] = (
        "TEST",
        "QUALIFICATION",
        "SUPERVISED_PILOT",
        "SUPERVISED_LIVE",
    ),
    candidate_status: str = ReleaseCandidateStatus.ASSEMBLED.value,
) -> ProductionReleaseCandidateV1:
    candidate = ProductionReleaseCandidateV1(
        production_release_candidate_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        release_manifest_ref=release_manifest_ref,
        release_evidence_bundle_ref=release_evidence_bundle_ref,
        release_governance_policy_ref=release_governance_policy_ref,
        exact_source_sha=exact_source_sha,
        artifact_hashes=artifact_hashes,
        configuration_schema_version="1",
        allowed_environment_kinds=allowed_environment_kinds,
        allowed_immutable_policy_refs=(
            "PILPOL-default",
            "SLO-default",
            "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED",
        ),
        current_champion_refs=(),
        known_limitations=BUILD35_KNOWN_LIMITATIONS,
        candidate_status=candidate_status,
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        lineage={"source_sha": exact_source_sha},
    )
    return ProductionReleaseCandidateV1(
        production_release_candidate_id=derive_release_candidate_id(candidate),
        schema_version=candidate.schema_version,
        release_manifest_ref=candidate.release_manifest_ref,
        release_evidence_bundle_ref=candidate.release_evidence_bundle_ref,
        release_governance_policy_ref=candidate.release_governance_policy_ref,
        exact_source_sha=candidate.exact_source_sha,
        artifact_hashes=candidate.artifact_hashes,
        configuration_schema_version=candidate.configuration_schema_version,
        allowed_environment_kinds=candidate.allowed_environment_kinds,
        allowed_immutable_policy_refs=candidate.allowed_immutable_policy_refs,
        current_champion_refs=candidate.current_champion_refs,
        known_limitations=candidate.known_limitations,
        candidate_status=candidate.candidate_status,
        implementation_version=candidate.implementation_version,
        lineage=candidate.lineage,
        metadata=candidate.metadata,
    )
