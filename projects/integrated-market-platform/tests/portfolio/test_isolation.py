"""Account/mode isolation regression matrix (G2 §37, §64).

Paper/Account A must never equal Paper/Account B, Demo, or Live through the
canonical portfolio — for cash, options, futures, crypto, and bonds alike.
There is no shared global position dictionary and no shared snapshot hash.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio,
    CashBalance,
    PortfolioKey,
    PositionInput,
    QuantityUnit,
    portfolio_identity_hash,
)
from market_platform_foundation.portfolio.valuation import ValuationContext, value_positions
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def _key(account_id: str, mode: str) -> PortfolioKey:
    return PortfolioKey(account_id=account_id, mode=mode)


def _equity_input(instrument_id: str, quantity: str) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="EQUITY",
        instrument_kind="TRADABLE_SECURITY",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.SHARES,
        native_currency="USD",
    )


def _option_input(instrument_id: str, quantity: str) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="OPTION",
        instrument_kind="OPTION_CONTRACT",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.CONTRACTS,
        native_currency="USD",
        multiplier=Decimal("100"),
    )


def _future_input(instrument_id: str, quantity: str) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="FUTURE",
        instrument_kind="FUTURE_CONTRACT",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.CONTRACTS,
        native_currency="USD",
        multiplier=Decimal("50"),
    )


def _crypto_input(instrument_id: str, quantity: str, quote: str = "USD") -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="CRYPTO",
        instrument_kind="CRYPTO_PAIR",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.BASE_UNITS,
        native_currency=quote,
    )


class AccountIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_paper_account_a_position_not_in_account_b(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.upsert_position(_equity_input("XA01:aapl", "100"))
        self.assertIn("XA01:aapl", portfolio_a.positions)
        self.assertEqual(portfolio_b.positions, {})

    def test_paper_account_a_cash_not_in_account_b(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.set_cash(CashBalance(currency="USD", settled=Decimal("5000")))
        self.assertEqual(portfolio_b.cash_balances, ())

    def test_paper_a_differs_from_demo_a(self) -> None:
        paper = CanonicalPortfolio(_key("acc-a", "PAPER"))
        demo = CanonicalPortfolio(_key("acc-a", "DEMO"))
        paper.upsert_position(_equity_input("XA01:aapl", "100"))
        self.assertIn("XA01:aapl", paper.positions)
        self.assertEqual(demo.positions, {})

    def test_paper_a_differs_from_live_a(self) -> None:
        paper = CanonicalPortfolio(_key("acc-a", "PAPER"))
        live = CanonicalPortfolio(_key("acc-a", "LIVE"))
        paper.upsert_position(_equity_input("XA01:aapl", "100"))
        self.assertEqual(live.positions, {})

    def test_demo_a_differs_from_live_a(self) -> None:
        demo = CanonicalPortfolio(_key("acc-a", "DEMO"))
        live = CanonicalPortfolio(_key("acc-a", "LIVE"))
        demo.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.assertEqual(live.cash_balances, ())

    def test_option_isolation_across_accounts(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.upsert_position(_option_input("XA01:opt1", "2"))
        self.assertEqual(portfolio_b.positions, {})

    def test_future_isolation_across_accounts(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.upsert_position(_future_input("XA01:es1", "1"))
        self.assertEqual(portfolio_b.positions, {})

    def test_crypto_isolation_across_accounts(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.upsert_position(_crypto_input("XA01:btcusd", "0.5"))
        self.assertEqual(portfolio_b.positions, {})

    def test_no_shared_global_position_dictionary(self) -> None:
        portfolio_a = CanonicalPortfolio(_key("acc-a", "PAPER"))
        portfolio_b = CanonicalPortfolio(_key("acc-b", "PAPER"))
        portfolio_a.upsert_position(_equity_input("XA01:aapl", "100"))
        self.assertIsNot(portfolio_a.positions, portfolio_b.positions)


class SnapshotIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_snapshot_hash_account_scoped(self) -> None:
        snapshot_a = CanonicalPortfolio(_key("acc-a", "PAPER")).build_snapshot()
        snapshot_b = CanonicalPortfolio(_key("acc-b", "PAPER")).build_snapshot()
        self.assertNotEqual(
            portfolio_identity_hash(snapshot_a),
            portfolio_identity_hash(snapshot_b),
        )

    def test_snapshot_hash_mode_scoped(self) -> None:
        snapshot_paper = CanonicalPortfolio(_key("acc-a", "PAPER")).build_snapshot()
        snapshot_demo = CanonicalPortfolio(_key("acc-a", "DEMO")).build_snapshot()
        self.assertNotEqual(
            portfolio_identity_hash(snapshot_paper),
            portfolio_identity_hash(snapshot_demo),
        )

    def test_snapshot_hash_same_state_deterministic(self) -> None:
        def build() -> str:
            portfolio = CanonicalPortfolio(_key("acc-a", "PAPER"))
            portfolio.upsert_position(_equity_input("XA01:aapl", "100"))
            portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
            return portfolio_identity_hash(portfolio.build_snapshot())

        self.assertEqual(build(), build())

    def test_apply_snapshot_rejects_foreign_key(self) -> None:
        from market_platform_foundation.portfolio.canonical import PortfolioError

        store = CanonicalPortfolio(_key("acc-a", "PAPER"))
        foreign = CanonicalPortfolio(_key("acc-b", "PAPER")).build_snapshot()
        with self.assertRaises(PortfolioError):
            store.apply_snapshot(foreign)


if __name__ == "__main__":
    unittest.main()