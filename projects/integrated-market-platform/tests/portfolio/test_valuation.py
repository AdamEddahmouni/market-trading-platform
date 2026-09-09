"""Asset-aware portfolio valuation tests (G2 §65–69, §71, §54).

Equity/ETF: qty x mark. Options: contracts x premium x multiplier (never a
hard-coded 100). Futures: notional separate from P&L, mark-to-market against a
reference; never equity-style cash value. Crypto: base units x pair price,
quote-currency native. Bonds: face/par-aware with explicit price basis.
Missing/stale/wrong-currency/wrong-instrument marks are explicit — never zero.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.admission import admission_result
from market_platform_foundation.portfolio.canonical import (
    BondPriceBasis,
    MarkDataStatus,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioPosition,
    PositionInput,
    QuantityUnit,
    ValuationMark,
    ValuationStatus,
)
from market_platform_foundation.portfolio.valuation import (
    ValuationContext,
    value_bond_position,
    value_position,
    value_positions,
)
from market_platform_foundation.xa01.registry import reset_registry_for_tests


def _position(
    *,
    instrument_id: str,
    asset_class: str = "EQUITY",
    instrument_kind: str = "TRADABLE_SECURITY",
    quantity: str = "100",
    quantity_unit: QuantityUnit = QuantityUnit.SHARES,
    native_currency: str = "USD",
    multiplier: str = "1",
    cost_basis: str | None = None,
    average_cost: str | None = None,
) -> PortfolioPosition:
    return PortfolioPosition(
        instrument_id=instrument_id,
        asset_class=asset_class,
        instrument_kind=instrument_kind,
        quantity=Decimal(quantity),
        quantity_unit=quantity_unit,
        native_currency=native_currency,
        multiplier=Decimal(multiplier),
        average_cost=Decimal(average_cost) if average_cost is not None else None,
        cost_basis=Decimal(cost_basis) if cost_basis is not None else None,
    )


def _mark(
    instrument_id: str,
    price: str,
    *,
    currency: str = "USD",
    data_status: MarkDataStatus = MarkDataStatus.FRESH,
    source_time_ns: int = 1000,
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


class EquityValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_long_position_market_value(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="100")
        valuation = value_position(position, mark=_mark("XA01:aapl", "150.00"))
        self.assertEqual(valuation.market_value_native, Decimal("15000"))
        self.assertEqual(valuation.valuation_status, ValuationStatus.COMPLETE)

    def test_short_position_market_value_signed(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="-100")
        valuation = value_position(position, mark=_mark("XA01:aapl", "150.00"))
        self.assertEqual(valuation.market_value_native, Decimal("-15000"))

    def test_unrealized_pnl_from_cost_basis(self) -> None:
        position = _position(
            instrument_id="XA01:aapl",
            quantity="100",
            cost_basis="12000",
        )
        valuation = value_position(position, mark=_mark("XA01:aapl", "150.00"))
        self.assertEqual(valuation.market_value_native, Decimal("15000"))
        self.assertEqual(valuation.unrealized_pnl_native, Decimal("3000"))

    def test_no_mark_never_zero(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="100")
        valuation = value_position(position, mark=None)
        self.assertIsNone(valuation.market_value_native)
        self.assertEqual(valuation.valuation_status, ValuationStatus.MISSING_MARK)

    def test_stale_mark_explicit(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="100")
        valuation = value_position(
            position,
            mark=_mark("XA01:aapl", "150.00", data_status=MarkDataStatus.STALE),
        )
        self.assertEqual(valuation.valuation_status, ValuationStatus.STALE)

    def test_wrong_currency_mark_rejected(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="100")
        with self.assertRaises(PortfolioError) as ctx:
            value_position(position, mark=_mark("XA01:aapl", "150.00", currency="EUR"))
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.WRONG_CURRENCY_MARK)

    def test_wrong_instrument_mark_rejected(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="100")
        with self.assertRaises(PortfolioError) as ctx:
            value_position(position, mark=_mark("XA01:other", "150.00"))
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.WRONG_INSTRUMENT_MARK)


class OptionValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_option_value_contracts_times_premium_times_multiplier(self) -> None:
        # 2 contracts, premium 3.50, multiplier 100 -> native value 700.
        position = _position(
            instrument_id="XA01:opt1",
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity="2",
            quantity_unit=QuantityUnit.CONTRACTS,
            multiplier="100",
            cost_basis="700",
        )
        valuation = value_position(position, mark=_mark("XA01:opt1", "3.50"))
        self.assertEqual(valuation.market_value_native, Decimal("700"))
        self.assertEqual(valuation.unrealized_pnl_native, Decimal("0"))

    def test_option_short_quantity_signed(self) -> None:
        position = _position(
            instrument_id="XA01:opt2",
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity="-5",
            quantity_unit=QuantityUnit.CONTRACTS,
            multiplier="100",
        )
        valuation = value_position(position, mark=_mark("XA01:opt2", "2.00"))
        self.assertEqual(valuation.market_value_native, Decimal("-1000"))

    def test_option_nonstandard_multiplier_honored(self) -> None:
        # A 10-multiplier contract (e.g. some index options) must not assume 100.
        position = _position(
            instrument_id="XA01:opt3",
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity="3",
            quantity_unit=QuantityUnit.CONTRACTS,
            multiplier="10",
        )
        valuation = value_position(position, mark=_mark("XA01:opt3", "5.00"))
        self.assertEqual(valuation.market_value_native, Decimal("150"))

    def test_option_missing_mark_explicit(self) -> None:
        position = _position(
            instrument_id="XA01:opt4",
            asset_class="OPTION",
            instrument_kind="OPTION_CONTRACT",
            quantity="2",
            quantity_unit=QuantityUnit.CONTRACTS,
            multiplier="100",
        )
        valuation = value_position(position, mark=None)
        self.assertIsNone(valuation.market_value_native)
        self.assertEqual(valuation.valuation_status, ValuationStatus.MISSING_MARK)


class FuturesValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def _future(self, quantity: str = "1") -> PortfolioPosition:
        return _position(
            instrument_id="XA01:es202506",
            asset_class="FUTURE",
            instrument_kind="FUTURE_CONTRACT",
            quantity=quantity,
            quantity_unit=QuantityUnit.CONTRACTS,
            multiplier="50",
        )

    def test_futures_mark_to_market_pnl(self) -> None:
        # 1 ES contract, multiplier 50, move +10 points -> P&L +500.
        position = self._future()
        context = ValuationContext(
            marks={"XA01:es202506": _mark("XA01:es202506", "5510.00")},
            reference_prices={"XA01:es202506": Decimal("5500.00")},
        )
        valuation = value_position(position, context=context)
        self.assertEqual(valuation.unrealized_pnl_native, Decimal("500"))
        self.assertEqual(valuation.notional_native, Decimal("275500"))

    def test_futures_never_valued_as_cash_equity(self) -> None:
        position = self._future()
        context = ValuationContext(
            marks={"XA01:es202506": _mark("XA01:es202506", "5500.00")},
            reference_prices={"XA01:es202506": Decimal("5500.00")},
        )
        valuation = value_position(position, context=context)
        # market_value_native stays None: full notional is exposure, not cash.
        self.assertIsNone(valuation.market_value_native)
        self.assertEqual(valuation.unrealized_pnl_native, Decimal("0"))

    def test_futures_negative_contract_count_signed(self) -> None:
        position = self._future(quantity="-2")
        context = ValuationContext(
            marks={"XA01:es202506": _mark("XA01:es202506", "5510.00")},
            reference_prices={"XA01:es202506": Decimal("5500.00")},
        )
        valuation = value_position(position, context=context)
        self.assertEqual(valuation.unrealized_pnl_native, Decimal("-1000"))

    def test_futures_missing_reference_price_explicit(self) -> None:
        position = self._future()
        context = ValuationContext(
            marks={"XA01:es202506": _mark("XA01:es202506", "5510.00")},
        )
        valuation = value_position(position, context=context)
        self.assertIsNone(valuation.unrealized_pnl_native)
        self.assertEqual(valuation.valuation_status, ValuationStatus.MISSING_MARK)

    def test_futures_missing_mark_explicit(self) -> None:
        position = self._future()
        valuation = value_position(position, mark=None)
        self.assertEqual(valuation.valuation_status, ValuationStatus.MISSING_MARK)
        self.assertIsNone(valuation.notional_native)

    def test_continuous_series_rejected_by_engine(self) -> None:
        position = _position(
            instrument_id="XA01:es-continuous",
            asset_class="FUTURE",
            instrument_kind="CONTINUOUS_SERIES",
            quantity="1",
            quantity_unit=QuantityUnit.CONTRACTS,
        )
        valuation = value_position(position, mark=_mark("XA01:es-continuous", "5500.00"))
        self.assertEqual(valuation.valuation_status, ValuationStatus.UNSUPPORTED)


class CryptoValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_crypto_native_value_quote_currency(self) -> None:
        # 0.5 BTC at BTC/USD 60,000 -> 30,000 USD.
        position = _position(
            instrument_id="XA01:btcusd",
            asset_class="CRYPTO",
            instrument_kind="CRYPTO_PAIR",
            quantity="0.5",
            quantity_unit=QuantityUnit.BASE_UNITS,
            native_currency="USD",
        )
        valuation = value_position(
            position, mark=_mark("XA01:btcusd", "60000.00", currency="USD")
        )
        self.assertEqual(valuation.market_value_native, Decimal("30000"))

    def test_crypto_usdt_native_currency_preserved(self) -> None:
        position = _position(
            instrument_id="XA01:btcusdt",
            asset_class="CRYPTO",
            instrument_kind="CRYPTO_PAIR",
            quantity="0.5",
            quantity_unit=QuantityUnit.BASE_UNITS,
            native_currency="USDT",
        )
        valuation = value_position(
            position, mark=_mark("XA01:btcusdt", "60000.00", currency="USDT")
        )
        self.assertEqual(valuation.market_value_native, Decimal("30000"))
        self.assertEqual(position.native_currency, "USDT")

    def test_crypto_fractional_quantity(self) -> None:
        position = _position(
            instrument_id="XA01:ethusd",
            asset_class="CRYPTO",
            instrument_kind="CRYPTO_PAIR",
            quantity="0.333333",
            quantity_unit=QuantityUnit.BASE_UNITS,
            native_currency="USD",
        )
        valuation = value_position(
            position, mark=_mark("XA01:ethusd", "3000.00", currency="USD")
        )
        self.assertEqual(valuation.market_value_native, Decimal("999.999"))

    def test_usdt_not_usd_without_conversion(self) -> None:
        # A USDT-denominated mark must never be labeled USD.
        position = _position(
            instrument_id="XA01:btcusdt",
            asset_class="CRYPTO",
            instrument_kind="CRYPTO_PAIR",
            quantity="1",
            quantity_unit=QuantityUnit.BASE_UNITS,
            native_currency="USDT",
        )
        with self.assertRaises(PortfolioError):
            value_position(position, mark=_mark("XA01:btcusdt", "60000", currency="USD"))


class BondValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_bond_par_percent_clean_value(self) -> None:
        # face = 10,000; clean price 98.50 % par -> clean value 9,850.
        valuation = value_bond_position(
            face_amount=Decimal("10000"),
            price=Decimal("98.50"),
            price_basis=BondPriceBasis.PAR_PERCENT,
            currency="USD",
        )
        self.assertEqual(valuation.market_value_native, Decimal("9850"))
        self.assertEqual(valuation.valuation_status, ValuationStatus.COMPLETE)

    def test_bond_currency_per_face_unit(self) -> None:
        valuation = value_bond_position(
            face_amount=Decimal("10000"),
            price=Decimal("1.02"),
            price_basis=BondPriceBasis.CURRENCY_PER_FACE_UNIT,
            currency="EUR",
        )
        self.assertEqual(valuation.market_value_native, Decimal("10200"))
        self.assertEqual(valuation.mark.currency, "EUR")  # type: ignore[union-attr]

    def test_bond_accrued_interest_optional(self) -> None:
        clean = value_bond_position(
            face_amount=Decimal("10000"),
            price=Decimal("98.50"),
            price_basis=BondPriceBasis.PAR_PERCENT,
            currency="USD",
        )
        self.assertEqual(clean.market_value_native, Decimal("9850"))
        dirty = value_bond_position(
            face_amount=Decimal("10000"),
            price=Decimal("98.50"),
            price_basis=BondPriceBasis.PAR_PERCENT,
            currency="USD",
            accrued_interest=Decimal("42.50"),
        )
        self.assertEqual(dirty.market_value_native, Decimal("9892.50"))

    def test_bond_missing_price_basis_fails_explicitly(self) -> None:
        with self.assertRaises(PortfolioError):
            value_bond_position(
                face_amount=Decimal("10000"),
                price=Decimal("98.50"),
                price_basis="NOT_A_BASIS",  # type: ignore[arg-type]
                currency="USD",
            )

    def test_bond_direct_position_rejected_reference_only(self) -> None:
        position = _position(
            instrument_id="XA01:bond1",
            asset_class="BOND",
            instrument_kind="BOND",
            quantity="10000",
            quantity_unit=QuantityUnit.FACE_VALUE,
        )
        valuation = value_position(position, mark=_mark("XA01:bond1", "98.50"))
        self.assertEqual(valuation.valuation_status, ValuationStatus.UNSUPPORTED)


class ValuationPrecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_decimal_precision_no_float_error(self) -> None:
        position = _position(instrument_id="XA01:aapl", quantity="3")
        valuation = value_position(position, mark=_mark("XA01:aapl", "0.1"))
        self.assertEqual(valuation.market_value_native, Decimal("0.3"))
        position_third = _position(instrument_id="XA01:msft", quantity="1")
        valuation_third = value_position(
            position_third, mark=_mark("XA01:msft", "0.33333333333333333333")
        )
        self.assertEqual(
            valuation_third.market_value_native,
            Decimal("0.33333333333333333333"),
        )

    def test_value_positions_dispatch(self) -> None:
        positions = (
            _position(instrument_id="XA01:aapl", quantity="100"),
            _position(
                instrument_id="XA01:opt1",
                asset_class="OPTION",
                instrument_kind="OPTION_CONTRACT",
                quantity="2",
                quantity_unit=QuantityUnit.CONTRACTS,
                multiplier="100",
            ),
        )
        valued = value_positions(
            positions,
            marks={
                "XA01:aapl": _mark("XA01:aapl", "150.00"),
                "XA01:opt1": _mark("XA01:opt1", "3.50"),
            },
        )
        self.assertEqual(valued[0].valuation.market_value_native, Decimal("15000"))
        self.assertEqual(valued[1].valuation.market_value_native, Decimal("700"))


if __name__ == "__main__":
    unittest.main()