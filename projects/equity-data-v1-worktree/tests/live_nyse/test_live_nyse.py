from __future__ import annotations

import os
import unittest


@unittest.skipUnless(os.environ.get("IMP_NYSE_REGSHO_LIVE") == "1", "opt-in live NYSE Reg SHO tests")
class LiveNyseSmokeTests(unittest.TestCase):
    def test_discover_markets_and_fetch_recent(self) -> None:
        from market_platform_foundation.nyse_regsho.live import fetch_threshold_observations
        from market_platform_foundation.nyse_regsho.transport import NyseTransport
        from market_platform_foundation.short_intelligence.identity import SymbolMap
        from pathlib import Path

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "short_intelligence" / "threshold_symbol_map.json"
        )
        transport = NyseTransport()
        markets = transport.discover_markets()
        self.assertIn("NYSE", markets)
        self.assertIn("NYSE American", markets)
        self.assertIn("NYSE Arca", markets)
        for market in markets:
            rows = fetch_threshold_observations(
                transport, mapping, "2026-08-19", market=market, requested_symbols=None
            )
            self.assertIsInstance(rows, tuple)
