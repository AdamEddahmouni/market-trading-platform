"""Environment promotion (BUILD 34)."""

from __future__ import annotations

from .identity import derive_promotion_record_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    EnvironmentKind,
    PromotionRecordV1,
    PromotionResult,
    ReleaseManifestV1,
)


def promote_release(
    *,
    release: ReleaseManifestV1,
    from_environment: str,
    to_environment: str,
    artifact_hash: str,
    qualification_refs: tuple[str, ...],
    promotion_time_ns: int,
    config_compatible: bool = True,
) -> PromotionRecordV1:
    if from_environment == to_environment:
        result = PromotionResult.INVALID.value
    elif not config_compatible:
        result = PromotionResult.BLOCKED.value
    else:
        result = PromotionResult.PROMOTED.value

    record = PromotionRecordV1(
        promotion_record_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        release_manifest_ref=release.release_manifest_id,
        from_environment=from_environment,
        to_environment=to_environment,
        qualification_evidence_refs=qualification_refs,
        configuration_compatibility_result="COMPATIBLE" if config_compatible else "INCOMPATIBLE",
        required_approvals=("operator", "release-owner"),
        promotion_time_ns=promotion_time_ns,
        result=result,
        artifact_hash=artifact_hash,
        lineage={
            "source_commit_sha": release.source_commit_sha,
            "same_artifact_promoted": True,
        },
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return PromotionRecordV1(
        promotion_record_id=derive_promotion_record_id(record),
        schema_version=record.schema_version,
        release_manifest_ref=record.release_manifest_ref,
        from_environment=record.from_environment,
        to_environment=record.to_environment,
        qualification_evidence_refs=record.qualification_evidence_refs,
        configuration_compatibility_result=record.configuration_compatibility_result,
        required_approvals=record.required_approvals,
        promotion_time_ns=record.promotion_time_ns,
        result=record.result,
        artifact_hash=record.artifact_hash,
        lineage=record.lineage,
        implementation_version=record.implementation_version,
    )


def validate_promotion_gates(
    *,
    release: ReleaseManifestV1,
    to_environment: str,
    build33_ref: str,
    artifact_hash: str,
    source_artifact_hash: str,
) -> tuple[bool, tuple[str, ...]]:
    violations: list[str] = []
    try:
        EnvironmentKind(to_environment)
    except ValueError:
        violations.append(f"unknown target environment: {to_environment}")
    if build33_ref not in release.required_build_qualification_refs:
        violations.append("BUILD33 qualification ref missing from release")
    if artifact_hash != source_artifact_hash:
        violations.append("artifact hash changed during promotion — rebuild detected")
    if not release.release_manifest_id.startswith("REL-"):
        violations.append("invalid release ID format")
    return len(violations) == 0, tuple(violations)


def floating_latest_prohibited(release_ref: str) -> bool:
    prohibited = ("latest", "head", "main", "master", "*")
    return release_ref.lower() in prohibited or release_ref.endswith("*")
