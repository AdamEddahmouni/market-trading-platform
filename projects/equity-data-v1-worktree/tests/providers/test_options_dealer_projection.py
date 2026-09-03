"""Tests for options dealer workspace projection (O6 wiring)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402

_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


class OptionsDealerProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=_CUTOFF))

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original)

    def test_biya_workspace_includes_dealer_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["dealer_position_available"])
        dealer = payload["dealer_snapshot"]
        self.assertTrue(dealer["available"])
        self.assertEqual(dealer["method"], "OI_GAMMA_PROXY_V1")
        self.assertIn("estimated_dealer_gamma", dealer)
        self.assertIn("gamma_regime", dealer)

    def test_nvda_chain_only_dealer_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertFalse(payload["available"])
        self.assertTrue(payload["chain_available"])
        self.assertTrue(payload["dealer_position_available"])
        self.assertTrue(payload["dealer_snapshot"]["available"])


if __name__ == "__main__":
    unittest.main()
