"""Content-addressed byte-bounded dataset cache per ADR-DCACHE-001."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..canonical import canonical_bytes, sha256_bytes


@dataclass
class DatasetCache:
    max_bytes: int
    source_hash: str
    schema_version: str
    normalization_version: str
    entries: dict[str, bytes] = field(default_factory=dict)
    entry_order: list[str] = field(default_factory=list)
    total_bytes: int = 0
    hits: int = 0
    misses: int = 0

    def cache_key(self, logical_id: str) -> str:
        body = {
            "logical_id": logical_id,
            "normalization_version": self.normalization_version,
            "schema_version": self.schema_version,
            "source_hash": self.source_hash,
        }
        return sha256_bytes(canonical_bytes(body))

    def _evict_until_fits(self, incoming_bytes: int) -> None:
        while self.total_bytes + incoming_bytes > self.max_bytes and self.entry_order:
            oldest = self.entry_order.pop(0)
            removed = self.entries.pop(oldest)
            self.total_bytes -= len(removed)

    def get_or_load(self, logical_id: str, loader: Callable[[], bytes]) -> bytes:
        key = self.cache_key(logical_id)
        if key in self.entries:
            self.hits += 1
            self.entry_order.remove(key)
            self.entry_order.append(key)
            return self.entries[key]
        self.misses += 1
        payload = loader()
        self._evict_until_fits(len(payload))
        self.entries[key] = payload
        self.entry_order.append(key)
        self.total_bytes += len(payload)
        return payload

    def invalidate_on_source_change(self, new_source_hash: str) -> bool:
        if new_source_hash == self.source_hash:
            return False
        self.entries.clear()
        self.entry_order.clear()
        self.total_bytes = 0
        self.source_hash = new_source_hash
        return True

    def report(self) -> dict[str, Any]:
        return {
            "entry_count": len(self.entries),
            "hits": self.hits,
            "logical_id": "phase4.dataset_cache_report",
            "max_bytes": self.max_bytes,
            "misses": self.misses,
            "normalization_version": self.normalization_version,
            "schema_version": self.schema_version,
            "source_hash": self.source_hash,
            "total_bytes": self.total_bytes,
        }
