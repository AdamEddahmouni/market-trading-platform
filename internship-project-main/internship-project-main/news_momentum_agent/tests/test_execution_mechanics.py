"""Regression tests for churn / market-hours / stale-quote / EOD summary fixes."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.eod_flatten_state import EOD_FLAT_PATH, mark_flattened, already_flattened
from agent.eod_summary import build_eod_summary
from agent.flip_guard import FLIP_AUDIT_PATH, FLIP_COOLDOWN_PATH
from agent.paper_trader import TRADE_JSON_PATH, append_paper_trade_entry, templated_log_why
from agent.portfolio import (
    EXECUTIONS_PATH,
    OPTION_MULTIPLIER,
    PORTFOLIO_PATH,
    default_portfolio,
    execute_options_decision,
    load_portfolio,
    manage_option_exits,
    save_portfolio,
)
from agent.quote_sanity import QUOTE_SANITY_PATH, check_and_record_quote
from agent.path_b_universe_health import HEALTH_PATH as PATH_B_HEALTH, update_universe_health
from screener.expiry_screener import screen_expiry_candidates_with_stats


ET = ZoneInfo("America/New_York")


class ExecutionMechanicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._backs = {}
        for path in (
            PORTFOLIO_PATH,
            EXECUTIONS_PATH,
            FLIP_COOLDOWN_PATH,
            FLIP_AUDIT_PATH,
            EOD_FLAT_PATH,
            QUOTE_SANITY_PATH,
            PATH_B_HEALTH,
            TRADE_JSON_PATH,
        ):
            self._backs[path] = path.read_text(encoding="utf-8") if path.exists() else None
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_PATH.write_text(json.dumps(default_portfolio(100000)), encoding="utf-8")
        EXECUTIONS_PATH.write_text("[]", encoding="utf-8")
        for path in (FLIP_COOLDOWN_PATH, FLIP_AUDIT_PATH, EOD_FLAT_PATH, QUOTE_SANITY_PATH, PATH_B_HEALTH):
            path.unlink(missing_ok=True)
        TRADE_JSON_PATH.write_text("[]", encoding="utf-8")

    def tearDown(self) -> None:
        for path, content in self._backs.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(content, encoding="utf-8")

    def _seed_call(self, opened_at: str = "2026-07-17T14:00:00+00:00") -> None:
        portfolio = load_portfolio({"trading": {"starting_cash": 100000}})
        portfolio["positions"]["SPYCALL"] = {
            "instrument_type": "option",
            "underlying": "SPY",
            "contract_symbol": "SPYCALL",
            "side": "call",
            "contracts": 2,
            "entry_price": 1.0,
            "mark_price": 1.0,
            "strike": 560.0,
            "expiration": "2026-07-17",
            "opened_at": opened_at,
        }
        portfolio["cash"] = float(portfolio["cash"]) - 2 * 1.0 * OPTION_MULTIPLIER
        save_portfolio(portfolio)

    def test_flip_oscillation_does_not_churn(self) -> None:
        settings = {
            "trading": {
                "auto_execute": True,
                "instrument": "options",
                "options_max_dte": 0,
                "starting_cash": 100000,
                "max_positions": 5,
                "options_exits": {"eod_flatten_et": "15:45"},
            },
            "execution": {
                "market_hours_only": False,
                "no_post_1545_opens": False,
                "exit_on_signal_flip": True,
                "min_hold_minutes_before_flip": 8,
                "flip_min_confidence": 70,
                "flip_reentry_cooldown_minutes": 30,
                "require_live_nbbo": False,
            },
            "risk": {"enabled": False},
            "_runtime": {"portfolio_reconciled": True},
        }
        self._seed_call(opened_at=datetime.now(timezone.utc).isoformat())
        # Immediate reverse with high confidence — still blocked by min_hold.
        with patch("agent.portfolio.fetch_option_mark", return_value=1.05):
            r1 = execute_options_decision(
                "SPY", "SELL", 560.0, "osc1", settings, option_side="put", signal_confidence=95
            )
        self.assertEqual(r1.get("action"), "hold")
        self.assertIn("min_hold", str(r1.get("flip_reason")))
        self.assertIn("SPYCALL", load_portfolio(settings)["positions"])

        # Age the position past min hold but fail hysteresis.
        portfolio = load_portfolio(settings)
        portfolio["positions"]["SPYCALL"]["opened_at"] = "2026-07-17T10:00:00+00:00"
        save_portfolio(portfolio)
        with patch("agent.portfolio.fetch_option_mark", return_value=1.05):
            r2 = execute_options_decision(
                "SPY", "SELL", 560.0, "osc2", settings, option_side="put", signal_confidence=40
            )
        self.assertEqual(r2.get("action"), "hold")
        self.assertEqual(r2.get("flip_reason"), "hysteresis")

        # Accept one flip.
        with patch("agent.portfolio.fetch_option_mark", return_value=1.05):
            r3 = execute_options_decision(
                "SPY", "SELL", 560.0, "osc3", settings, option_side="put", signal_confidence=90
            )
        self.assertEqual(r3.get("action"), "close_only")
        self.assertEqual(len(r3.get("fills") or []), 1)

        # Immediate opposite re-entry blocked by cooldown.
        fake_contract = {
            "contract_symbol": "SPYPUT",
            "underlying": "SPY",
            "side": "put",
            "strike": 560.0,
            "expiration": "2026-07-17",
            "premium": 1.1,
            "has_nbbo": True,
        }
        with patch("agent.portfolio.select_atm_contract", return_value=fake_contract):
            r4 = execute_options_decision(
                "SPY", "SELL", 560.0, "osc4", settings, option_side="put", signal_confidence=75
            )
        self.assertEqual(r4.get("action"), "flip_reentry_blocked")

    def test_eod_flatten_idempotent(self) -> None:
        settings = {
            "trading": {
                "starting_cash": 100000,
                "options_exits": {"take_profit_pct": 0.40, "stop_loss_pct": 0.30, "eod_flatten_et": "15:45"},
            },
            "execution": {"market_hours_only": False},
        }
        self._seed_call(opened_at="2026-07-15T14:00:00+00:00")
        portfolio = load_portfolio({"trading": {"starting_cash": 100000}})
        portfolio["positions"]["SPYCALL"]["expiration"] = "2026-07-15"
        save_portfolio(portfolio)
        with patch("agent.portfolio.fetch_option_mark", return_value=1.05):
            # Wednesday (not Friday) so exit reason stays eod_flatten, not deadline_flatten.
            fills1 = manage_option_exits(settings, now_et=datetime(2026, 7, 15, 15, 50, tzinfo=ET))
            fills2 = manage_option_exits(settings, now_et=datetime(2026, 7, 15, 15, 51, tzinfo=ET))
        self.assertEqual(len(fills1), 1)
        self.assertEqual(fills1[0]["reason"], "eod_flatten")
        self.assertEqual(len(fills2), 0)
        self.assertTrue(already_flattened("SPYCALL"))

    def test_identical_quote_pause(self) -> None:
        settings = {"execution": {"require_live_nbbo": True, "identical_quote_pause_count": 3}}
        ok1, _, _ = check_and_record_quote("IWM", "IWM1", 0.495, settings=settings, has_nbbo=True)
        ok2, _, _ = check_and_record_quote("IWM", "IWM1", 0.495, settings=settings, has_nbbo=True)
        ok3, reason, _ = check_and_record_quote("IWM", "IWM1", 0.495, settings=settings, has_nbbo=True)
        self.assertTrue(ok1 and ok2)
        self.assertFalse(ok3)
        self.assertEqual(reason, "identical_quote_pause")
        ok4, reason4, _ = check_and_record_quote("IWM", "IWM1", 0.495, settings=settings, has_nbbo=True)
        self.assertFalse(ok4)
        self.assertEqual(reason4, "identical_quote_pause")
        ok5, _, _ = check_and_record_quote("IWM", "IWM1", 0.51, settings=settings, has_nbbo=True)
        self.assertTrue(ok5)

    def test_missing_nbbo_rejected(self) -> None:
        settings = {"execution": {"require_live_nbbo": True}}
        ok, reason, _ = check_and_record_quote("SPY", "SPY1", 1.2, settings=settings, has_nbbo=False)
        self.assertFalse(ok)
        self.assertEqual(reason, "stale_quote")

    def test_eod_summary_flags_flip_and_ooh(self) -> None:
        executions = [
            {
                "timestamp": "2026-07-17T14:00:00+00:00",
                "ticker": "SPY",
                "instrument_type": "option",
                "contract_symbol": "SPYC",
                "action": "open",
                "price": 1.0,
            },
            {
                "timestamp": "2026-07-17T14:02:00+00:00",
                "ticker": "SPY",
                "instrument_type": "option",
                "contract_symbol": "SPYC",
                "action": "close",
                "reason": "signal_flip",
                "price": 1.0,
                "realized_pnl": 0,
            },
            {
                "timestamp": "2026-07-17T20:30:00+00:00",  # 16:30 ET
                "ticker": "IWM",
                "instrument_type": "option",
                "contract_symbol": "IWMP",
                "action": "open",
                "price": 0.5,
            },
            {
                "timestamp": "2026-07-17T20:31:00+00:00",
                "ticker": "IWM",
                "instrument_type": "option",
                "contract_symbol": "IWMP",
                "action": "close",
                "reason": "eod_flatten",
                "price": 0.48,
                "realized_pnl": -30,
            },
        ]
        trade_log = [
            {
                "timestamp": "2026-07-17T15:00:00+00:00",
                "decision": "LOG",
                "decision_reason_code": "stale_quote",
            }
        ]
        summary = build_eod_summary(
            session_date="2026-07-17", executions=executions, trade_log=trade_log
        )
        self.assertEqual(summary["opens"], 2)
        self.assertGreater(summary["signal_flip_pct"], 20)
        self.assertGreaterEqual(summary["out_of_hours_opens"], 1)
        self.assertTrue(summary["flags"]["signal_flip_high"])
        self.assertIn("stale_quote", summary["rejection_codes"])
        self.assertIn("NEEDS REVIEW", summary["headline"])

    def test_path_b_universe_stats_empty_finviz(self) -> None:
        with patch("screener.expiry_screener.fetch_finviz_rows", return_value=[]):
            rows, stats = screen_expiry_candidates_with_stats(
                screener_cfg={"provider": "scraper"},
                expiry_cfg={"max_dte": 0, "seed_tickers": ["SPY", "QQQ", "IWM"]},
            )
        self.assertEqual(stats["finviz_raw"], 0)
        self.assertEqual(stats["after_filters"], 0)
        self.assertEqual(stats["seed_count"], 3)
        self.assertEqual(len(rows), 3)
        health = update_universe_health(stats, kept_0dte=3, dropped_non_0dte=0, settings={})
        self.assertEqual(health["consecutive_zero_finviz"], 1)

    def test_log_reason_templated_and_persisted(self) -> None:
        self.assertIn("liquidity", templated_log_why("liquidity_reject").lower())
        settings = {
            "trading": {"auto_execute": False, "instrument": "options"},
            "execution": {"autonomous_buy_sell": False},
        }
        entry = append_paper_trade_entry(
            ticker="IWM",
            decision="LOG",
            claude_response={"score": 0, "reasoning": "blocked", "confidence": "low"},
            news_headline="Path B",
            news_source="expiry_screener",
            social_signal_level="IGNORE",
            social_signal_posts=[],
            settings=settings,
            decision_meta={"decision_reason_code": "liquidity_reject", "lean": "WAIT", "lean_pct": 0},
            decision_reason="liquidity",
        )
        self.assertEqual(entry["decision"], "LOG")
        self.assertEqual(entry["decision_reason_code"], "liquidity_reject")
        self.assertIn("liquidity", entry["why"].lower())


if __name__ == "__main__":
    unittest.main()
