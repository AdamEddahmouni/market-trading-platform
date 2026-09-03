"""Offline unit tests for the Finviz screener universe resolver."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.finviz_screener import _to_export_url, parse_screener_tickers, resolve_universe


SAMPLE_SCREENER_CSV = (
    '"No.","Ticker","Company","Sector","Price","Volume"\n'
    '1,"AAPL","Apple Inc","Technology","291.2","1000"\n'
    '2,"TSLA","Tesla Inc","Consumer Cyclical","406.2","2000"\n'
    '3,"AAPL","Apple Inc","Technology","291.2","1000"\n'
    '4,"NVDA","NVIDIA Corp","Technology","206.2","3000"\n'
)


class ScreenerTests(unittest.TestCase):
    def test_parse_dedupes_and_orders(self) -> None:
        self.assertEqual(parse_screener_tickers(SAMPLE_SCREENER_CSV), ["AAPL", "TSLA", "NVDA"])

    def test_parse_empty(self) -> None:
        self.assertEqual(parse_screener_tickers(""), [])

    def test_to_export_url_rewrites_and_adds_auth(self) -> None:
        url = _to_export_url("https://elite.finviz.com/screener.ashx?v=111&s=ta_mostactive", "TOK")
        self.assertIn("export.ashx", url)
        self.assertNotIn("screener.ashx", url)
        self.assertIn("auth=TOK", url)
        self.assertIn("v=111", url)

    def test_resolve_static_source(self) -> None:
        settings = {"universe": {"source": "static", "fallback_tickers": ["spy", "qqq"], "max_tickers": 5}}
        self.assertEqual(resolve_universe(settings), ["SPY", "QQQ"])

    def test_resolve_falls_back_without_token(self) -> None:
        settings = {
            "universe": {"source": "finviz_screener", "fallback_tickers": ["AAPL"], "max_tickers": 5},
            "chain": {"finviz": {"auth_token_env": "DEFINITELY_UNSET_TOKEN_ENV_123"}},
        }
        self.assertEqual(resolve_universe(settings), ["AAPL"])


if __name__ == "__main__":
    unittest.main()
