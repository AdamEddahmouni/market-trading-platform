from __future__ import annotations

import os
import unittest


@unittest.skipUnless(os.environ.get("IMP_CBOE_REGSHO_LIVE") == "1", "opt-in live Cboe Reg SHO tests")
class LiveCboeSmokeTests(unittest.TestCase):
    def test_latest_date_and_fetch(self) -> None:
        from market_platform_foundation.cboe_regsho.live import fetch_threshold_observations
        from market_platform_foundation.cboe_regsho.transport import CboeTransport
        from market_platform_foundation.short_intelligence.identity import SymbolMap
        from pathlib import Path

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "short_intelligence" / "threshold_symbol_map.json"
        )
        transport = CboeTransport()
        latest = transport.fetch_latest_date()
        self.assertRegex(latest, r"^\d{4}-\d{2}-\d{2}$")
        holidays = transport.fetch_holidays()
        self.assertGreater(len(holidays), 10)
        rows = fetch_threshold_observations(transport, mapping, latest, requested_symbols=None)
        self.assertIsInstance(rows, tuple)
