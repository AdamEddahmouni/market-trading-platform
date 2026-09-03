"""Research dataset, model, and evaluation infrastructure."""

from .baseline_naive import NaiveLastValueModel, MODEL_FAMILY, MODEL_INTERFACE_VERSION
from .dataset_manifest import build_dataset_manifest, dataset_fingerprint, materialize_dataset_rows
from .dataset_pipeline import (
    build_manifest_from_projection,
    build_research_dataset_from_events,
    load_research_dataset_from_jsonl,
    project_research_rows_jsonl,
    RESEARCH_ROW_SPEC,
)
from .dataset_reader import (
    DatasetProjectionSpec,
    DatasetProjectionResult,
    DatasetReadError,
    projection_identity,
    read_json_array_projection,
    read_jsonl_projection,
    read_jsonl_projection_bytes,
    serialize_rows_jsonl,
    READER_VERSION,
)
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
    "DatasetProjectionResult",
    "DatasetProjectionSpec",
    "DatasetReadError",
    "READER_VERSION",
    "RESEARCH_ROW_SPEC",
    "build_dataset_manifest",
    "build_manifest_from_projection",
    "build_research_dataset_from_events",
    "build_forecast",
    "build_model_identity",
    "build_target_rows",
    "build_walk_forward_folds",
    "dataset_fingerprint",
    "evaluation_root_hash",
    "load_artifact",
    "load_research_dataset_from_jsonl",
    "materialize_dataset_rows",
    "model_artifact_hash",
    "projection_identity",
    "project_research_rows_jsonl",
    "read_json_array_projection",
    "read_jsonl_projection",
    "read_jsonl_projection_bytes",
    "run_walk_forward_evaluation",
    "serialize_rows_jsonl",
    "serialize_artifact",
    "verify_fold_pit",
    "verify_label_availability",
]
