"""G4 BL-0211 — canonical instrument economics contract + accounting kernel tests.

Proves the fail-closed economics contract (Phase 1) and the central exact
Decimal accounting kernel (Phase 2):

- economics resolve from canonical XA-01 descriptors and instrument refs;
- quantity unit is kind-driven (SHARES/CONTRACTS/BASE_UNITS), never symbolic;
- derivative multipliers are explicit and positive — missing/zero fails closed;
- multiplier=1 is valid only for equity/ETF semantics;
- the accounting kernel rejects binary float and is exact for options/futures;
- working reservation uses remaining x price x multiplier (never desired qty).
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.portfolio.accounting import (  # noqa: E402
    AccountingError,
    AccountingErrorCode,
    cash_requirement_by_kind,
    exact_decimal,
    future_exposure,
    future_variation_pnl,
    market_value_by_kind,
    option_premium,
    realized_pnl_on_close,
    working_reservation,
)
from market_platform_foundation.portfolio.canonical import (  # noqa: E402
    PortfolioError,
    PortfolioErrorCode,
    QuantityUnit,
)
from market_platform_foundation.portfolio.instrument_economics import (  # noqa: E402
    EconomicsError,
    EconomicsErrorCode,
    InstrumentEconomics,
    assert_derivative_position_economics,
    economics_from_descriptor,
    economics_from_instrument_ref,
    kind_default_quantity_unit,
)
from market_platform_foundation.xa01.compatibility import (  # noqa: E402
    register_equity,
    register_future_contract,
    register_option_contract,
)
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests  # noqa: E402


class KindQuantityUnitTests(unittest.TestCase):
    def test_kind_default_units(self) -> None:
        self.assertEqual(kind_default_quantity_unit("TRADABLE_SECURITY"), QuantityUnit.SHARES)
        self.assertEqual(kind_default_quantity_unit("ETF_FUND"), QuantityUnit.SHARES)
        self.assertEqual(kind_default_quantity_unit("OPTION_CONTRACT"), QuantityUnit.CONTRACTS)
        self.assertEqual(kind_default_quantity_unit("FUTURE_CONTRACT"), QuantityUnit.CONTRACTS)
        self.assertEqual(kind_default_quantity_unit("CRYPTO_PAIR"), QuantityUnit.BASE_UNITS)
        self.assertEqual(kind_default_quantity_unit("BOND"), QuantityUnit.FACE_VALUE)

    def test_unknown_kind_fails_closed(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            kind_default_quantity_unit("NOT_A_KIND")
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.UNSUPPORTED_ECONOMICS)


class DescriptorEconomicsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_equity_descriptor_economics(self) -> None:
        equity_id = register_equity(symbol="AAPL", registry=self.registry)
        record = self.registry.get(equity_id)
        economics = economics_from_descriptor(record.descriptor, registry=self.registry)
        self.assertEqual(economics.instrument_kind, "TRADABLE_SECURITY")
        self.assertEqual(economics.quantity_unit, QuantityUnit.SHARES)
        self.assertEqual(economics.price_currency, "USD")
        self.assertEqual(economics.settlement_currency, "USD")
        self.assertEqual(economics.contract_multiplier, Decimal("1"))
        self.assertEqual(economics.instrument_id, equity_id)

    def test_option_descriptor_multiplier_explicit(self) -> None:
        option_id = register_option_contract(
            option_id="SPY260918C00500000",
            underlying_symbol="SPY",
            expiration="2026-09-18",
            strike="500.0",
            call_put="CALL",
            registry=self.registry,
        )
        record = self.registry.get(option_id)
        economics = economics_from_descriptor(record.descriptor, registry=self.registry)
        self.assertEqual(economics.instrument_kind, "OPTION_CONTRACT")
        self.assertEqual(economics.quantity_unit, QuantityUnit.CONTRACTS)
        self.assertEqual(economics.contract_multiplier, Decimal("100"))
        self.assertEqual(economics.strike, "500.0")
        self.assertEqual(economics.option_right, "CALL")
        self.assertEqual(economics.expiration, "2026-09-18")
        # UNDERLYING relationship resolves to the SPY equity identity.
        self.assertIsNotNone(economics.underlying_id)

    def test_option_nonstandard_multiplier_carried(self) -> None:
        option_id = register_option_contract(
            option_id="SPX260918C00500000",
            underlying_symbol="SPX",
            expiration="2026-09-18",
            strike="5000.0",
            call_put="CALL",
            contract_multiplier="10",
            registry=self.registry,
        )
        record = self.registry.get(option_id)
        economics = economics_from_descriptor(record.descriptor, registry=self.registry)
        self.assertEqual(economics.contract_multiplier, Decimal("10"))

    def test_future_descriptor_multiplier_explicit(self) -> None:
        future_id = register_future_contract(
            contract_id="ES202512",
            family_root="ES",
            expiration="2025-12-19",
            contract_multiplier="50",
            registry=self.registry,
        )
        record = self.registry.get(future_id)
        economics = economics_from_descriptor(record.descriptor, registry=self.registry)
        self.assertEqual(economics.instrument_kind, "FUTURE_CONTRACT")
        self.assertEqual(economics.quantity_unit, QuantityUnit.CONTRACTS)
        self.assertEqual(economics.contract_multiplier, Decimal("50"))
        self.assertEqual(economics.expiration, "2025-12-19")

    def test_descriptor_round_trip(self) -> None:
        equity_id = register_equity(symbol="MSFT", registry=self.registry)
        record = self.registry.get(equity_id)
        economics = economics_from_descriptor(record.descriptor, registry=self.registry)
        restored = InstrumentEconomics.from_dict(economics.to_dict())
        self.assertEqual(restored, economics)


class InstrumentRefEconomicsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_legacy_equity_ref_multiplier_one_valid(self) -> None:
        # Legacy equity refs (no instrument_kind) keep multiplier=1 ONLY
        # because they prove equity semantics — G4 Phase 10 migration rule.
        economics = economics_from_instrument_ref(
            {
                "instrument_id": "BIYA",
                "symbol": "BIYA",
                "currency": "USD",
            }
        )
        self.assertEqual(economics.instrument_kind, "TRADABLE_SECURITY")
        self.assertEqual(economics.contract_multiplier, Decimal("1"))
        self.assertEqual(economics.quantity_unit, QuantityUnit.SHARES)

    def test_option_ref_requires_multiplier(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {
                    "instrument_id": "OPT1",
                    "instrument_kind": "OPTION_CONTRACT",
                    "currency": "USD",
                }
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.MISSING_CONTRACT_MULTIPLIER)

    def test_future_ref_requires_multiplier(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {
                    "instrument_id": "ES202512",
                    "instrument_kind": "FUTURE_CONTRACT",
                    "currency": "USD",
                }
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.MISSING_CONTRACT_MULTIPLIER)

    def test_zero_multiplier_rejected(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {
                    "instrument_id": "OPT1",
                    "instrument_kind": "OPTION_CONTRACT",
                    "contract_multiplier": "0",
                    "currency": "USD",
                }
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER)

    def test_missing_currency_fails_closed(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {
                    "instrument_id": "BIYA",
                    "instrument_kind": "TRADABLE_SECURITY",
                }
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.MISSING_CURRENCY)

    def test_unknown_kind_fails_closed(self) -> None:
        with self.assertRaises(EconomicsError) as ctx:
            economics_from_instrument_ref(
                {
                    "instrument_id": "X",
                    "instrument_kind": "SYNTHETIC_WRAPPER",
                    "currency": "USD",
                }
            )
        self.assertEqual(ctx.exception.code, EconomicsErrorCode.UNKNOWN_INSTRUMENT_KIND)

    def test_no_symbol_heuristics(self) -> None:
        # A ticker-shaped id must never imply CONTRACTS semantics.
        economics = economics_from_instrument_ref(
            {
                "instrument_id": "ES",
                "instrument_kind": "TRADABLE_SECURITY",
                "contract_multiplier": "1",
                "currency": "USD",
            }
        )
        self.assertEqual(economics.quantity_unit, QuantityUnit.SHARES)


class DerivativePositionEconomicsTests(unittest.TestCase):
    def test_option_requires_contracts_unit(self) -> None:
        with self.assertRaises(PortfolioError) as ctx:
            assert_derivative_position_economics(
                instrument_kind="OPTION_CONTRACT",
                quantity_unit=QuantityUnit.SHARES,
                multiplier=Decimal("100"),
            )
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.INVALID_POSITION_ECONOMICS)

    def test_future_requires_positive_multiplier(self) -> None:
        with self.assertRaises(PortfolioError) as ctx:
            assert_derivative_position_economics(
                instrument_kind="FUTURE_CONTRACT",
                quantity_unit=QuantityUnit.CONTRACTS,
                multiplier=Decimal("0"),
            )
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.INVALID_POSITION_ECONOMICS)

    def test_equity_skips_derivative_rules(self) -> None:
        # No derivative economics requirement for equities.
        assert_derivative_position_economics(
            instrument_kind="TRADABLE_SECURITY",
            quantity_unit=QuantityUnit.SHARES,
            multiplier=Decimal("1"),
        )


class AccountingKernelTests(unittest.TestCase):
    def test_float_rejected_at_kernel_boundary(self) -> None:
        with self.assertRaises(AccountingError) as ctx:
            exact_decimal(0.1, field_name="price")
        self.assertEqual(ctx.exception.code, AccountingErrorCode.UNSUPPORTED_BINARY_FLOAT)

    def test_float_string_exact_conversion(self) -> None:
        # Boundary conversion is string-exact: 0.1 becomes Decimal('0.1'),
        # never the binary expansion.
        self.assertEqual(exact_decimal(0.1, field_name="price", allow_float=True), Decimal("0.1"))

    def test_equity_notional_exact(self) -> None:
        from market_platform_foundation.portfolio.accounting import equity_notional

        self.assertEqual(equity_notional(Decimal("10"), Decimal("150.25")), Decimal("1502.50"))

    def test_option_premium_multiplier_applied_once(self) -> None:
        # 2 contracts x 3.50 premium x 100 multiplier = 700 exactly.
        self.assertEqual(
            option_premium(Decimal("2"), Decimal("3.50"), Decimal("100")),
            Decimal("700"),
        )
        # Multiplier applied exactly once — not squared.
        self.assertEqual(
            option_premium(Decimal("1"), Decimal("1.85"), Decimal("100")),
            Decimal("185"),
        )

    def test_future_exposure_and_pnl(self) -> None:
        # 1 ES contract (multiplier 50): exposure = 1 x 50 x 5510.
        self.assertEqual(future_exposure(Decimal("1"), Decimal("50"), Decimal("5510")), Decimal("275500"))
        # Move +10 points -> +500; short (-1) -> -500.
        self.assertEqual(
            future_variation_pnl(Decimal("1"), Decimal("50"), Decimal("5510"), Decimal("5500")),
            Decimal("500"),
        )
        self.assertEqual(
            future_variation_pnl(Decimal("-1"), Decimal("50"), Decimal("5510"), Decimal("5500")),
            Decimal("-500"),
        )
        # Multiple contracts scale linearly.
        self.assertEqual(
            future_variation_pnl(Decimal("3"), Decimal("50"), Decimal("5510"), Decimal("5500")),
            Decimal("1500"),
        )
        # 0.25-point tick = $12.50 per contract.
        self.assertEqual(
            future_variation_pnl(Decimal("1"), Decimal("50"), Decimal("5500.25"), Decimal("5500")),
            Decimal("12.50"),
        )

    def test_no_float_drift(self) -> None:
        # 0.1 x 3 stays exactly 0.3 — the classic float failure case.
        from market_platform_foundation.portfolio.accounting import equity_notional

        self.assertEqual(equity_notional(Decimal("3"), Decimal("0.1")), Decimal("0.3"))
        # Long chain of tick arithmetic stays exact.
        value = Decimal("0")
        for _ in range(1000):
            value += Decimal("0.1")
        self.assertEqual(value, Decimal("100"))

    def test_cash_requirement_kind_aware(self) -> None:
        self.assertEqual(
            cash_requirement_by_kind(
                instrument_kind="TRADABLE_SECURITY",
                side="BUY",
                quantity=Decimal("10"),
                price=Decimal("150"),
            ),
            Decimal("1500"),
        )
        self.assertEqual(
            cash_requirement_by_kind(
                instrument_kind="OPTION_CONTRACT",
                side="BUY",
                quantity=Decimal("2"),
                price=Decimal("3.50"),
                multiplier=Decimal("100"),
            ),
            Decimal("700"),
        )
        # Futures never use equity cash arithmetic.
        self.assertIsNone(
            cash_requirement_by_kind(
                instrument_kind="FUTURE_CONTRACT",
                side="BUY",
                quantity=Decimal("1"),
                price=Decimal("5510"),
                multiplier=Decimal("50"),
            )
        )
        # Uncovered short option has no invented margin.
        self.assertIsNone(
            cash_requirement_by_kind(
                instrument_kind="OPTION_CONTRACT",
                side="SELL",
                quantity=Decimal("1"),
                price=Decimal("3.50"),
                multiplier=Decimal("100"),
            )
        )

    def test_realized_pnl_sign_semantics(self) -> None:
        # Long option bought 1.85, sold 2.85: (2.85-1.85) x 1 x 100 = 100.
        self.assertEqual(
            realized_pnl_on_close(
                instrument_kind="OPTION_CONTRACT",
                entry_price=Decimal("1.85"),
                exit_price=Decimal("2.85"),
                quantity=Decimal("1"),
                multiplier=Decimal("100"),
            ),
            Decimal("100"),
        )
        # Short equity: quantity -10, bought back lower -> positive realized.
        self.assertEqual(
            realized_pnl_on_close(
                instrument_kind="TRADABLE_SECURITY",
                entry_price=Decimal("150"),
                exit_price=Decimal("140"),
                quantity=Decimal("-10"),
            ),
            Decimal("100"),
        )

    def test_working_reservation_uses_remaining_not_desired(self) -> None:
        reservation = working_reservation(Decimal("6"), Decimal("10"), Decimal("1"))
        self.assertEqual(reservation, Decimal("60"))
        option_reservation = working_reservation(Decimal("2"), Decimal("3.50"), Decimal("100"))
        self.assertEqual(option_reservation, Decimal("700"))

    def test_market_value_by_kind(self) -> None:
        self.assertEqual(
            market_value_by_kind(instrument_kind="TRADABLE_SECURITY", quantity=Decimal("100"), price=Decimal("150")),
            Decimal("15000"),
        )
        self.assertEqual(
            market_value_by_kind(
                instrument_kind="OPTION_CONTRACT",
                quantity=Decimal("2"),
                price=Decimal("3.50"),
                multiplier=Decimal("100"),
            ),
            Decimal("700"),
        )
        self.assertIsNone(
            market_value_by_kind(
                instrument_kind="FUTURE_CONTRACT",
                quantity=Decimal("1"),
                price=Decimal("5510"),
                multiplier=Decimal("50"),
            )
        )


if __name__ == "__main__":
    unittest.main()