from __future__ import annotations

import os
import unittest


@unittest.skipUnless(os.environ.get("IMP_NASDAQ_REGSHO_LIVE") == "1", "opt-in live Nasdaq Reg SHO tests")
class LiveNasdaqSmokeTests(unittest.TestCase):
    def test_current_or_biya_historical_file(self) -> None:
        from market_platform_foundation.nasdaq_regsho.live import fetch_threshold_observations
        from market_platform_foundation.nasdaq_regsho.transport import NasdaqTransport
        from market_platform_foundation.short_intelligence.identity import SymbolMap
        from pathlib import Path

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "short_intelligence" / "symbol_map.json"
        )
        transport = NasdaqTransport()
        rows = fetch_threshold_observations(
            transport, mapping, "2026-07-28", requested_symbols=("BIYA",)
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0].provider_symbol, "BIYA")
        self.assertTrue(rows[0].currently_threshold)
        self.assertTrue(rows[0].content_hash)
