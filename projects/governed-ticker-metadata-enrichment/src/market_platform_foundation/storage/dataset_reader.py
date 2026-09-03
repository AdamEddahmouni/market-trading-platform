"""Bounded tabular dataset projection reader (GridIQ parquet pattern, stdlib JSON/JSONL)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, load_json_strict, sha256_bytes
from ..contracts.schema_compat import compatible_reader

READER_VERSION = "1.0.0"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class DatasetProjectionSpec:
    """Column projection and schema policy for immutable dataset members."""

    columns: tuple[str, ...]
    schema_version: str
    optional_columns: frozenset[str] = frozenset()
    max_bytes: int = DEFAULT_MAX_BYTES
    missing_optional_value: object = None
    reader_version: str = READER_VERSION


@dataclass
class DatasetProjectionResult:
    rows: list[dict[str, object]] = field(default_factory=list)
    content_hash: str = ""
    projected_columns: tuple[str, ...] = ()
    row_count: int = 0
    reason_codes: list[str] = field(default_factory=list)


class DatasetReadError(ValueError):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


def _verify_schema_version(spec: DatasetProjectionSpec) -> None:
    if not compatible_reader(spec.schema_version, spec.reader_version):
        raise DatasetReadError(
            "SCHEMA_VERSION_INCOMPATIBLE",
            f"reader={spec.reader_version} schema={spec.schema_version}",
        )


def _read_bounded_bytes(path: Path, max_bytes: int) -> bytes:
    if not path.is_file():
        raise DatasetReadError("DATASET_SOURCE_MISSING", str(path))
    size = path.stat().st_size
    if size > max_bytes:
        raise DatasetReadError("DATASET_BYTE_LIMIT_EXCEEDED", f"{size}>{max_bytes}")
    return path.read_bytes()


def _verify_content_hash(data: bytes, expected_hash: str | None) -> str:
    observed = sha256_bytes(data)
    if expected_hash and observed != expected_hash.upper():
        raise DatasetReadError("DATASET_HASH_MISMATCH", f"expected={expected_hash}")
    return observed


def _project_row(
    record: dict[str, Any],
    spec: DatasetProjectionSpec,
    *,
    line_number: int,
) -> dict[str, object]:
    unknown_keys = set(record.keys()) - set(spec.columns) - spec.optional_columns
    if unknown_keys:
        raise DatasetReadError(
            "SCHEMA_DRIFT_UNKNOWN_COLUMN",
            f"line={line_number} keys={sorted(unknown_keys)}",
        )
    projected: dict[str, object] = {}
    for column in spec.columns:
        if column in record:
            projected[column] = record[column]
        elif column in spec.optional_columns:
            projected[column] = spec.missing_optional_value
        else:
            raise DatasetReadError(
                "SCHEMA_MISSING_REQUIRED_COLUMN",
                f"line={line_number} column={column}",
            )
    return projected


def read_jsonl_projection_bytes(
    data: bytes,
    spec: DatasetProjectionSpec,
    *,
    expected_content_hash: str | None = None,
) -> DatasetProjectionResult:
    """Read JSONL from memory with byte bounds, hash identity, and column projection."""
    _verify_schema_version(spec)
    if len(data) > spec.max_bytes:
        raise DatasetReadError("DATASET_BYTE_LIMIT_EXCEEDED", f"{len(data)}>{spec.max_bytes}")
    content_hash = _verify_content_hash(data, expected_content_hash)
    rows: list[dict[str, object]] = []
    offset = 0
    line_number = 0
    for raw_line in data.splitlines():
        offset += len(raw_line) + 1
        if offset > spec.max_bytes:
            raise DatasetReadError("DATASET_BYTE_LIMIT_EXCEEDED", f"offset={offset}")
        stripped = raw_line.strip()
        if not stripped:
            continue
        line_number += 1
        import json

        from ..canonical import _pairs_no_duplicates

        record = json.loads(stripped.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        if not isinstance(record, dict):
            raise DatasetReadError("DATASET_ROW_NOT_OBJECT", f"line={line_number}")
        rows.append(_project_row(record, spec, line_number=line_number))
    return DatasetProjectionResult(
        rows=rows,
        content_hash=content_hash,
        projected_columns=spec.columns,
        row_count=len(rows),
    )


def read_jsonl_projection(
    path: Path,
    spec: DatasetProjectionSpec,
    *,
    expected_content_hash: str | None = None,
) -> DatasetProjectionResult:
    """Read JSONL with byte bounds, hash identity, and column projection."""
    _verify_schema_version(spec)
    data = _read_bounded_bytes(path, spec.max_bytes)
    return read_jsonl_projection_bytes(
        data,
        spec,
        expected_content_hash=expected_content_hash,
    )


def read_json_array_projection(
    path: Path,
    spec: DatasetProjectionSpec,
    *,
    expected_content_hash: str | None = None,
) -> DatasetProjectionResult:
    """Read a JSON array file with the same projection contract as JSONL."""
    _verify_schema_version(spec)
    data = _read_bounded_bytes(path, spec.max_bytes)
    content_hash = _verify_content_hash(data, expected_content_hash)
    payload = load_json_strict(path)
    if not isinstance(payload, list):
        raise DatasetReadError("DATASET_NOT_ARRAY", str(path))
    rows: list[dict[str, object]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise DatasetReadError("DATASET_ROW_NOT_OBJECT", f"index={index}")
        rows.append(_project_row(item, spec, line_number=index + 1))
    return DatasetProjectionResult(
        rows=rows,
        content_hash=content_hash,
        projected_columns=spec.columns,
        row_count=len(rows),
    )


def serialize_rows_jsonl(rows: list[dict[str, object]]) -> bytes:
    lines = [canonical_bytes(row).decode("utf-8").strip() for row in rows]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def projection_identity(spec: DatasetProjectionSpec, content_hash: str) -> str:
    """Content-addressed projection identity for cache invalidation (ADR-DCACHE-001)."""
    body = {
        "content_hash": content_hash,
        "columns": list(spec.columns),
        "optional_columns": sorted(spec.optional_columns),
        "reader_version": spec.reader_version,
        "schema_version": spec.schema_version,
    }
    return sha256_bytes(canonical_bytes(body))
