"""Unit tests for Finviz Elite screener integration."""

from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from screener.finviz_screener import (
    build_elite_export_url,
    parse_elite_csv_rows,
    screen_quiet_stocks,
)


SAMPLE_CSV = """Ticker,Company,Sector,Industry,Country,Market Cap,P/E,Price,Change,Volume
AAPL,Apple Inc,Technology,Consumer Electronics,USA,2.90T,28.50,198.50,0.12%,45.2M
TINY,Tiny Co,Healthcare,Biotech,USA,150.00M,-,1.25,-0.20%,1.2M
LOUD,Loud Co,Energy,Oil,USA,800.00M,12.00,4.50,2.50%,900.00K
"""


class FinvizEliteScreenerTests(unittest.TestCase):
    """Validate CSV parsing, URL building, and local filtering."""

    def test_parse_elite_csv_rows(self) -> None:
        rows = parse_elite_csv_rows(SAMPLE_CSV)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["Ticker"], "AAPL")
        self.assertEqual(rows[1]["Company"], "Tiny Co")

    def test_build_elite_export_url_includes_auth(self) -> None:
        url = build_elite_export_url(
            token="test-token",
            screener_cfg={"elite": {"filters": "ind_stocksonly,cap_smallunder"}},
        )
        self.assertIn("auth=test-token", url)
        self.assertIn("cap_smallunder", url)

    def test_screen_quiet_stocks_filters_local(self) -> None:
        rows = parse_elite_csv_rows(SAMPLE_CSV)
        meta = {
            "provider": "elite",
            "scrape_ok": True,
            "scrape_error": None,
            "raw": len(rows),
            "elapsed_sec": None,
        }

        with unittest.mock.patch(
            "screener.finviz_screener.fetch_finviz_rows_with_meta",
            return_value=(rows, meta),
        ):
            matches = screen_quiet_stocks(
                price_change_min=-0.5,
                price_change_max=0.5,
                market_cap_max_billion=2.0,
                screener_cfg={"provider": "elite"},
            )
        tickers = {row["ticker"] for row in matches}
        self.assertIn("TINY", tickers)
        self.assertNotIn("LOUD", tickers)


if __name__ == "__main__":
    unittest.main()
