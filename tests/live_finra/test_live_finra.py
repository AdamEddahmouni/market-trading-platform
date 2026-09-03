from __future__ import annotations

import os
import unittest


@unittest.skipUnless(os.environ.get("IMP_FINRA_LIVE") == "1", "opt-in live FINRA tests")
class LiveFinraSmokeTests(unittest.TestCase):
    def test_oauth_and_tiny_queries(self) -> None:
        from market_platform_foundation.finra.live import (
            probe_short_interest,
            probe_short_sale_volume,
            transport_from_env,
        )
        from market_platform_foundation.short_intelligence.identity import SymbolMap
        from pathlib import Path

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "short_intelligence" / "symbol_map.json"
        )
        transport = transport_from_env()
        interest = probe_short_interest(transport, mapping, "AAPL")
        volume = probe_short_sale_volume(transport, mapping, "AAPL")
        self.assertIsInstance(interest, tuple)
        self.assertIsInstance(volume, tuple)
        self.assertGreaterEqual(transport.request_count, 1)
