"""Tests for bounded in-memory cache and projection memory cache."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.research.dataset_pipeline import RESEARCH_ROW_SPEC, rows_to_jsonl_bytes
from market_platform_foundation.research.dataset_reader import projection_identity
from market_platform_foundation.storage.bounded_memory_cache import BoundedMemoryCache, ProjectionMemoryCache

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/research/fixtures/phase5r-research-rows/sample-research-rows.jsonl"


class BoundedMemoryCacheTests(unittest.TestCase):
    def test_entry_and_byte_eviction(self) -> None:
        cache = BoundedMemoryCache(max_bytes=30, max_entries=2)
        cache.get_or_load("a", lambda: b"12345")
        cache.get_or_load("b", lambda: b"12345")
        cache.get_or_load("c", lambda: b"12345")
        self.assertGreaterEqual(cache.evictions, 1)
        self.assertLessEqual(cache.total_bytes, 30)

    def test_deterministic_eviction_order(self) -> None:
        cache = BoundedMemoryCache(max_bytes=20, max_entries=2)
        cache.get_or_load("first", lambda: b"aaaa")
        cache.get_or_load("second", lambda: b"bbbb")
        cache.get_or_load("third", lambda: b"cccc")
        self.assertNotIn("first", cache.entries)
        self.assertIn("third", cache.entries)

    def test_cache_hit_avoids_loader(self) -> None:
        cache = BoundedMemoryCache(max_bytes=1024, max_entries=4)
        calls = 0

        def loader() -> bytes:
            nonlocal calls
            calls += 1
            return b"payload"

        cache.get_or_load("key", loader)
        cache.get_or_load("key", loader)
        self.assertEqual(calls, 1)
        self.assertEqual(cache.hits, 1)


class ProjectionMemoryCacheTests(unittest.TestCase):
    def test_memory_projection_matches_direct_read(self) -> None:
        source = FIXTURE.read_bytes()
        memory = ProjectionMemoryCache(max_bytes=1024 * 1024, max_entries=4)
        direct = memory.get_or_project(source, RESEARCH_ROW_SPEC)
        cached = memory.get_or_project(source, RESEARCH_ROW_SPEC)
        self.assertEqual(direct.row_count, cached.row_count)
        self.assertEqual(memory.hits, 1)
        self.assertEqual(memory.misses, 1)

    def test_corrupt_memory_entry_rejected(self) -> None:
        source = FIXTURE.read_bytes()
        memory = ProjectionMemoryCache(max_bytes=1024 * 1024, max_entries=4)
        memory.get_or_project(source, RESEARCH_ROW_SPEC)
        projection_id = projection_identity(RESEARCH_ROW_SPEC, sha256_bytes(source))
        memory._backend.entries[projection_id] = b'{"projection_identity":"bad"}\n'
        result = memory.get_or_project(source, RESEARCH_ROW_SPEC)
        self.assertEqual(result.row_count, 2)
        self.assertEqual(memory.corrupt_rejections, 1)

    def test_source_hash_change_is_new_projection(self) -> None:
        rows = [
            {
                "available_time": 1,
                "capability": "BAR_OHLCV_1M",
                "feature_id": "bar_close",
                "instrument_id": "X",
                "prediction_cutoff": 1,
                "value": "1",
            }
        ]
        source_a = rows_to_jsonl_bytes(rows)
        source_b = rows_to_jsonl_bytes([{**rows[0], "value": "2"}])
        memory = ProjectionMemoryCache(max_bytes=1024 * 1024, max_entries=4)
        result_a = memory.get_or_project(source_a, RESEARCH_ROW_SPEC)
        result_b = memory.get_or_project(source_b, RESEARCH_ROW_SPEC)
        self.assertEqual(result_a.rows[0]["value"], "1")
        self.assertEqual(result_b.rows[0]["value"], "2")
        self.assertEqual(memory.misses, 2)


if __name__ == "__main__":
    unittest.main()
