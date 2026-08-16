"""Research dataset, model, and evaluation infrastructure."""

from .baseline_naive import NaiveLastValueModel, MODEL_FAMILY, MODEL_INTERFACE_VERSION
from .dataset_manifest import build_dataset_manifest, dataset_fingerprint, materialize_dataset_rows
from .evaluation import run_walk_forward_evaluation, evaluation_root_hash
from .forecast import ForecastResult, build_forecast
from .model_spec import build_model_identity, model_artifact_hash
from .serialization import load_artifact, serialize_artifact
from .targets import build_target_rows, verify_label_availability
from .walk_forward import build_walk_forward_folds, verify_fold_pit

__all__ = [
    "ForecastResult",
    "MODEL_FAMILY",
    "MODEL_INTERFACE_VERSION",
    "NaiveLastValueModel",
    "build_dataset_manifest",
    "build_forecast",
    "build_model_identity",
    "build_target_rows",
    "build_walk_forward_folds",
    "dataset_fingerprint",
    "evaluation_root_hash",
    "load_artifact",
    "materialize_dataset_rows",
    "model_artifact_hash",
    "run_walk_forward_evaluation",
    "serialize_artifact",
    "verify_fold_pit",
    "verify_label_availability",
]
