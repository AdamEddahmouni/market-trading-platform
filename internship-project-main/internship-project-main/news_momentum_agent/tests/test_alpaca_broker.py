"""Tests for Alpaca paper broker adapter (mocked — no live API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import alpaca_broker
from agent.portfolio import (
    EXECUTIONS_PATH,
    PORTFOLIO_PATH,
    default_portfolio,
    execute_options_decision,
    load_portfolio,
    save_portfolio,
)
import json


class AlpacaBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._pf = PORTFOLIO_PATH.read_text(encoding="utf-8") if PORTFOLIO_PATH.exists() else None
        self._ex = EXECUTIONS_PATH.read_text(encoding="utf-8") if EXECUTIONS_PATH.exists() else None
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_PATH.write_text(json.dumps(default_portfolio(100000)), encoding="utf-8")
        EXECUTIONS_PATH.write_text("[]", encoding="utf-8")

    def tearDown(self) -> None:
        if self._pf is None:
            PORTFOLIO_PATH.unlink(missing_ok=True)
        else:
            PORTFOLIO_PATH.write_text(self._pf, encoding="utf-8")
        if self._ex is None:
            EXECUTIONS_PATH.unlink(missing_ok=True)
        else:
            EXECUTIONS_PATH.write_text(self._ex, encoding="utf-8")

    def test_disabled_without_keys(self) -> None:
        settings = {"alpaca": {"enabled": True, "api_key": "", "secret_key": ""}}
        with patch.dict("os.environ", {}, clear=False):
            # Clear only our keys if present
            with patch("agent.alpaca_broker._credentials", return_value=("", "")):
                self.assertFalse(alpaca_broker.is_alpaca_paper_enabled(settings))

    def test_submit_open_mocked(self) -> None:
        settings = {
            "alpaca": {
                "enabled": True,
                "api_key": "PK_TEST",
                "secret_key": "SK_TEST",
                "require_broker_ack": False,
            }
        }
        mock_order = MagicMock()
        mock_order.id = "ord-123"
        mock_order.status = "filled"
        mock_order.filled_avg_price = "1.25"
        mock_client = MagicMock()
        mock_client.submit_order.return_value = mock_order
        with patch("agent.alpaca_broker.get_trading_client", return_value=mock_client):
            result = alpaca_broker.submit_option_open("SPY260717C00500000", 2, settings)
        self.assertTrue(result["ok"])
        self.assertEqual(result["order_id"], "ord-123")
        mock_client.submit_order.assert_called_once()

    def test_open_mirrors_to_alpaca(self) -> None:
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
                "no_post_1545_opens": False,
                "require_live_nbbo": False,
                "identical_quote_pause_count": 99,
            },
            "risk": {"enabled": False},
            "alpaca": {
                "enabled": True,
                "api_key": "PK_TEST",
                "secret_key": "SK_TEST",
                "require_broker_ack": False,
            },
            "_runtime": {"portfolio_reconciled": True},
        }
        contract = {
            "contract_symbol": "SPY260717C00500000",
            "underlying": "SPY",
            "side": "call",
            "strike": 500.0,
            "expiration": "2026-07-17",
            "premium": 1.5,
            "has_nbbo": True,
        }
        broker_resp = {
            "ok": True,
            "broker": "alpaca_paper",
            "order_id": "ord-999",
            "status": "accepted",
            "filled_avg_price": 1.5,
        }
        with patch("agent.portfolio.select_atm_contract", return_value=contract):
            with patch("agent.portfolio._maybe_alpaca_open", return_value=broker_resp):
                with patch("agent.quote_sanity.check_and_record_quote", return_value=(True, "ok", {})):
                    result = execute_options_decision(
                        "SPY",
                        "BUY",
                        500.0,
                        "alpaca test",
                        settings,
                        option_side="call",
                        signal_confidence=80,
                    )
        self.assertIsNotNone(result)
        fills = (result or {}).get("fills") or []
        self.assertTrue(fills)
        self.assertEqual(fills[0].get("broker"), "alpaca_paper")
        self.assertEqual(fills[0].get("broker_order_id"), "ord-999")
        pos = load_portfolio(settings)["positions"].get("SPY260717C00500000")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.get("broker_order_id"), "ord-999")

    def test_probe_no_credentials(self) -> None:
        with patch("agent.alpaca_broker.has_alpaca_credentials", return_value=False):
            probe = alpaca_broker.probe_option_contracts_for_expiry("SPY", "2026-07-15")
        self.assertEqual(probe["outcome"], "no_credentials")
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["contracts"], [])

    def test_probe_confirmed_empty_vs_error(self) -> None:
        mock_client = MagicMock()
        empty_resp = MagicMock()
        empty_resp.option_contracts = []
        empty_resp.next_page_token = None
        mock_client.get_option_contracts.return_value = empty_resp

        mock_req_mod = MagicMock()
        mock_req_mod.GetOptionContractsRequest = MagicMock(return_value=MagicMock())

        with patch.dict(
            "sys.modules",
            {
                "alpaca": MagicMock(),
                "alpaca.trading": MagicMock(),
                "alpaca.trading.requests": mock_req_mod,
            },
        ):
            with patch("agent.alpaca_broker.has_alpaca_credentials", return_value=True):
                with patch(
                    "agent.alpaca_broker.get_readonly_trading_client", return_value=mock_client
                ):
                    empty = alpaca_broker.probe_option_contracts_for_expiry("CLDI", "2026-07-15")
                    self.assertEqual(empty["outcome"], "confirmed_empty")
                    self.assertTrue(empty["ok"])

                    mock_client.get_option_contracts.side_effect = RuntimeError(
                        "429 Too Many Requests"
                    )
                    err = alpaca_broker.probe_option_contracts_for_expiry("SPY", "2026-07-15")
                    self.assertEqual(err["outcome"], "error")
                    self.assertEqual(err["error_kind"], "rate_limit")
                    self.assertFalse(err["ok"])
                    self.assertEqual(
                        alpaca_broker.fetch_option_contracts_for_expiry("SPY", "2026-07-15"),
                        [],
                    )


if __name__ == "__main__":
    unittest.main()
