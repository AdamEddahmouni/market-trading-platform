"""Source attribution and provenance reference validation."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .commands import AttachProvenanceReference, AttachSourceAttribution, PreparedArtifactToken
from .errors import OF01Error, OF01ErrorCode
from .records import ArtifactRecord, ReferenceKind, SourceState

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\)")
_SECRET_MARKERS = ("password", "secret", "token", "api_key", "apikey", "credential")


def validate_stable_identity(value: str, *, field: str, max_len: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid stable identity for {field}",
            {"field": field},
        )
    if value != value.strip():
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"stable identity must not have leading/trailing whitespace for {field}",
            {"field": field},
        )
    if len(value) > max_len:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"stable identity too long for {field}",
            {"field": field, "max_len": max_len},
        )
    if _CONTROL_RE.search(value):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"control characters prohibited in {field}",
            {"field": field},
        )
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                f"secret-like content prohibited in {field}",
                {"field": field},
            )
    if _ABSOLUTE_PATH_RE.match(value):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"absolute filesystem path prohibited in {field}",
            {"field": field},
        )
    return value


def normalize_repository_identity(value: str) -> str:
    return validate_stable_identity(value, field="repository_identity")


def normalize_root_identity(value: str) -> str:
    return validate_stable_identity(value, field="root_identity")


def _validate_artifact_token(
    artifact: ArtifactRecord,
    tokens: Mapping[str, PreparedArtifactToken],
) -> None:
    token = tokens.get(artifact.artifact_id)
    if token is None:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "missing prepared artifact token",
            {"artifact_id": artifact.artifact_id},
        )
    if token.content_hash != artifact.content_hash or token.byte_size != artifact.byte_size:
        raise OF01Error(
            OF01ErrorCode.CAS_HASH_MISMATCH,
            "artifact token does not match record metadata",
            {"artifact_id": artifact.artifact_id},
        )


def validate_attach_source_attribution(
    command: AttachSourceAttribution,
    prepared_artifacts: Mapping[str, PreparedArtifactToken],
) -> None:
    source = command.source_attribution
    normalize_repository_identity(source.repository_identity)
    normalize_root_identity(source.root_identity)
    if source.source_state == SourceState.DIRTY_ATTRIBUTABLE:
        if source.capsule_artifact_id is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "DIRTY_ATTRIBUTABLE requires capsule_artifact_id",
                {},
            )
        if not command.capsule_artifacts:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "DIRTY_ATTRIBUTABLE requires co-committed capsule artifact",
                {},
            )
        for artifact in command.capsule_artifacts:
            _validate_artifact_token(artifact, prepared_artifacts)
    if source.source_state == SourceState.UNATTRIBUTABLE:
        if source.outside_scope_proof_artifact_id is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "UNATTRIBUTABLE requires outside_scope_proof_artifact_id",
                {},
            )
        if not command.proof_artifacts:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "UNATTRIBUTABLE requires co-committed proof artifact",
                {},
            )
        for artifact in command.proof_artifacts:
            _validate_artifact_token(artifact, prepared_artifacts)
    if source.scope_manifest_artifact_id is not None and not command.scope_manifest_artifacts:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "scope manifest artifact must be co-committed when referenced",
            {},
        )
    for artifact in command.scope_manifest_artifacts:
        _validate_artifact_token(artifact, prepared_artifacts)


def validate_attach_provenance_reference(command: AttachProvenanceReference) -> None:
    ref = command.provenance_reference
    validate_stable_identity(ref.canonical_identity, field="canonical_identity")
    if ref.reference_kind not in ReferenceKind:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "invalid provenance reference kind",
            {"reference_kind": ref.reference_kind},
        )
    if ref.coverage_start_ns is not None and ref.coverage_end_ns is not None:
        if ref.coverage_end_ns < ref.coverage_start_ns:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "coverage_end_ns must be >= coverage_start_ns",
                {},
            )
