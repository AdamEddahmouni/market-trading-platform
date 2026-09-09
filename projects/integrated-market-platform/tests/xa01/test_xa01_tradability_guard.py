"""XA-01 tradability and continuous-futures non-execution guard tests (G1).

Mandatory safety matrix (§13, §26): specific future contracts stay tradable;
family/root and continuous series are reference-only; a continuous future can
never cross an execution boundary — including through a provider alias.
"""

from __future__ import annotations

import unittest

from market_platform_foundation.paper.contracts import (
    build_instrument_ref,
    build_user_order_intent,
)
from market_platform_foundation.xa01.compatibility import (
    register_commodity_economic,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.contracts import ExternalIdentifier
from market_platform_foundation.xa01.enums import (
    ExternalIdentifierType,
    InstrumentKind,
    Tradability,
    XaAssetClass,
)
from market_platform_foundation.xa01.errors import Xa01Error
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa01.resolver import resolve_executable_alias
from market_platform_foundation.xa01.tradability import (
    assert_executable,
    default_tradability,
    is_executable,
)


class Xa01TradabilitySemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_specific_future_contract_tradable(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=registry,
        )
        record = registry.get(contract)
        self.assertEqual(record.descriptor.tradability, Tradability.TRADABLE)
        assert_executable(record)

    def test_future_family_reference_only(self) -> None:
        registry = InstrumentRegistry()
        family = register_future_family(family_root="ES", registry=registry)
        record = registry.get(family)
        self.assertEqual(record.descriptor.tradability, Tradability.REFERENCE_ONLY)
        with self.assertRaises(Xa01Error) as ctx:
            assert_executable(record)
        self.assertEqual(ctx.exception.code.value, "NON_EXECUTABLE_INSTRUMENT")

    def test_continuous_future_reference_only(self) -> None:
        registry = InstrumentRegistry()
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="additive_back_adjusted",
            registry=registry,
        )
        record = registry.get(series)
        # Continuous construction succeeds for research…
        self.assertEqual(record.descriptor.tradability, Tradability.CONTINUOUS_SERIES)
        # …but is never executable.
        with self.assertRaises(Xa01Error) as ctx:
            assert_executable(record)
        self.assertEqual(ctx.exception.code.value, "NON_EXECUTABLE_INSTRUMENT")

    def test_default_tradability_is_deterministic(self) -> None:
        self.assertEqual(default_tradability(InstrumentKind.TRADABLE_SECURITY), Tradability.TRADABLE)
        self.assertEqual(default_tradability(InstrumentKind.FUTURE_CONTRACT), Tradability.TRADABLE)
        self.assertEqual(default_tradability(InstrumentKind.OPTION_CONTRACT), Tradability.TRADABLE)
        self.assertEqual(default_tradability(InstrumentKind.CRYPTO_PAIR), Tradability.TRADABLE)
        self.assertEqual(default_tradability(InstrumentKind.FUTURE_FAMILY), Tradability.REFERENCE_ONLY)
        self.assertEqual(default_tradability(InstrumentKind.CONTINUOUS_SERIES), Tradability.CONTINUOUS_SERIES)
        self.assertEqual(default_tradability(InstrumentKind.COMMODITY_ECONOMIC), Tradability.REFERENCE_ONLY)
        self.assertEqual(default_tradability(InstrumentKind.BOND), Tradability.REFERENCE_ONLY)
        self.assertEqual(default_tradability(InstrumentKind.CURRENCY_UNIT), Tradability.REFERENCE_ONLY)

    def test_is_executable_deterministic(self) -> None:
        self.assertTrue(is_executable(instrument_kind=InstrumentKind.FUTURE_CONTRACT))
        self.assertFalse(is_executable(instrument_kind=InstrumentKind.CONTINUOUS_SERIES))
        self.assertFalse(
            is_executable(
                instrument_kind=InstrumentKind.FUTURE_CONTRACT,
                tradability=Tradability.REFERENCE_ONLY,
            )
        )

    def test_descriptor_tradability_conflict_rejected(self) -> None:
        from market_platform_foundation.xa01.contracts import (
            CanonicalInstrumentIdentity,
            DenominationMetadata,
            InstrumentDescriptor,
        )
        from market_platform_foundation.xa01.enums import IDENTITY_PROFILE
        from market_platform_foundation.xa01.tradability import validate_tradability

        identity = CanonicalInstrumentIdentity(
            canonical_id="XA01:deadbeef",
            instrument_kind=InstrumentKind.BOND,
            asset_class=XaAssetClass.BOND,
            identity_profile=IDENTITY_PROFILE,
            identity_key={"issuer": "ACME", "maturity_date": "2035-01-15"},
        )
        descriptor = InstrumentDescriptor(
            identity=identity,
            tradability=Tradability.TRADABLE,
            denomination=DenominationMetadata(),
        )
        with self.assertRaises(Xa01Error) as ctx:
            validate_tradability(
                instrument_kind=descriptor.identity.instrument_kind,
                tradability=descriptor.tradability,
            )
        self.assertEqual(ctx.exception.code.value, "TRADABILITY_CONFLICT")


class Xa01OrderBoundaryGuardTests(unittest.TestCase):
    """The Paper order-intent boundary fails closed on reference identities."""

    def _intent(self, instrument: dict, **overrides: object) -> dict:
        return build_user_order_intent(
            instrument=instrument,
            side="BUY",
            quantity=1,
            observation_time=1,
            client_order_id="co-1",
            idempotency_key="ik-1",
            **overrides,  # type: ignore[arg-type]
        )

    def test_continuous_future_intent_rejected(self) -> None:
        ref = build_instrument_ref(
            instrument_id="ES continuous",
            symbol="ES1!",
            asset_class="FUTURE",
            instrument_kind=InstrumentKind.CONTINUOUS_SERIES.value,
            tradability=Tradability.CONTINUOUS_SERIES.value,
        )
        with self.assertRaises(ValueError) as ctx:
            self._intent(ref)
        self.assertIn("INSTRUMENT_NOT_EXECUTABLE", str(ctx.exception))

    def test_family_root_intent_rejected(self) -> None:
        ref = build_instrument_ref(
            instrument_id="ES",
            symbol="ES",
            asset_class="FUTURE",
            instrument_kind=InstrumentKind.FUTURE_FAMILY.value,
            tradability=Tradability.REFERENCE_ONLY.value,
        )
        with self.assertRaises(ValueError):
            self._intent(ref)

    def test_reference_only_tradability_rejected(self) -> None:
        ref = build_instrument_ref(
            instrument_id="GC202612",
            symbol="GC",
            asset_class="FUTURE",
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            tradability=Tradability.REFERENCE_ONLY.value,
        )
        with self.assertRaises(ValueError) as ctx:
            self._intent(ref)
        self.assertIn("INSTRUMENT_NOT_EXECUTABLE", str(ctx.exception))

    def test_specific_future_intent_accepted(self) -> None:
        ref = build_instrument_ref(
            instrument_id="ES202506",
            symbol="ES",
            asset_class="FUTURE",
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            tradability=Tradability.TRADABLE.value,
        )
        intent = self._intent(ref)
        self.assertEqual(intent["instrument_id"], "ES202506")

    def test_legacy_equity_intent_unchanged(self) -> None:
        ref = build_instrument_ref(instrument_id="AAPL", symbol="AAPL")
        intent = self._intent(ref)
        self.assertEqual(intent["instrument"]["asset_class"], "EQUITY")

    def test_invalid_kind_or_tradability_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_instrument_ref(
                instrument_id="X",
                symbol="X",
                instrument_kind="NOT_A_KIND",
            )
        with self.assertRaises(ValueError):
            build_instrument_ref(
                instrument_id="X",
                symbol="X",
                tradability="NOT_A_TRADABILITY",
            )


class Xa01ProviderAliasGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_provider_alias_resolving_to_continuous_future_rejected(self) -> None:
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
        with self.assertRaises(Xa01Error) as ctx:
            resolve_executable_alias(provider_id="ibkr", alias_value="ES1!", registry=registry)
        self.assertEqual(ctx.exception.code.value, "NON_EXECUTABLE_INSTRUMENT")

    def test_provider_alias_resolving_to_specific_contract_accepted(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
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
        canonical_id = resolve_executable_alias(
            provider_id="ibkr",
            alias_value="ESM5",
            registry=registry,
        )
        self.assertEqual(canonical_id, contract)

    def test_ambiguous_alias_fails_closed(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="BTC", registry=registry)
        registry.add_alias(
            equity,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="BTC",
                provider_id="moomoo",
            ),
        )
        with self.assertRaises(Xa01Error):
            resolve_executable_alias(
                provider_id="ibkr",
                alias_value="BTC",
                registry=registry,
            )

    def test_alias_resolution_cannot_mutate_tradability(self) -> None:
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
                alias_value="ESU6",
                provider_id="ibkr",
            ),
        )
        # Adding an alias must never flip a reference identity to tradable.
        record = registry.get(series)
        self.assertEqual(record.descriptor.tradability, Tradability.CONTINUOUS_SERIES)
        with self.assertRaises(Xa01Error):
            resolve_executable_alias(provider_id="ibkr", alias_value="ESU6", registry=registry)


class Xa01ExecutableKindsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_equity_option_crypto_are_executable(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="AAPL", registry=registry)
        option = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=registry,
        )
        crypto = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            registry=registry,
        )
        for canonical_id in (equity, option, crypto):
            assert_executable(registry.get(canonical_id))

    def test_commodity_economic_not_executable(self) -> None:
        registry = InstrumentRegistry()
        gold = register_commodity_economic(commodity_code="GOLD", registry=registry)
        with self.assertRaises(Xa01Error):
            assert_executable(registry.get(gold))


if __name__ == "__main__":
    unittest.main()