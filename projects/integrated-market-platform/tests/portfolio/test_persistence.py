"""Canonical portfolio persistence tests (G2 §60, §73).

Serialization is deterministic, preserves Decimal exactness, account/mode
scope, canonical instrument ids, cash-by-currency, and incomplete valuation
status. Old-shape decode keeps safe defaults.
"""

from __future__ import annotations

import json
import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.canonical import (
    BondPriceBasis,
    CanonicalPortfolio,
    CashBalance,
    MarkDataStatus,
    MarkType,
    PortfolioKey,
    PortfolioPosition,
    PortfolioSnapshot,
    PositionInput,
    PositionValuation,
    QuantityUnit,
    ValuationMark,
    ValuationStatus,
    portfolio_identity_hash,
)
from market_platform_foundation.portfolio.valuation import value_position
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def _equity_input(instrument_id: str, quantity: str) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="EQUITY",
        instrument_kind="TRADABLE_SECURITY",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.SHARES,
        native_currency="USD",
        average_cost=Decimal("120.00"),
        cost_basis=Decimal(quantity) * Decimal("120.00"),
        realized_pnl_native=Decimal("12.34"),
    )


class CanonicalPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def _snapshot(self, *, base_currency: str | None = "USD") -> PortfolioSnapshot:
        portfolio = CanonicalPortfolio(
            PortfolioKey(account_id="acc-a", mode="PAPER", portfolio_id="acc-a")
        )
        portfolio.upsert_position(_equity_input("XA01:aapl", "100"))
        portfolio.apply_mark(
            ValuationMark(
                instrument_id="XA01:aapl",
                price=Decimal("150.25"),
                currency="USD",
                source="test",
                source_time_ns=5000,
                observed_at_ns=5000,
            )
        )
        portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("1000.50")))
        portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("250.25")))
        return portfolio.build_snapshot(base_currency=base_currency)

    def test_round_trip_preserves_everything(self) -> None:
        snapshot = self._snapshot()
        payload = snapshot.to_dict()
        restored = PortfolioSnapshot.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.key.account_id, "acc-a")
        self.assertEqual(restored.key.mode, "PAPER")
        position = restored.positions[0]
        self.assertEqual(position.instrument_id, "XA01:aapl")
        self.assertEqual(position.quantity, Decimal("100"))
        self.assertEqual(position.average_cost, Decimal("120.00"))
        self.assertEqual(position.realized_pnl_native, Decimal("12.34"))
        self.assertEqual(position.valuation.market_value_native, Decimal("15025"))
        self.assertEqual(
            position.valuation.mark.currency,  # type: ignore[union-attr]
            "USD",
        )

    def test_deterministic_serialization(self) -> None:
        payload_a = json.dumps(self._snapshot().to_dict(), sort_keys=True)
        payload_b = json.dumps(self._snapshot().to_dict(), sort_keys=True)
        self.assertEqual(payload_a, payload_b)
        self.assertEqual(
            portfolio_identity_hash(self._snapshot()),
            portfolio_identity_hash(self._snapshot()),
        )

    def test_cash_by_currency_preserved(self) -> None:
        snapshot = self._snapshot()
        restored = PortfolioSnapshot.from_dict(snapshot.to_dict())
        cash = {row.currency: row.settled for row in restored.cash_balances}
        self.assertEqual(cash["USD"], Decimal("1000.50"))
        self.assertEqual(cash["EUR"], Decimal("250.25"))

    def test_decimal_exactness_preserved(self) -> None:
        position = PortfolioPosition(
            instrument_id="XA01:msft",
            asset_class="EQUITY",
            instrument_kind="TRADABLE_SECURITY",
            quantity=Decimal("0.33333333333333333333"),
            quantity_unit=QuantityUnit.SHARES,
            native_currency="USD",
        )
        restored = PortfolioPosition.from_dict(position.to_dict())
        self.assertEqual(restored.quantity, Decimal("0.33333333333333333333"))

    def test_incomplete_valuation_status_preserved(self) -> None:
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-a", mode="PAPER"))
        portfolio.upsert_position(_equity_input("XA01:aapl", "100"))
        # No marks at all -> MISSING_MARK must survive the round trip.
        snapshot = portfolio.build_snapshot(base_currency="USD")
        self.assertEqual(snapshot.valuation_status, ValuationStatus.MISSING_MARK)
        restored = PortfolioSnapshot.from_dict(snapshot.to_dict())
        self.assertEqual(restored.valuation_status, ValuationStatus.MISSING_MARK)

    def test_missing_fx_status_preserved(self) -> None:
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-a", mode="PAPER"))
        portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        portfolio.set_cash(CashBalance(currency="JPY", settled=Decimal("10000")))
        snapshot = portfolio.build_snapshot(base_currency="USD")
        self.assertEqual(snapshot.valuation_status, ValuationStatus.MISSING_FX)
        restored = PortfolioSnapshot.from_dict(snapshot.to_dict())
        self.assertEqual(restored.valuation_status, ValuationStatus.MISSING_FX)

    def test_legacy_shape_decode_safe_defaults(self) -> None:
        # A minimal old-shape payload (no valuation, no extras) decodes with
        # safe defaults rather than failing.
        payload = {
            "key": {"account_id": "acc-old", "mode": "PAPER"},
            "base_currency": None,
            "cash_balances": [{"currency": "USD", "settled": "500"}],
            "positions": [
                {
                    "instrument_id": "AAPL",
                    "asset_class": "EQUITY",
                    "instrument_kind": "TRADABLE_SECURITY",
                    "quantity": "10",
                    "quantity_unit": "SHARES",
                    "native_currency": "USD",
                    "multiplier": "1",
                    "realized_pnl_native": "0",
                }
            ],
            "native_totals": {"USD": "500"},
            "base_currency_totals": {},
            "valuation_status": "COMPLETE",
        }
        restored = PortfolioSnapshot.from_dict(payload)
        self.assertEqual(restored.positions[0].quantity, Decimal("10"))
        self.assertIsNone(restored.positions[0].valuation)
        self.assertEqual(restored.key.mode, "PAPER")

    def test_multiplier_and_price_basis_preserved(self) -> None:
        position = PortfolioPosition(
            instrument_id="XA01:opt1",
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity=Decimal("2"),
            quantity_unit=QuantityUnit.CONTRACTS,
            native_currency="USD",
            multiplier=Decimal("100"),
            price_basis=BondPriceBasis.PAR_PERCENT,
        )
        restored = PortfolioPosition.from_dict(position.to_dict())
        self.assertEqual(restored.multiplier, Decimal("100"))
        self.assertEqual(restored.price_basis, BondPriceBasis.PAR_PERCENT)

    def test_position_valuation_round_trip(self) -> None:
        valuation = PositionValuation(
            market_value_native=Decimal("15025"),
            unrealized_pnl_native=Decimal("3025"),
            notional_native=None,
            reference_price=None,
            valuation_status=ValuationStatus.COMPLETE,
            mark=ValuationMark(
                instrument_id="XA01:aapl",
                price=Decimal("150.25"),
                currency="USD",
                mark_type=MarkType.LAST,
                source="test",
                source_time_ns=1,
                observed_at_ns=1,
                data_status=MarkDataStatus.FRESH,
            ),
        )
        restored = PositionValuation.from_dict(valuation.to_dict())
        self.assertEqual(restored.market_value_native, Decimal("15025"))
        self.assertEqual(restored.mark.price, Decimal("150.25"))  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()