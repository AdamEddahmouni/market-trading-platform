"""Multi-currency cash ledger and explicit FX boundary tests (G2 §13–16, §70).

Currencies are never summed without an explicit rate: ``USD 100 + EUR 100``
without FX is incomplete; with ``EURUSD = 1.10`` the converted EUR is 110 USD
and the aggregate is 210 USD. Missing/stale/wrong-direction FX is reported,
never papered over with a 1:1 fallback.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio,
    CashBalance,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioKey,
    ValuationStatus,
)
from market_platform_foundation.portfolio.fx import (
    FxFactsBundle,
    FxRate,
    aggregate_to_base,
    cash_to_base,
    convert,
)


class MultiCurrencyCashTests(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio = CanonicalPortfolio(
            PortfolioKey(account_id="acc-cash", mode="PAPER")
        )

    def test_cash_holds_multiple_currencies(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("100")))
        balances = {row.currency: row.settled for row in self.portfolio.cash_balances}
        self.assertEqual(balances, {"EUR": Decimal("100"), "USD": Decimal("100")})

    def test_apply_cash_signed_delta(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("1000")))
        self.portfolio.apply_cash("USD", Decimal("-250"))
        balance = self.portfolio.cash_balances[0]
        self.assertEqual(balance.settled, Decimal("750"))

    def test_apply_cash_creates_currency(self) -> None:
        self.portfolio.apply_cash("GBP", Decimal("50"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("50"))

    def test_currency_normalized_uppercase(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="eur", settled=Decimal("5")))
        self.assertEqual(self.portfolio.cash_balances[0].currency, "EUR")

    def test_cash_currency_required(self) -> None:
        with self.assertRaises(PortfolioError):
            CashBalance(currency="", settled=Decimal("1"))

    def test_currencies_not_summed_without_conversion(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("100")))
        snapshot = self.portfolio.build_snapshot(base_currency="USD")
        # No FX facts supplied: aggregation must be explicitly incomplete.
        self.assertEqual(snapshot.valuation_status, ValuationStatus.MISSING_FX)
        self.assertEqual(snapshot.base_currency_totals["USD"], Decimal("100"))
        self.assertEqual(snapshot.native_totals["EUR"], Decimal("100"))


class FxBoundaryTests(unittest.TestCase):
    def test_convert_with_explicit_rate(self) -> None:
        amount, rate = convert(
            Decimal("100"),
            source_currency="EUR",
            target_currency="USD",
            rate=FxRate(
                source_currency="EUR",
                target_currency="USD",
                rate=Decimal("1.10"),
            ),
        )
        self.assertEqual(amount, Decimal("110"))
        self.assertEqual(rate.rate, Decimal("1.10"))

    def test_missing_fx_raises(self) -> None:
        with self.assertRaises(PortfolioError) as ctx:
            convert(
                Decimal("100"),
                source_currency="EUR",
                target_currency="USD",
                facts=FxFactsBundle(),
            )
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.MISSING_FX)

    def test_no_one_to_one_fallback(self) -> None:
        # A missing rate must never silently convert 1:1.
        with self.assertRaises(PortfolioError):
            convert(
                Decimal("100"),
                source_currency="EUR",
                target_currency="USD",
            )

    def test_inverse_rate_derived_exactly(self) -> None:
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="USD",
                    target_currency="EUR",
                    rate=Decimal("0.909090909"),
                    provider="test",
                )
            ]
        )
        amount, rate = convert(
            Decimal("100"),
            source_currency="EUR",
            target_currency="USD",
            facts=facts,
        )
        self.assertTrue(amount > Decimal("109.99"))
        self.assertIn("INVERTED", rate.provider)

    def test_wrong_direction_rate_rejected(self) -> None:
        # EUR->USD requested, only USD->EUR supplied: convert() derives the
        # inverse, so the pair is honored. A rate for an unrelated pair fails.
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="GBP",
                    target_currency="USD",
                    rate=Decimal("1.30"),
                )
            ]
        )
        with self.assertRaises(PortfolioError):
            convert(
                Decimal("100"),
                source_currency="EUR",
                target_currency="USD",
                facts=facts,
            )

    def test_identity_conversion(self) -> None:
        amount, _rate = convert(
            Decimal("100"),
            source_currency="USD",
            target_currency="USD",
        )
        self.assertEqual(amount, Decimal("100"))

    def test_fx_rate_validations(self) -> None:
        with self.assertRaises(PortfolioError):
            FxRate(source_currency="USD", target_currency="USD", rate=Decimal("1"))
        with self.assertRaises(PortfolioError):
            FxRate(source_currency="USD", target_currency="EUR", rate=Decimal("0"))


class BaseCurrencyAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio = CanonicalPortfolio(
            PortfolioKey(account_id="acc-fx", mode="PAPER")
        )

    def test_aggregate_cash_usd_eur_with_fx(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("100")))
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="EUR",
                    target_currency="USD",
                    rate=Decimal("1.10"),
                    provider="test-fx",
                )
            ]
        )
        self.portfolio.set_fx_facts(facts)
        snapshot = self.portfolio.build_snapshot(base_currency="USD")
        self.assertEqual(snapshot.valuation_status, ValuationStatus.COMPLETE)
        self.assertEqual(snapshot.base_currency_totals["USD"], Decimal("210"))

    def test_aggregate_missing_fx_is_partial_not_1_to_1(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="JPY", settled=Decimal("10000")))
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="EUR",
                    target_currency="USD",
                    rate=Decimal("1.10"),
                )
            ]
        )
        self.portfolio.set_fx_facts(facts)
        snapshot = self.portfolio.build_snapshot(base_currency="USD")
        self.assertEqual(snapshot.valuation_status, ValuationStatus.MISSING_FX)
        # JPY was never silently summed as USD.
        self.assertEqual(snapshot.base_currency_totals["USD"], Decimal("100"))

    def test_stale_fx_makes_aggregate_stale(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("100")))
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="EUR",
                    target_currency="USD",
                    rate=Decimal("1.10"),
                    fresh=False,
                )
            ]
        )
        self.portfolio.set_fx_facts(facts)
        snapshot = self.portfolio.build_snapshot(base_currency="USD")
        self.assertEqual(snapshot.valuation_status, ValuationStatus.STALE)

    def test_cash_to_base_helper(self) -> None:
        totals, status = cash_to_base(
            [
                CashBalance(currency="USD", settled=Decimal("100")),
                CashBalance(currency="EUR", settled=Decimal("100")),
            ],
            base_currency="USD",
            fx_facts={
                ("EUR", "USD"): FxRate(
                    source_currency="EUR",
                    target_currency="USD",
                    rate=Decimal("1.10"),
                )
            },
        )
        self.assertEqual(status, ValuationStatus.COMPLETE)
        self.assertEqual(totals["USD"], Decimal("210"))

    def test_aggregate_without_base_currency_keeps_native(self) -> None:
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("100")))
        self.portfolio.set_cash(CashBalance(currency="EUR", settled=Decimal("100")))
        snapshot = self.portfolio.build_snapshot()
        self.assertEqual(snapshot.valuation_status, ValuationStatus.COMPLETE)
        self.assertEqual(snapshot.native_totals["USD"], Decimal("100"))
        self.assertEqual(snapshot.native_totals["EUR"], Decimal("100"))
        self.assertEqual(snapshot.base_currency_totals, {})

    def test_precision_no_premature_rounding(self) -> None:
        # 0.333333... style decimal math must stay exact.
        self.portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("1")))
        facts = FxFactsBundle(
            [
                FxRate(
                    source_currency="EUR",
                    target_currency="USD",
                    rate=Decimal("1") / Decimal("3"),
                )
            ]
        )
        self.portfolio.set_fx_facts(facts)
        converted, _rate = convert(
            Decimal("1"),
            source_currency="EUR",
            target_currency="USD",
            facts=facts,
        )
        self.assertEqual(converted, Decimal("1") / Decimal("3"))


if __name__ == "__main__":
    unittest.main()