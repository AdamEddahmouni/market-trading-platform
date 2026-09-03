"""Byte- and entry-bounded in-memory cache (GridIQ PBP store concept)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ..canonical import _pairs_no_duplicates, canonical_bytes, sha256_bytes
from .dataset_reader import (
    DatasetProjectionResult,
    DatasetProjectionSpec,
    DatasetReadError,
    projection_identity,
    read_jsonl_projection_bytes,
    serialize_rows_jsonl,
)


@dataclass
class BoundedMemoryCache:
    """Deterministic FIFO eviction by bytes and entry count."""

    max_bytes: int
    max_entries: int = 64
    entries: dict[str, bytes] = field(default_factory=dict)
    entry_order: list[str] = field(default_factory=list)
    total_bytes: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    def cache_key(self, logical_id: str, **parts: object) -> str:
        body = {"logical_id": logical_id, **parts}
        return sha256_bytes(canonical_bytes(body))

    def _evict_until_fits(self, incoming_bytes: int) -> None:
        while self.entry_order and (
            self.total_bytes + incoming_bytes > self.max_bytes
            or len(self.entry_order) >= self.max_entries
        ):
            oldest = self.entry_order.pop(0)
            removed = self.entries.pop(oldest)
            self.total_bytes -= len(removed)
            self.evictions += 1

    def get_or_load(self, key: str, loader: Callable[[], bytes]) -> bytes:
        if key in self.entries:
            self.hits += 1
            self.entry_order.remove(key)
            self.entry_order.append(key)
            return self.entries[key]
        self.misses += 1
        payload = loader()
        self._evict_until_fits(len(payload))
        if key in self.entries:
            old = self.entries.pop(key)
            self.total_bytes -= len(old)
            self.entry_order.remove(key)
        self.entries[key] = payload
        self.entry_order.append(key)
        self.total_bytes += len(payload)
        return payload

    def invalidate(self, key: str) -> bool:
        if key not in self.entries:
            return False
        removed = self.entries.pop(key)
        self.total_bytes -= len(removed)
        self.entry_order.remove(key)
        return True

    def report(self) -> dict[str, Any]:
        return {
            "entry_count": len(self.entry_order),
            "evictions": self.evictions,
            "hits": self.hits,
            "logical_id": "storage.bounded_memory_cache_report",
            "max_bytes": self.max_bytes,
            "max_entries": self.max_entries,
            "misses": self.misses,
            "total_bytes": self.total_bytes,
        }


@dataclass
class ProjectionMemoryCache:
    """In-memory disposable projection cache mirroring ProjectionDiskCache semantics."""

    max_bytes: int
    max_entries: int = 32
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    corrupt_rejections: int = 0
    _backend: BoundedMemoryCache = field(init=False)

    def __post_init__(self) -> None:
        self._backend = BoundedMemoryCache(max_bytes=self.max_bytes, max_entries=self.max_entries)

    def get_or_project(
        self,
        source_bytes: bytes,
        spec: DatasetProjectionSpec,
    ) -> DatasetProjectionResult:
        content_hash = sha256_bytes(source_bytes)
        projection_id = projection_identity(spec, content_hash)
        spec_fingerprint = sha256_bytes(
            canonical_bytes(
                {
                    "columns": list(spec.columns),
                    "optional_columns": sorted(spec.optional_columns),
                    "schema_version": spec.schema_version,
                }
            )
        )

        if projection_id in self._backend.entries:
            try:
                entry_bytes = self._backend.entries[projection_id]
                payload = json.loads(entry_bytes.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
                if not isinstance(payload, dict):
                    raise DatasetReadError("CACHE_META_INVALID", projection_id)
                if str(payload.get("spec_fingerprint")) != spec_fingerprint:
                    raise DatasetReadError("CACHE_SPEC_MISMATCH", projection_id)
                projected_b64 = str(payload.get("projected_b64", ""))
                projected_bytes = base64.b64decode(projected_b64.encode("ascii"))
                if sha256_bytes(projected_bytes) != str(payload.get("projected_content_hash", "")):
                    raise DatasetReadError("CACHE_PROJECTED_HASH_MISMATCH", projection_id)
                if str(payload.get("source_content_hash")) != content_hash:
                    raise DatasetReadError("CACHE_SOURCE_HASH_MISMATCH", projection_id)
                result = read_jsonl_projection_bytes(
                    projected_bytes,
                    spec,
                    expected_content_hash=sha256_bytes(projected_bytes),
                )
                self.hits += 1
                self._backend.hits += 1
                self._backend.entry_order.remove(projection_id)
                self._backend.entry_order.append(projection_id)
                return result
            except (DatasetReadError, ValueError, KeyError):
                self.corrupt_rejections += 1
                self._backend.invalidate(projection_id)

        self.misses += 1
        result = read_jsonl_projection_bytes(
            source_bytes,
            spec,
            expected_content_hash=content_hash,
        )
        projected_bytes = serialize_rows_jsonl(result.rows)
        projected_hash = sha256_bytes(projected_bytes)
        entry_payload = canonical_bytes(
            {
                "logical_id": "storage.projection_memory_entry",
                "projection_identity": projection_id,
                "projected_b64": base64.b64encode(projected_bytes).decode("ascii"),
                "projected_content_hash": projected_hash,
                "projected_row_count": result.row_count,
                "source_content_hash": content_hash,
                "spec_fingerprint": spec_fingerprint,
            }
        )
        self._backend.get_or_load(projection_id, lambda: entry_payload)
        self.evictions = self._backend.evictions
        return result

    def report(self) -> dict[str, Any]:
        backend_report = self._backend.report()
        return {
            "corrupt_rejections": self.corrupt_rejections,
            "entry_count": backend_report["entry_count"],
            "evictions": self.evictions,
            "hits": self.hits,
            "logical_id": "storage.projection_memory_cache_report",
            "max_bytes": self.max_bytes,
            "max_entries": self.max_entries,
            "misses": self.misses,
            "total_bytes": backend_report["total_bytes"],
        }
