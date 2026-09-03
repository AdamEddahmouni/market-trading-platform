"""Training and distillation factory (BUILD 18)."""

from .errors import TrainingFactoryError
from .factory import TrainingFactory
from .identity import (
    derive_candidate_id,
    derive_candidate_spec_id,
    derive_training_dataset_fingerprint,
    derive_training_run_id,
)
from .serialization import (
    candidate_artifact_v1_from_dict,
    candidate_artifact_v1_to_dict,
    training_dataset_manifest_v1_from_dict,
    training_dataset_manifest_v1_to_dict,
    training_run_manifest_v1_from_dict,
    training_run_manifest_v1_to_dict,
)
from .types import (
    TRAINING_IMPLEMENTATION_VERSION,
    CandidateArtifactV1,
    CandidateStatus,
    CandidateTrainingSpec,
    TrainerKind,
    TrainingDatasetManifestV1,
    TrainingFactoryResult,
    TrainingRunManifestV1,
    TrainingRunStatus,
)

__all__ = [
    "TRAINING_IMPLEMENTATION_VERSION",
    "CandidateArtifactV1",
    "CandidateStatus",
    "CandidateTrainingSpec",
    "TrainerKind",
    "TrainingDatasetManifestV1",
    "TrainingFactory",
    "TrainingFactoryError",
    "TrainingFactoryResult",
    "TrainingRunManifestV1",
    "TrainingRunStatus",
    "candidate_artifact_v1_from_dict",
    "candidate_artifact_v1_to_dict",
    "derive_candidate_id",
    "derive_candidate_spec_id",
    "derive_training_dataset_fingerprint",
    "derive_training_run_id",
    "training_dataset_manifest_v1_from_dict",
    "training_dataset_manifest_v1_to_dict",
    "training_run_manifest_v1_from_dict",
    "training_run_manifest_v1_to_dict",
]
