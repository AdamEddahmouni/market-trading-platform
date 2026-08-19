"""Tests for Platform P1 catalyst runtime and corporate event registry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)
from market_platform_foundation.runtime.catalyst_attention import CatalystAttentionRuntime  # noqa: E402
from market_platform_foundation.runtime.corporate_events import CorporateEventRegistry  # noqa: E402

CUTOFF_NS = iso_to_epoch_ns("2026-07-23T00:00:00.000000000Z")


class TestPlatformP1Runtime(unittest.TestCase):
    def test_workspace_exposes_corporate_registry_and_catalyst_runtime(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["corporate_event_registry_available"])
        self.assertTrue(payload["catalyst_runtime_available"])
        self.assertTrue(payload["corporate_event_registry"])
        runtime = payload["catalyst_attention_runtime"]
        self.assertEqual(runtime["instrument_id"], "BOXL")
        self.assertGreaterEqual(runtime["gated_catalyst_count"], 1)

    def test_corporate_registry_pit_filters(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z"),
        )
        self.assertLess(len(payload["corporate_event_registry"]), 5)

    def test_catalyst_attention_runtime_from_summaries(self) -> None:
        summaries = [
            {"gate_ok": True, "lean": "BULLISH", "catalyst_strength": 0.7},
            {"gate_ok": True, "lean": "BULLISH", "catalyst_strength": 0.8},
        ]
        snapshot = CatalystAttentionRuntime().build_snapshot(
            summaries,
            instrument_id="BOXL",
        )
        self.assertTrue(snapshot.runtime_available)
        self.assertEqual(snapshot.bullish_catalyst_count, 2)
        self.assertEqual(snapshot.max_catalyst_strength, 0.8)

    def test_registry_from_extraction_summaries(self) -> None:
        registry = CorporateEventRegistry.from_extraction_summaries(
            [
                {
                    "event_id": "evt-1",
                    "canonical_event_type": "earnings_beat",
                    "event_time": "2026-07-15T14:30:00.000000000Z",
                    "available_time": "2026-07-15T14:45:00.000000000Z",
                }
            ],
            instrument_id="BOXL",
        )
        rows = registry.query_events("BOXL", prediction_cutoff=CUTOFF_NS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].canonical_event_type, "earnings_beat")


if __name__ == "__main__":
    unittest.main()
