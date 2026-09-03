"""Tests for fund/ETF cross-asset lane acceptance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_patterns.fund_etf_lane import flow_direction_label
from market_platform_foundation.features.institutional import (
    FUND_ETF_FAMILY,
    configure_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_fund_etf import (
    DEFAULT_FUND_ETF_FIXTURE,
    FixtureFundEtfProvider,
)
from market_platform_foundation.providers.projections import build_workspace_fund_etf_payload
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_FUND_ETF, build_combined_fixture_ledger


class FundEtfLaneAcceptanceTests(unittest.TestCase):
    def test_flow_direction_label(self) -> None:
        self.assertEqual(flow_direction_label(1.3), "supports_long")
        self.assertEqual(flow_direction_label(0.7), "supports_short")

    def test_fixture_provider_deterministic(self) -> None:
        first = FixtureFundEtfProvider(fixture_path=DEFAULT_FUND_ETF_FIXTURE)
        second = FixtureFundEtfProvider(fixture_path=DEFAULT_FUND_ETF_FIXTURE)
        ids_a = [row["normalized_event_id"] for row in first.build_envelopes()]
        ids_b = [row["normalized_event_id"] for row in second.build_envelopes()]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 5)

    def test_whale_entitlement_nvda_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        nvda = query_institutional_evidence(FUND_ETF_FAMILY, prediction_cutoff=cutoff, instrument_id="NVDA")
        boxl = query_institutional_evidence(FUND_ETF_FAMILY, prediction_cutoff=cutoff, instrument_id="BOXL")
        self.assertEqual(nvda["status"], "available")
        self.assertEqual(nvda["reason_code"], WHALE_ENTITLED_FUND_ETF)
        self.assertEqual(boxl["status"], "unavailable")
        configure_institutional_ledger(None)

    def test_workspace_payload_research_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        payload = build_workspace_fund_etf_payload(
            "NVDA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertGreater(len(payload.get("events", [])), 0)
        configure_institutional_ledger(None)


if __name__ == "__main__":
    unittest.main()
