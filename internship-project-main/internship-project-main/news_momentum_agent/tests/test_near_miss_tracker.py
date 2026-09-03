"""Tests for observation-only near-miss / shadow outcome tracker."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.eod_summary import build_eod_summary, format_telegram_summary
from agent.near_miss_tracker import (
    _tracker_path,
    build_near_miss_eod_section,
    maybe_record_near_miss,
    tick_pending_near_misses,
)
from agent.portfolio import evaluate_option_exit_rule
from agent.quote_sanity import QUOTE_SANITY_PATH, validate_entry_quote


ET = ZoneInfo("America/New_York")


def _base_settings() -> dict:
    return {
        "trading": {
            "options_max_dte": 0,
            "options_exits": {
                "take_profit_pct": 0.40,
                "stop_loss_pct": 0.30,
                "eod_flatten_et": "15:45",
            },
        },
        "execution": {
            "min_confidence_for_action": 40,
            "min_confidence_for_path_b": 65,
            "require_live_nbbo": True,
            "identical_quote_pause_count": 3,
        },
        "near_miss_tracker": {
            "enabled": True,
            "cooldown_minutes": 60,
        },
    }


def _log_entry(**overrides) -> dict:
    ts = datetime(2026, 7, 21, 14, 0, 0, tzinfo=ET).astimezone(timezone.utc).isoformat()
    row = {
        "ticker": "TSLA",
        "timestamp": ts,
        "decision": "LOG",
        "decision_reason_code": "low_confidence",
        "signal_source": "expiry",
        "instrument_hint": "option",
        "options_bias": "bullish",
        "options_score": 62.0,
        "lean": "WAIT",
        "lean_pct": 50,
        "price_at_signal": 250.0,
        "decision_meta": {"confidence_pct": 58.0},
    }
    row.update(overrides)
    return row


class NearMissTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._backs: dict[Path, str | None] = {}
        for path in (_tracker_path("2026-07-21"), QUOTE_SANITY_PATH):
            if path.exists():
                self._backs[path] = path.read_text(encoding="utf-8")
            elif path.parent.exists():
                self._backs[path] = None
            if path.exists():
                path.unlink()

    def tearDown(self) -> None:
        for path, content in self._backs.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_text(content, encoding="utf-8")

    def test_validate_entry_quote_no_record_skips_persist(self) -> None:
        settings = _base_settings()
        ok1, _, _ = validate_entry_quote(
            "TSLA", "TSLA260721C00250000", 4.0, settings=settings, has_nbbo=True, record=False
        )
        self.assertTrue(ok1)
        self.assertFalse(QUOTE_SANITY_PATH.exists())

        ok2, _, _ = validate_entry_quote(
            "TSLA", "TSLA260721C00250000", 4.0, settings=settings, has_nbbo=True, record=True
        )
        self.assertTrue(ok2)
        self.assertTrue(QUOTE_SANITY_PATH.exists())

    def test_evaluate_option_exit_rule_tp_sl_eod(self) -> None:
        settings = _base_settings()
        now = datetime(2026, 7, 21, 15, 50, tzinfo=ET)
        self.assertEqual(
            evaluate_option_exit_rule(
                entry=4.0, mark=5.6, expiration="2026-07-21", settings=settings, now_et=now
            ),
            "take_profit",
        )
        self.assertEqual(
            evaluate_option_exit_rule(
                entry=4.0, mark=2.7, expiration="2026-07-21", settings=settings, now_et=now
            ),
            "stop_loss",
        )
        self.assertEqual(
            evaluate_option_exit_rule(
                entry=4.0, mark=4.1, expiration="2026-07-21", settings=settings, now_et=now
            ),
            "eod_flatten",
        )

    @patch("agent.near_miss_tracker.validate_entry_quote", return_value=(True, "ok", {}))
    @patch("agent.near_miss_tracker.lookup_atm_contract")
    def test_record_low_confidence_log(self, mock_lookup, _mock_quote) -> None:
        mock_lookup.return_value = {
            "contract": {
                "contract_symbol": "TSLA260721C00250000",
                "expiration": "2026-07-21",
                "premium": 4.025,
                "has_nbbo": True,
            },
            "status": "ok",
            "detail": "dte=0",
            "nearest_listed_dte": 0,
        }
        settings = _base_settings()
        item = maybe_record_near_miss(_log_entry(), settings)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["reason_code"], "low_confidence")
        self.assertEqual(item["distance_from_threshold"], -7.0)
        self.assertEqual(item["would_be_side"], "call")
        self.assertEqual(item["entry_quote_status"], "ok")
        self.assertEqual(item["followup_status"], "active")

        path = _tracker_path("2026-07-21")
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data.get("items") or {}), 1)

    @patch("agent.near_miss_tracker.validate_entry_quote", return_value=(True, "ok", {}))
    @patch("agent.near_miss_tracker.lookup_atm_contract")
    def test_cooldown_suppresses_duplicate(self, mock_lookup, _mock_quote) -> None:
        mock_lookup.return_value = {
            "contract": {
                "contract_symbol": "TSLA260721C00250000",
                "expiration": "2026-07-21",
                "premium": 4.0,
                "has_nbbo": True,
            },
            "status": "ok",
            "detail": "dte=0",
            "nearest_listed_dte": 0,
        }
        settings = _base_settings()
        first = maybe_record_near_miss(_log_entry(), settings)
        second = maybe_record_near_miss(_log_entry(), settings)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    @patch("agent.near_miss_tracker.lookup_atm_contract")
    def test_no_0dte_chain_status(self, mock_lookup) -> None:
        mock_lookup.return_value = {
            "contract": None,
            "status": "no_0dte_chain_exists",
            "detail": "no same-day expiry listed; nearest_dte=1",
            "nearest_listed_dte": 1,
            "expiries_seen": ["2026-07-22"],
        }
        item = maybe_record_near_miss(_log_entry(decision_reason_code="liquidity_reject"), _base_settings())
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["entry_quote_status"], "no_0dte_chain_exists")
        self.assertEqual(item["contract_lookup_status"], "no_0dte_chain_exists")
        self.assertIn("nearest_dte=1", str(item.get("entry_quote_reject") or ""))

    @patch("agent.near_miss_tracker.lookup_atm_contract")
    def test_alpaca_error_status_preserved(self, mock_lookup) -> None:
        mock_lookup.return_value = {
            "contract": None,
            "status": "alpaca_error",
            "detail": "yfinance omitted today; alpaca_error kind=rate_limit — NOT confirmed",
            "nearest_listed_dte": 1,
            "provider": "alpaca_error",
            "alpaca_error_kind": "rate_limit",
        }
        item = maybe_record_near_miss(_log_entry(decision_reason_code="liquidity_reject"), _base_settings())
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["entry_quote_status"], "alpaca_error")
        self.assertEqual(item["alpaca_error_kind"], "rate_limit")
        self.assertNotEqual(item["entry_quote_status"], "no_0dte_chain_exists")

    @patch("agent.near_miss_tracker.lookup_atm_contract")
    def test_alpaca_confirmed_empty_status_preserved(self, mock_lookup) -> None:
        mock_lookup.return_value = {
            "contract": None,
            "status": "alpaca_confirmed_empty",
            "detail": "alpaca_confirmed_empty for today",
            "nearest_listed_dte": 7,
            "provider": "alpaca_confirmed_empty",
        }
        item = maybe_record_near_miss(_log_entry(decision_reason_code="liquidity_reject"), _base_settings())
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["entry_quote_status"], "alpaca_confirmed_empty")

    @patch("agent.near_miss_tracker.fetch_option_mark")
    def test_tick_checkpoints_and_tp(self, mock_mark) -> None:
        settings = _base_settings()
        rejected = datetime(2026, 7, 21, 14, 0, 0, tzinfo=ET).astimezone(timezone.utc)
        item = {
            "id": "TSLA|test|low_confidence",
            "ticker": "TSLA",
            "rejected_at": rejected.isoformat(),
            "reason_code": "low_confidence",
            "confidence_pct": 62.0,
            "entry_quote_status": "ok",
            "followup_status": "active",
            "contract_symbol": "TSLA260721C00250000",
            "expiration": "2026-07-21",
            "entry_premium": 4.0,
            "checkpoints": {
                "t15": {
                    "due_at": (rejected + timedelta(minutes=15)).isoformat(),
                    "status": "pending",
                    "premium": None,
                    "pnl_pct": None,
                },
                "t30": {
                    "due_at": (rejected + timedelta(minutes=30)).isoformat(),
                    "status": "pending",
                    "premium": None,
                    "pnl_pct": None,
                },
                "t60": {
                    "due_at": (rejected + timedelta(minutes=60)).isoformat(),
                    "status": "pending",
                    "premium": None,
                    "pnl_pct": None,
                },
                "eod": {
                    "due_at": datetime(2026, 7, 21, 15, 45, tzinfo=ET).isoformat(),
                    "status": "pending",
                    "premium": None,
                    "pnl_pct": None,
                },
            },
            "first_exit_rule": None,
            "first_exit_at": None,
            "shadow_outcome": None,
        }
        path = _tracker_path("2026-07-21")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"session_date": "2026-07-21", "items": {item["id"]: item}}, indent=2),
            encoding="utf-8",
        )

        mock_mark.return_value = 5.8
        now = rejected + timedelta(minutes=16)
        updated = tick_pending_near_misses(settings, now=now)
        self.assertGreaterEqual(updated, 1)

        data = json.loads(path.read_text(encoding="utf-8"))
        saved = data["items"][item["id"]]
        self.assertEqual(saved["checkpoints"]["t15"]["status"], "recorded")
        self.assertEqual(saved["first_exit_rule"], "take_profit")
        self.assertEqual(saved["shadow_outcome"], "would_have_won")

    def test_eod_section_confidence_bands(self) -> None:
        path = _tracker_path("2026-07-21")
        path.parent.mkdir(parents=True, exist_ok=True)
        items = {
            "a": {
                "reason_code": "low_confidence",
                "confidence_pct": 62.0,
                "entry_quote_status": "ok",
                "followup_status": "complete",
                "first_exit_rule": "take_profit",
                "shadow_outcome": "would_have_won",
            },
            "b": {
                "reason_code": "low_confidence",
                "confidence_pct": 50.0,
                "entry_quote_status": "ok",
                "followup_status": "complete",
                "first_exit_rule": "stop_loss",
                "shadow_outcome": "would_have_lost",
            },
            "c": {
                "reason_code": "liquidity_reject",
                "confidence_pct": 70.0,
                "entry_quote_status": "skipped_stale_quote",
                "followup_status": "skipped",
            },
        }
        path.write_text(
            json.dumps({"session_date": "2026-07-21", "items": items}, indent=2),
            encoding="utf-8",
        )
        section = build_near_miss_eod_section("2026-07-21", _base_settings())
        self.assertEqual(section["total"], 3)
        self.assertEqual(section["by_reason"]["low_confidence"], 2)
        self.assertEqual(section["confidence_bands"]["60-64"]["count"], 1)
        self.assertEqual(section["confidence_bands"]["60-64"]["hit_tp"], 1)
        self.assertIn("60-64", section["headline_detail"])

    def test_eod_summary_includes_near_miss_telegram(self) -> None:
        path = _tracker_path("2026-07-21")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "session_date": "2026-07-21",
                    "items": {
                        "x": {
                            "reason_code": "low_confidence",
                            "confidence_pct": 63.0,
                            "entry_quote_status": "ok",
                            "followup_status": "complete",
                            "first_exit_rule": "take_profit",
                            "shadow_outcome": "would_have_won",
                        }
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        summary = build_eod_summary(
            session_date="2026-07-21",
            executions=[],
            trade_log=[],
            settings=_base_settings(),
        )
        self.assertIn("near_miss", summary)
        text = format_telegram_summary(summary)
        self.assertIn("Near-misses:", text)

    def test_module_does_not_import_execution(self) -> None:
        source = (PROJECT_ROOT / "agent" / "near_miss_tracker.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.append(alias.name)
        banned = [m for m in imported if "execute_decision" in m or "alpaca" in m.lower()]
        self.assertEqual(banned, [])
        self.assertNotIn("agent.portfolio.execute_decision", source)


if __name__ == "__main__":
    unittest.main()
