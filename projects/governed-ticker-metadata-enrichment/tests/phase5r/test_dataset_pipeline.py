"""Tests for Phase 5R dataset pipeline wiring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.research.dataset_pipeline import (
    build_research_dataset_from_events,
    load_research_dataset_from_jsonl,
    RESEARCH_ROW_SPEC,
)
from market_platform_foundation.research.evaluation import evaluation_root_hash, run_walk_forward_evaluation
from market_platform_foundation.storage.projection_cache import ProjectionDiskCache

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/research/fixtures/phase5r-research-rows/sample-research-rows.jsonl"


def _synthetic_events(count: int = 6) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2000000000000000000
    for index in range(count):
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {
                    "close": str(100 + index),
                    "high": str(101 + index),
                    "low": str(99 + index),
                    "open": str(100 + index),
                    "timeframe": "1_MINUTE",
                    "volume": 100 + index,
                },
                "channel_id": "EQ-1",
                "event_time": available - 1,
                "event_type": "BAR_OHLCV_1M",
                "historical_ingested_time": available,
                "ingest_run_id": "RUN-SYNTH",
                "instrument_id": "EQ-1",
                "normalization_version": "test/1.0.0",
                "normalized_event_id": f"evt-{index}",
                "operation": "UPSERT",
                "publisher_id": "PUB-1",
                "quality_observation_refs": [],
                "raw_reference": f"test://{index}",
                "schema_version": "1.0.0",
                "source_instance_id": "SRC-1",
                "source_record_id": f"REC-{index}",
                "source_revision_id": "1",
                "venue_id": "VEN-1",
            }
        )
    return events


class DatasetPipelineTests(unittest.TestCase):
    def test_events_pipeline_adds_projection_metadata(self) -> None:
        rows, manifest = build_research_dataset_from_events(_synthetic_events(4))
        self.assertEqual(len(rows), 4)
        self.assertIn("projection_identity", manifest)
        self.assertIn("source_content_hash", manifest)
        self.assertIn("dataset_fingerprint", manifest)

    def test_fixture_jsonl_loads_through_projection(self) -> None:
        rows, manifest = load_research_dataset_from_jsonl(FIXTURE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["instrument_id"], "BIYA")
        self.assertEqual(manifest["row_count"], 2)

    def test_cache_hit_on_second_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = ProjectionDiskCache(root=Path(tmp), max_bytes=1024 * 1024)
            rows_a, manifest_a = load_research_dataset_from_jsonl(FIXTURE, cache=cache)
            rows_b, manifest_b = load_research_dataset_from_jsonl(FIXTURE, cache=cache)
            self.assertEqual(rows_a, rows_b)
            self.assertEqual(manifest_a["dataset_fingerprint"], manifest_b["dataset_fingerprint"])
            self.assertEqual(cache.hits, 1)
            self.assertEqual(cache.misses, 1)

    def test_walk_forward_still_deterministic_with_pipeline(self) -> None:
        events = _synthetic_events(8)
        result_a = run_walk_forward_evaluation(events)
        result_b = run_walk_forward_evaluation(events)
        self.assertEqual(evaluation_root_hash(result_a), evaluation_root_hash(result_b))
        self.assertIn("projection_identity", result_a["dataset_manifest"])


if __name__ == "__main__":
    unittest.main()
