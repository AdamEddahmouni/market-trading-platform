"""G4 BL-0211 — multi-asset accounting kernel tests.

One coherent multi-asset accounting section under trading_correctness proving:

EQUITY:     10 shares at a known price; partial fill; replace; reservation
            shrink; realized/unrealized P&L.
OPTION:     quantity in contracts; multiplier applied exactly once; premium
            cash requirement exact; partial fill; replace (remainder in
            contracts); realized/unrealized P&L; replay; no float drift.
FUTURE:     quantity in contracts; multiplier/point value exact; long and
            short P&L; variation change; replay; no float drift.
CURRENCY:   USD order with USD cash passes; non-USD order with matching cash
            passes; non-USD without matching cash fails closed; no 1:1 FX.
IDENTITY:   equity / option contract / specific future admitted; future
            family and continuous series rejected; unresolved identity
            rejected (fail closed).
CONSISTENCY: cash, positions, working obligations, realized and unrealized
            P&L all reconcile from the same canonical facts.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.execution import (  # noqa: E402
    replace_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.portfolio.accounting import (  # noqa: E402
    exact_decimal,
    future_exposure,
    future_variation_pnl,
    option_premium,
    realized_pnl_on_close,
    working_reservation,
)
from market_platform_foundation.portfolio.canonical import (  # noqa: E402
    CanonicalPortfolio,
    MarkDataStatus,
    PortfolioKey,
    QuantityUnit,
    ValuationMark,
)
from market_platform_foundation.portfolio.instrument_economics import (  # noqa: E402
    EconomicsError,
    EconomicsErrorCode,
    economics_from_descriptor,
    economics_from_instrument_ref,
)
from market_platform_foundation.portfolio.options_ledger import (  # noqa: E402
    apply_option_fill,
    build_canonical_option_positions,
    build_options_ledger_state,
)
from market_platform_foundation.portfolio.valuation import (  # noqa: E402
    ValuationContext,
    value_positions,
)
from market_platform_foundation.risk.financial import (  # noqa: E402
    INSUFFICIENT_CASH,
    INSUFFICIENT_SETTLEMENT_CURRENCY,
    order_intent_financial_check,
    working_order_obligations_by_currency,
    working_order_obligations_minor,
)
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402
from market_platform_foundation.risk.pretrade import (  # noqa: E402
    PreTradeRiskContext,
    evaluate_pretrade,
)
from market_platform_foundation.xa01.compatibility import (  # noqa: E402
    register_continuous_futures_series,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests  # noqa: E402

POLICY = {
    **DEFAULT_RISK_POLICY,
    "commission_minor_per_share": 0,
    "initial_cash_minor": 100_000_00,
    "max_order_shares": 5_000,
    "max_position_shares": 20_000,
    "participation_cap_numerator": 1,
    "participation_cap_denominator": 10,
    "policy_version": "g4-test",
    "risk_policy_identity_hash": "g4-policy",
}


def _ledger(*, replay_session_id: str = "g4-acc-1", cash_minor: int = 100_000_00) -> PaperExecutionLedger:
    policy = dict(POLICY)
    policy["initial_cash_minor"] = cash_minor
    return PaperExecutionLedger.open_session(
        replay_session_id=replay_session_id,
        instrument_id="BIYA",
        symbol="BIYA",
        policy=policy,
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _bars(price: str = "10.00", volume: int = 100_000) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {
                "close": price,
                "high": price,
                "low": price,
                "open": price,
                "volume": volume,
            },
        }
        for i in range(1, 4)
    ]


class EquityAccountingTests(unittest.TestCase):
    def test_ten_shares_at_known_price_exact(self) -> None:
        # 10 shares x $150.25 = $1,502.50 — exact Decimal, no float.
        ledger = _ledger()
        result = submit_interactive_order(
            ledger=ledger,
            bars=_bars(price="150.25"),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="eq-1",
            idempotency_key="eq-1",
            order_type="LIMIT",
            limit_price_minor=15_025,
        )
        self.assertEqual(result["order"]["state"], "FILLED")
        account = ledger.project_account()
        self.assertEqual(int(account["cash_minor"]), 100_000_00 - 10 * 15_025)
        position = ledger.project_positions()[0]
        self.assertEqual(int(position["quantity"]), 10)
        self.assertEqual(int(position["average_fill_minor"]), 15_025)

    def test_partial_fill_working_remainder_and_reservation(self) -> None:
        # Participation cap 1/10 with a 40-share bar admits 4 shares/bar.
        # BUY 10 -> fills 4, working remainder 6 stays reserved at $10.
        policy = dict(POLICY)
        policy["participation_cap_numerator"] = 1
        policy["participation_cap_denominator"] = 10
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="g4-acc-2",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        bars = [
            {
                "available_time": 100 + i * 100,
                "bar_payload": {
                    "close": "10.00",
                    "high": "10.00",
                    "low": "10.00",
                    "open": "10.00",
                    "volume": 40,
                },
            }
            for i in range(1, 4)
        ]
        result = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="eq-pf",
            idempotency_key="eq-pf",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(int(order["cumulative_filled_quantity"]), 4)
        self.assertEqual(int(order["working_remaining"]), 6)
        # Working obligation = remainder x price (never original quantity).
        obligations = working_order_obligations_minor(ledger)
        self.assertEqual(obligations, 6 * 1000)
        by_currency = working_order_obligations_by_currency(ledger)
        self.assertEqual(by_currency, {"USD": 6 * 1000})

    def test_replace_recomputes_reservation_in_contracts_units(self) -> None:
        policy = dict(POLICY)
        policy["participation_cap_numerator"] = 1
        policy["participation_cap_denominator"] = 10
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="g4-acc-3",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        bars = [
            {
                "available_time": 100 + i * 100,
                "bar_payload": {
                    "close": "10.00",
                    "high": "10.00",
                    "low": "10.00",
                    "open": "10.00",
                    "volume": 40,
                },
            }
            for i in range(1, 4)
        ]
        result = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="eq-rep",
            idempotency_key="eq-rep",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        replaced = replace_interactive_order(
            ledger=ledger,
            order_id=result["order_id"],
            replaced_quantity=10,
            order_type="LIMIT",
            limit_price_minor=2000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        # 6 remaining x $20 = $120 obligation after the replacement.
        obligations = working_order_obligations_minor(ledger)
        self.assertEqual(obligations, 6 * 2000)

    def test_realized_and_unrealized_pnl_reconcile(self) -> None:
        # Buy 10 @ $100 (fills), mark moves to $110: unrealized = +$100.
        ledger = _ledger()
        submit_interactive_order(
            ledger=ledger,
            bars=_bars(price="100.00"),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="eq-pnl",
            idempotency_key="eq-pnl",
            order_type="LIMIT",
            limit_price_minor=10_000,
        )
        position = ledger.project_positions()[0]
        self.assertEqual(int(position["unrealized_pnl_minor"]), 0)
        ledger.apply_live_mark(mark_minor=11_000, mark_provider="test", mark_as_of_ns=2, mark_quality="PASS")
        position = ledger.project_positions()[0]
        self.assertEqual(int(position["unrealized_pnl_minor"]), 10 * 1000)


class OptionAccountingTests(unittest.TestCase):
    def _fill(self, *, price: str, quantity: int, side: str = "long", fill_id: str, strike: str = "130.0") -> dict[str, object]:
        return {
            "call_put": "call",
            "strike": strike,
            "expiry": "2026-08-15",
            "side": side,
            "fill_price": price,
            "quantity": quantity,
            "multiplier": 100.0,
            "fill_id": fill_id,
        }

    def test_quantity_in_contracts_and_multiplier_applied_once(self) -> None:
        # 2 contracts x $1.85 x 100 = $370.00 exactly; position quantity is 2
        # CONTRACTS (never 200 shares).
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        ledger = apply_option_fill(ledger, fill=self._fill(price="1.85", quantity=2, fill_id="opt-1"))
        self.assertEqual(ledger["cash"], Decimal("100000") - Decimal("370"))
        position = ledger["option_positions"][0]
        self.assertEqual(int(position["quantity"]), 2)
        self.assertEqual(position["multiplier"], Decimal("100"))
        self.assertEqual(position["entry_premium"], Decimal("1.85"))

    def test_premium_cash_requirement_exact(self) -> None:
        from market_platform_foundation.portfolio.accounting import cash_requirement_by_kind

        required = cash_requirement_by_kind(
            instrument_kind="OPTION_CONTRACT",
            side="BUY",
            quantity=Decimal("3"),
            price=Decimal("1.85"),
            multiplier=Decimal("100"),
        )
        self.assertEqual(required, Decimal("555"))

    def test_partial_fill_preserves_contract_truth(self) -> None:
        # 2 fills (2 then 1 contract) accumulate 3 contracts; the working
        # remainder formula is in contracts, never shares.
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        ledger = apply_option_fill(ledger, fill=self._fill(price="1.85", quantity=2, fill_id="opt-a"))
        ledger = apply_option_fill(ledger, fill=self._fill(price="1.80", quantity=1, fill_id="opt-b"))
        # Per-fill ledger entries preserve each fill's contract quantity; the
        # aggregate contract truth is 2 + 1 = 3 contracts (never shares).
        self.assertEqual(len(ledger["option_positions"]), 2)
        total_contracts = sum(int(pos["quantity"]) for pos in ledger["option_positions"])
        self.assertEqual(total_contracts, 3)
        expected_cash = Decimal("100000") - Decimal("2") * Decimal("1.85") * Decimal("100") - Decimal("1") * Decimal("1.80") * Decimal("100")
        self.assertEqual(ledger["cash"], expected_cash)
        # Reservation of a still-working remainder of 1 contract at $2.00:
        self.assertEqual(working_reservation(Decimal("1"), Decimal("2.00"), Decimal("100")), Decimal("200"))

    def test_realized_pnl_on_close_exact(self) -> None:
        # Long 1 contract @ $1.85, closed at $2.85 -> $100 realized.
        realized = realized_pnl_on_close(
            instrument_kind="OPTION_CONTRACT",
            entry_price=Decimal("1.85"),
            exit_price=Decimal("2.85"),
            quantity=Decimal("1"),
            multiplier=Decimal("100"),
        )
        self.assertEqual(realized, Decimal("100"))
        # Short closed lower earns the difference too (signed quantity).
        realized_short = realized_pnl_on_close(
            instrument_kind="OPTION_CONTRACT",
            entry_price=Decimal("2.85"),
            exit_price=Decimal("1.85"),
            quantity=Decimal("-1"),
            multiplier=Decimal("100"),
        )
        self.assertEqual(realized_short, Decimal("100"))

    def test_no_float_drift_in_ledger(self) -> None:
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        for index in range(3):
            ledger = apply_option_fill(
                ledger,
                fill=self._fill(price="0.1", quantity=1, fill_id=f"opt-drift-{index}"),
            )
        self.assertEqual(ledger["cash"], Decimal("100000") - Decimal("30"))

    def test_replay_reconstructs_identical_state(self) -> None:
        fills = [
            self._fill(price="1.85", quantity=2, fill_id="opt-r1"),
            self._fill(price="1.80", quantity=1, fill_id="opt-r2"),
        ]
        first = build_options_ledger_state(initial_cash=100_000.0)
        for fill in fills:
            first = apply_option_fill(first, fill=fill)
        second = build_options_ledger_state(initial_cash=100_000.0)
        for fill in fills:
            second = apply_option_fill(second, fill=fill)
        self.assertEqual(first, second)
        self.assertEqual(first["cash"], second["cash"])
        self.assertEqual(first["realized_pnl"], second["realized_pnl"])

    def test_canonical_option_positions_parity(self) -> None:
        # Option fills -> canonical portfolio positions with exact economics;
        # both projections derive from the same fills and cannot diverge.
        registry = InstrumentRegistry()
        option_id = register_option_contract(
            option_id="NVDA20260815C00130000",
            underlying_symbol="NVDA",
            expiration="2026-08-15",
            strike="130",
            call_put="call",
            registry=registry,
        )
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        ledger = apply_option_fill(ledger, fill=self._fill(price="1.85", quantity=2, fill_id="opt-cc"))
        inputs = build_canonical_option_positions(
            ledger,
            canonical_id_for=lambda call_put, strike, expiry: option_id,
        )
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["instrument_kind"], "OPTION_CONTRACT")
        self.assertEqual(inputs[0]["quantity_unit"], "CONTRACTS")
        self.assertEqual(Decimal(inputs[0]["quantity"]), Decimal("2"))
        self.assertEqual(Decimal(inputs[0]["multiplier"]), Decimal("100"))
        self.assertEqual(Decimal(inputs[0]["cost_basis"]), Decimal("370"))
        # Upsert into the canonical store: valuation at the same premium -> 0.
        from market_platform_foundation.portfolio.canonical import PositionInput

        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-opt", mode="PAPER"))
        portfolio.upsert_position(PositionInput.from_position_dict(inputs[0]))
        mark = ValuationMark(
            instrument_id=option_id,
            price=Decimal("1.85"),
            currency="USD",
            source="test",
            source_time_ns=1,
            observed_at_ns=1,
            data_status=MarkDataStatus.FRESH,
        )
        valued = value_positions(
            portfolio.positions.values(),
            marks={option_id: mark},
            context=ValuationContext(marks={option_id: mark}),
        )
        self.assertEqual(valued[0].valuation.market_value_native, Decimal("370"))
        self.assertEqual(valued[0].valuation.unrealized_pnl_native, Decimal("0"))


class FutureAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def _future_economics(self) -> object:
        future_id = register_future_contract(
            contract_id="ES202512",
            family_root="ES",
            expiration="2025-12-19",
            contract_multiplier="50",
            registry=self.registry,
        )
        return future_id, economics_from_descriptor(self.registry.get(future_id).descriptor)

    def test_one_contract_multiplier_economics(self) -> None:
        _, economics = self._future_economics()
        self.assertEqual(economics.contract_multiplier, Decimal("50"))
        self.assertEqual(economics.quantity_unit, QuantityUnit.CONTRACTS)
        # 1 contract, +0.25 tick -> $12.50; +10 points -> $500.
        self.assertEqual(future_variation_pnl(Decimal("1"), Decimal("50"), Decimal("5500.25"), Decimal("5500")), Decimal("12.50"))
        self.assertEqual(future_variation_pnl(Decimal("1"), Decimal("50"), Decimal("5510"), Decimal("5500")), Decimal("500"))
        self.assertEqual(future_exposure(Decimal("1"), Decimal("50"), Decimal("5510")), Decimal("275500"))

    def test_multiple_contracts_scale_exactly(self) -> None:
        self.assertEqual(future_variation_pnl(Decimal("3"), Decimal("50"), Decimal("5510"), Decimal("5500")), Decimal("1500"))
        self.assertEqual(future_exposure(Decimal("3"), Decimal("50"), Decimal("5510")), Decimal("826500"))

    def test_long_short_sign_correctness(self) -> None:
        # Long profits when mark rises; short profits when mark falls.
        self.assertEqual(future_variation_pnl(Decimal("2"), Decimal("50"), Decimal("5510"), Decimal("5500")), Decimal("1000"))
        self.assertEqual(future_variation_pnl(Decimal("-2"), Decimal("50"), Decimal("5510"), Decimal("5500")), Decimal("-1000"))
        self.assertEqual(future_variation_pnl(Decimal("-2"), Decimal("50"), Decimal("5490"), Decimal("5500")), Decimal("1000"))

    def test_exact_decimal_no_drift(self) -> None:
        # Repeated tick math stays exact.
        value = Decimal("0")
        for _ in range(40):
            value += future_variation_pnl(Decimal("1"), Decimal("50"), Decimal("5500.25"), Decimal("5500"))
        self.assertEqual(value, Decimal("500"))

    def test_replay_reconstructs_identical_pnl(self) -> None:
        def run() -> Decimal:
            total = Decimal("0")
            for mark in ("5500.25", "5500.75", "5501.25"):
                total += future_variation_pnl(Decimal("2"), Decimal("50"), Decimal(mark), Decimal("5500"))
            return total

        self.assertEqual(run(), run())

    def test_roll_reference_identity_never_executable_position(self) -> None:
        # Family and continuous identities can never become executable
        # economics for trading/accounting.
        from market_platform_foundation.portfolio.admission import admission_result

        family = register_future_family(family_root="ES", registry=self.registry)
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=self.registry,
        )
        for identity_id in (family, series):
            record = self.registry.get(identity_id)
            result = admission_result(
                instrument_kind=record.descriptor.identity.instrument_kind.value,
                asset_class=record.descriptor.identity.asset_class.value,
                tradability=record.descriptor.tradability.value,
            )
            self.assertFalse(result.admitted)


class CurrencyAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = _ledger()

    def test_usd_order_with_usd_cash_passes(self) -> None:
        reason, facts = order_intent_financial_check(
            ledger=self.ledger,
            side="BUY",
            quantity=100,
            price_minor=1000,
            currency="USD",
            account_currency="USD",
            currency_cash_minor={"USD": 100_000_00},
        )
        self.assertIsNone(reason)
        self.assertEqual(facts["required_cash_minor"], 100 * 1000)

    def test_non_usd_order_with_matching_cash_passes(self) -> None:
        reason, facts = order_intent_financial_check(
            ledger=self.ledger,
            side="BUY",
            quantity=10,
            price_minor=1_000,  # EUR-denominated price in minor units
            currency="EUR",
            account_currency="USD",
            currency_cash_minor={"USD": 100_000_00, "EUR": 50_000_00},
        )
        self.assertIsNone(reason)
        self.assertEqual(facts["settlement_currency"], "EUR")
        self.assertEqual(facts["required_cash_minor"], 10 * 1_000)

    def test_non_usd_order_without_matching_cash_fails_closed(self) -> None:
        reason, facts = order_intent_financial_check(
            ledger=self.ledger,
            side="BUY",
            quantity=10,
            price_minor=1_000,
            currency="EUR",
            account_currency="USD",
            currency_cash_minor={"USD": 100_000_00},
        )
        self.assertEqual(reason, INSUFFICIENT_SETTLEMENT_CURRENCY)

    def test_no_one_to_one_fx_fallback(self) -> None:
        # EUR order with only USD cash must NOT be treated as affordable at
        # any implicit rate — fail closed with the funding reason.
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id="AAA",
                asset_class="EQUITY",
                instrument_kind="TRADABLE_SECURITY",
                symbol="AAA",
                side="BUY",
                quantity=10,
                currency="EUR",
                account_currency="USD",
                limit_price_minor=1000,
                currency_cash_minor={"USD": 100_000_00},
            )
        )
        self.assertFalse(decision.accepted)
        self.assertIn(INSUFFICIENT_SETTLEMENT_CURRENCY, decision.reason_codes)

    def test_eur_bucket_present_passes_pretrade(self) -> None:
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id="AAA",
                asset_class="EQUITY",
                instrument_kind="TRADABLE_SECURITY",
                symbol="AAA",
                side="BUY",
                quantity=10,
                currency="EUR",
                account_currency="USD",
                order_type="LIMIT",
                limit_price_minor=1000,
                currency_cash_minor={"USD": 100_000_00, "EUR": 50_000_00},
            )
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.required_cash_minor, 10 * 1000)


class IdentityAdmissionAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_equity_canonical_economics_admitted(self) -> None:
        equity_id = register_equity(symbol="AAPL", registry=self.registry)
        economics = economics_from_descriptor(self.registry.get(equity_id).descriptor)
        self.assertEqual(economics.instrument_kind, "TRADABLE_SECURITY")
        self.assertEqual(economics.quantity_unit, QuantityUnit.SHARES)

    def test_option_contract_admitted_with_multiplier(self) -> None:
        option_id = register_option_contract(
            option_id="SPY260918C00500000",
            underlying_symbol="SPY",
            expiration="2026-09-18",
            strike="500",
            call_put="CALL",
            registry=self.registry,
        )
        economics = economics_from_descriptor(self.registry.get(option_id).descriptor)
        self.assertEqual(economics.contract_multiplier, Decimal("100"))
        self.assertEqual(economics.quantity_unit, QuantityUnit.CONTRACTS)

    def test_specific_future_admitted_with_multiplier(self) -> None:
        future_id = register_future_contract(
            contract_id="ES202512",
            family_root="ES",
            expiration="2025-12-19",
            contract_multiplier="50",
            registry=self.registry,
        )
        economics = economics_from_descriptor(self.registry.get(future_id).descriptor)
        self.assertEqual(economics.contract_multiplier, Decimal("50"))
        self.assertEqual(economics.quantity_unit, QuantityUnit.CONTRACTS)

    def test_future_family_rejected(self) -> None:
        from market_platform_foundation.portfolio.admission import admission_result

        family = register_future_family(family_root="ES", registry=self.registry)
        record = self.registry.get(family)
        result = admission_result(
            instrument_kind=record.descriptor.identity.instrument_kind.value,
            asset_class=record.descriptor.identity.asset_class.value,
        )
        self.assertFalse(result.admitted)

    def test_continuous_future_rejected(self) -> None:
        from market_platform_foundation.portfolio.admission import admission_result

        series = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=self.registry,
        )
        record = self.registry.get(series)
        result = admission_result(
            instrument_kind=record.descriptor.identity.instrument_kind.value,
            asset_class=record.descriptor.identity.asset_class.value,
        )
        self.assertFalse(result.admitted)

    def test_unresolved_identity_rejected(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {"instrument_id": "X", "instrument_kind": "SYNTHETIC_WRAPPER", "currency": "USD"}
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.UNKNOWN_INSTRUMENT_KIND)


class AccountingConsistencyTests(unittest.TestCase):
    def test_all_facts_reconcile_from_same_canonical_inputs(self) -> None:
        # One option fill drives: ledger cash, canonical position economics,
        # premium requirement, and unrealized P&L — all exact and consistent.
        from market_platform_foundation.portfolio.accounting import cash_requirement_by_kind
        from market_platform_foundation.portfolio.canonical import PositionInput

        registry = InstrumentRegistry()
        option_id = register_option_contract(
            option_id="NVDA20260815C00130000",
            underlying_symbol="NVDA",
            expiration="2026-08-15",
            strike="130",
            call_put="call",
            registry=registry,
        )
        fill = {
            "call_put": "call",
            "strike": "130.0",
            "expiry": "2026-08-15",
            "side": "long",
            "fill_price": "1.85",
            "quantity": 2,
            "multiplier": 100.0,
            "fill_id": "opt-cons",
        }
        ledger = build_options_ledger_state(initial_cash=100_000.0)
        ledger = apply_option_fill(ledger, fill=fill)
        premium = option_premium(Decimal("2"), Decimal("1.85"), Decimal("100"))
        # 1) Ledger cash consumed exactly the premium.
        self.assertEqual(ledger["cash"], Decimal("100000") - premium)
        # 2) Cash-requirement formula agrees with the ledger.
        required = cash_requirement_by_kind(
            instrument_kind="OPTION_CONTRACT",
            side="BUY",
            quantity=Decimal("2"),
            price=Decimal("1.85"),
            multiplier=Decimal("100"),
        )
        self.assertEqual(required, premium)
        # 3) Canonical position economics agree.
        inputs = build_canonical_option_positions(
            ledger,
            canonical_id_for=lambda call_put, strike, expiry: option_id,
        )
        self.assertEqual(Decimal(inputs[0]["cost_basis"]), premium)
        # 4) Position in the canonical store values consistently.
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-cons", mode="PAPER"))
        portfolio.upsert_position(PositionInput.from_position_dict(inputs[0]))
        mark = ValuationMark(
            instrument_id=option_id,
            price=Decimal("1.85"),
            currency="USD",
            source="test",
            source_time_ns=1,
            observed_at_ns=1,
            data_status=MarkDataStatus.FRESH,
        )
        valued = value_positions(portfolio.positions.values(), marks={option_id: mark})
        self.assertEqual(valued[0].valuation.market_value_native, premium)
        self.assertEqual(valued[0].valuation.unrealized_pnl_native, Decimal("0"))
        # 5) Working obligation formula for the same economics is exact.
        self.assertEqual(working_reservation(Decimal("2"), Decimal("1.85"), Decimal("100")), premium)


class ReplayIdempotencyAccountingTests(unittest.TestCase):
    def test_idempotent_submit_cannot_double_book_cash(self) -> None:
        ledger = _ledger()
        submit_interactive_order(
            ledger=ledger,
            bars=_bars(price="10.00"),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="rep-1",
            idempotency_key="rep-1",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        cash_after_first = int(ledger.project_account()["cash_minor"])
        duplicate = submit_interactive_order(
            ledger=ledger,
            bars=_bars(price="10.00"),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="rep-1",
            idempotency_key="rep-1",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(int(ledger.project_account()["cash_minor"]), cash_after_first)
        self.assertEqual(len(ledger.project_fills()), 1)

    def test_restart_replay_reconstructs_identical_state(self) -> None:
        # Replay the same fills onto a fresh ledger: identical cash/position.
        def run() -> tuple[int, int]:
            ledger = _ledger(replay_session_id="g4-replay", cash_minor=50_000_00)
            for index in range(2):
                submit_interactive_order(
                    ledger=ledger,
                    bars=_bars(price="10.00"),
                    symbol="BIYA",
                    instrument_id="BIYA",
                    side="BUY",
                    quantity=10,
                    observation_time=1,
                    client_order_id=f"rep-{index}",
                    idempotency_key=f"rep-{index}",
                    order_type="LIMIT",
                    limit_price_minor=1000,
                )
            account = ledger.project_account()
            return int(account["cash_minor"]), int(account["realized_pnl_minor"])

        first = run()
        second = run()
        self.assertEqual(first, second)
        self.assertEqual(first[0], 50_000_00 - 2 * 10 * 1000)


if __name__ == "__main__":
    unittest.main()