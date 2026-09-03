"""Tests for futures macro event engine (F7)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.futures.macro_events import (
    MacroRiskRegime,
    build_macro_event_snapshot,
    compute_surprise_zscore,
    event_window_active,
    macro_events_payload,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_futures_macro import (
    FixtureFuturesMacroEventsProvider,
)
from market_platform_foundation.donor_bridge.cross_lane_adapter import build_cross_lane_snapshot_from_futures


class MacroEventsEngineTests(unittest.TestCase):
    def test_compute_surprise_zscore(self) -> None:
        self.assertEqual(compute_surprise_zscore(0.3, 0.5), 0.666667)

    def test_event_window_active_within_horizon(self) -> None:
        self.assertTrue(
            event_window_active(
                "2025-06-02T14:41:07.000000000Z",
                "2025-06-03T12:30:00Z",
            )
        )

    def test_es_macro_events_golden_fixture_regression(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_macro_events_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))

        provider = FixtureFuturesMacroEventsProvider()
        result = provider.fetch_macro_events("ES", as_of_time_ns=cutoff)
        payload = macro_events_payload(
            result,
            instrument_family="ES",
            decision_time=cutoff,
        )

        exp = expected["expected"]
        self.assertTrue(payload.get("futures_macro_available"))
        self.assertEqual(payload.get("macro_risk_regime"), exp["macro_risk_regime"])
        self.assertEqual(payload.get("event_window_active"), exp["event_window_active"])

        snapshot = payload.get("macro_event_snapshot")
        self.assertIsInstance(snapshot, dict)
        assert isinstance(snapshot, dict)
        exp_snapshot = exp["macro_event_snapshot"]
        for key, value in exp_snapshot.items():
            self.assertEqual(snapshot.get(key), value, msg=key)

    def test_cross_lane_emits_macro_event_risk(self) -> None:
        futures_payload = {
            "available": True,
            "snapshot_count": 1,
            "futures_macro_available": True,
            "macro_event_snapshot": {
                "macro_risk_regime": MacroRiskRegime.ELEVATED.value,
                "upcoming_event_type": "PPI",
            },
        }
        _, evidence = build_cross_lane_snapshot_from_futures(futures_payload)
        signals = [row.get("signal") for row in evidence]
        self.assertIn("FUTURES_MACRO_EVENT_RISK", signals)


if __name__ == "__main__":
    unittest.main()
