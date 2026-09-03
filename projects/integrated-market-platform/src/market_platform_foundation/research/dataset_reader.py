"""Backward-compatible re-export; canonical module is storage.dataset_reader."""

from ..storage.dataset_reader import (
    READER_VERSION,
    DEFAULT_MAX_BYTES,
    DatasetProjectionResult,
    DatasetProjectionSpec,
    DatasetReadError,
    projection_identity,
    read_json_array_projection,
    read_jsonl_projection,
    read_jsonl_projection_bytes,
    serialize_rows_jsonl,
)

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DatasetProjectionResult",
    "DatasetProjectionSpec",
    "DatasetReadError",
    "READER_VERSION",
    "projection_identity",
    "read_json_array_projection",
    "read_jsonl_projection",
    "read_jsonl_projection_bytes",
    "serialize_rows_jsonl",
]
