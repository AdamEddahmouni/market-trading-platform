"""Offline raw-artifact integrity validation. Bytes are read, never modified."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .models import ArtifactValidationReport, IntakeManifest, RawArtifactDescriptor
from .semantics import ArtifactFormat, IntakeReasonCode, IntakeValidationStatus


def _artifact_path(root: Path, manifest: IntakeManifest) -> Path:
    return root.joinpath(*manifest.artifact_relative_path.split("/"))


def describe_raw_artifact(manifest: IntakeManifest) -> RawArtifactDescriptor:
    """Identity descriptor derived only from declared, relative-path metadata."""
    return RawArtifactDescriptor(
        bundle_id=manifest.bundle_id,
        artifact_id=f"{manifest.bundle_id}::raw",
        relative_path=manifest.artifact_relative_path,
        media_type=manifest.artifact_media_type,
        artifact_format=manifest.artifact_format,
        byte_length=manifest.artifact_byte_length,
        sha256=manifest.artifact_sha256,
    )


def validate_artifact_bytes(
    manifest: IntakeManifest, content: bytes | None
) -> ArtifactValidationReport:
    """Validate raw bytes (or absence) against the manifest byte length and SHA-256."""
    artifact_id = f"{manifest.bundle_id}::raw"
    reasons: list[IntakeReasonCode] = []

    if manifest.artifact_format is not ArtifactFormat.CSV:
        # Only CSV is normalized this batch; other declared formats are rejected here
        # so the workflow never silently accepts an unnormalizable artifact.
        reasons.append(IntakeReasonCode.UNSUPPORTED_FORMAT)

    if content is None:
        reasons.append(IntakeReasonCode.ARTIFACT_MISSING)
        return ArtifactValidationReport(
            bundle_id=manifest.bundle_id,
            artifact_id=artifact_id,
            status=IntakeValidationStatus.REJECTED,
            expected_byte_length=manifest.artifact_byte_length,
            actual_byte_length=None,
            expected_sha256=manifest.artifact_sha256,
            actual_sha256=None,
            reason_codes=tuple(reasons),
        )

    actual_length = len(content)
    actual_sha = hashlib.sha256(content).hexdigest()

    if actual_length == 0:
        reasons.append(IntakeReasonCode.ARTIFACT_EMPTY)
    if actual_length != manifest.artifact_byte_length:
        reasons.append(IntakeReasonCode.ARTIFACT_BYTE_LENGTH_MISMATCH)
    if actual_sha != manifest.artifact_sha256:
        reasons.append(IntakeReasonCode.ARTIFACT_SHA256_MISMATCH)

    status = (
        IntakeValidationStatus.ACCEPTED
        if not reasons
        else IntakeValidationStatus.REJECTED
    )
    return ArtifactValidationReport(
        bundle_id=manifest.bundle_id,
        artifact_id=artifact_id,
        status=status,
        expected_byte_length=manifest.artifact_byte_length,
        actual_byte_length=actual_length,
        expected_sha256=manifest.artifact_sha256,
        actual_sha256=actual_sha,
        reason_codes=tuple(reasons),
    )


def read_artifact_bytes(root: Path, manifest: IntakeManifest) -> bytes | None:
    path = _artifact_path(root, manifest)
    return path.read_bytes() if path.is_file() else None


def validate_raw_artifact(root: Path, manifest: IntakeManifest) -> ArtifactValidationReport:
    """Validate the on-disk artifact against the manifest's byte length and SHA-256."""
    return validate_artifact_bytes(manifest, read_artifact_bytes(root, manifest))


def inspect_artifact(root: Path, manifest: IntakeManifest) -> dict:
    """Non-identity operational view of the artifact for the inspect CLI.

    The absolute path is emitted only as an operational diagnostic and never
    enters any deterministic identity.
    """
    report = validate_raw_artifact(root, manifest)
    return {
        "bundle_id": manifest.bundle_id,
        "artifact_id": report.artifact_id,
        "relative_path": manifest.artifact_relative_path,
        "declared_media_type": manifest.artifact_media_type,
        "declared_format": manifest.artifact_format.value,
        "expected_byte_length": report.expected_byte_length,
        "actual_byte_length": report.actual_byte_length,
        "expected_sha256": report.expected_sha256,
        "actual_sha256": report.actual_sha256,
        "status": report.status.value,
        "reason_codes": tuple(code.value for code in report.reason_codes),
    }


__all__ = [
    "describe_raw_artifact",
    "validate_artifact_bytes",
    "validate_raw_artifact",
    "read_artifact_bytes",
    "inspect_artifact",
]
