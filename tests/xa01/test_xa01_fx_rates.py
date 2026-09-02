"""XA-01 FX and sovereign identity tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    register_currency,
    register_fx_pair,
    register_sovereign_security,
)
from market_platform_foundation.xa01.enums import InstrumentKind, XaAssetClass
from market_platform_foundation.xa01.identity import fx_pair_identity_key
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa01.resolver import resolve_alias
from market_platform_foundation.xa01.enums import AliasResolutionStatus


class Xa01FxRatesTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_sovereign_external_ids_same_object(self) -> None:
        registry = InstrumentRegistry()
        first = register_sovereign_security(
            cusip="912828ZT0",
            issuer="US_TREASURY",
            maturity_date="2030-05-15",
            coupon="2.5",
            registry=registry,
        )
        second = register_sovereign_security(
            cusip="912828ZT0",
            issuer="US_TREASURY",
            maturity_date="2030-05-15",
            coupon="2.5",
            registry=registry,
        )
        self.assertEqual(first, second)
        different = register_sovereign_security(
            cusip="912828ZQ6",
            issuer="US_TREASURY",
            maturity_date="2028-05-15",
            registry=registry,
        )
        self.assertNotEqual(first, different)

    def test_fx_pair_and_currency_distinct(self) -> None:
        registry = InstrumentRegistry()
        eur_id = register_currency(iso_code="EUR", registry=registry)
        usd_id = register_currency(iso_code="USD", registry=registry)
        pair_id = register_fx_pair(
            base_currency="EUR",
            quote_currency="USD",
            provider_id="IBKR",
            provider_symbol="EUR.USD",
            registry=registry,
        )
        reversed_key = fx_pair_identity_key(base_currency="USD", quote_currency="EUR")
        pair_record = registry.get(pair_id)
        self.assertEqual(pair_record.descriptor.base_currency, "EUR")
        self.assertEqual(pair_record.descriptor.quote_currency, "USD")
        self.assertNotEqual(pair_id, eur_id)
        self.assertNotEqual(pair_id, usd_id)
        self.assertNotEqual(
            pair_record.descriptor.identity.identity_key,
            reversed_key,
        )
        resolved = resolve_alias(provider_id="IBKR", alias_value="EUR.USD", registry=registry)
        self.assertEqual(resolved.status, AliasResolutionStatus.RESOLVED)
        self.assertEqual(resolved.canonical_id, pair_id)
        eur_record = registry.get(eur_id)
        self.assertEqual(eur_record.descriptor.identity.instrument_kind, InstrumentKind.CURRENCY_UNIT)
        self.assertEqual(eur_record.descriptor.identity.asset_class, XaAssetClass.CURRENCY)
