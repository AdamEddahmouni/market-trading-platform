"""Disk-backed disposable projection cache per ADR-DCACHE-001."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import load_json_strict, sha256_bytes, write_canonical_json
from .dataset_reader import (
    DatasetProjectionResult,
    DatasetProjectionSpec,
    DatasetReadError,
    projection_identity,
    read_jsonl_projection_bytes,
    serialize_rows_jsonl,
)

@dataclass
class ProjectionDiskCache:
    """Content-addressed disposable cache for projected dataset members."""

    root: Path
    max_bytes: int
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    corrupt_rejections: int = 0
    _entry_order: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _entry_dir(self, projection_id: str) -> Path:
        return self.root / projection_id

    def _meta_path(self, projection_id: str) -> Path:
        return self._entry_dir(projection_id) / "cache-meta.json"

    def _data_path(self, projection_id: str) -> Path:
        return self._entry_dir(projection_id) / "projected-rows.jsonl"

    def _total_bytes(self) -> int:
        total = 0
        for entry_id in self._entry_order:
            data_path = self._data_path(entry_id)
            if data_path.is_file():
                total += data_path.stat().st_size
        return total

    def _delete_entry(self, projection_id: str) -> None:
        entry_dir = self._entry_dir(projection_id)
        if entry_dir.exists():
            for child in entry_dir.iterdir():
                child.unlink()
            entry_dir.rmdir()
        if projection_id in self._entry_order:
            self._entry_order.remove(projection_id)

    def _evict_until_fits(self, incoming_bytes: int) -> None:
        while self._total_bytes() + incoming_bytes > self.max_bytes and self._entry_order:
            oldest = self._entry_order.pop(0)
            self._delete_entry(oldest)
            self.evictions += 1

    def invalidate_projection(self, projection_id: str) -> bool:
        if projection_id not in self._entry_order:
            return False
        self._delete_entry(projection_id)
        return True

    def get_or_project(
        self,
        source_bytes: bytes,
        spec: DatasetProjectionSpec,
    ) -> DatasetProjectionResult:
        content_hash = sha256_bytes(source_bytes)
        projection_id = projection_identity(spec, content_hash)
        meta_path = self._meta_path(projection_id)
        data_path = self._data_path(projection_id)

        if meta_path.is_file() and data_path.is_file():
            try:
                meta = load_json_strict(meta_path)
                if not isinstance(meta, dict):
                    raise DatasetReadError("CACHE_META_INVALID", projection_id)
                if str(meta.get("projection_identity")) != projection_id:
                    raise DatasetReadError("CACHE_IDENTITY_MISMATCH", projection_id)
                if str(meta.get("source_content_hash")) != content_hash:
                    raise DatasetReadError("CACHE_SOURCE_HASH_MISMATCH", projection_id)
                projected_bytes = data_path.read_bytes()
                if sha256_bytes(projected_bytes) != str(meta.get("projected_content_hash", "")):
                    raise DatasetReadError("CACHE_PROJECTED_HASH_MISMATCH", projection_id)
                result = read_jsonl_projection_bytes(
                    projected_bytes,
                    spec,
                    expected_content_hash=sha256_bytes(projected_bytes),
                )
                self.hits += 1
                if projection_id in self._entry_order:
                    self._entry_order.remove(projection_id)
                self._entry_order.append(projection_id)
                return result
            except (DatasetReadError, ValueError, OSError):
                self.corrupt_rejections += 1
                self._delete_entry(projection_id)

        self.misses += 1
        result = read_jsonl_projection_bytes(
            source_bytes,
            spec,
            expected_content_hash=content_hash,
        )
        projected_bytes = serialize_rows_jsonl(result.rows)
        projected_hash = sha256_bytes(projected_bytes)
        self._evict_until_fits(len(projected_bytes))
        entry_dir = self._entry_dir(projection_id)
        entry_dir.mkdir(parents=True, exist_ok=True)
        data_path.write_bytes(projected_bytes)
        write_canonical_json(
            meta_path,
            {
                "logical_id": "storage.projection_cache_entry",
                "projection_identity": projection_id,
                "projected_content_hash": projected_hash,
                "projected_row_count": result.row_count,
                "source_content_hash": content_hash,
            },
        )
        if projection_id in self._entry_order:
            self._entry_order.remove(projection_id)
        self._entry_order.append(projection_id)
        return result

    def report(self) -> dict[str, Any]:
        return {
            "corrupt_rejections": self.corrupt_rejections,
            "entry_count": len(self._entry_order),
            "evictions": self.evictions,
            "hits": self.hits,
            "logical_id": "storage.projection_cache_report",
            "max_bytes": self.max_bytes,
            "misses": self.misses,
            "total_bytes": self._total_bytes(),
        }
