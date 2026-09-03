"""XA-01 core identity, vertical slice, and serialization tests."""

from __future__ import annotations

import json
import unittest

from market_platform_foundation.xa01.compatibility import (
    from_symbol_mapping,
    legacy_instrument_ref,
    register_commodity_economic,
    register_equity,
    register_future_contract,
    register_sovereign_security,
)
from market_platform_foundation.xa01.contracts import record_to_dict
from market_platform_foundation.xa01.enums import (
    AnalyticalDomain,
    InstrumentKind,
    RelationshipType,
    XaAssetClass,
)
from market_platform_foundation.xa01.identity import derive_canonical_id, equity_identity_key
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.providers.contracts import SymbolMapping


class Xa01CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_equity_identity_deterministic(self) -> None:
        first = derive_canonical_id(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY,
            asset_class=XaAssetClass.EQUITY,
            identity_key=equity_identity_key(symbol="AAPL", venue_id="US_EQUITY"),
        )
        second = derive_canonical_id(
            instrument_kind=InstrumentKind.TRADABLE_SECURITY,
            asset_class=XaAssetClass.EQUITY,
            identity_key=equity_identity_key(symbol="AAPL", venue_id="US_EQUITY"),
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("XA01:"))

    def test_vertical_slice_equity_sovereign_gold(self) -> None:
        registry = InstrumentRegistry()
        equity_id = register_equity(symbol="AAPL", registry=registry)
        sovereign_id = register_sovereign_security(
            cusip="912828ZT0",
            issuer="US_TREASURY",
            maturity_date="2030-05-15",
            coupon="2.5",
            registry=registry,
        )
        gold_id = register_commodity_economic(commodity_code="GOLD", registry=registry)
        gc_id = register_future_contract(
            contract_id="GC202506",
            family_root="GC",
            underlying_commodity_code="GOLD",
            expiration="2025-06-26",
            registry=registry,
        )
        gold_record = registry.get(gold_id)
        domains = {item.domain for item in gold_record.analytical_domains}
        self.assertIn(AnalyticalDomain.COMMODITY, domains)
        self.assertIn(AnalyticalDomain.MONETARY_RESERVE, domains)
        self.assertEqual(len(domains), 4)
        gc_record = registry.get(gc_id)
        self.assertNotEqual(gc_id, gold_id)
        rel_types = {rel.relationship_type for rel in gc_record.relationships}
        self.assertIn(RelationshipType.UNDERLYING, rel_types)
        self.assertIn(RelationshipType.CONTRACT_ROOT, rel_types)
        underlying_targets = {
            rel.to_canonical_id
            for rel in gc_record.relationships
            if rel.relationship_type == RelationshipType.UNDERLYING
        }
        self.assertIn(gold_id, underlying_targets)
        payload = record_to_dict(registry.get(equity_id))
        roundtrip = json.loads(json.dumps(payload))
        self.assertEqual(roundtrip["canonical_id"], equity_id)
        self.assertNotEqual(equity_id, sovereign_id)

    def test_symbol_mapping_compatibility(self) -> None:
        registry = InstrumentRegistry()
        mapping = SymbolMapping(provider_symbol="US.AAPL", instrument_id="AAPL", venue_id="US_EQUITY")
        canonical_id = from_symbol_mapping(mapping, provider_id="moomoo", registry=registry)
        legacy = legacy_instrument_ref(canonical_id, registry=registry)
        self.assertEqual(legacy["instrument_id"], "AAPL")
        self.assertEqual(legacy["venue_id"], "US_EQUITY")

    def test_duplicate_registration_idempotent(self) -> None:
        registry = InstrumentRegistry()
        first = register_equity(symbol="AAPL", registry=registry)
        second = register_equity(symbol="AAPL", registry=registry)
        self.assertEqual(first, second)
        self.assertEqual(len(registry.list_ids()), 1)
