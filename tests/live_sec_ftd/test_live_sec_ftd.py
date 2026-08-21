from __future__ import annotations

import os
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("IMP_SEC_FTD_LIVE") == "1", "opt-in live SEC FTD tests")
class LiveSecFtdSmokeTests(unittest.TestCase):
    def test_discovery_parse_and_biya_probe(self) -> None:
        from market_platform_foundation.sec_ftd.discovery import latest_discovered_period
        from market_platform_foundation.sec_ftd.live import fetch_ftd_observations, transport_from_env
        from market_platform_foundation.sec_ftd.transport import FtdTransport
        from market_platform_foundation.short_intelligence.identity import SymbolMap

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "short_intelligence"
            / "symbol_map.json"
        )
        sec = transport_from_env()
        latest = latest_discovered_period(sec)
        self.assertIsNotNone(latest)
        assert latest is not None
        transport = FtdTransport(sec)
        rows = fetch_ftd_observations(transport, mapping, period_key=latest.period.period_key, requested_symbols=("BIYA",))
        self.assertGreaterEqual(len(rows), 1)
        sample = rows[0]
        self.assertEqual(sample.raw_symbol, "BIYA")
        self.assertTrue(sample.cusip)
        self.assertGreater(sample.ftd_balance_quantity, 0)
        self.assertEqual(sample.observation_family.value, "FAILS_TO_DELIVER")
        self.assertTrue(sample.clocks.get("available_time"))
