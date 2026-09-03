"""Tests for Path B expiry screener seed universe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from screener.expiry_screener import merge_seed_tickers


class ExpiryScreenerSeedTests(unittest.TestCase):
    def test_zero_dte_seeds_spy_universe(self) -> None:
        rows = merge_seed_tickers([], {"max_dte": 0})
        tickers = [row["ticker"] for row in rows]
        self.assertIn("SPY", tickers)
        self.assertIn("QQQ", tickers)

    def test_seed_does_not_duplicate_existing(self) -> None:
        existing = [{"ticker": "SPY", "source": "expiry"}]
        rows = merge_seed_tickers(existing, {"max_dte": 0, "seed_tickers": ["SPY", "QQQ"]})
        self.assertEqual(sum(1 for row in rows if row["ticker"] == "SPY"), 1)
        self.assertIn("QQQ", [row["ticker"] for row in rows])

    def test_non_zero_dte_without_config_skips_default_seed(self) -> None:
        rows = merge_seed_tickers([], {"max_dte": 14})
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
