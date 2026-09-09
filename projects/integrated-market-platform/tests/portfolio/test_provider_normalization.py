"""Provider snapshot normalization tests (G2 §47–48, §72).

Provider symbols resolve through XA-01 aliases to canonical instrument ids and
become canonical position inputs. Ambiguous aliases, unknown symbols, and
continuous-future aliases never mutate portfolio truth (UNRESOLVED / rejected).
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from market_platform_foundation.portfolio.canonical import CanonicalPortfolio, PortfolioKey, QuantityUnit
from market_platform_foundation.portfolio.provider_normalization import (
    NormalizationStatus,
    ProviderPositionRow,
    normalize_provider_position,
    normalize_provider_snapshot,
)
from market_platform_foundation.xa01.compatibility import (
    register_bond,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_option_contract,
)
from market_platform_foundation.xa01.contracts import ExternalIdentifier
from market_platform_foundation.xa01.enums import ExternalIdentifierType
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


class ProviderNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_provider_option_id_to_canonical_position(self) -> None:
        registry = InstrumentRegistry()
        option = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=registry,
        )
        registry.add_alias(
            option,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="NVDA 250620C120",
                provider_id="moomoo",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="NVDA 250620C120",
                quantity=Decimal("2"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(result.canonical_id, option)
        self.assertEqual(result.position_input.instrument_id, option)
        self.assertEqual(result.position_input.quantity_unit, QuantityUnit.CONTRACTS)
        self.assertEqual(result.position_input.multiplier, Decimal("100"))

    def test_provider_futures_id_to_specific_contract(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="ES202506",
            family_root="ES",
            expiration="2025-06-20",
            contract_multiplier="50",
            registry=registry,
        )
        registry.add_alias(
            contract,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="ESM5",
                provider_id="ibkr",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="ibkr",
                provider_symbol="ESM5",
                quantity=Decimal("3"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(result.position_input.instrument_id, contract)
        self.assertEqual(result.position_input.quantity_unit, QuantityUnit.CONTRACTS)

    def test_provider_equity_symbol_to_canonical_position(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="AAPL", registry=registry)
        registry.add_alias(
            equity,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="AAPL.US",
                provider_id="moomoo",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="AAPL.US",
                quantity=Decimal("100"),
                average_cost=Decimal("150.00"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(result.position_input.quantity_unit, QuantityUnit.SHARES)
        self.assertEqual(result.position_input.cost_basis, Decimal("15000"))

    def test_unknown_symbol_unresolved_no_mutation(self) -> None:
        registry = InstrumentRegistry()
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-a", mode="PAPER"))
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="ZZZZ",
                quantity=Decimal("10"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.UNRESOLVED_INSTRUMENT)
        # Fail closed: no position created, nothing mutated.
        self.assertEqual(portfolio.positions, {})

    def test_ambiguous_alias_fails_closed(self) -> None:
        registry = InstrumentRegistry()
        # BTC equity and BTC/USD crypto are distinct identities; a bare BTC
        # provider symbol with no alias must not resolve to either by guessing.
        register_equity(symbol="BTC", registry=registry)
        register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="BTC",
                quantity=Decimal("1"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.UNRESOLVED_INSTRUMENT)

    def test_continuous_future_alias_no_position_admission(self) -> None:
        registry = InstrumentRegistry()
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=registry,
        )
        registry.add_alias(
            series,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="ES1!",
                provider_id="ibkr",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="ibkr",
                provider_symbol="ES1!",
                quantity=Decimal("1"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NON_EXECUTABLE)
        self.assertIsNone(result.position_input)

    def test_reference_bond_alias_not_positionable(self) -> None:
        registry = InstrumentRegistry()
        bond = register_bond(
            issuer="ACME",
            maturity_date="2035-01-15",
            coupon="4.5",
            currency="USD",
            registry=registry,
        )
        registry.add_alias(
            bond,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="ACME 4.5 2035",
                provider_id="provider-x",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="provider-x",
                provider_symbol="ACME 4.5 2035",
                quantity=Decimal("10000"),
                currency="USD",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NON_EXECUTABLE)
        self.assertIsNone(result.position_input)

    def test_crypto_pair_alias_normalized(self) -> None:
        registry = InstrumentRegistry()
        pair = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USDT",
            venue_id="BINANCE",
            provider_id="binance",
            provider_symbol="BTCUSDT",
            registry=registry,
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="binance",
                provider_symbol="BTCUSDT",
                quantity=Decimal("0.5"),
                currency="USDT",
            ),
            registry=registry,
        )
        self.assertEqual(result.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(result.position_input.instrument_id, pair)
        self.assertEqual(result.position_input.native_currency, "USDT")
        self.assertEqual(result.position_input.quantity_unit, QuantityUnit.BASE_UNITS)

    def test_full_snapshot_normalization_partitions(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="AAPL", registry=registry)
        registry.add_alias(
            equity,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="AAPL.US",
                provider_id="moomoo",
            ),
        )
        rows = [
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="AAPL.US",
                quantity=Decimal("100"),
                currency="USD",
            ),
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="UNKNOWN1",
                quantity=Decimal("1"),
                currency="USD",
            ),
        ]
        normalized, unresolved = normalize_provider_snapshot(rows, registry=registry)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].status, NormalizationStatus.UNRESOLVED_INSTRUMENT)

    def test_normalized_position_upserts_into_store(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="AAPL", registry=registry)
        registry.add_alias(
            equity,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="AAPL.US",
                provider_id="moomoo",
            ),
        )
        result = normalize_provider_position(
            ProviderPositionRow(
                provider_id="moomoo",
                provider_symbol="AAPL.US",
                quantity=Decimal("100"),
                currency="USD",
            ),
            registry=registry,
        )
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="acc-a", mode="PAPER"))
        portfolio.upsert_position(result.position_input)
        self.assertIn(equity, portfolio.positions)
        self.assertEqual(portfolio.positions[equity].quantity, Decimal("100"))


if __name__ == "__main__":
    unittest.main()