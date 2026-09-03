"""XA-02 cross-asset reference relationship tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import register_future_family
from market_platform_foundation.xa01.registry import (
    InstrumentRegistry,
    get_registry as get_xa01_registry,
    reset_registry_for_tests as reset_xa01_registry,
)
from market_platform_foundation.xa02.catalog import build_catalog_relationships, bootstrap_xa_targets
from market_platform_foundation.xa02.enums import CrossAssetReferenceType
from market_platform_foundation.xa02.errors import Xa02Error, Xa02ErrorCode
from market_platform_foundation.xa02.fixtures import admit_fixture
from market_platform_foundation.xa02.identity import derive_relationship_id
from market_platform_foundation.xa02.registry import AdmissionRegistry, get_registry, reset_registry_for_tests
from market_platform_foundation.xa01.enums import AnalyticalDomain


class Xa02RelationshipTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_registry_for_tests()

    def test_indicator_to_xa_target_resolves(self) -> None:
        admit_fixture(fixture_name="rates_reference_vertical.json")
        registry = get_registry()
        relationships = registry.list_relationships_for_indicator("US_10Y_TREASURY_YIELD")
        self.assertEqual(len(relationships), 1)
        rel = relationships[0]
        self.assertEqual(rel.relationship_type, CrossAssetReferenceType.MACRO_REFERENCE_FOR)
        self.assertEqual(rel.domain, AnalyticalDomain.RATES)
        record = get_xa01_registry().get(rel.target_xa_canonical_id)
        self.assertEqual(record.descriptor.identity.identity_key["family_root"], "ZN")

    def test_reverse_lookup_by_target(self) -> None:
        registry = get_registry()
        targets = registry.bootstrap_catalog()
        relationships = registry.list_relationships_for_target(targets["ZN"])
        subjects = {item.subject_id for item in relationships}
        self.assertIn("US_10Y_TREASURY_YIELD", subjects)

    def test_relationship_direction_preserved(self) -> None:
        registry = get_registry()
        targets = registry.bootstrap_catalog()
        forward = registry.list_relationships_for_indicator("US_2Y_TREASURY_YIELD")[0]
        reverse = registry.list_relationships_for_target(targets["ZT"])
        self.assertEqual(forward.subject_id, "US_2Y_TREASURY_YIELD")
        self.assertEqual(forward.target_xa_canonical_id, targets["ZT"])
        self.assertTrue(any(item.subject_id == "US_2Y_TREASURY_YIELD" for item in reverse))
        inverse = registry.list_relationships_for_indicator(targets["ZT"])
        self.assertEqual(inverse, ())

    def test_duplicate_relationship_idempotent(self) -> None:
        registry = AdmissionRegistry()
        registry.bootstrap_catalog()
        relationships = registry.list_all_relationships()
        first_id = registry.register_relationship(relationships[0])
        second_id = registry.register_relationship(relationships[0])
        self.assertEqual(first_id, second_id)

    def test_unknown_target_fails_closed(self) -> None:
        xa_registry = InstrumentRegistry()
        targets = bootstrap_xa_targets(xa_registry)
        relationships = build_catalog_relationships(xa_targets=targets)
        registry = AdmissionRegistry(xa_registry=InstrumentRegistry())
        with self.assertRaises(Xa02Error) as ctx:
            registry.register_relationship(relationships[0])
        self.assertEqual(ctx.exception.code, Xa02ErrorCode.UNKNOWN_XA_TARGET)

    def test_relationship_conflict_on_changed_target(self) -> None:
        from dataclasses import replace

        xa_registry = InstrumentRegistry()
        targets = bootstrap_xa_targets(xa_registry)
        registry = AdmissionRegistry(xa_registry=xa_registry)
        relationship = build_catalog_relationships(xa_targets=targets)[0]
        registry.register_relationship(relationship)
        other_target = register_future_family(family_root="ES", registry=xa_registry)
        tampered = replace(relationship, target_xa_canonical_id=other_target)
        with self.assertRaises(Xa02Error) as ctx:
            registry.register_relationship(tampered)
        self.assertEqual(ctx.exception.code, Xa02ErrorCode.RELATIONSHIP_CONFLICT)
