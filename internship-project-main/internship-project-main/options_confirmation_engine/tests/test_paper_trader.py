"""Offline unit tests for simulated paper trading."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import options_engine.paper_trader as pt


SETTINGS = {
    "trading": {
        "enabled": True,
        "starting_cash": 100000,
        "max_positions": 10,
        "allow_short": True,
        "exit_on_neutral": True,
    },
    "runtime": {"state_write_atomic": False},
}


def _signal(ticker: str, bias: str, price: float) -> dict:
    return {"ticker": ticker, "options_bias": bias, "spot_price": price, "options_score": 70}


class PaperTraderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.port_path = Path(self.tmp.name) / "portfolio.json"
        self.exec_path = Path(self.tmp.name) / "executions.json"
        self.patcher_port = patch.object(pt, "PORTFOLIO_PATH", self.port_path)
        self.patcher_exec = patch.object(pt, "EXECUTIONS_PATH", self.exec_path)
        self.patcher_port.start()
        self.patcher_exec.start()

    def tearDown(self) -> None:
        self.patcher_port.stop()
        self.patcher_exec.stop()
        self.tmp.cleanup()

    def test_open_long_on_bullish(self) -> None:
        result = pt.update([_signal("AAPL", "bullish", 100.0)], SETTINGS, request_id="t1")
        portfolio = result["portfolio"]
        self.assertIn("AAPL", portfolio["positions"])
        self.assertGreater(portfolio["positions"]["AAPL"]["qty"], 0)
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["fills"][0]["action"], "open")

    def test_open_short_on_bearish(self) -> None:
        result = pt.update([_signal("TSLA", "bearish", 200.0)], SETTINGS, request_id="t2")
        pos = result["portfolio"]["positions"]["TSLA"]
        self.assertLess(pos["qty"], 0)
        self.assertEqual(pos["side"], "short")

    def test_exit_on_neutral(self) -> None:
        pt.update([_signal("AAPL", "bullish", 100.0)], SETTINGS, request_id="t3")
        result = pt.update([_signal("AAPL", "neutral", 105.0)], SETTINGS, request_id="t4")
        self.assertNotIn("AAPL", result["portfolio"]["positions"])
        actions = [f["action"] for f in result["fills"]]
        self.assertIn("close", actions)

    def test_flip_long_to_short(self) -> None:
        pt.update([_signal("NVDA", "bullish", 100.0)], SETTINGS, request_id="t5")
        result = pt.update([_signal("NVDA", "bearish", 100.0)], SETTINGS, request_id="t6")
        pos = result["portfolio"]["positions"]["NVDA"]
        self.assertLess(pos["qty"], 0)
        actions = [f["action"] for f in result["fills"]]
        self.assertIn("close", actions)
        self.assertIn("open", actions)

    def test_short_profit_when_price_falls(self) -> None:
        pt.update([_signal("XYZ", "bearish", 100.0)], SETTINGS, request_id="t7")
        result = pt.update([_signal("XYZ", "neutral", 90.0)], SETTINGS, request_id="t8")
        self.assertGreater(result["portfolio"]["realized_pnl"], 0)

    def test_signed_share_equity_math(self) -> None:
        portfolio = pt.default_portfolio(100000)
        portfolio["cash"] = 110000
        portfolio["positions"]["XYZ"] = {"qty": -10, "entry_price": 100.0, "side": "short"}
        equity = pt.compute_equity(portfolio, {"XYZ": 90.0})
        self.assertAlmostEqual(equity, 109100.0)

    def test_respects_max_positions(self) -> None:
        settings = dict(SETTINGS)
        settings["trading"] = dict(SETTINGS["trading"])
        settings["trading"]["max_positions"] = 1
        pt.update([_signal("AAPL", "bullish", 100.0)], settings, request_id="t9")
        result = pt.update([_signal("TSLA", "bullish", 200.0)], settings, request_id="t10")
        self.assertIn("AAPL", result["portfolio"]["positions"])
        self.assertNotIn("TSLA", result["portfolio"]["positions"])


if __name__ == "__main__":
    unittest.main()
