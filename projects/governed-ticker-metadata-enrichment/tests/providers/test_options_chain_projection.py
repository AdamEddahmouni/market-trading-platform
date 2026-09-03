"""Tests for options chain workspace projection (O1 wiring)."""

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


class OptionsChainProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=_CUTOFF))

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original)

    def test_biya_workspace_includes_chain_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["chain_available"])
        snapshot = payload["chain_snapshot"]
        self.assertTrue(snapshot["available"])
        self.assertGreater(snapshot["contract_count"], 0)
        self.assertEqual(snapshot["underlying_id"], "BIYA")

    def test_nvda_workspace_chain_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertFalse(payload["available"])
        self.assertTrue(payload["chain_available"])
        self.assertEqual(payload["chain_snapshot"]["contract_count"], 2)

    def test_unknown_symbol_chain_unavailable(self) -> None:
        payload = build_workspace_options_payload(
            "ZZZZ",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertFalse(payload["available"])


if __name__ == "__main__":
    unittest.main()
