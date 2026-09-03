"""Deterministic training identity helpers (BUILD 18)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import ForecastTarget, forecast_target_to_dict
from .types import (
    CandidateArtifactV1,
    CandidateTrainingSpec,
    DistillationDatasetManifestV1,
    TrainingDatasetManifestV1,
    TrainingRunManifestV1,
)

DATASET_FINGERPRINT_VERSION = "training-dataset-sha256-v1"
CANDIDATE_SPEC_VERSION = "candidate-spec-sha256-v1"
CANDIDATE_ID_VERSION = "candidate-artifact-sha256-v1"
TRAINING_RUN_VERSION = "training-run-sha256-v1"
DISTILLATION_DATASET_VERSION = "distillation-dataset-sha256-v1"


def _sorted_hyperparameters(hyperparameters: dict[str, Any]) -> dict[str, Any]:
    return {key: hyperparameters[key] for key in sorted(hyperparameters)}


def derive_training_dataset_fingerprint(
    *,
    feature_schema_fingerprint: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    training_cutoff_ns: int,
    development_start_ns: int,
    development_end_ns: int,
    supervision_kind: str,
    examples: list[dict[str, Any]],
    quality_policy: tuple[str, ...] = (),
    teacher_identity: str | None = None,
    teacher_version: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": DATASET_FINGERPRINT_VERSION,
        "feature_schema_fingerprint": feature_schema_fingerprint,
        "target_kind": target_kind,
        "horizon_ns": horizon_ns,
        "mode": mode,
        "training_cutoff_ns": training_cutoff_ns,
        "development_start_ns": development_start_ns,
        "development_end_ns": development_end_ns,
        "supervision_kind": supervision_kind,
        "quality_policy": list(quality_policy),
        "examples": sorted(examples, key=lambda row: (row["decision_time_ns"], row["snapshot_id"])),
    }
    if teacher_identity is not None:
        payload["teacher_identity"] = teacher_identity
    if teacher_version is not None:
        payload["teacher_version"] = teacher_version
    return f"TRDS-{sha256_bytes(canonical_bytes(payload))}"


def derive_training_dataset_id(
    experiment_id: str,
    dataset_fingerprint: str,
) -> str:
    payload = {
        "experiment_id": experiment_id,
        "dataset_fingerprint": dataset_fingerprint,
    }
    return f"TRDM-{sha256_bytes(canonical_bytes(payload))}"


def derive_candidate_spec_id(
    *,
    experiment_id: str,
    dataset_fingerprint: str,
    trainer_kind: str,
    trainer_version: str,
    hyperparameters: dict[str, Any],
    seed: int,
    authorized_mutation_surface: tuple[str, ...],
) -> str:
    payload = {
        "identity_version": CANDIDATE_SPEC_VERSION,
        "experiment_id": experiment_id,
        "dataset_fingerprint": dataset_fingerprint,
        "trainer_kind": trainer_kind,
        "trainer_version": trainer_version,
        "hyperparameters": _sorted_hyperparameters(hyperparameters),
        "seed": seed,
        "authorized_mutation_surface": list(sorted(authorized_mutation_surface)),
    }
    return f"CSP-{sha256_bytes(canonical_bytes(payload))}"


def derive_training_run_id(
    *,
    candidate_spec_id: str,
    trainer_version: str,
) -> str:
    payload = {
        "identity_version": TRAINING_RUN_VERSION,
        "candidate_spec_id": candidate_spec_id,
        "trainer_version": trainer_version,
    }
    return f"TRN-{sha256_bytes(canonical_bytes(payload))}"


def derive_candidate_id(spec: CandidateTrainingSpec) -> str:
    payload = {
        "identity_version": CANDIDATE_ID_VERSION,
        "candidate_spec_id": spec.candidate_spec_id,
        "experiment_id": spec.experiment_id,
        "dataset_fingerprint": spec.dataset_fingerprint,
        "trainer_kind": spec.trainer_kind.value,
        "trainer_version": spec.trainer_version,
        "seed": spec.seed,
    }
    return f"CAND-{sha256_bytes(canonical_bytes(payload))}"


def derive_distillation_dataset_id(
    *,
    experiment_id: str,
    teacher_id: str,
    teacher_version: str,
    dataset_fingerprint: str,
) -> str:
    payload = {
        "identity_version": DISTILLATION_DATASET_VERSION,
        "experiment_id": experiment_id,
        "teacher_id": teacher_id,
        "teacher_version": teacher_version,
        "dataset_fingerprint": dataset_fingerprint,
    }
    return f"DSDM-{sha256_bytes(canonical_bytes(payload))}"


def artifact_content_hash(content: bytes) -> str:
    return sha256_bytes(content)


__all__ = [
    "CANDIDATE_ID_VERSION",
    "CANDIDATE_SPEC_VERSION",
    "DATASET_FINGERPRINT_VERSION",
    "DISTILLATION_DATASET_VERSION",
    "TRAINING_RUN_VERSION",
    "artifact_content_hash",
    "derive_candidate_id",
    "derive_candidate_spec_id",
    "derive_distillation_dataset_id",
    "derive_training_dataset_fingerprint",
    "derive_training_dataset_id",
    "derive_training_run_id",
]
