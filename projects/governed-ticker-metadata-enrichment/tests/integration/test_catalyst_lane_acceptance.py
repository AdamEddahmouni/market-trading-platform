"""Tests for catalyst lane acceptance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_patterns.catalyst_lane import gate_catalyst, lean_to_direction_label
from market_platform_foundation.features.institutional import (
    PUBLIC_CATALYST_FAMILY,
    configure_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_catalyst import (
    DEFAULT_CATALYST_FIXTURE,
    FixtureCatalystProvider,
)
from market_platform_foundation.providers.projections import build_workspace_catalyst_payload
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_CATALYST, build_combined_fixture_ledger


class CatalystLaneAcceptanceTests(unittest.TestCase):
    def test_lean_to_direction_label(self) -> None:
        self.assertEqual(lean_to_direction_label("BULLISH"), "supports_long")
        self.assertEqual(lean_to_direction_label("BEARISH"), "supports_short")

    def test_fixture_provider_deterministic(self) -> None:
        first = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        second = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        ids_a = [row["normalized_event_id"] for row in first.build_envelopes()]
        ids_b = [row["normalized_event_id"] for row in second.build_envelopes()]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 5)

    def test_whale_entitlement_boxl_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        boxl = query_institutional_evidence(PUBLIC_CATALYST_FAMILY, prediction_cutoff=cutoff, instrument_id="BOXL")
        nvda = query_institutional_evidence(PUBLIC_CATALYST_FAMILY, prediction_cutoff=cutoff, instrument_id="NVDA")
        self.assertEqual(boxl["status"], "available")
        self.assertEqual(boxl["reason_code"], WHALE_ENTITLED_CATALYST)
        self.assertEqual(nvda["status"], "unavailable")
        configure_institutional_ledger(None)

    def test_workspace_payload_research_only(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        payload = build_workspace_catalyst_payload(
            "BOXL",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertGreater(len(payload.get("catalysts", [])), 0)
        configure_institutional_ledger(None)

    def test_gate_catalyst_reasons(self) -> None:
        ok, reasons = gate_catalyst(confidence=0.2, min_confidence=0.5, lean="NEUTRAL", liquidity_ok=True)
        self.assertFalse(ok)
        self.assertIn("CONFIDENCE_BELOW_THRESHOLD", reasons)
        self.assertIn("LEAN_NEUTRAL", reasons)


if __name__ == "__main__":
    unittest.main()
