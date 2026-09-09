"""XA-01 cross-asset collision tests (G1 §25).

Symbols alone must never determine global canonical equality: the same
character string in different asset classes/kinds resolves to different
canonical identities.
"""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    register_bond,
    register_commodity_economic,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.enums import InstrumentKind, XaAssetClass
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


class Xa01CrossAssetCollisionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_equity_btc_differs_from_crypto_pair(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="BTC", registry=registry)
        pair = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        self.assertNotEqual(equity, pair)
        self.assertEqual(registry.get(equity).descriptor.identity.instrument_kind, InstrumentKind.TRADABLE_SECURITY)
        self.assertEqual(registry.get(pair).descriptor.identity.instrument_kind, InstrumentKind.CRYPTO_PAIR)

    def test_equity_gc_differs_from_commodity_gold(self) -> None:
        registry = InstrumentRegistry()
        equity = register_equity(symbol="GC", registry=registry)
        gold = register_commodity_economic(commodity_code="GOLD", registry=registry)
        self.assertNotEqual(equity, gold)

    def test_future_root_es_differs_from_equity_es(self) -> None:
        registry = InstrumentRegistry()
        family = register_future_family(family_root="ES", registry=registry)
        equity = register_equity(symbol="ES", registry=registry)
        self.assertNotEqual(family, equity)
        self.assertEqual(registry.get(family).descriptor.identity.instrument_kind, InstrumentKind.FUTURE_FAMILY)
        self.assertEqual(registry.get(equity).descriptor.identity.instrument_kind, InstrumentKind.TRADABLE_SECURITY)

    def test_bond_issuer_symbol_differs_from_equity_ticker(self) -> None:
        registry = InstrumentRegistry()
        bond = register_bond(
            issuer="GE",
            maturity_date="2035-01-15",
            registry=registry,
        )
        equity = register_equity(symbol="GE", registry=registry)
        self.assertNotEqual(bond, equity)

    def test_option_underlying_symbol_differs_from_option_contract_id(self) -> None:
        registry = InstrumentRegistry()
        option = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=registry,
        )
        underlying_id = next(
            rel.to_canonical_id
            for rel in registry.get(option).relationships
            if rel.relationship_type.value == "UNDERLYING"
        )
        self.assertNotEqual(option, underlying_id)

    def test_future_contract_differs_from_continuous_series_of_same_root(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=registry,
        )
        continuous = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=registry,
        )
        self.assertNotEqual(contract, continuous)

    def test_all_identity_kinds_distinct_for_same_symbol_family(self) -> None:
        registry = InstrumentRegistry()
        ids = {
            register_equity(symbol="XAU", registry=registry),
            register_commodity_economic(commodity_code="XAU", registry=registry),
            register_future_family(family_root="XAU", registry=registry),
            register_crypto_pair(base_asset="XAU", quote_asset="USD", registry=registry),
        }
        self.assertEqual(len(ids), 4)

    def test_symbol_does_not_define_equality_across_venues(self) -> None:
        from market_platform_foundation.xa01.enums import InstrumentKind
        from market_platform_foundation.xa01.identity import derive_canonical_id, equity_identity_key

        # The same symbol on different venues is a different canonical identity
        # (venue participates in equity identity material).
        nyse = derive_canonical_id(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY,
            asset_class=XaAssetClass.EQUITY,
            identity_key=equity_identity_key(symbol="AAPL", venue_id="XNYS"),
        )
        nasdaq = derive_canonical_id(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY,
            asset_class=XaAssetClass.EQUITY,
            identity_key=equity_identity_key(symbol="AAPL", venue_id="XNAS"),
        )
        self.assertNotEqual(nyse, nasdaq)

        # Registering the same symbol+venue twice is idempotent.
        registry = InstrumentRegistry()
        first = register_equity(symbol="AAPL", venue_id="XNYS", registry=registry)
        second = register_equity(symbol="AAPL", venue_id="XNYS", registry=registry)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()