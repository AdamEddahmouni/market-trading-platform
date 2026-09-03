"""Unit tests for IBKR bracket order transmit chain (no live connection)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

WORKSPACE = Path(__file__).resolve().parents[1] / "src_client" / "workspace"
sys.path.insert(0, str(WORKSPACE))

from ibkr_manager import IBApp  # noqa: E402


class BracketOrderTests(unittest.TestCase):
    def _recording_app(self) -> IBApp:
        app = IBApp()
        app.orderId = 100
        app.placed: list = []

        def _place(order_id, contract, order) -> None:
            app.placed.append(order)

        app.placeOrder = _place  # type: ignore[method-assign]
        return app

    @patch("ibkr_manager.get_latest_futures_contract", return_value=MagicMock(symbol="ES"))
    def test_buy_market_bracket_transmit_chain(self, _mock_contract: MagicMock) -> None:
        app = self._recording_app()
        app.buy_bracket_order_market("ES", 1, 6100.0, 5900.0)
        self.assertEqual(len(app.placed), 3)
        parent, profit_taker, stop_loss = app.placed
        self.assertFalse(parent.transmit)
        self.assertFalse(profit_taker.transmit)
        self.assertTrue(stop_loss.transmit)
        self.assertEqual(profit_taker.parentId, parent.orderId)
        self.assertEqual(stop_loss.parentId, parent.orderId)

    @patch("ibkr_manager.get_latest_futures_contract", return_value=MagicMock(symbol="ES"))
    def test_sell_market_bracket_transmit_chain(self, _mock_contract: MagicMock) -> None:
        app = self._recording_app()
        app.sell_bracket_order_market("ES", 1, 5900.0, 6100.0)
        self.assertEqual(len(app.placed), 3)
        parent, profit_taker, stop_loss = app.placed
        self.assertFalse(parent.transmit)
        self.assertFalse(profit_taker.transmit)
        self.assertTrue(stop_loss.transmit)
        self.assertEqual(profit_taker.action, "BUY")
        self.assertEqual(stop_loss.action, "BUY")


if __name__ == "__main__":
    unittest.main()
