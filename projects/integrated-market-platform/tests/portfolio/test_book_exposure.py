"""Canonical book exposure aggregation and limit utilization.

Read-only risk view over G2 position state. G4 economics supply exposure:
equity/option/crypto use signed mark value; futures use economic notional,
never cash-equity market value. Missing marks stay missing. Mixed currencies
are not summed 1:1. This is not a second pre-trade engine and does not
mutate the book or automate Live portfolios.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio,
    MarkDataStatus,
    PortfolioKey,
    PositionInput,
    QuantityUnit,
    ValuationMark,
)
from market_platform_foundation.risk.book_exposure import (
    BookLimitPolicy,
    aggregate_book_exposure,
)
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def _paper_book(account_id: str = "acct-a") -> CanonicalPortfolio:
    return CanonicalPortfolio(PortfolioKey(account_id=account_id, mode="PAPER"))


def _equity(instrument_id: str, quantity: str, currency: str = "USD") -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="EQUITY",
        instrument_kind="TRADABLE_SECURITY",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.SHARES,
        native_currency=currency,
    )


def _option(instrument_id: str, quantity: str, multiplier: str = "100") -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="OPTION",
        instrument_kind="OPTION_CONTRACT",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.CONTRACTS,
        native_currency="USD",
        multiplier=Decimal(multiplier),
    )


def _future(instrument_id: str, quantity: str, multiplier: str = "50") -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="FUTURE",
        instrument_kind="FUTURE_CONTRACT",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.CONTRACTS,
        native_currency="USD",
        multiplier=Decimal(multiplier),
    )


def _mark(
    instrument_id: str,
    price: str,
    *,
    currency: str = "USD",
    data_status: MarkDataStatus = MarkDataStatus.FRESH,
    source_time_ns: int = 1_000,
) -> ValuationMark:
    return ValuationMark(
        instrument_id=instrument_id,
        price=Decimal(price),
        currency=currency,
        source="test",
        source_time_ns=source_time_ns,
        observed_at_ns=source_time_ns,
        data_status=data_status,
    )


class EmptyBookTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_empty_paper_book_is_complete_zero_exposure_within_limits(self) -> None:
        book = _paper_book()
        report = aggregate_book_exposure(
            book,
            policy=BookLimitPolicy(
                currency="USD",
                max_gross_exposure=Decimal("10000"),
                max_net_exposure=Decimal("10000"),
                max_instrument_concentration_fraction=Decimal("0.25"),
            ),
        )
        self.assertEqual(report.account_id, "acct-a")
        self.assertEqual(report.mode, "PAPER")
        self.assertEqual(report.status, "COMPLETE")
        self.assertEqual(report.gross_exposure, Decimal("0"))
        self.assertEqual(report.net_exposure, Decimal("0"))
        self.assertTrue(report.within_limits)
        self.assertEqual(report.positions, ())
        self.assertFalse(hasattr(report, "order_id"))
        self.assertFalse(hasattr(report, "execution_authority"))


class PositionExposureTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_long_equity_gross_and_net_match_signed_notional(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.apply_mark(_mark("AAPL", "10"))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.status, "COMPLETE")
        self.assertEqual(report.gross_exposure, Decimal("1000"))
        self.assertEqual(report.net_exposure, Decimal("1000"))
        self.assertEqual(report.by_asset_class["EQUITY"].gross_exposure, Decimal("1000"))
        self.assertEqual(report.positions[0].signed_exposure, Decimal("1000"))

    def test_long_and_short_aggregate_gross_abs_and_net_signed(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.upsert_position(_equity("MSFT", "-40"))
        book.apply_mark(_mark("AAPL", "10"))
        book.apply_mark(_mark("MSFT", "20"))
        report = aggregate_book_exposure(book)
        # AAPL 1000 long + MSFT 800 short → gross 1800, net 200
        self.assertEqual(report.gross_exposure, Decimal("1800"))
        self.assertEqual(report.net_exposure, Decimal("200"))

    def test_option_exposure_uses_contract_multiplier(self) -> None:
        book = _paper_book()
        book.upsert_position(_option("AAPL-C", "2", multiplier="100"))
        book.apply_mark(_mark("AAPL-C", "3.50"))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.gross_exposure, Decimal("700"))
        self.assertEqual(report.net_exposure, Decimal("700"))
        self.assertEqual(report.by_asset_class["OPTION"].gross_exposure, Decimal("700"))

    def test_future_uses_economic_notional_not_variation_pnl(self) -> None:
        book = _paper_book()
        book.upsert_position(_future("ES-M26", "2", multiplier="50"))
        book.apply_mark(_mark("ES-M26", "5000"))
        report = aggregate_book_exposure(book)
        # 2 * 50 * 5000 = 500_000 economic exposure; P&L is not exposure
        self.assertEqual(report.gross_exposure, Decimal("500000"))
        self.assertEqual(report.net_exposure, Decimal("500000"))
        self.assertEqual(report.by_asset_class["FUTURE"].gross_exposure, Decimal("500000"))
        self.assertIsNone(report.positions[0].cash_market_value)


class FailClosedAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_missing_mark_is_partial_and_not_zero_filled(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.upsert_position(_equity("MSFT", "10"))
        book.apply_mark(_mark("AAPL", "10"))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.status, "PARTIAL")
        self.assertEqual(report.gross_exposure, Decimal("1000"))
        self.assertIn("MISSING_MARK", report.reason_codes)
        msft = next(row for row in report.positions if row.instrument_id == "MSFT")
        self.assertIsNone(msft.signed_exposure)
        self.assertNotEqual(msft.signed_exposure, Decimal("0"))

    def test_stale_mark_is_excluded_from_totals(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.apply_mark(_mark("AAPL", "10", data_status=MarkDataStatus.STALE))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.status, "PARTIAL")
        self.assertEqual(report.gross_exposure, Decimal("0"))
        self.assertIn("STALE_MARK", report.reason_codes)

    def test_mixed_currencies_fail_closed_without_fx(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "10", currency="USD"))
        book.upsert_position(_equity("SAP", "10", currency="EUR"))
        book.apply_mark(_mark("AAPL", "10", currency="USD"))
        book.apply_mark(_mark("SAP", "10", currency="EUR"))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.status, "FAIL_CLOSED")
        self.assertIsNone(report.gross_exposure)
        self.assertIsNone(report.net_exposure)
        self.assertFalse(report.within_limits)
        self.assertIn("MIXED_CURRENCY_NO_FX", report.reason_codes)

    def test_aggregation_does_not_mutate_positions(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.apply_mark(_mark("AAPL", "10"))
        before = book.get_position("AAPL")
        aggregate_book_exposure(book)
        after = book.get_position("AAPL")
        self.assertEqual(before, after)
        self.assertEqual(after.quantity, Decimal("100"))


class LimitUtilizationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_gross_limit_breach_is_reported_without_resizing(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.apply_mark(_mark("AAPL", "10"))
        report = aggregate_book_exposure(
            book,
            policy=BookLimitPolicy(currency="USD", max_gross_exposure=Decimal("500")),
        )
        self.assertEqual(report.status, "COMPLETE")
        self.assertFalse(report.within_limits)
        self.assertIn("GROSS_EXPOSURE_LIMIT", report.limit_breaches)
        self.assertEqual(book.get_position("AAPL").quantity, Decimal("100"))

    def test_net_limit_uses_absolute_net_exposure(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "-100"))
        book.apply_mark(_mark("AAPL", "10"))
        report = aggregate_book_exposure(
            book,
            policy=BookLimitPolicy(currency="USD", max_net_exposure=Decimal("500")),
        )
        self.assertFalse(report.within_limits)
        self.assertIn("NET_EXPOSURE_LIMIT", report.limit_breaches)

    def test_instrument_concentration_flags_dominant_name(self) -> None:
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "80"))
        book.upsert_position(_equity("MSFT", "20"))
        book.apply_mark(_mark("AAPL", "10"))
        book.apply_mark(_mark("MSFT", "10"))
        report = aggregate_book_exposure(
            book,
            policy=BookLimitPolicy(
                currency="USD",
                max_instrument_concentration_fraction=Decimal("0.50"),
            ),
        )
        self.assertEqual(report.gross_exposure, Decimal("1000"))
        self.assertFalse(report.within_limits)
        self.assertIn("INSTRUMENT_CONCENTRATION", report.limit_breaches)
        self.assertEqual(report.concentrated_instrument_ids, ("AAPL",))

    def test_live_mode_is_observational_aggregation_only(self) -> None:
        book = CanonicalPortfolio(PortfolioKey(account_id="live-1", mode="LIVE"))
        book.upsert_position(_equity("AAPL", "5"))
        book.apply_mark(_mark("AAPL", "10"))
        report = aggregate_book_exposure(book)
        self.assertEqual(report.mode, "LIVE")
        self.assertEqual(report.gross_exposure, Decimal("50"))
        self.assertNotIn("LIVE_AUTOMATION", report.reason_codes)
        self.assertFalse(hasattr(report, "submit"))


if __name__ == "__main__":
    unittest.main()
