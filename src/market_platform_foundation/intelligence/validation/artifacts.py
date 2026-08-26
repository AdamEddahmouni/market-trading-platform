"""Candidate artifact integrity checks (BUILD 19)."""

from __future__ import annotations

from pathlib import Path

from ..persistence.repository import IntelligenceRepository
from ..training.artifacts import verify_and_parse_logistic_artifact
from ..training.errors import TrainingFactoryError
from ..training.types import CandidateArtifactV1, TrainerKind
from .errors import ValidationError


def verify_candidate_artifact_hash(
    candidate: CandidateArtifactV1,
    artifact_bytes: bytes,
) -> None:
    from ..training.identity import artifact_content_hash

    actual = artifact_content_hash(artifact_bytes)
    if actual != candidate.artifact_hash:
        raise ValidationError(
            "INVALID_CANDIDATE_ARTIFACT_HASH",
            details={"expected": candidate.artifact_hash, "actual": actual},
        )


def verify_training_dataset_fingerprint(
    repository: IntelligenceRepository,
    candidate: CandidateArtifactV1,
) -> None:
    manifest = repository.get_training_dataset_manifest(candidate.training_dataset_id)
    if manifest is None:
        raise ValidationError("TRAINING_DATASET_MANIFEST_MISSING")
    if manifest.dataset_fingerprint != candidate.dataset_fingerprint:
        raise ValidationError(
            "DATASET_FINGERPRINT_MISMATCH",
            details={
                "candidate": candidate.dataset_fingerprint,
                "manifest": manifest.dataset_fingerprint,
            },
        )


def load_verified_logistic_artifact(
    candidate: CandidateArtifactV1,
    artifact_bytes: bytes,
) -> dict:
    verify_candidate_artifact_hash(candidate, artifact_bytes)
    try:
        return verify_and_parse_logistic_artifact(artifact_bytes, candidate.artifact_hash)
    except TrainingFactoryError as exc:
        raise ValidationError(exc.code, details=exc.details) from exc


def resolve_artifact_bytes(
    candidate: CandidateArtifactV1,
    *,
    artifact_bytes: bytes | None = None,
    artifact_base_dir: Path | None = None,
) -> bytes:
    if artifact_bytes is not None:
        return artifact_bytes
    if candidate.artifact_ref and artifact_base_dir is not None:
        path = Path(candidate.artifact_ref)
        if not path.is_absolute():
            path = artifact_base_dir / path
        if path.exists():
            return path.read_bytes()
    raise ValidationError("CANDIDATE_ARTIFACT_BYTES_UNAVAILABLE")


def verify_candidate_ready_for_validation(
    repository: IntelligenceRepository,
    candidate: CandidateArtifactV1,
    *,
    artifact_bytes: bytes | None = None,
    artifact_base_dir: Path | None = None,
) -> bytes:
    verify_training_dataset_fingerprint(repository, candidate)
    content = resolve_artifact_bytes(
        candidate, artifact_bytes=artifact_bytes, artifact_base_dir=artifact_base_dir
    )
    verify_candidate_artifact_hash(candidate, content)
    if candidate.candidate_kind == TrainerKind.LOGISTIC_REGRESSION:
        load_verified_logistic_artifact(candidate, content)
    return content


__all__ = [
    "load_verified_logistic_artifact",
    "resolve_artifact_bytes",
    "verify_candidate_artifact_hash",
    "verify_candidate_ready_for_validation",
    "verify_training_dataset_fingerprint",
]
