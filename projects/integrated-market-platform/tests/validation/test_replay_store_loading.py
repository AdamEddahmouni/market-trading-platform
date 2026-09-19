"""Regression tests for safe ReplayStore base-payload reuse."""

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes
from market_platform_foundation.ui_api import store as store_module


class ReplayStoreLoadingTests(unittest.TestCase):
    def test_verified_payload_is_reused_but_mutable_state_is_not_shared(self) -> None:
        self.assertTrue(hasattr(store_module, "_cached_replay_payload"))
        store_module._cached_replay_payload.cache_clear()
        store_module._cached_decoded_replay_snapshot.cache_clear()
        payload = canonical_bytes(
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
        with tempfile.TemporaryDirectory() as first_audit, tempfile.TemporaryDirectory() as second_audit:
            with patch.object(store_module, "_replay_source_digest", return_value="verified"), patch.object(
                store_module, "_build_replay_payload", return_value=payload
            ) as build:
                first = store_module.ReplayStore(
                    collection_root=Path("collection"),
                    assistant_audit_root=Path(first_audit),
                )
                second = store_module.ReplayStore(
                    collection_root=Path("collection"),
                    assistant_audit_root=Path(second_audit),
                )
                first.load()
                second.load()
        self.assertEqual(build.call_count, 1)
        self.assertEqual(first.bars, second.bars)
        self.assertIsNot(first.bars, second.bars)
        self.assertIsNot(first.bars[0], second.bars[0])
        first.bars[0]["instrument_id"] = "MUTATED"
        self.assertEqual(second.bars[0]["instrument_id"], "TEST")

    def test_load_decoded_snapshot_keeps_fixture_replay_under_live_gate(self) -> None:
        snapshot = {
            "evaluation": {"risk_decisions": []},
            "events": [
                {
                    "available_time": 1,
                    "event_type": "BAR_OHLCV_1M",
                    "instrument_id": "HIST",
                    "normalized_event_id": "hist-event-1",
                    "bar_payload": {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                }
            ],
            "instrument_id": "HIST",
            "session_id": "hist-session",
            "strategy": {"interpretations": []},
        }
        with tempfile.TemporaryDirectory() as audit_dir:
            store = store_module.ReplayStore(
                collection_root=Path("collection"),
                data_mode="FIXTURE_REPLAY",
                mode="REPLAY",
                assistant_audit_root=Path(audit_dir),
            )
            with patch(
                "market_platform_foundation.market_data.live_config.live_observational_enabled",
                return_value=True,
            ):
                store.load_decoded_snapshot(snapshot)
        self.assertEqual(store.data_mode, "FIXTURE_REPLAY")


if __name__ == "__main__":
    unittest.main()
