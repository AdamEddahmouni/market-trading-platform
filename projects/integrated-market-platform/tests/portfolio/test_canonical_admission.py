"""Canonical portfolio identity admission tests (G2 §63).

Admission matrix: equity/ETF tradable identities, option contracts, specific
future contracts, and crypto pairs are admitted; futures family/root,
continuous series, economic commodities, spot references, benchmarks, and
reference-only bonds are rejected. Unknown identities fail closed.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.admission import (
    AdmissionStatus,
    admission_result,
    assert_position_admissible,
)
from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioKey,
    PositionInput,
    QuantityUnit,
)
from market_platform_foundation.xa01.compatibility import (
    register_bond,
    register_commodity_economic,
    register_commodity_spot,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.enums import InstrumentKind, Tradability
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


def _input(
    *,
    instrument_id: str,
    asset_class: str,
    instrument_kind: str,
    quantity: str = "10",
    quantity_unit: QuantityUnit = QuantityUnit.SHARES,
    native_currency: str = "USD",
    multiplier: str = "1",
) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class=asset_class,
        instrument_kind=instrument_kind,
        quantity=Decimal(quantity),
        quantity_unit=quantity_unit,
        native_currency=native_currency,
        multiplier=Decimal(multiplier),
    )


class CanonicalAdmissionMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_equity_tradable_identity_admitted(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
            asset_class="EQUITY",
        )
        self.assertEqual(result.status, AdmissionStatus.ADMITTED)

    def test_etf_fund_security_admitted(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
            asset_class="ETF_FUND",
        )
        self.assertEqual(result.status, AdmissionStatus.ADMITTED)

    def test_option_contract_admitted(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
            asset_class="OPTION",
        )
        self.assertEqual(result.status, AdmissionStatus.ADMITTED)

    def test_specific_future_contract_admitted(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            asset_class="FUTURE",
        )
        self.assertEqual(result.status, AdmissionStatus.ADMITTED)

    def test_crypto_spot_pair_admitted(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.CRYPTO_PAIR.value,
            asset_class="CRYPTO",
        )
        self.assertEqual(result.status, AdmissionStatus.ADMITTED)

    def test_bond_identity_rejected_reference_only(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.BOND.value,
            asset_class="BOND",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_futures_family_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.FUTURE_FAMILY.value,
            asset_class="FUTURE",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_continuous_future_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.CONTINUOUS_SERIES.value,
            asset_class="FUTURE",
            tradability=Tradability.CONTINUOUS_SERIES.value,
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_economic_commodity_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.COMMODITY_ECONOMIC.value,
            asset_class="COMMODITY",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_commodity_spot_reference_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.COMMODITY_SPOT.value,
            asset_class="COMMODITY",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_index_benchmark_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.INDEX_BENCHMARK.value,
            asset_class="INDEX_BENCHMARK",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_currency_and_fx_pair_rejected(self) -> None:
        for kind, asset_class in (
            (InstrumentKind.CURRENCY_UNIT, "CURRENCY"),
            (InstrumentKind.FX_PAIR, "FX_PAIR"),
        ):
            result = admission_result(
                instrument_kind=kind.value,
                asset_class=asset_class,
            )
            self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_sovereign_security_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.SOVEREIGN_SECURITY.value,
            asset_class="SOVEREIGN_DEBT",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)

    def test_unknown_kind_fails_closed(self) -> None:
        result = admission_result(
            instrument_kind="NOT_A_KIND",
            asset_class="EQUITY",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_UNKNOWN)

    def test_unknown_asset_class_fails_closed(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
            asset_class="NOT_A_CLASS",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_UNKNOWN)

    def test_asset_class_mismatch_rejected(self) -> None:
        # TRADABLE_SECURITY under CRYPTO is a collision, not a position.
        result = admission_result(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
            asset_class="CRYPTO",
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_ASSET_CLASS_MISMATCH)

    def test_reference_only_tradability_rejected(self) -> None:
        result = admission_result(
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            asset_class="FUTURE",
            tradability=Tradability.REFERENCE_ONLY.value,
        )
        self.assertEqual(result.status, AdmissionStatus.REJECTED_NON_EXECUTABLE)


class CanonicalUpsertBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.portfolio = CanonicalPortfolio(
            PortfolioKey(account_id="acc-a", mode="PAPER")
        )

    def test_upsert_position_equity_accepted(self) -> None:
        position = self.portfolio.upsert_position(
            _input(
                instrument_id="XA01:equity-aapl",
                asset_class="EQUITY",
                instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
                quantity="100",
            )
        )
        self.assertEqual(position.quantity, Decimal("100"))
        self.assertEqual(position.quantity_unit, QuantityUnit.SHARES)

    def test_upsert_position_continuous_future_rejected(self) -> None:
        with self.assertRaises(PortfolioError) as ctx:
            self.portfolio.upsert_position(
                _input(
                    instrument_id="XA01:continuous-es",
                    asset_class="FUTURE",
                    instrument_kind=InstrumentKind.CONTINUOUS_SERIES.value,
                    quantity="1",
                    quantity_unit=QuantityUnit.CONTRACTS,
                )
            )
        self.assertEqual(ctx.exception.code, PortfolioErrorCode.NON_EXECUTABLE_INSTRUMENT)
        # No store mutation happened.
        self.assertEqual(self.portfolio.positions, {})

    def test_upsert_position_economic_commodity_rejected(self) -> None:
        with self.assertRaises(PortfolioError):
            self.portfolio.upsert_position(
                _input(
                    instrument_id="XA01:gold",
                    asset_class="COMMODITY",
                    instrument_kind=InstrumentKind.COMMODITY_ECONOMIC.value,
                )
            )

    def test_zero_quantity_removes_position_deterministically(self) -> None:
        self.portfolio.upsert_position(
            _input(
                instrument_id="XA01:equity-aapl",
                asset_class="EQUITY",
                instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
                quantity="100",
            )
        )
        self.assertEqual(len(self.portfolio.positions), 1)
        self.portfolio.upsert_position(
            _input(
                instrument_id="XA01:equity-aapl",
                asset_class="EQUITY",
                instrument_kind=InstrumentKind.TRADABLE_SECURITY.value,
                quantity="0",
            )
        )
        self.assertEqual(self.portfolio.positions, {})

    def test_registry_backed_admission(self) -> None:
        """A registered identity's record is the admission authority."""
        registry = InstrumentRegistry()
        continuous = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=registry,
        )
        record = registry.get(continuous)
        from market_platform_foundation.portfolio.admission import assert_record_admissible

        with self.assertRaises(PortfolioError):
            assert_record_admissible(record)

        contract = register_future_contract(
            contract_id="ES202506",
            family_root="ES",
            expiration="2025-06-20",
            contract_multiplier="50",
            registry=registry,
        )
        assert_record_admissible(registry.get(contract))

    def test_market_value_native_never_fabricated_for_continuous(self) -> None:
        # Even when a quantity exists in a provider feed, a continuous series
        # must never become a position (fail closed, no equity default).
        registry = InstrumentRegistry()
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=registry,
        )
        from market_platform_foundation.portfolio.admission import assert_record_admissible

        with self.assertRaises(PortfolioError):
            assert_record_admissible(registry.get(series))


if __name__ == "__main__":
    unittest.main()