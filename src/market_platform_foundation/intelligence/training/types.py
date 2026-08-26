"""Training factory contracts (BUILD 18)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

TRAINING_IMPLEMENTATION_VERSION = "training-distillation-factory-v1"


class CandidateStatus(StrEnum):
    DEVELOPMENT_CANDIDATE = "DEVELOPMENT_CANDIDATE"
    UNVALIDATED = "UNVALIDATED"


class TrainingRunStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TRAINER_UNAVAILABLE = "TRAINER_UNAVAILABLE"
    VALIDATION_BLOCKED_PENDING_BUILD19 = "VALIDATION_BLOCKED_PENDING_BUILD19"


class TrainerKind(StrEnum):
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    GRADIENT_BOOSTING = "GRADIENT_BOOSTING"
    DISTILLATION_LOGISTIC = "DISTILLATION_LOGISTIC"
    LORA_ADAPTER = "LORA_ADAPTER"


class SupervisionKind(StrEnum):
    OUTCOME_LABEL = "OUTCOME_LABEL"
    TEACHER_TARGET = "TEACHER_TARGET"


class DistillationTargetKind(StrEnum):
    TEACHER_PROBABILITIES = "TEACHER_PROBABILITIES"
    TEACHER_CLASSIFICATION_BEHAVIOR = "TEACHER_CLASSIFICATION_BEHAVIOR"
    TEACHER_STRUCTURED_EVIDENCE = "TEACHER_STRUCTURED_EVIDENCE"


class TrainingDatasetMode(StrEnum):
    SUPERVISED = "SUPERVISED"
    DISTILLATION = "DISTILLATION"


@dataclass(frozen=True, slots=True)
class TrainingExampleRef:
    snapshot_id: str
    decision_time_ns: int
    outcome_id: str | None = None
    forecast_id: str | None = None
    teacher_output_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("SNAPSHOT_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class TrainingDatasetManifestV1:
    training_dataset_id: str
    schema_version: str
    experiment_id: str
    development_start_ns: int
    development_end_ns: int
    training_cutoff_ns: int
    target_kind: str
    horizon_ns: int
    mode: str
    feature_schema_fingerprint: str
    example_count: int
    example_refs: tuple[TrainingExampleRef, ...]
    dataset_fingerprint: str
    supervision_kind: SupervisionKind
    dataset_mode: TrainingDatasetMode = TrainingDatasetMode.SUPERVISED
    scenario_id: str | None = None
    quality_policy: tuple[str, ...] = ()
    source_artifact_refs: tuple[str, ...] = ()
    builder_version: str = TRAINING_IMPLEMENTATION_VERSION
    holdout_boundary_ns: int | None = None
    teacher_identity: str | None = None
    teacher_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.training_dataset_id or not self.experiment_id:
            raise ValueError("TRAINING_DATASET_FIELDS_INCOMPLETE")
        if self.development_start_ns >= self.development_end_ns:
            raise ValueError("DEVELOPMENT_RANGE_INVALID")
        if self.example_count < 0:
            raise ValueError("EXAMPLE_COUNT_INVALID")


@dataclass(frozen=True, slots=True)
class CandidateTrainingSpec:
    candidate_spec_id: str
    experiment_id: str
    training_dataset_id: str
    dataset_fingerprint: str
    trainer_kind: TrainerKind
    hyperparameters: dict[str, Any]
    seed: int
    authorized_mutation_surface: tuple[str, ...]
    trainer_version: str = TRAINING_IMPLEMENTATION_VERSION
    target_kind: str = ""
    horizon_ns: int = 0
    mode: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_spec_id:
            raise ValueError("CANDIDATE_SPEC_ID_REQUIRED")
        if not isinstance(self.hyperparameters, dict):
            raise ValueError("HYPERPARAMETERS_INVALID")


@dataclass(frozen=True, slots=True)
class TrainingDiagnostics:
    example_count: int
    up_count: int = 0
    down_count: int = 0
    training_loss: float | None = None
    teacher_target_loss: float | None = None
    convergence_status: str | None = None
    iterations: int | None = None
    parameter_norm: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.example_count < 0:
            raise ValueError("EXAMPLE_COUNT_INVALID")


@dataclass(frozen=True, slots=True)
class TrainingRunManifestV1:
    training_run_id: str
    schema_version: str
    experiment_id: str
    candidate_spec_id: str
    training_dataset_id: str
    dataset_fingerprint: str
    trainer_kind: TrainerKind
    trainer_version: str
    hyperparameters: dict[str, Any]
    seed: int
    status: TrainingRunStatus
    candidate_id: str | None = None
    diagnostics: TrainingDiagnostics | None = None
    software_lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.training_run_id:
            raise ValueError("TRAINING_RUN_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class CandidateArtifactV1:
    candidate_id: str
    schema_version: str
    experiment_id: str
    training_run_id: str
    candidate_spec_id: str
    training_dataset_id: str
    dataset_fingerprint: str
    candidate_kind: TrainerKind
    model_family: str
    artifact_format: str
    artifact_hash: str
    parameter_fingerprint: str
    trainer_version: str
    target_kind: str
    horizon_ns: int
    input_schema_fingerprint: str
    seed: int
    status: CandidateStatus
    supervision_kind: SupervisionKind
    artifact_ref: str | None = None
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("CANDIDATE_ID_REQUIRED")
        if self.status not in (CandidateStatus.DEVELOPMENT_CANDIDATE, CandidateStatus.UNVALIDATED):
            raise ValueError("CANDIDATE_STATUS_INVALID")


@dataclass(frozen=True, slots=True)
class TeacherOutputV1:
    teacher_id: str
    teacher_version: str
    input_ref: str
    target_kind: DistillationTargetKind
    output: dict[str, Any]
    availability_time_ns: int
    provenance: str = "TEACHER"

    def __post_init__(self) -> None:
        if not self.teacher_id or not self.teacher_version:
            raise ValueError("TEACHER_IDENTITY_REQUIRED")
        if not self.input_ref:
            raise ValueError("TEACHER_INPUT_REF_REQUIRED")
        if self.provenance != "TEACHER":
            raise ValueError("TEACHER_PROVENANCE_INVALID")


@dataclass(frozen=True, slots=True)
class DistillationDatasetManifestV1:
    distillation_dataset_id: str
    schema_version: str
    experiment_id: str
    training_dataset_id: str
    teacher_id: str
    teacher_version: str
    target_kind: DistillationTargetKind
    example_count: int
    dataset_fingerprint: str
    teacher_output_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.distillation_dataset_id:
            raise ValueError("DISTILLATION_DATASET_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class CandidateTrainingResult:
    run: TrainingRunManifestV1
    candidate: CandidateArtifactV1 | None
    artifact_bytes: bytes | None = None


@dataclass(frozen=True, slots=True)
class PreparedTrainingDataset:
    """In-memory dataset bound to a manifest for trainer consumption."""

    manifest: TrainingDatasetManifestV1
    baseline_dataset: Any  # BaselineTrainingDataset — avoid circular import in type hint
    distillation_targets: dict[str, float] | None = None


@dataclass(frozen=True, slots=True)
class TrainingFactoryResult:
    experiment_id: str
    dataset_manifest: TrainingDatasetManifestV1
    candidates: tuple[CandidateArtifactV1, ...]
    runs: tuple[TrainingRunManifestV1, ...]
    distillation_manifest: DistillationDatasetManifestV1 | None = None


__all__ = [
    "TRAINING_IMPLEMENTATION_VERSION",
    "CandidateArtifactV1",
    "CandidateStatus",
    "CandidateTrainingResult",
    "CandidateTrainingSpec",
    "DistillationDatasetManifestV1",
    "DistillationTargetKind",
    "PreparedTrainingDataset",
    "SupervisionKind",
    "TeacherOutputV1",
    "TrainerKind",
    "TrainingDatasetManifestV1",
    "TrainingDatasetMode",
    "TrainingDiagnostics",
    "TrainingFactoryResult",
    "TrainingRunManifestV1",
    "TrainingRunStatus",
    "TrainingExampleRef",
]
