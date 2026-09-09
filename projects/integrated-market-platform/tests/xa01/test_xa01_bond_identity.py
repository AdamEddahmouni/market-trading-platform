"""XA-01 bond / fixed-income identity tests (G1 / BL-0103)."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    legacy_instrument_ref,
    register_bond,
    register_sovereign_security,
)
from market_platform_foundation.xa01.enums import (
    ExternalIdentifierType,
    InstrumentKind,
    Tradability,
    XaAssetClass,
)
from market_platform_foundation.xa01.identity import bond_identity_key, derive_canonical_id
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa01.resolver import resolve_alias


class Xa01BondIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_typed_corporate_bond(self) -> None:
        registry = InstrumentRegistry()
        bond_id = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            coupon="4.5",
            cusip="012345678",
            par_value="1000",
            currency="USD",
            registry=registry,
        )
        record = registry.get(bond_id)
        desc = record.descriptor
        self.assertEqual(desc.identity.asset_class, XaAssetClass.BOND)
        self.assertEqual(desc.identity.instrument_kind, InstrumentKind.BOND)
        self.assertEqual(desc.issuer, "ACME CORP")
        self.assertEqual(desc.maturity_date, "2035-01-15")
        self.assertEqual(desc.coupon, "4.5")
        self.assertEqual(desc.credit_tier, "CORPORATE")
        self.assertEqual(desc.par_value, "1000")
        # Bond identity is reference-only until a bond execution surface exists.
        self.assertEqual(desc.tradability, Tradability.REFERENCE_ONLY)

    def test_differing_maturity_distinct_identity(self) -> None:
        registry = InstrumentRegistry()
        first = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            registry=registry,
        )
        second = register_bond(
            issuer="ACME CORP",
            maturity_date="2040-06-01",
            registry=registry,
        )
        self.assertNotEqual(first, second)

    def test_external_identifier_distinction(self) -> None:
        registry = InstrumentRegistry()
        by_cusip = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            cusip="012345678",
            registry=registry,
        )
        by_terms = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            registry=registry,
        )
        self.assertNotEqual(by_cusip, by_terms)

    def test_government_and_corporate_representable(self) -> None:
        registry = InstrumentRegistry()
        corporate = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            credit_tier="CORPORATE",
            registry=registry,
        )
        sovereign = register_sovereign_security(
            cusip="912828ZT0",
            issuer="US_TREASURY",
            maturity_date="2030-05-15",
            coupon="2.5",
            registry=registry,
        )
        self.assertNotEqual(corporate, sovereign)
        self.assertEqual(registry.get(sovereign).descriptor.identity.asset_class, XaAssetClass.SOVEREIGN_DEBT)

    def test_typed_terms_identity_deterministic(self) -> None:
        first = derive_canonical_id(
            instrument_kind=InstrumentKind.BOND,
            asset_class=XaAssetClass.BOND,
            identity_key=bond_identity_key(
                issuer="ACME CORP",
                maturity_date="2035-01-15",
                coupon="4.5",
            ),
        )
        second = derive_canonical_id(
            instrument_kind=InstrumentKind.BOND,
            asset_class=XaAssetClass.BOND,
            identity_key=bond_identity_key(
                issuer="ACME CORP",
                maturity_date="2035-01-15",
                coupon="4.5",
            ),
        )
        self.assertEqual(first, second)

    def test_missing_optional_provider_id_does_not_destroy_identity(self) -> None:
        registry = InstrumentRegistry()
        with_alias = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            cusip="012345678",
            provider_id="bloomberg",
            provider_symbol="ACME 4.5 01/15/35",
            registry=registry,
        )
        plain = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            cusip="012345678",
            registry=registry,
        )
        self.assertEqual(with_alias, plain)

    def test_cusip_alias_resolution(self) -> None:
        registry = InstrumentRegistry()
        bond_id = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            cusip="012345678",
            registry=registry,
        )
        resolution = resolve_alias(
            provider_id="",
            alias_value="012345678",
            identifier_type=ExternalIdentifierType.CUSIP,
            registry=registry,
        )
        self.assertEqual(resolution.status.value, "RESOLVED")
        self.assertEqual(resolution.canonical_id, bond_id)

    def test_legacy_ref_shape(self) -> None:
        registry = InstrumentRegistry()
        bond_id = register_bond(
            issuer="ACME CORP",
            maturity_date="2035-01-15",
            registry=registry,
        )
        legacy = legacy_instrument_ref(bond_id, registry=registry)
        self.assertIn("ACME CORP", legacy["instrument_id"])
        self.assertEqual(legacy["venue_id"], "FIXED_INCOME")


if __name__ == "__main__":
    unittest.main()