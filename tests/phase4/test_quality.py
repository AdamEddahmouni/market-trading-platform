"""Phase 4 quality, state, and cache tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes
from market_platform_foundation.data_quality.observations import consumer_eligibility, evaluate_bar_event, validate_bar_payload
from market_platform_foundation.phase4_assertions import MANDATORY_IDS, aggregate_status, build_registry
from market_platform_foundation.replay.quality_lifecycle import run_quality_replay, run_quality_root_hash
from market_platform_foundation.state.bar_book import BarBookState
from market_platform_foundation.storage.dataset_cache import DatasetCache

FIXTURE_DIR = ROOT / "docs/research/fixtures/phase4-corruption"


class Phase4QualityTests(unittest.TestCase):
    def test_registry_has_four_predicates(self) -> None:
        registry = build_registry(ROOT / "manifests/phase4/assertion-predicates.json")
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_invalid_bar_payload_detected(self) -> None:
        event = load_json_strict(FIXTURE_DIR / "bar-invalid-ohlc.json")
        reasons = validate_bar_payload(dict(event["bar_payload"]))
        self.assertTrue(reasons)

    def test_invalid_bar_blocks_consumer(self) -> None:
        event = load_json_strict(FIXTURE_DIR / "bar-invalid-ohlc.json")
        observations = evaluate_bar_event(event, prior_bar=None)
        eligibility, reasons = consumer_eligibility(observations)
        self.assertEqual(eligibility, "BLOCKED")
        self.assertTrue(reasons)

    def test_bar_book_rejects_unsupported_event_type(self) -> None:
        book = BarBookState()
        status, reasons = book.apply_event({"event_type": "MBO", "normalized_event_id": "x"})
        self.assertEqual(status, "REJECTED")
        self.assertTrue(reasons)

    def test_dataset_cache_is_deterministic(self) -> None:
        cache = DatasetCache(
            max_bytes=1024,
            source_hash="abc",
            schema_version="1.0.0",
            normalization_version="1.0.0",
        )
        payload = b"fixture-bytes"
        first = cache.get_or_load("events", lambda: payload)
        second = cache.get_or_load("events", lambda: b"other")
        self.assertEqual(first, second)
        self.assertEqual(cache.hits, 1)

    def test_quality_replay_deterministic(self) -> None:
        events = [
            load_json_strict(FIXTURE_DIR / "bar-valid-a.json"),
            load_json_strict(FIXTURE_DIR / "late-correction-bar.json"),
        ]
        max_time = max(int(event["available_time"]) for event in events)
        state_a = run_quality_replay(events, clocks=[max_time], decision_times=[max_time])
        state_b = run_quality_replay(events, clocks=[max_time], decision_times=[max_time])
        self.assertEqual(run_quality_root_hash(state_a), run_quality_root_hash(state_b))

    def test_aggregate_status_all_pass(self) -> None:
        self.assertEqual(aggregate_status([{"status": "PASS"}]), "PASS")


if __name__ == "__main__":
    unittest.main()
