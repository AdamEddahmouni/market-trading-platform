"""Tests for projection disk cache (ADR-DCACHE-001)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.research.dataset_pipeline import RESEARCH_ROW_SPEC, rows_to_jsonl_bytes
from market_platform_foundation.research.dataset_reader import projection_identity
from market_platform_foundation.storage.projection_cache import ProjectionDiskCache

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/research/fixtures/phase5r-research-rows/sample-research-rows.jsonl"


class ProjectionCacheTests(unittest.TestCase):
    def test_eviction_when_over_byte_limit(self) -> None:
        source = FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            cache = ProjectionDiskCache(root=Path(tmp), max_bytes=len(source) + 50)
            cache.get_or_project(source, RESEARCH_ROW_SPEC)
            cache.get_or_project(source + b"\n", RESEARCH_ROW_SPEC)
            self.assertGreaterEqual(cache.evictions, 1)

    def test_corrupt_cache_entry_rejected(self) -> None:
        source = FIXTURE.read_bytes()
        projection_id = projection_identity(RESEARCH_ROW_SPEC, sha256_bytes(source))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = ProjectionDiskCache(root=root, max_bytes=1024 * 1024)
            cache.get_or_project(source, RESEARCH_ROW_SPEC)
            data_path = root / projection_id / "projected-rows.jsonl"
            data_path.write_bytes(b"corrupt\n")
            result = cache.get_or_project(source, RESEARCH_ROW_SPEC)
            self.assertEqual(result.row_count, 2)
            self.assertEqual(cache.corrupt_rejections, 1)
            self.assertEqual(cache.misses, 2)

    def test_source_hash_change_invalidates_entry(self) -> None:
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
        with tempfile.TemporaryDirectory() as tmp:
            cache = ProjectionDiskCache(root=Path(tmp), max_bytes=1024 * 1024)
            result_a = cache.get_or_project(source_a, RESEARCH_ROW_SPEC)
            result_b = cache.get_or_project(source_b, RESEARCH_ROW_SPEC)
            self.assertEqual(result_a.rows[0]["value"], "1")
            self.assertEqual(result_b.rows[0]["value"], "2")
            self.assertEqual(cache.misses, 2)


if __name__ == "__main__":
    unittest.main()
