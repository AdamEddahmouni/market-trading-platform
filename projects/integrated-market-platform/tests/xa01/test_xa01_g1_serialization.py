"""XA-01 G1 identity serialization tests (§28).

The new identity fields (tradability, bond/crypto/commodity descriptors) must
round-trip deterministically, and legacy persisted documents without those
fields must decode with safe defaults — no silent identity reinterpretation.
"""

from __future__ import annotations

import json
import unittest

from market_platform_foundation.xa01.compatibility import (
    register_bond,
    register_commodity_spot,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
)
from market_platform_foundation.xa01.contracts import record_to_dict
from market_platform_foundation.xa01.enums import InstrumentKind, Tradability, XaAssetClass
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa04.codec import instrument_record_from_dict


class Xa01G1SerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def _roundtrip(self, canonical_id: str, registry: InstrumentRegistry) -> dict:
        payload = record_to_dict(registry.get(canonical_id))
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return json.loads(encoded)

    def test_crypto_roundtrip_and_deterministic_encode(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="COINBASE",
            network="BITCOIN",
            registry=registry,
        )
        first = self._roundtrip(pair_id, registry)
        second = self._roundtrip(pair_id, registry)
        self.assertEqual(first, second)
        self.assertEqual(first["tradability"], "TRADABLE")
        self.assertEqual(first["base_asset"], "BTC")
        self.assertEqual(first["quote_asset"], "USD")
        self.assertEqual(first["network"], "BITCOIN")
        self.assertEqual(first["asset_class"], XaAssetClass.CRYPTO.value)

    def test_bond_roundtrip(self) -> None:
        registry = InstrumentRegistry()
        bond_id = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            coupon="4.5",
            cusip="012345678",
            credit_tier="CORPORATE",
            registry=registry,
        )
        payload = self._roundtrip(bond_id, registry)
        self.assertEqual(payload["issuer"], "ACME CORP")
        self.assertEqual(payload["credit_tier"], "CORPORATE")
        self.assertEqual(payload["tradability"], "REFERENCE_ONLY")
        self.assertEqual(payload["asset_class"], XaAssetClass.BOND.value)

    def test_continuous_series_roundtrip(self) -> None:
        registry = InstrumentRegistry()
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="ratio_adjusted",
            registry=registry,
        )
        payload = self._roundtrip(series, registry)
        self.assertEqual(payload["instrument_kind"], InstrumentKind.CONTINUOUS_SERIES.value)
        self.assertEqual(payload["tradability"], Tradability.CONTINUOUS_SERIES.value)

    def test_legacy_document_decodes_with_safe_defaults(self) -> None:
        # A persisted pre-G1 equity document has no tradability/issuer/etc.
        legacy_body = {
            "schema_version": 1,
            "canonical_id": "XA01:legacy1234",
            "instrument_kind": "TRADABLE_SECURITY",
            "asset_class": "EQUITY",
            "identity_profile": "imp-xa01-instrument-identity-v1",
            "identity_key": {"symbol": "AAPL", "venue_id": "US_EQUITY"},
            "display_name": "AAPL",
            "venue_id": "US_EQUITY",
            "denomination": {"currency": "USD", "price_unit_kind": "CURRENCY_PER_SHARE"},
        }
        record = instrument_record_from_dict(legacy_body)
        # Decodes without reinterpretation; tradability falls back to
        # REFERENCE_ONLY (fail-closed default), never silently TRADABLE.
        self.assertEqual(record.descriptor.tradability, Tradability.REFERENCE_ONLY)
        self.assertEqual(record.descriptor.identity.canonical_id, "XA01:legacy1234")
        self.assertEqual(record.descriptor.base_asset, "")
        self.assertEqual(record.descriptor.credit_tier, "")

    def test_g1_document_codec_roundtrip(self) -> None:
        registry = InstrumentRegistry()
        pair_id = register_crypto_pair(
            base_asset="ETH",
            quote_asset="USDT",
            venue_id="BINANCE",
            registry=registry,
        )
        body = record_to_dict(registry.get(pair_id))
        record = instrument_record_from_dict(body)
        self.assertEqual(record.descriptor.identity.canonical_id, pair_id)
        self.assertEqual(record.descriptor.tradability, Tradability.TRADABLE)
        self.assertEqual(record.descriptor.base_asset, "ETH")
        self.assertEqual(record.descriptor.quote_asset, "USDT")

    def test_enum_stability(self) -> None:
        # Values are stable strings — persisted JSON survives renames.
        self.assertEqual(XaAssetClass.CRYPTO.value, "CRYPTO")
        self.assertEqual(XaAssetClass.BOND.value, "BOND")
        self.assertEqual(InstrumentKind.CRYPTO_PAIR.value, "CRYPTO_PAIR")
        self.assertEqual(InstrumentKind.CONTINUOUS_SERIES.value, "CONTINUOUS_SERIES")
        self.assertEqual(InstrumentKind.BOND.value, "BOND")
        self.assertEqual(InstrumentKind.COMMODITY_SPOT.value, "COMMODITY_SPOT")
        self.assertEqual(Tradability.CONTINUOUS_SERIES.value, "CONTINUOUS_SERIES")

    def test_commodity_spot_roundtrip(self) -> None:
        registry = InstrumentRegistry()
        spot = register_commodity_spot(
            commodity_code="GOLD",
            quote_currency="USD",
            registry=registry,
        )
        payload = self._roundtrip(spot, registry)
        self.assertEqual(payload["instrument_kind"], InstrumentKind.COMMODITY_SPOT.value)
        self.assertEqual(payload["tradability"], "REFERENCE_ONLY")
        self.assertEqual(payload["commodity_code"], "GOLD")

    def test_equity_serialization_unchanged(self) -> None:
        registry = InstrumentRegistry()
        equity_id = register_equity(symbol="AAPL", registry=registry)
        payload = self._roundtrip(equity_id, registry)
        self.assertEqual(payload["asset_class"], "EQUITY")
        self.assertEqual(payload["instrument_kind"], "TRADABLE_SECURITY")
        self.assertEqual(payload["tradability"], "TRADABLE")
        self.assertEqual(payload["identity_key"], {"symbol": "AAPL", "venue_id": "US_EQUITY"})


if __name__ == "__main__":
    unittest.main()