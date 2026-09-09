"""XA-01 crypto pair identity tests (G1 / BL-0102)."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    legacy_instrument_ref,
    register_crypto_pair,
)
from market_platform_foundation.xa01.contracts import ExternalIdentifier
from market_platform_foundation.xa01.enums import (
    ExternalIdentifierType,
    InstrumentKind,
    RelationshipType,
    Tradability,
    XaAssetClass,
)
from market_platform_foundation.xa01.identity import crypto_pair_identity_key, derive_canonical_id
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa01.resolver import resolve_alias


class Xa01CryptoIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_btc_usd_differs_from_btc_usdt(self) -> None:
        registry = InstrumentRegistry()
        btc_usd = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        btc_usdt = register_crypto_pair(base_asset="BTC", quote_asset="USDT", registry=registry)
        self.assertNotEqual(btc_usd, btc_usdt)
        self.assertEqual(
            registry.get(btc_usd).descriptor.identity.identity_key["quote_asset"],
            "USD",
        )
        self.assertEqual(
            registry.get(btc_usdt).descriptor.identity.identity_key["quote_asset"],
            "USDT",
        )

    def test_base_quote_order_matters(self) -> None:
        registry = InstrumentRegistry()
        btc_usd = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        usd_btc = register_crypto_pair(base_asset="USD", quote_asset="BTC", registry=registry)
        self.assertNotEqual(btc_usd, usd_btc)

    def test_venue_qualifies_identity(self) -> None:
        registry = InstrumentRegistry()
        coinbase = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="COINBASE",
            registry=registry,
        )
        binance = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="BINANCE",
            registry=registry,
        )
        unqualified = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        self.assertNotEqual(coinbase, binance)
        self.assertNotEqual(coinbase, unqualified)
        self.assertNotEqual(binance, unqualified)

    def test_bare_asset_not_silently_a_pair(self) -> None:
        # BTC alone is not BTC/USD: the pair identity requires both legs.
        key = crypto_pair_identity_key(base_asset="BTC", quote_asset="USD")
        bare = derive_canonical_id(
            instrument_kind=InstrumentKind.CRYPTO_PAIR,
            asset_class=XaAssetClass.CRYPTO,
            identity_key={"base_asset": "BTC"},
        )
        pair = derive_canonical_id(
            instrument_kind=InstrumentKind.CRYPTO_PAIR,
            asset_class=XaAssetClass.CRYPTO,
            identity_key=key,
        )
        self.assertNotEqual(bare, pair)

    def test_self_pair_rejected(self) -> None:
        with self.assertRaises(Exception):
            register_crypto_pair(base_asset="BTC", quote_asset="BTC")

    def test_pair_metadata_and_tradability(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="ETH",
            quote_asset="USD",
            venue_id="COINBASE",
            network="ETHEREUM",
            product_type="SPOT",
            provider_id="coinbase",
            provider_symbol="ETH-USD",
            registry=registry,
        )
        record = registry.get(pair_id)
        desc = record.descriptor
        self.assertEqual(desc.identity.asset_class, XaAssetClass.CRYPTO)
        self.assertEqual(desc.identity.instrument_kind, InstrumentKind.CRYPTO_PAIR)
        self.assertEqual(desc.tradability, Tradability.TRADABLE)
        self.assertEqual(desc.base_asset, "ETH")
        self.assertEqual(desc.quote_asset, "USD")
        self.assertEqual(desc.network, "ETHEREUM")
        # ETH/USD on Coinbase is not ETH/USD on a different venue.
        other = register_crypto_pair(
            base_asset="ETH",
            quote_asset="USD",
            venue_id="BINANCE",
            registry=registry,
        )
        self.assertNotEqual(pair_id, other)

    def test_provider_alias_normalization(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="COINBASE",
            provider_id="coinbase",
            provider_symbol="BTC-USD",
            registry=registry,
        )
        resolution = resolve_alias(
            provider_id="coinbase",
            alias_value="BTC-USD",
            registry=registry,
        )
        self.assertEqual(resolution.status.value, "RESOLVED")
        self.assertEqual(resolution.canonical_id, pair_id)

    def test_alias_does_not_alter_canonical_identity(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            registry=registry,
        )
        registry.add_alias(
            pair_id,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="XBTCUSD",
                provider_id="moomoo",
            ),
        )
        same_pair = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        self.assertEqual(pair_id, same_pair)

    def test_legacy_ref_shape(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="COINBASE",
            registry=registry,
        )
        legacy = legacy_instrument_ref(pair_id, registry=registry)
        self.assertEqual(legacy["instrument_id"], "BTC/USD")
        self.assertEqual(legacy["venue_id"], "COINBASE")

    def test_pair_denominated_in_quote_currency(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(base_asset="BTC", quote_asset="USD", registry=registry)
        record = registry.get(pair_id)
        rel_types = {rel.relationship_type for rel in record.relationships}
        self.assertIn(RelationshipType.DENOMINATED_IN, rel_types)


if __name__ == "__main__":
    unittest.main()