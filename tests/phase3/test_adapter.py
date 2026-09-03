"""Phase 3 adapter and assertion tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import (
    COLLECTION_RELATIVE_PATH,
    PINNED_SHA256,
    EquityIntradayJsonlAdapter,
    verify_dependency_lock,
    verify_registry_integrity,
)
from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.phase3_assertions import MANDATORY_IDS, aggregate_status, build_registry
from market_platform_foundation.registry import registry_snapshot

COLLECTION_ROOT = ROOT.parent
SOURCE_PATH = COLLECTION_ROOT / COLLECTION_RELATIVE_PATH


class Phase3AdapterTests(unittest.TestCase):
    def test_registry_has_four_predicates(self) -> None:
        registry = build_registry(ROOT / "manifests/phase3/assertion-predicates.json")
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_iso_to_epoch_ns(self) -> None:
        self.assertEqual(
            iso_to_epoch_ns("2024-01-02T15:04:05Z"),
            1704207845000000000,
        )

    def test_source_bytes_match_pin(self) -> None:
        self.assertTrue(SOURCE_PATH.is_file())
        observed = sha256_bytes(SOURCE_PATH.read_bytes())
        self.assertEqual(observed, PINNED_SHA256)

    def test_adapter_normalizes_admitted_fixture(self) -> None:
        adapter = EquityIntradayJsonlAdapter(ingest_run_id="test-run")
        result = adapter.ingest_path(SOURCE_PATH)
        self.assertGreater(result.record_count, 0)
        self.assertGreater(len(result.canonical_events), 0)
        self.assertEqual(result.conflict_count, 0)
        self.assertEqual(result.dangling_count, 0)
        sample = result.canonical_events[0]
        self.assertEqual(sample["event_type"], "BAR_OHLCV_1M")
        self.assertIsInstance(sample["available_time"], int)
        self.assertLessEqual(sample["event_time"], sample["available_time"])

    def test_idempotent_reingest(self) -> None:
        adapter = EquityIntradayJsonlAdapter(ingest_run_id="test-run")
        first = adapter.ingest_path(SOURCE_PATH)
        second = adapter.ingest_path(SOURCE_PATH)
        self.assertEqual(second.idempotent_replays, len(first.canonical_events))
        self.assertEqual(second.conflict_count, 0)

    def test_registry_integrity_passes(self) -> None:
        registry_ids = [row["registry_id"] for row in registry_snapshot()]
        status, reasons = verify_registry_integrity(registry_ids)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])

    def test_dependency_lock_passes(self) -> None:
        status, reasons = verify_dependency_lock(ROOT / "phase0-dependency-lock.json")
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])

    def test_aggregate_status_all_pass(self) -> None:
        results = [{"status": "PASS"}, {"status": "PASS"}]
        self.assertEqual(aggregate_status(results), "PASS")


if __name__ == "__main__":
    unittest.main()
