"""Phase 5R dataset materialization, projection, and manifest binding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..canonical import sha256_bytes
from ..storage.projection_cache import ProjectionDiskCache
from ..storage.bounded_memory_cache import ProjectionMemoryCache
from .dataset_manifest import DATASET_SCHEMA_VERSION, build_dataset_manifest, materialize_dataset_rows
from ..storage.dataset_reader import (
    DatasetProjectionResult,
    DatasetProjectionSpec,
    projection_identity,
    read_jsonl_projection,
    read_jsonl_projection_bytes,
    serialize_rows_jsonl,
)

RESEARCH_ROW_COLUMNS: tuple[str, ...] = (
    "available_time",
    "capability",
    "feature_id",
    "instrument_id",
    "prediction_cutoff",
    "value",
)

RESEARCH_ROW_SPEC = DatasetProjectionSpec(
    columns=RESEARCH_ROW_COLUMNS,
    schema_version=DATASET_SCHEMA_VERSION,
)

DEFAULT_MEMBER_FILENAME = "research-rows.jsonl"


def rows_to_jsonl_bytes(rows: list[dict[str, object]]) -> bytes:
    return serialize_rows_jsonl(rows)


def build_manifest_from_projection(
    result: DatasetProjectionResult,
    spec: DatasetProjectionSpec,
    *,
    member_filename: str = DEFAULT_MEMBER_FILENAME,
) -> dict[str, object]:
    """Bind projected rows to an immutable manifest per ADR-RDATA-001."""
    manifest = build_dataset_manifest(result.rows, member_filename=member_filename)
    manifest["projection_identity"] = projection_identity(spec, result.content_hash)
    manifest["source_content_hash"] = result.content_hash
    manifest["projected_columns"] = list(result.projected_columns)
    return manifest


def project_research_rows_jsonl(
    source_bytes: bytes,
    *,
    spec: DatasetProjectionSpec = RESEARCH_ROW_SPEC,
) -> DatasetProjectionResult:
    content_hash = sha256_bytes(source_bytes)
    return read_jsonl_projection_bytes(
        source_bytes,
        spec,
        expected_content_hash=content_hash,
    )


def build_research_dataset_from_events(
    events: list[dict[str, Any]],
    *,
    cache: ProjectionDiskCache | None = None,
    memory_cache: ProjectionMemoryCache | None = None,
    member_filename: str = DEFAULT_MEMBER_FILENAME,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Materialize events, project through bounded reader, return rows and manifest."""
    materialized = materialize_dataset_rows(events)
    source_bytes = rows_to_jsonl_bytes(materialized)
    if memory_cache is not None:
        result = memory_cache.get_or_project(source_bytes, RESEARCH_ROW_SPEC)
    elif cache is not None:
        result = cache.get_or_project(source_bytes, RESEARCH_ROW_SPEC)
    else:
        result = project_research_rows_jsonl(source_bytes)
    manifest = build_manifest_from_projection(
        result,
        RESEARCH_ROW_SPEC,
        member_filename=member_filename,
    )
    return result.rows, manifest


def load_research_dataset_from_jsonl(
    path: Path,
    *,
    cache: ProjectionDiskCache | None = None,
    spec: DatasetProjectionSpec = RESEARCH_ROW_SPEC,
    member_filename: str = DEFAULT_MEMBER_FILENAME,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Load admitted fixture JSONL through projection reader and build manifest."""
    source_bytes = path.read_bytes()
    if cache is not None:
        result = cache.get_or_project(source_bytes, spec)
    else:
        content_hash = sha256_bytes(source_bytes)
        result = read_jsonl_projection(path, spec, expected_content_hash=content_hash)
    manifest = build_manifest_from_projection(result, spec, member_filename=member_filename)
    return result.rows, manifest
