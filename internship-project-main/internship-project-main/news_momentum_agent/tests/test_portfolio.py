"""Tests for auto paper portfolio execution."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.eod_flatten_state import EOD_FLAT_PATH
from agent.portfolio import (
    EXECUTIONS_PATH,
    OPTION_MULTIPLIER,
    PORTFOLIO_PATH,
    default_portfolio,
    execute_decision,
    execute_options_decision,
    load_portfolio,
    manage_option_exits,
    save_portfolio,
)


class PortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self._backup_portfolio = PORTFOLIO_PATH.read_text(encoding="utf-8") if PORTFOLIO_PATH.exists() else None
        self._backup_executions = EXECUTIONS_PATH.read_text(encoding="utf-8") if EXECUTIONS_PATH.exists() else None
        self._backup_eod = EOD_FLAT_PATH.read_text(encoding="utf-8") if EOD_FLAT_PATH.exists() else None
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_PATH.write_text(json.dumps(default_portfolio(100000)), encoding="utf-8")
        EXECUTIONS_PATH.write_text("[]", encoding="utf-8")
        EOD_FLAT_PATH.unlink(missing_ok=True)

    def tearDown(self) -> None:
        if self._backup_portfolio is None:
            PORTFOLIO_PATH.unlink(missing_ok=True)
        else:
            PORTFOLIO_PATH.write_text(self._backup_portfolio, encoding="utf-8")
        if self._backup_executions is None:
            EXECUTIONS_PATH.unlink(missing_ok=True)
        else:
            EXECUTIONS_PATH.write_text(self._backup_executions, encoding="utf-8")
        if self._backup_eod is None:
            EOD_FLAT_PATH.unlink(missing_ok=True)
        else:
            EOD_FLAT_PATH.write_text(self._backup_eod, encoding="utf-8")

    def test_buy_opens_long(self) -> None:
        settings = {"trading": {"auto_execute": True, "starting_cash": 100000, "max_positions": 5, "allow_short": True}}
        result = execute_decision("TEST", "BUY", 10.0, "unit test buy", settings)
        self.assertIsNotNone(result)
        portfolio = load_portfolio(settings)
        self.assertIn("TEST", portfolio.get("positions", {}))
        self.assertGreater(float(portfolio["positions"]["TEST"]["qty"]), 0)

    def test_sell_flips_to_short_when_allowed(self) -> None:
        settings = {"trading": {"auto_execute": True, "starting_cash": 100000, "max_positions": 5, "allow_short": True}}
        execute_decision("TEST", "BUY", 10.0, "open", settings)
        execute_decision("TEST", "SELL", 11.0, "flip", settings)
        portfolio = load_portfolio(settings)
        pos = portfolio.get("positions", {}).get("TEST", {})
        self.assertLess(float(pos.get("qty", 0)), 0)

    def test_sell_closes_long_when_short_disabled(self) -> None:
        settings = {"trading": {"auto_execute": True, "starting_cash": 100000, "max_positions": 5, "allow_short": False}}
        execute_decision("TEST", "BUY", 10.0, "open", settings)
        execute_decision("TEST", "SELL", 11.0, "close", settings)
        portfolio = load_portfolio(settings)
        self.assertNotIn("TEST", portfolio.get("positions", {}))
        self.assertGreater(float(portfolio.get("realized_pnl", 0.0)), 0.0)

    def test_review_does_not_trade(self) -> None:
        settings = {"trading": {"auto_execute": True, "starting_cash": 100000, "max_positions": 5, "allow_short": True}}
        result = execute_decision("TEST", "REVIEW", 10.0, "no trade", settings)
        self.assertIsNone(result)

    def _seed_open_call(self, settings: dict, entry: float = 1.0, expiration: str = "2026-07-15") -> None:
        portfolio = load_portfolio(settings)
        portfolio["positions"]["SPYCALL"] = {
            "instrument_type": "option",
            "underlying": "SPY",
            "contract_symbol": "SPYCALL",
            "side": "call",
            "contracts": 2,
            "entry_price": entry,
            "mark_price": entry,
            "strike": 560.0,
            "expiration": expiration,
            "opened_at": "2026-07-15T14:00:00+00:00",
        }
        portfolio["cash"] = float(portfolio["cash"]) - 2 * entry * OPTION_MULTIPLIER
        save_portfolio(portfolio)

    def test_take_profit_exit(self) -> None:
        settings = {
            "trading": {
                "starting_cash": 100000,
                "options_exits": {"take_profit_pct": 0.40, "stop_loss_pct": 0.30, "eod_flatten_et": "15:45"},
            }
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark", return_value=1.40):
            fills = manage_option_exits(settings, now_et=datetime(2026, 7, 15, 12, 0, 0))
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["reason"], "take_profit")
        portfolio = load_portfolio(settings)
        self.assertEqual(portfolio.get("positions"), {})
        self.assertAlmostEqual(float(portfolio.get("realized_pnl", 0.0)), 80.0, places=2)

    def test_stop_loss_exit(self) -> None:
        settings = {
            "trading": {
                "starting_cash": 100000,
                "options_exits": {"take_profit_pct": 0.40, "stop_loss_pct": 0.30, "eod_flatten_et": "15:45"},
            }
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark", return_value=0.70):
            fills = manage_option_exits(settings, now_et=datetime(2026, 7, 15, 12, 0, 0))
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["reason"], "stop_loss")

    def test_eod_flatten_exit(self) -> None:
        settings = {
            "trading": {
                "starting_cash": 100000,
                "options_exits": {"take_profit_pct": 0.40, "stop_loss_pct": 0.30, "eod_flatten_et": "15:45"},
            }
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark", return_value=1.05):
            fills = manage_option_exits(settings, now_et=datetime(2026, 7, 15, 15, 50, 0))
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["reason"], "eod_flatten")

    def test_sell_closes_call_without_opening_put(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
            },
            "execution": {
                "market_hours_only": False,
                "exit_on_signal_flip": True,
                "min_hold_minutes_before_flip": 0,
                "flip_min_confidence": 50,
            },
            "_runtime": {"portfolio_reconciled": True},
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark", return_value=1.10):
            with patch("agent.portfolio.select_atm_contract") as select_mock:
                result = execute_options_decision(
                    "SPY",
                    "SELL",
                    560.0,
                    "flip",
                    settings,
                    option_side="put",
                    signal_confidence=90,
                )
                select_mock.assert_not_called()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.get("action"), "close_only")
        portfolio = load_portfolio(settings)
        self.assertEqual(portfolio.get("positions"), {})

    def test_reverse_signal_holds_when_flip_disabled(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
            },
            "execution": {"market_hours_only": False, "exit_on_signal_flip": False},
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark") as mark_mock:
            result = execute_options_decision("SPY", "SELL", 560.0, "ignore reverse", settings, option_side="put")
            mark_mock.assert_not_called()
        self.assertEqual(result.get("action"), "hold")
        self.assertIn("SPYCALL", load_portfolio(settings).get("positions", {}))

    def test_same_side_signal_holds_without_flip(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
            },
            "execution": {"market_hours_only": False},
        }
        self._seed_open_call(settings, entry=1.0, expiration="2026-07-15")
        with patch("agent.portfolio.fetch_option_mark") as mark_mock:
            with patch("agent.portfolio.select_atm_contract") as select_mock:
                result = execute_options_decision("SPY", "BUY", 560.0, "reaffirm", settings, option_side="call")
                mark_mock.assert_not_called()
                select_mock.assert_not_called()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.get("action"), "hold")
        portfolio = load_portfolio(settings)
        self.assertIn("SPYCALL", portfolio.get("positions", {}))

    def test_no_new_open_after_eod_flatten_time(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
                "options_exits": {"eod_flatten_et": "15:45"},
            },
            "execution": {"market_hours_only": True},
        }
        with patch("agent.portfolio.select_atm_contract") as select_mock:
            result = execute_options_decision(
                "IWM",
                "SELL",
                220.0,
                "Path B near-expiry options scan",
                settings,
                option_side="put",
                now_et=datetime(2026, 7, 16, 15, 50, 0),
            )
            select_mock.assert_not_called()
        self.assertEqual(result.get("action"), "past_eod")
        self.assertEqual(load_portfolio(settings).get("positions"), {})

    def test_no_new_open_when_options_market_closed(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
            },
            "execution": {"market_hours_only": True},
        }
        with patch("agent.portfolio.select_atm_contract") as select_mock:
            result = execute_options_decision(
                "IWM",
                "SELL",
                220.0,
                "after hours",
                settings,
                option_side="put",
                now_et=datetime(2026, 7, 16, 17, 30, 0),
            )
            select_mock.assert_not_called()
        self.assertEqual(result.get("action"), "outside_rth")


if __name__ == "__main__":
    unittest.main()
