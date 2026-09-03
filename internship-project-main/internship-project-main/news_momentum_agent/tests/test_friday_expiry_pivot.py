"""Tests for expiry horizon modes (same_day / deadline / range) and deadline flatten."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.market_session import (  # noqa: E402
    allows_overnight_holds,
    deadline_flatten_enabled,
    effective_options_max_dte,
    effective_options_min_dte,
    normalize_options_expiry_horizon,
    options_dte_cap_through_friday_et,
    resolve_deadline_date_et,
    this_friday_date_et,
)
from agent.near_miss_tracker import _build_checkpoints, _shadow_outcome_from_rule  # noqa: E402
from agent.option_contracts import lookup_atm_contract, select_atm_contract  # noqa: E402
from agent.portfolio import evaluate_option_exit_rule  # noqa: E402
from agent.risk_manager import check_new_trade_allowed  # noqa: E402

ET = ZoneInfo("America/New_York")


class FridayHorizonHelperTests(unittest.TestCase):
    def test_this_friday_from_wednesday(self) -> None:
        now = datetime(2026, 7, 29, 10, 0, tzinfo=ET)  # Wednesday
        self.assertEqual(this_friday_date_et(now).isoformat(), "2026-07-31")
        self.assertEqual(options_dte_cap_through_friday_et(now), 2)

    def test_effective_max_dte_through_friday_alias(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "through_friday",
                "options_max_dte": 5,
            }
        }
        now = datetime(2026, 7, 29, 10, 0, tzinfo=ET)
        self.assertEqual(normalize_options_expiry_horizon(settings), "deadline")
        self.assertEqual(effective_options_max_dte(settings, now), 2)

    def test_deadline_mode_with_explicit_date(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "deadline",
                "deadline_date": "2026-07-31",
                "options_max_dte": 5,
            }
        }
        now = datetime(2026, 7, 29, 10, 0, tzinfo=ET)
        self.assertEqual(resolve_deadline_date_et(settings, now).isoformat(), "2026-07-31")
        self.assertEqual(effective_options_max_dte(settings, now), 2)
        self.assertEqual(effective_options_min_dte(settings, now), 0)
        self.assertTrue(deadline_flatten_enabled(settings))
        self.assertTrue(allows_overnight_holds(settings))

    def test_range_mode_bounds(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "range",
                "options_dte_range": [1, 30],
            }
        }
        self.assertEqual(normalize_options_expiry_horizon(settings), "range")
        self.assertEqual(effective_options_min_dte(settings), 1)
        self.assertEqual(effective_options_max_dte(settings), 30)
        self.assertFalse(deadline_flatten_enabled(settings))
        self.assertTrue(allows_overnight_holds(settings))

    def test_same_day_mode(self) -> None:
        settings = {"trading": {"options_expiry_horizon": "same_day", "options_max_dte": 5}}
        self.assertEqual(normalize_options_expiry_horizon(settings), "same_day")
        self.assertEqual(effective_options_max_dte(settings), 0)
        self.assertFalse(allows_overnight_holds(settings))


class ThroughFridayContractTests(unittest.TestCase):
    def test_picks_nearest_within_friday_skips_beyond(self) -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260731C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        stock = MagicMock()
        # Wed Jul 29: eligible Fri Jul 31; Aug 7 is beyond Friday.
        stock.options = ["2026-07-31", "2026-08-07"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()
        stock.option_chain.return_value = MagicMock(calls=frame, puts=pd.DataFrame())

        settings = {
            "trading": {
                "options_expiry_horizon": "through_friday",
                "options_max_dte": 5,
            }
        }
        now = datetime(2026, 7, 29, 12, 0, 0)
        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=now):
                result = select_atm_contract("SPY", "call", 560.0, max_dte=0, settings=settings)
                lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0, settings=settings)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["expiration"], "2026-07-31")
        self.assertEqual(result["dte"], 2)
        self.assertEqual(lookup["status"], "ok")

    def test_deadline_mode_picks_nearest_within_deadline(self) -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260731C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        stock = MagicMock()
        stock.options = ["2026-07-31", "2026-08-07"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()
        stock.option_chain.return_value = MagicMock(calls=frame, puts=pd.DataFrame())
        settings = {
            "trading": {
                "options_expiry_horizon": "deadline",
                "deadline_date": "2026-07-31",
                "options_max_dte": 5,
            }
        }
        now = datetime(2026, 7, 29, 12, 0, 0)
        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=now):
                result = select_atm_contract("SPY", "call", 560.0, max_dte=0, settings=settings)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["expiration"], "2026-07-31")

    def test_skips_when_only_beyond_friday(self) -> None:
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260807C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        stock = MagicMock()
        stock.options = ["2026-08-07", "2026-08-14"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()
        stock.option_chain.return_value = MagicMock(calls=frame, puts=pd.DataFrame())
        settings = {
            "trading": {
                "options_expiry_horizon": "through_friday",
                "options_max_dte": 5,
            }
        }
        now = datetime(2026, 7, 29, 12, 0, 0)
        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=now):
                with patch(
                    "agent.option_contracts._lookup_from_alpaca",
                    return_value={
                        "outcome": "confirmed_empty",
                        "contract": None,
                        "error": None,
                        "error_kind": None,
                    },
                ):
                    lookup = lookup_atm_contract("SPY", "call", 560.0, max_dte=0, settings=settings)
        self.assertIsNone(lookup.get("contract"))
        self.assertEqual(lookup["status"], "no_0dte_chain_exists")
        self.assertIn("deadline", lookup.get("detail") or "")

    def test_range_picks_post_friday_expiry(self) -> None:
        import pandas as pd

        frame_aug = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260807C00560000",
                    "strike": 560.0,
                    "bid": 2.0,
                    "ask": 2.2,
                    "lastPrice": 2.1,
                }
            ]
        )
        frame_fri = pd.DataFrame(
            [
                {
                    "contractSymbol": "SPY20260731C00560000",
                    "strike": 560.0,
                    "bid": 1.0,
                    "ask": 1.2,
                    "lastPrice": 1.1,
                }
            ]
        )
        stock = MagicMock()
        stock.options = ["2026-07-31", "2026-08-07"]
        stock.fast_info = {"lastPrice": 560.0}
        stock.history.return_value = pd.DataFrame()

        def _chain(expiry: str):
            if expiry == "2026-07-31":
                return MagicMock(calls=frame_fri, puts=pd.DataFrame())
            return MagicMock(calls=frame_aug, puts=pd.DataFrame())

        stock.option_chain.side_effect = _chain
        # min_dte=5 skips Friday (dte=2 on Wed); Aug 7 (dte=9) is in [5, 30].
        settings = {
            "trading": {
                "options_expiry_horizon": "range",
                "options_dte_range": [5, 30],
            }
        }
        now = datetime(2026, 7, 29, 12, 0, 0)
        with patch("agent.option_contracts.yf.Ticker", return_value=stock):
            with patch("agent.option_contracts._now_et", return_value=now):
                result = select_atm_contract("SPY", "call", 560.0, max_dte=0, settings=settings)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["expiration"], "2026-08-07")
        self.assertEqual(result["dte"], 9)


class DeadlineFlattenTests(unittest.TestCase):
    def test_friday_deadline_flatten(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "deadline",
                "deadline_date": "2026-07-31",
                "options_exits": {
                    "take_profit_pct": 0.40,
                    "stop_loss_pct": 0.30,
                    "eod_flatten_et": "15:45",
                    "deadline_flatten_weekday": 4,
                },
            }
        }
        # Friday Jul 31 2026 15:50 — multi-day expiry still within deadline.
        now = datetime(2026, 7, 31, 15, 50, tzinfo=ET)
        rule = evaluate_option_exit_rule(
            entry=4.0,
            mark=4.1,
            expiration="2026-07-31",
            settings=settings,
            now_et=now,
        )
        self.assertEqual(rule, "deadline_flatten")

    def test_range_mode_no_deadline_flatten(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "range",
                "options_dte_range": [1, 30],
                "options_exits": {
                    "take_profit_pct": 0.40,
                    "stop_loss_pct": 0.30,
                    "eod_flatten_et": "15:45",
                },
            }
        }
        now = datetime(2026, 7, 31, 15, 50, tzinfo=ET)
        rule = evaluate_option_exit_rule(
            entry=4.0,
            mark=4.1,
            expiration="2026-08-14",
            settings=settings,
            now_et=now,
        )
        self.assertEqual(rule, "")

    def test_wednesday_no_flatten_for_friday_expiry(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "deadline",
                "deadline_date": "2026-07-31",
                "options_exits": {
                    "take_profit_pct": 0.40,
                    "stop_loss_pct": 0.30,
                    "eod_flatten_et": "15:45",
                    "deadline_flatten_weekday": 4,
                },
            }
        }
        now = datetime(2026, 7, 29, 15, 50, tzinfo=ET)
        rule = evaluate_option_exit_rule(
            entry=4.0,
            mark=4.1,
            expiration="2026-07-31",
            settings=settings,
            now_et=now,
        )
        self.assertEqual(rule, "")

    def test_shadow_maps_deadline(self) -> None:
        self.assertEqual(_shadow_outcome_from_rule("deadline_flatten"), "would_have_flattened_flat")


class NearMissCheckpointTests(unittest.TestCase):
    def test_build_includes_friday_close(self) -> None:
        settings = {
            "near_miss_tracker": {
                "checkpoint_offsets_min": {"t60": 60, "t240": 240},
            },
            "trading": {"options_exits": {"eod_flatten_et": "15:45"}},
        }
        rejected = datetime(2026, 7, 29, 11, 0, tzinfo=ET)
        cps = _build_checkpoints(rejected, settings)
        self.assertIn("t60", cps)
        self.assertIn("t240", cps)
        self.assertIn("friday_close", cps)
        self.assertIn("next_day_eod", cps)
        self.assertTrue(str(cps["friday_close"]["due_at"]).startswith("2026-07-31"))


class OvernightRiskTests(unittest.TestCase):
    def test_blocks_when_overnight_cap_hit(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "through_friday",
                "options_max_dte": 5,
            },
            "risk": {
                "enabled": True,
                "max_concurrent_0dte": 5,
                "max_overnight_positions": 1,
                "max_correlated_group": 5,
                "max_new_0dte_entries_per_day": 99,
                "min_minutes_between_entries_same_ticker": 0,
            },
        }
        portfolio = {
            "positions": {
                "OPT1": {
                    "instrument_type": "option",
                    "underlying": "AAA",
                    "option_side": "call",
                    "expiration": "2026-07-31",
                }
            }
        }
        with patch("agent.risk_manager.now_et", create=True):
            with patch("agent.market_session.now_et") as mock_now:
                mock_now.return_value = datetime(2026, 7, 29, 10, 0, tzinfo=ET)
                with patch("agent.risk_manager.load_daily_risk", return_value={"entries_today": 0, "halted": False}):
                    allowed, reason, _ = check_new_trade_allowed(
                        ticker="BBB",
                        decision="BUY",
                        portfolio=portfolio,
                        settings=settings,
                        option_side="call",
                    )
        self.assertFalse(allowed)
        self.assertIn("max_overnight_positions", reason)

    def test_range_mode_overnight_cap(self) -> None:
        settings = {
            "trading": {
                "options_expiry_horizon": "range",
                "options_dte_range": [1, 30],
            },
            "risk": {
                "enabled": True,
                "max_concurrent_0dte": 5,
                "max_overnight_positions": 1,
                "max_correlated_group": 5,
                "max_new_0dte_entries_per_day": 99,
                "min_minutes_between_entries_same_ticker": 0,
            },
        }
        portfolio = {
            "positions": {
                "OPT1": {
                    "instrument_type": "option",
                    "underlying": "AAA",
                    "option_side": "call",
                    "expiration": "2026-08-14",
                }
            }
        }
        with patch("agent.market_session.now_et") as mock_now:
            mock_now.return_value = datetime(2026, 7, 29, 10, 0, tzinfo=ET)
            with patch("agent.risk_manager.load_daily_risk", return_value={"entries_today": 0, "halted": False}):
                allowed, reason, _ = check_new_trade_allowed(
                    ticker="BBB",
                    decision="BUY",
                    portfolio=portfolio,
                    settings=settings,
                    option_side="call",
                )
        self.assertFalse(allowed)
        self.assertIn("max_overnight_positions", reason)


if __name__ == "__main__":
    unittest.main()
