"""Isolation regressions for P4 immutable fixture/setup caches."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.providers import whale_ledger as whale_ledger_module
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger
from market_platform_foundation.ui_api import store as store_module


class CombinedFixtureLedgerCacheIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        whale_ledger_module._cached_combined_fixture_ledger_template.cache_clear()

    def test_repeated_builds_are_isolated(self) -> None:
        first = build_combined_fixture_ledger()
        second = build_combined_fixture_ledger()
        self.assertEqual(first.events, second.events)
        self.assertIsNot(first.events, second.events)
        self.assertIsNot(first.events[0], second.events[0])
        first.events[0]["instrument_id"] = "MUTATED"
        self.assertNotEqual(second.events[0].get("instrument_id"), "MUTATED")

    def test_reversed_order_remains_isolated(self) -> None:
        second = build_combined_fixture_ledger()
        first = build_combined_fixture_ledger()
        first.events[0]["instrument_id"] = "MUTATED"
        self.assertNotEqual(second.events[0].get("instrument_id"), "MUTATED")


class ReplayStoreHydrationIsolationTests(unittest.TestCase):
    def test_hydrated_store_does_not_share_mutable_bars(self) -> None:
        store_module._cached_replay_payload.cache_clear()
        store_module._cached_decoded_replay_snapshot.cache_clear()
        payload = store_module.canonical_bytes(
            {
                "evaluation": {"risk_decisions": []},
                "events": [
                    {
                        "available_time": 1,
                        "event_type": "BAR_OHLCV_1M",
                        "instrument_id": "TEST",
                        "normalized_event_id": "event-1",
                    }
                ],
                "instrument_id": "TEST",
                "session_id": "session-1",
                "strategy": {"interpretations": []},
            }
        )
        with mock.patch.object(store_module, "_replay_source_digest", return_value="verified"), mock.patch.object(
            store_module, "_build_replay_payload", return_value=payload
        ):
            warm = store_module.ReplayStore(collection_root=Path("collection"))
            warm.load()
            fork = store_module.ReplayStore(collection_root=Path("collection"))
            fork.hydrate_replay_bars_from(warm)
            fork.refresh_mutable_runtime()
        fork.bars[0]["instrument_id"] = "MUTATED"
        self.assertEqual(warm.bars[0]["instrument_id"], "TEST")
        self.assertIsNot(fork.paper_ledger, warm.paper_ledger)


class DecodedReplaySnapshotCacheIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        store_module._cached_replay_payload.cache_clear()
        store_module._cached_decoded_replay_snapshot.cache_clear()

    def test_decoded_snapshot_does_not_share_mutable_events(self) -> None:
        payload = store_module.canonical_bytes(
            {
                "evaluation": {"risk_decisions": []},
                "events": [
                    {
                        "available_time": 1,
                        "event_type": "BAR_OHLCV_1M",
                        "instrument_id": "TEST",
                        "normalized_event_id": "event-1",
                    }
                ],
                "instrument_id": "TEST",
                "session_id": "session-1",
                "strategy": {"interpretations": []},
            }
        )
        with mock.patch.object(store_module, "_replay_source_digest", return_value="verified"), mock.patch.object(
            store_module, "_build_replay_payload", return_value=payload
        ):
            first = store_module.ReplayStore(collection_root=Path("collection"))
            second = store_module.ReplayStore(collection_root=Path("collection"))
            first.load()
            second.load()
        first.bars[0]["instrument_id"] = "MUTATED"
        self.assertEqual(second.bars[0]["instrument_id"], "TEST")


if __name__ == "__main__":
    unittest.main()
