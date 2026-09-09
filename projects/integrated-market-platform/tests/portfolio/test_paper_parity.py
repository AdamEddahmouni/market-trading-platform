"""Paper dual-run parity tests (G2 §65, §35, §43, BL-0105 strategy).

The canonical portfolio model runs alongside the legacy Paper equity ledger;
for pure-equity Paper state the canonical snapshot must agree exactly with
the Paper projections (quantity, average cost, cash, realized P&L, market
value) after int-minor -> Decimal conversion. Paper behavior itself is
unchanged; this adapter is a read-side projection.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.portfolio.paper_adapter import (
    paper_position_input,
    paper_snapshot_to_canonical,
)
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def _ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="g2-parity-session",
        instrument_id="AAPL",
        symbol="AAPL",
    )


def _fill(
    *,
    fill_id: str,
    order_id: str,
    direction: str,
    quantity: int,
    price_minor: int,
    fill_time: int,
) -> dict:
    return {
        "fill_id": fill_id,
        "order_id": order_id,
        "instrument_id": "AAPL",
        "direction": direction,
        "fill_quantity": quantity,
        "fill_price_minor": price_minor,
        "fill_time": fill_time,
    }


class PaperEquityParityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.ledger = _ledger()

    def _order(self, order_id: str, quantity: int) -> dict:
        return {
            "order_id": order_id,
            "instrument_id": "AAPL",
            "quantity": quantity,
            "state": "ACTIVATED",
        }

    def _buy(self, *, order_id: str, quantity: int, price_minor: int, fill_time: int) -> None:
        self.ledger.append_order(self._order(order_id, quantity), intent={"intent_id": f"intent-{order_id}"})
        self.ledger.append_fill(
            _fill(
                fill_id=f"fill-{order_id}",
                order_id=order_id,
                direction="long",
                quantity=quantity,
                price_minor=price_minor,
                fill_time=fill_time,
            ),
            order=self._order(order_id, quantity),
        )

    def _sell(self, *, order_id: str, quantity: int, price_minor: int, fill_time: int) -> None:
        self.ledger.append_order(self._order(order_id, quantity), intent={"intent_id": f"intent-{order_id}"})
        self.ledger.append_fill(
            _fill(
                fill_id=f"fill-{order_id}",
                order_id=order_id,
                direction="short",
                quantity=quantity,
                price_minor=price_minor,
                fill_time=fill_time,
            ),
            order=self._order(order_id, quantity),
        )

    def test_empty_ledger_snapshot(self) -> None:
        snapshot = paper_snapshot_to_canonical(self.ledger)
        self.assertEqual(snapshot.key.mode, "PAPER")
        self.assertEqual(snapshot.positions, ())
        self.assertEqual(len(snapshot.cash_balances), 1)
        # Initial cash 1,000,000.00 preserved exactly.
        self.assertEqual(snapshot.cash_balances[0].settled, Decimal("1000000.00"))

    def test_long_position_parity(self) -> None:
        self._buy(order_id="o1", quantity=100, price_minor=15000, fill_time=1000)
        projection = self.ledger.project_positions()[0]
        snapshot = paper_snapshot_to_canonical(self.ledger)
        canonical_position = snapshot.positions[0]
        self.assertEqual(int(canonical_position.quantity), projection["quantity"])
        self.assertEqual(canonical_position.quantity, Decimal("100"))
        # Average fill 150.00.
        self.assertEqual(canonical_position.average_cost, Decimal("150.00"))
        # Market value from the internal last-fill mark: 100 x 150.00.
        self.assertEqual(canonical_position.valuation.market_value_native, Decimal("15000.00"))
        self.assertEqual(snapshot.valuation_status.value, "COMPLETE")

    def test_cash_parity_after_buy(self) -> None:
        self._buy(order_id="o1", quantity=100, price_minor=15000, fill_time=1000)
        account = self.ledger.project_account()
        snapshot = paper_snapshot_to_canonical(self.ledger)
        expected_cash = Decimal(account["cash_minor"]) / Decimal(100)
        self.assertEqual(snapshot.cash_balances[0].settled, expected_cash)
        # 1,000,000.00 - 100 x 150.00.
        self.assertEqual(snapshot.cash_balances[0].settled, Decimal("985000.00"))

    def test_partial_reduction_parity(self) -> None:
        self._buy(order_id="o1", quantity=100, price_minor=10000, fill_time=1000)
        self._sell(order_id="o2", quantity=40, price_minor=12000, fill_time=2000)
        projection = self.ledger.project_positions()[0]
        account = self.ledger.project_account()
        snapshot = paper_snapshot_to_canonical(self.ledger)
        canonical_position = snapshot.positions[0]
        # Remaining quantity 60 with remaining average cost 100.00.
        self.assertEqual(int(canonical_position.quantity), 60)
        self.assertEqual(int(canonical_position.quantity), projection["quantity"])
        self.assertEqual(canonical_position.average_cost, Decimal("100.00"))
        # Realized P&L recorded by the ledger: (120.00 - 100.00) x 40.
        self.assertEqual(
            canonical_position.realized_pnl_native,
            Decimal(account["realized_pnl_minor"]) / Decimal(100),
        )
        self.assertEqual(canonical_position.realized_pnl_native, Decimal("800.00"))

    def test_reversal_parity(self) -> None:
        self._buy(order_id="o1", quantity=100, price_minor=10000, fill_time=1000)
        self._sell(order_id="o2", quantity=150, price_minor=12000, fill_time=2000)
        projection = self.ledger.project_positions()[0]
        snapshot = paper_snapshot_to_canonical(self.ledger)
        canonical_position = snapshot.positions[0]
        self.assertEqual(int(canonical_position.quantity), -50)
        self.assertEqual(int(canonical_position.quantity), projection["quantity"])
        self.assertEqual(canonical_position.quantity_unit.value, "SHARES")

    def test_position_input_from_ledger(self) -> None:
        self._buy(order_id="o1", quantity=25, price_minor=20000, fill_time=1000)
        position_input = paper_position_input(self.ledger)
        self.assertIsNotNone(position_input)
        self.assertEqual(position_input.instrument_id, "AAPL")
        self.assertEqual(position_input.quantity, Decimal("25"))
        self.assertEqual(position_input.quantity_unit.value, "SHARES")

    def test_snapshot_identity_hash_stable(self) -> None:
        from market_platform_foundation.portfolio.canonical import portfolio_identity_hash

        self._buy(order_id="o1", quantity=100, price_minor=15000, fill_time=1000)
        snapshot = paper_snapshot_to_canonical(self.ledger)
        self.assertEqual(
            portfolio_identity_hash(snapshot),
            portfolio_identity_hash(paper_snapshot_to_canonical(self.ledger)),
        )


if __name__ == "__main__":
    unittest.main()