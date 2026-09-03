"""Tests for Market Context → Squeeze cross-lane adapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.market_context_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_catalyst,
    build_ss_p2_structures_from_catalyst,
)
from market_platform_foundation.features.institutional import configure_institutional_ledger  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_catalyst_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402


class MarketContextAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_institutional_ledger(bootstrap_default_providers())
        cls.cutoff = iso_to_epoch_ns("2026-07-22T21:00:00.000000000Z")

    def test_boxl_fixture_produces_catalyst_cross_lane(self) -> None:
        payload = build_workspace_catalyst_payload(
            "BOXL",
            as_of_context={"replay_mode": "fixture"},
            prediction_cutoff=self.cutoff,
        )
        self.assertTrue(payload.get("available"))
        snapshot, evidence = build_cross_lane_snapshot_from_catalyst(payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot.get("catalyst_available"))
        self.assertIsNotNone(snapshot.get("catalyst_strength"))
        signals = {item["signal"] for item in evidence}
        self.assertIn("CATALYST_STRENGTH", signals)

    def test_ss_p2_structures_from_catalyst(self) -> None:
        payload = build_workspace_catalyst_payload(
            "BOXL",
            as_of_context={"replay_mode": "fixture"},
            prediction_cutoff=self.cutoff,
        )
        ss_p2 = build_ss_p2_structures_from_catalyst(payload)
        self.assertIsNotNone(ss_p2.get("catalyst_strength"))
        self.assertIsNotNone(ss_p2.get("attention_feature"))

    def test_unavailable_payload_is_fail_closed(self) -> None:
        snapshot, evidence = build_cross_lane_snapshot_from_catalyst({"available": False})
        self.assertIsNone(snapshot)
        self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
