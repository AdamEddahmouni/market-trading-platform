from __future__ import annotations

import os
import unittest


@unittest.skipUnless(
    os.environ.get("IMP_FINRA_OTC_THRESHOLD_LIVE") == "1",
    "opt-in live FINRA OTC threshold tests",
)
class LiveFinraOtcThresholdSmokeTests(unittest.TestCase):
    def test_recent_threshold_list(self) -> None:
        from market_platform_foundation.finra.auth import FinraTokenManager
        from market_platform_foundation.finra.client_config import load_finra_credentials
        from market_platform_foundation.finra.otc_threshold import normalize_otc_threshold_rows
        from market_platform_foundation.finra.query import query_otc_threshold
        from market_platform_foundation.finra.transport import FinraTransport
        from market_platform_foundation.short_intelligence.identity import SymbolMap
        from pathlib import Path

        mapping = SymbolMap.from_path(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "short_intelligence" / "threshold_symbol_map.json"
        )
        creds = load_finra_credentials()
        transport = FinraTransport(FinraTokenManager(creds))
        response = query_otc_threshold(transport, trade_date="2026-08-18", limit=10)
        rows = normalize_otc_threshold_rows(
            response.records,
            symbol_map=mapping,
            observed_time="2026-08-20T08:00:00Z",
            retrieved_time="2026-08-20T08:00:00Z",
            finra_request_id=response.request_id,
        )
        self.assertGreaterEqual(len(rows), 1)
        sample = rows[0]
        self.assertTrue(sample.source_sro == "FINRA_OTC")
        self.assertIn(sample.reg_sho_threshold_flag, {"Y", "N", None})
        self.assertIn(sample.rule_4320_flag, {"Y", "N", None})
