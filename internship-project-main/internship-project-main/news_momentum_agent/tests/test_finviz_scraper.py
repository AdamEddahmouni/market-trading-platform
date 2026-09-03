"""Unit tests for fast Finviz HTML scraper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from screener.finviz_screener import (
    build_quiet_filter_codes,
    fetch_finviz_rows,
    parse_screener_html,
    screen_path_a_universe_with_stats,
    screen_quiet_stocks,
)


SAMPLE_HTML = """
<html><body>
<select id="pageSelect"><option>1</option></select>
<table class="screener_table">
<tr><th>No.</th><th>Ticker</th><th>Company</th><th>Market Cap</th><th>Change</th><th>Volume</th><th>Avg Volume</th><th>Price</th></tr>
<tr><td>1</td><td>TINY</td><td>Tiny Co</td><td>150.00M</td><td>-0.20%</td><td>1.2M</td><td>400.00K</td><td>1.25</td></tr>
<tr><td>2</td><td>LOUD</td><td>Loud Co</td><td>800.00M</td><td>2.50%</td><td>900.00K</td><td>100.00K</td><td>4.50</td></tr>
</table>
</body></html>
"""

# Finviz currently renders ticker as first-letter icon link + full ticker link.
DOUBLED_TICKER_HTML = """
<html><body>
<table class="screener_table">
<tr><th>No.</th><th>Ticker</th><th>Company</th><th>Market Cap</th><th>Change</th><th>Volume</th><th>Avg Volume</th><th>Price</th></tr>
<tr>
  <td><a href="stock?t=PYPL&ty=c&p=d&b=1">1</a></td>
  <td>
    <a href="stock?t=PYPL&ty=c&p=d&b=1">P</a>
    <a href="stock?t=PYPL&ty=c&p=d&b=1">PYPL</a>
  </td>
  <td>PayPal Holdings Inc</td><td>65.00B</td><td>1.20%</td><td>12.0M</td><td>8.00M</td><td>62.50</td>
</tr>
<tr>
  <td><a href="stock?t=IBM&ty=c&p=d&b=1">2</a></td>
  <td>
    <a href="stock?t=IBM&ty=c&p=d&b=1">I</a>
    <a href="stock?t=IBM&ty=c&p=d&b=1">IBM</a>
  </td>
  <td>IBM</td><td>170.00B</td><td>-0.40%</td><td>5.0M</td><td>4.00M</td><td>180.00</td>
</tr>
</table>
</body></html>
"""


class FinvizScraperTests(unittest.TestCase):
    def test_parse_screener_html(self) -> None:
        rows, pages = parse_screener_html(SAMPLE_HTML)
        self.assertEqual(pages, 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Ticker"], "TINY")
        self.assertEqual(rows[0]["Company"], "Tiny Co")

    def test_parse_does_not_double_ticker_letter(self) -> None:
        rows, _ = parse_screener_html(DOUBLED_TICKER_HTML)
        self.assertEqual([row["Ticker"] for row in rows], ["PYPL", "IBM"])
        self.assertNotIn("PPYPL", [row["Ticker"] for row in rows])
        self.assertNotIn("IIBM", [row["Ticker"] for row in rows])

    def test_provider_scraper_never_calls_elite(self) -> None:
        with patch("screener.finviz_screener.fetch_finviz_rows_elite") as elite:
            with patch(
                "screener.finviz_screener.fetch_finviz_rows_scraper_with_meta",
                return_value=([{"Ticker": "AAA"}], {"provider": "scraper", "scrape_ok": True, "raw": 1}),
            ) as scraper:
                rows = fetch_finviz_rows(screener_cfg={"provider": "scraper"}, max_rows=10)
        elite.assert_not_called()
        scraper.assert_called_once()
        self.assertEqual(rows[0]["Ticker"], "AAA")

    def test_screen_quiet_stocks_includes_relative_volume(self) -> None:
        rows, _ = parse_screener_html(SAMPLE_HTML)
        meta = {
            "provider": "scraper",
            "scrape_ok": True,
            "scrape_error": None,
            "raw": len(rows),
            "elapsed_sec": 0.1,
        }
        with patch("screener.finviz_screener.fetch_finviz_rows_with_meta", return_value=(rows, meta)):
            matches = screen_quiet_stocks(
                price_change_min=-0.5,
                price_change_max=0.5,
                market_cap_max_billion=2.0,
                screener_cfg={"provider": "scraper"},
            )
        tickers = {row["ticker"]: row for row in matches}
        self.assertIn("TINY", tickers)
        self.assertNotIn("LOUD", tickers)
        self.assertIsNotNone(tickers["TINY"].get("relative_volume"))
        self.assertGreater(tickers["TINY"]["relative_volume"], 1.0)

    def test_mid_large_filter_codes_use_cap_midover_and_optionable(self) -> None:
        codes = build_quiet_filter_codes(
            market_cap_max_billion=None,
            market_cap_min_billion=2.0,
            require_optionable=True,
        )
        self.assertIn("cap_midover", codes)
        self.assertIn("sh_opt_option", codes)
        self.assertNotIn("cap_smallunder", codes)

    def test_path_a_universe_merges_small_and_mid_large(self) -> None:
        small_rows = [
            {
                "Ticker": "TINY",
                "Company": "Tiny Co",
                "Price": "1.25",
                "Change": "-0.20%",
                "Volume": "1.2M",
                "Average Volume": "400K",
                "Market Cap.": "150M",
            }
        ]
        mid_rows = [
            {
                "Ticker": "BIG",
                "Company": "Big Co",
                "Price": "85.0",
                "Change": "4.50%",
                "Volume": "8.0M",
                "Average Volume": "3.0M",
                "Market Cap.": "25B",
            }
        ]
        meta = {"provider": "scraper", "scrape_ok": True, "scrape_error": None, "raw": 1, "elapsed_sec": 0.1}

        def _fake_fetch(**kwargs):
            codes = str(kwargs.get("filter_codes") or "")
            if "cap_midover" in codes:
                return mid_rows, {**meta, "raw": len(mid_rows)}
            return small_rows, {**meta, "raw": len(small_rows)}

        with patch("screener.finviz_screener.fetch_finviz_rows_with_meta", side_effect=_fake_fetch):
            merged, stats = screen_path_a_universe_with_stats(
                price_change_min=-0.5,
                price_change_max=0.5,
                market_cap_max_billion=2.0,
                screener_cfg={
                    "provider": "scraper",
                    "include_mid_large_cap": True,
                    "mid_large": {
                        "market_cap_min_billion": 2,
                        "price_change_min": -8.0,
                        "price_change_max": 8.0,
                        "require_optionable": True,
                    },
                },
            )
        tickers = {row["ticker"]: row for row in merged}
        self.assertIn("TINY", tickers)
        self.assertIn("BIG", tickers)
        self.assertEqual(tickers["BIG"]["universe_tier"], "mid_large_catalyst")
        self.assertEqual(tickers["TINY"]["universe_tier"], "small_quiet")
        self.assertGreaterEqual(float(tickers["BIG"]["market_cap_billion"]), 2.0)
        self.assertEqual(stats["mid_large_count"], 1)
        self.assertEqual(stats["small_quiet_count"], 1)

    def test_path_a_watchlist_cap_keeps_both_tiers(self) -> None:
        def _row(ticker: str, cap: str, change: str) -> Dict[str, Any]:
            return {
                "Ticker": ticker,
                "Company": ticker,
                "Price": "10",
                "Change": change,
                "Volume": "2.0M",
                "Average Volume": "1.0M",
                "Market Cap.": cap,
            }

        small_rows = [_row(f"S{i}", "100M", "0.10%") for i in range(10)]
        mid_rows = [_row(f"M{i}", "20B", "3.00%") for i in range(10)]
        meta = {"provider": "scraper", "scrape_ok": True, "scrape_error": None, "raw": 10, "elapsed_sec": 0.1}

        def _fake_fetch(**kwargs):
            codes = str(kwargs.get("filter_codes") or "")
            if "cap_midover" in codes:
                return mid_rows, {**meta, "raw": len(mid_rows)}
            return small_rows, {**meta, "raw": len(small_rows)}

        with patch("screener.finviz_screener.fetch_finviz_rows_with_meta", side_effect=_fake_fetch):
            merged, stats = screen_path_a_universe_with_stats(
                price_change_min=-1.0,
                price_change_max=1.0,
                market_cap_max_billion=2.0,
                screener_cfg={
                    "provider": "scraper",
                    "include_mid_large_cap": True,
                    "max_watchlist_symbols": 5,
                    "small_quiet_watchlist_share": 0.4,
                    "mid_large": {
                        "market_cap_min_billion": 2,
                        "price_change_min": -8.0,
                        "price_change_max": 8.0,
                        "require_optionable": True,
                    },
                },
            )
        self.assertEqual(len(merged), 5)
        tiers = {row["universe_tier"] for row in merged}
        self.assertIn("mid_large_catalyst", tiers)
        self.assertIn("small_quiet", tiers)
        self.assertGreaterEqual(stats["small_quiet_kept"], 1)
        self.assertGreaterEqual(stats["mid_large_kept"], 1)


if __name__ == "__main__":
    unittest.main()
