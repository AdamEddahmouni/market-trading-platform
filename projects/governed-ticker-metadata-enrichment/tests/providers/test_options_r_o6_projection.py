"""Tests for Options R-O6 workspace projection wiring (O10-S2)."""

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


class OptionsRO6ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=_CUTOFF))

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original)

    def test_nvda_workspace_includes_r_o6_research(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertIn("r_o6_research", payload)
        r_o6 = payload["r_o6_research"]
        self.assertEqual(r_o6.get("gate_milestone"), "R-O6")
        if r_o6.get("available"):
            self.assertIn("p_vs_q_edge", r_o6)
            self.assertIn("delta_hedged", r_o6)
            self.assertTrue(r_o6.get("not_trade_signal"))

    def test_biya_workspace_includes_r_o6_research(self) -> None:
        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertIn("r_o6_research", payload)
        self.assertEqual(payload["r_o6_research"].get("gate_milestone"), "R-O6")

    def test_unknown_symbol_r_o6_fail_closed(self) -> None:
        payload = build_workspace_options_payload(
            "ZZZZ",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        r_o6 = payload.get("r_o6_research")
        if r_o6 is not None:
            self.assertFalse(r_o6.get("available"))


if __name__ == "__main__":
    unittest.main()
