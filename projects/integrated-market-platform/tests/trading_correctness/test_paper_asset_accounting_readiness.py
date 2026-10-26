"""Exact fill accounting regressions; all fixtures are internal simulation."""

from decimal import Decimal
import unittest

import market_platform_foundation.paper  # Initialize the established Paper package boundary.
from market_platform_foundation.portfolio.accounting import AccountingError
from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio, CashBalance, PortfolioError, PortfolioKey, PortfolioSnapshot, PositionInput,
    QuantityUnit, ValuationMark,
)
from market_platform_foundation.portfolio.paper_fill import (
    apply_paper_fill_to_portfolio, rebuild_portfolio_from_fills,
)


POLICY = {"currency": "USD", "price_scale": 100,
          "commission_minor_per_share": 0, "fee_minor_per_order": 0}


def instrument(kind="OPTION_CONTRACT", **extra):
    return {"instrument_id": "TEST", "instrument_kind": kind,
            "asset_class": {"OPTION_CONTRACT": "OPTION", "FUTURE_CONTRACT": "FUTURE",
                            "CRYPTO_PAIR": "CRYPTO", "TRADABLE_SECURITY": "EQUITY"}[kind],
            "currency": "USD", "contract_multiplier": "50" if kind == "FUTURE_CONTRACT" else
            "100" if kind == "OPTION_CONTRACT" else "1", **extra}


def margin(amount="15000", **extra):
    return {"instrument_id": "TEST", "provider": "fixture", "currency": "USD",
            "initial_margin_per_contract": amount, "maintenance_margin_per_contract": amount,
            "effective_time_ns": 1, "received_time_ns": 1, **extra}


def fill(ref, qty=1, price=200, direction="long", **extra):
    return {"fill_id": "f", "instrument_id": "TEST", "instrument": ref,
            "fill_quantity": qty, "fill_price_minor": price, "direction": direction,
            "fill_time": 10, **extra}


class PaperAssetAccountingReadinessTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = CanonicalPortfolio(PortfolioKey(account_id="test", mode="PAPER"))
        self.portfolio.set_cash(CashBalance("USD", Decimal("100000")))
        self.ids = set()

    def apply(self, row, policy=None):
        return apply_paper_fill_to_portfolio(self.portfolio, fill=row,
                                           policy=policy or POLICY, applied_fill_ids=self.ids)

    def state(self):
        return self.portfolio.build_snapshot().to_dict()

    def assert_rejected_unchanged(self, row):
        before, ids = self.state(), set(self.ids)
        with self.assertRaises((ValueError, PortfolioError, AccountingError)):
            self.apply(row)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.ids, ids)

    def test_option_average_cost_is_quoted_premium_not_contract_value(self):
        self.apply(fill(instrument()))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(pos.average_cost, Decimal("2"))
        self.assertEqual(pos.cost_basis, Decimal("200"))
        result = self.apply(fill(instrument(), price=300, direction="short", fill_id="close"))
        self.assertEqual(result.realized_pnl_delta_native, Decimal("100"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("100100"))

    def test_option_partial_close_retains_multiplier_cost_basis(self):
        self.apply(fill(instrument(), qty=3))
        result = self.apply(fill(instrument(), price=300, direction="short", fill_id="close"))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(pos.cost_basis, Decimal("400"))
        self.assertEqual(pos.average_cost, Decimal("2"))
        self.assertEqual(result.realized_pnl_delta_native, Decimal("100"))

    def test_option_scale_in_keeps_weighted_quote_and_mark_pnl(self):
        self.apply(fill(instrument(), qty=2))
        self.apply(fill(instrument(), qty=2, price=400, fill_id="scale"))
        self.portfolio.apply_mark(ValuationMark("TEST", Decimal("4"), "USD"))
        pos = self.portfolio.build_snapshot().positions[0]
        self.assertEqual(pos.average_cost, Decimal("3"))
        self.assertEqual(pos.cost_basis, Decimal("1200"))
        self.assertEqual(pos.valuation.unrealized_pnl_native, Decimal("400"))

    def test_futures_scale_in_reserves_every_fill(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, qty=2, price=500000, margin_facts=margin()))
        result = self.apply(fill(ref, price=560000, margin_facts=margin("18000"), fill_id="scale"))
        self.assertEqual(result.cash_delta_native, Decimal("-18000"))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(getattr(pos, "reserved_margin_native", None), Decimal("48000"))
        self.assertEqual(pos.average_cost, Decimal("5200"))

    def test_futures_partial_close_retains_entry_basis(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, qty=2, price=500000, margin_facts=margin()))
        result = self.apply(fill(ref, price=510000, direction="short", fill_id="close"))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(pos.average_cost, Decimal("5000"))
        self.assertEqual(pos.cost_basis, Decimal("5000"))
        self.assertEqual(result.realized_pnl_delta_native, Decimal("5000"))
        self.assertEqual(result.cash_delta_native, Decimal("20000"))

    def test_futures_close_releases_recorded_margin_not_new_facts(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, qty=2, price=500000, margin_facts=margin()))
        result = self.apply(fill(ref, qty=2, price=510000, direction="short",
                                 margin_facts=margin("99000"), fill_id="close"))
        self.assertEqual(result.cash_delta_native, Decimal("40000"))
        self.assertIsNone(self.portfolio.get_position("TEST"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("110000"))

    def test_reserved_margin_round_trips_before_close(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, qty=2, price=500000, margin_facts=margin()))
        raw = self.state()
        self.assertEqual(raw["positions"][0].get("reserved_margin_native"), "30000")
        restored = PortfolioSnapshot.from_dict(raw)
        self.portfolio = CanonicalPortfolio(self.portfolio.key)
        self.portfolio.apply_snapshot(restored)
        self.apply(fill(ref, qty=2, price=500000, direction="short", fill_id="close"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("100000"))

    def test_futures_scale_in_requires_its_own_margin_facts(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, price=500000, margin_facts=margin()))
        self.assert_rejected_unchanged(fill(ref, price=500000, fill_id="scale"))

    def test_futures_margin_reservation_rounds_up_to_settlement_unit(self):
        ref = instrument("FUTURE_CONTRACT")
        result = self.apply(fill(ref, margin_facts=margin("15000.001")))
        self.assertEqual(result.cash_delta_native, Decimal("-15000.01"))
        result = self.apply(fill(ref, direction="short", fill_id="close"))
        self.assertEqual(result.cash_delta_native, Decimal("15000.01"))

    def test_futures_weighted_reservation_and_entry_survive_two_closes(self):
        ref = instrument("FUTURE_CONTRACT")
        self.apply(fill(ref, qty=2, price=500000, margin_facts=margin()))
        self.apply(fill(ref, price=560000, margin_facts=margin("18000"), fill_id="scale"))
        result = self.apply(fill(ref, price=530000, direction="short", fill_id="close1"))
        self.assertEqual(result.cash_delta_native, Decimal("21000"))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(pos.average_cost, Decimal("5200"))
        self.assertEqual(pos.reserved_margin_native, Decimal("32000"))
        result = self.apply(fill(ref, qty=2, price=540000, direction="short", fill_id="close2"))
        self.assertEqual(result.cash_delta_native, Decimal("52000"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("125000"))

    def test_mismatched_fill_identity_is_rejected_before_mutation(self):
        self.assert_rejected_unchanged(fill(instrument(), instrument_id="OTHER"))

    def test_futures_open_rejects_wrong_currency_or_instrument_margin(self):
        ref = instrument("FUTURE_CONTRACT")
        for facts in [margin(currency="EUR"), margin(instrument_id="OTHER"), margin("-1")]:
            with self.subTest(facts=facts):
                self.assert_rejected_unchanged(fill(ref, margin_facts=facts))

    def test_derivative_oversells_fail_before_any_mutation(self):
        for kind in ("OPTION_CONTRACT", "FUTURE_CONTRACT"):
            with self.subTest(kind=kind):
                self.setUp()
                ref = instrument(kind)
                self.apply(fill(ref, margin_facts=margin()))
                self.assert_rejected_unchanged(fill(ref, qty=2, direction="short", fill_id="oversell"))

    def test_invalid_existing_short_derivative_fails_before_buy(self):
        for kind in ("OPTION_CONTRACT", "FUTURE_CONTRACT"):
            with self.subTest(kind=kind):
                self.setUp()
                self.portfolio.upsert_position(PositionInput("TEST", "OPTION" if kind == "OPTION_CONTRACT"
                                                             else "FUTURE", kind, Decimal("-1"),
                                                             QuantityUnit.CONTRACTS, "USD"))
                self.assert_rejected_unchanged(fill(instrument(kind)))

    def test_invalid_admission_never_mutates_cash_or_duplicate_set(self):
        self.assert_rejected_unchanged(fill(instrument(asset_class="CRYPTO")))

    def test_failed_fill_can_retry_same_id_after_fix(self):
        row = fill(instrument("FUTURE_CONTRACT"))
        with self.assertRaises(ValueError):
            self.apply(row)
        self.assertNotIn("f", self.ids)
        self.apply({**row, "margin_facts": margin()})
        self.assertIn("f", self.ids)

    def test_crypto_fractional_open_partial_close_and_mark_are_exact(self):
        ref = instrument("CRYPTO_PAIR", price_scale=100000000)
        self.apply(fill(ref, qty="0.125", price=123456789,
                        commission_minor=3, fees_minor=2))
        result = self.apply(fill(ref, qty="0.025", price=200000000, direction="short",
                                 commission_minor=1, fees_minor=1, fill_id="close"))
        pos = self.portfolio.get_position("TEST")
        self.assertEqual(pos.quantity, Decimal("0.100"))
        self.assertEqual(pos.cost_basis, Decimal("0.123456789"))
        self.assertEqual(pos.average_cost, Decimal("1.23456789"))
        self.assertEqual(result.realized_pnl_delta_native, Decimal("-0.00086419725"))
        self.assertEqual(self.portfolio.cash_balances[0].settled, Decimal("99999.82567901375"))
        self.portfolio.apply_mark(ValuationMark("TEST", Decimal("2"), "USD"))
        marked = self.portfolio.build_snapshot().positions[0]
        self.assertEqual(marked.valuation.unrealized_pnl_native, Decimal("0.076543211"))

    def test_crypto_replay_and_full_close_preserve_exact_cash(self):
        ref = instrument("CRYPTO_PAIR", price_scale=100000000)
        rows = [fill(ref, qty="0.1", price=123456789),
                fill(ref, qty="0.2", price=200000000, fill_id="scale"),
                fill(ref, qty="0.3", price=300000000, direction="short", fill_id="close")]
        replay = CanonicalPortfolio(self.portfolio.key)
        rebuild_portfolio_from_fills(replay, fills=[(row, None) for row in rows],
                                     policy=POLICY, initial_cash_minor=10000000)
        for row in rows:
            self.apply(row)
        self.assertIsNone(replay.get_position("TEST"))
        self.assertEqual(replay.cash_balances[0].settled, Decimal("100000.376543211"))
        self.assertEqual(replay.build_snapshot().to_dict(), self.state())

    def test_crypto_cannot_oversell_or_borrow(self):
        ref = instrument("CRYPTO_PAIR")
        self.assert_rejected_unchanged(fill(ref, direction="short"))
        self.assert_rejected_unchanged(fill(ref, qty="100000", price=200))

    def test_crypto_quote_currency_cannot_spend_usd_as_usdt(self):
        self.assert_rejected_unchanged(fill(instrument("CRYPTO_PAIR", currency="USDT")))

    def test_invalid_quantity_direction_price_and_derivative_multiplier_are_atomic(self):
        for change in [{"fill_quantity": "1.1"}, {"fill_quantity": 0},
                       {"fill_quantity": -1}, {"fill_quantity": True},
                       {"fill_quantity": 1.25}, {"direction": "garbage"},
                       {"fill_price_minor": -1}]:
            with self.subTest(change=change):
                self.assert_rejected_unchanged({**fill(instrument()), **change})
        self.assert_rejected_unchanged(fill(instrument(contract_multiplier="0")))

    def test_crypto_nonfinite_float_and_overprecision_quantities_rejected(self):
        ref = instrument("CRYPTO_PAIR", quantity_step="0.00000001")
        for qty in ["NaN", "Infinity", 0.1, "0.000000001"]:
            with self.subTest(qty=qty):
                self.assert_rejected_unchanged(fill(ref, qty=qty))

    def test_crypto_valid_partial_fill_can_be_below_order_minimum(self):
        ref = instrument("CRYPTO_PAIR", quantity_step="0.001", minimum_quantity="0.1")
        result = self.apply(fill(ref, qty="0.025"))
        self.assertEqual(result.position_quantity_after, Decimal("0.025"))
        self.assertEqual(result.cash_delta_native, Decimal("-0.05"))

    def test_legacy_equity_integer_fill_replay_is_unchanged(self):
        ref = instrument("TRADABLE_SECURITY")
        self.apply(fill(ref, qty=3, price=1250))
        result = self.apply(fill(ref, qty=1, price=1500, direction="short", fill_id="close"))
        self.assertEqual(result.realized_pnl_delta_native, Decimal("2.5"))
        self.assertEqual(self.portfolio.get_position("TEST").cost_basis, Decimal("25"))
        self.assertNotIn("reserved_margin_native", self.state()["positions"][0])
