"""Tests for futures lane acceptance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_patterns.futures_lane import (
    depth_imbalance_signal,
    is_rth,
    quarterly_contract_month,
)
from market_platform_foundation.features.institutional import (
    FUTURES_DEPTH_FAMILY,
    FUTURES_FAMILY,
    configure_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_futures import (
    DEFAULT_FUTURES_FIXTURE,
    FixtureFuturesProvider,
)
from market_platform_foundation.providers.projections import build_workspace_futures_payload
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_FUTURES, build_combined_fixture_ledger


class FuturesLaneAcceptanceTests(unittest.TestCase):
    def test_quarterly_contract_month_format(self) -> None:
        value = quarterly_contract_month()
        self.assertEqual(len(value), 6)
        self.assertTrue(value.isdigit())

    def test_rth_gate(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        rth = datetime(2025, 6, 2, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        self.assertTrue(is_rth(rth))
        after = datetime(2025, 6, 2, 17, 0, tzinfo=ZoneInfo("America/New_York"))
        self.assertFalse(is_rth(after))

    def test_depth_imbalance_signal(self) -> None:
        bids = [{"size": 100}, {"size": 100}]
        asks = [{"size": 10}, {"size": 10}]
        signal, ratio = depth_imbalance_signal(bids, asks, threshold=1.5)
        self.assertEqual(signal, "supports_short")
        self.assertGreater(ratio, 1.5)

    def test_fixture_provider_deterministic(self) -> None:
        first = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
        second = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
        ids_a = [row["normalized_event_id"] for row in first.build_envelopes()]
        ids_b = [row["normalized_event_id"] for row in second.build_envelopes()]
        self.assertEqual(ids_a, ids_b)
        self.assertGreater(len(ids_a), 0)

    def test_whale_entitlement_es_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        es = query_institutional_evidence(FUTURES_FAMILY, prediction_cutoff=cutoff, instrument_id="ES")
        nvda = query_institutional_evidence(FUTURES_FAMILY, prediction_cutoff=cutoff, instrument_id="NVDA")
        self.assertEqual(es["status"], "available")
        self.assertEqual(es["reason_code"], WHALE_ENTITLED_FUTURES)
        self.assertEqual(nvda["status"], "unavailable")
        configure_institutional_ledger(None)

    def test_futures_depth_alias_returns_same_events_as_legacy(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        legacy = query_institutional_evidence(FUTURES_FAMILY, prediction_cutoff=cutoff, instrument_id="ES")
        canonical = query_institutional_evidence(
            FUTURES_DEPTH_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="ES",
        )
        self.assertEqual(legacy["status"], "available")
        self.assertEqual(canonical["status"], "available")
        self.assertEqual(legacy["event_count"], canonical["event_count"])
        configure_institutional_ledger(None)

    def test_workspace_payload_research_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        payload = build_workspace_futures_payload(
            "ES",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertEqual(payload.get("canonical_family"), "futures_depth")
        self.assertEqual(payload.get("legacy_whale_family"), "futures_positioning")
        self.assertGreater(len(payload.get("snapshots", [])), 0)
        self.assertTrue(payload.get("futures_positioning_available"))
        self.assertEqual(payload.get("crowding_regime"), "CROWDED_LONG")
        positioning = payload.get("positioning_snapshot")
        self.assertIsInstance(positioning, dict)
        assert isinstance(positioning, dict)
        self.assertEqual(positioning.get("net"), 75000)
        self.assertTrue(payload.get("futures_baselines_available"))
        self.assertEqual(payload.get("trend_regime"), "TREND_UP")
        trend = payload.get("trend_baseline_snapshot")
        self.assertIsInstance(trend, dict)
        assert isinstance(trend, dict)
        self.assertEqual(trend.get("trend_3m"), 3.305202)
        carry_baseline = payload.get("carry_baseline")
        self.assertIsInstance(carry_baseline, dict)
        assert isinstance(carry_baseline, dict)
        self.assertEqual(carry_baseline.get("carry_percentile"), 0.0)
        configure_institutional_ledger(None)

    def test_explain_futures_ref(self) -> None:
        from market_platform_foundation.ui_api.projections import build_explain_payload, build_inspect_payload
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        explain = build_explain_payload(store, "explain:futures:ES")
        self.assertEqual(explain["explanation"]["ref"], "explain:futures:ES")
        inspect = build_inspect_payload(store, "inspect:futures:ES")
        self.assertIn("tabs", inspect)


if __name__ == "__main__":
    unittest.main()
