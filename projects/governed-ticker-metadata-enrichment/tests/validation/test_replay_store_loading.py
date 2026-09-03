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


if __name__ == "__main__":
    unittest.main()
