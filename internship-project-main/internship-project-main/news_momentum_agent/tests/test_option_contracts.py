"""Tests for 0DTE contract selection helpers."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.option_contracts import _calendar_dte, lookup_atm_contract, select_atm_contract


class OptionContracts0DTETests(unittest.TestCase):
    def test_calendar_dte_today_is_zero(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, 0)
        self.assertEqual(_calendar_dte("2026-07-15", now), 0)
        self.assertEqual(_calendar_dte("2026-07-16", now), 1)
        self.assertEqual(_calendar_dte("2026-07-14", now), -1)

    def test_max_dte_zero_rejects_weekly(self) -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260722C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        puts = pd.DataFrame()

        stock = MagicMock()
        stock.options = ["2026-07-22", "2026-07-29"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()
        stock.option_chain.return_value = MagicMock(calls=frame, puts=puts)

        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=datetime(2026, 7, 15, 12, 0, 0)):
                with patch(
                    "agent.option_contracts._lookup_from_alpaca",
                    return_value={
                        "outcome": "no_credentials",
                        "contract": None,
                        "error": "missing keys",
                        "error_kind": "no_credentials",
                    },
                ):
                    result = select_atm_contract("SPY", "call", 560.0, max_dte=0)
                    lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0)
        self.assertIsNone(result)
        self.assertEqual(lookup["status"], "alpaca_no_credentials")
        self.assertEqual(lookup["nearest_listed_dte"], 7)

    def test_max_dte_zero_picks_today(self) -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260715C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        stock = MagicMock()
        stock.options = ["2026-07-15", "2026-07-22"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()
        stock.option_chain.return_value = MagicMock(calls=frame, puts=pd.DataFrame())

        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=datetime(2026, 7, 15, 12, 0, 0)):
                result = select_atm_contract("SPY", "call", 560.0, max_dte=0)
                lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["dte"], 0)
        self.assertEqual(result["expiration"], "2026-07-15")
        self.assertEqual(lookup["provider"], "yfinance")

    def test_alpaca_fallback_when_yahoo_omits_today(self) -> None:
        """Regression: SPY weekday 0DTE must surface via Alpaca when Yahoo list starts tomorrow."""
        import pandas as pd

        stock = MagicMock()
        stock.options = ["2026-07-16", "2026-07-17"]  # tomorrow+, no today
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame({"Close": [560.0]})
        stock.option_chain.side_effect = ValueError("Expiration not found")

        alpaca_contract = {
            "contract_symbol": "SPY260715C00560000",
            "underlying": "SPY",
            "side": "call",
            "strike": 560.0,
            "expiration": "2026-07-15",
            "premium": 2.5,
            "spot_price": 560.0,
            "dte": 0,
            "bid": 2.4,
            "ask": 2.6,
            "last": 2.5,
            "has_nbbo": True,
            "quote_as_of": "2026-07-15T16:00:00+00:00",
            "provider": "alpaca_fallback",
        }

        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=datetime(2026, 7, 15, 12, 0, 0)):
                with patch(
                    "agent.option_contracts._lookup_from_alpaca",
                    return_value={
                        "outcome": "ok",
                        "contract": alpaca_contract,
                        "error": None,
                        "error_kind": None,
                    },
                ):
                    lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0)

        self.assertEqual(lookup["status"], "ok")
        self.assertEqual(lookup["provider"], "alpaca_fallback")
        assert lookup["contract"] is not None
        self.assertEqual(lookup["contract"]["expiration"], "2026-07-15")
        self.assertEqual(lookup["nearest_listed_dte"], 0)
        self.assertIn("alpaca_fallback", lookup["detail"])

    def test_alpaca_error_not_collapsed_to_no_chain(self) -> None:
        """Rate-limit/auth failures must not look like confirmed empty 0DTE."""
        import pandas as pd

        stock = MagicMock()
        stock.options = ["2026-07-16", "2026-07-17"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame({"Close": [560.0]})
        stock.option_chain.side_effect = ValueError("Expiration not found")

        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=datetime(2026, 7, 15, 12, 0, 0)):
                with patch(
                    "agent.option_contracts._lookup_from_alpaca",
                    return_value={
                        "outcome": "error",
                        "contract": None,
                        "error": "429 Too Many Requests",
                        "error_kind": "rate_limit",
                    },
                ):
                    lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0)

        self.assertEqual(lookup["status"], "alpaca_error")
        self.assertEqual(lookup["alpaca_error_kind"], "rate_limit")
        self.assertNotEqual(lookup["status"], "no_0dte_chain_exists")
        self.assertIn("NOT confirmed missing", lookup["detail"])

    def test_alpaca_confirmed_empty_distinct_from_error(self) -> None:
        import pandas as pd

        stock = MagicMock()
        stock.options = ["2026-07-16"]
        stock.fast_info = {"lastPrice": 100.0}
        stock.history.return_value = pd.DataFrame({"Close": [100.0]})
        stock.option_chain.side_effect = ValueError("Expiration not found")

        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=datetime(2026, 7, 15, 12, 0, 0)):
                with patch(
                    "agent.option_contracts._lookup_from_alpaca",
                    return_value={
                        "outcome": "confirmed_empty",
                        "contract": None,
                        "error": None,
                        "error_kind": None,
                    },
                ):
                    lookup = lookup_atm_contract("AAPL", "call", 100.0, max_dte=0)

        self.assertEqual(lookup["status"], "alpaca_confirmed_empty")
        self.assertEqual(lookup["provider"], "alpaca_confirmed_empty")


if __name__ == "__main__":
    unittest.main()
