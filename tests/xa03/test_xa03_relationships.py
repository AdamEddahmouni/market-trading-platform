"""XA-03 cross-asset reference relationship tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import register_future_family
from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa01.registry import (
    InstrumentRegistry,
    get_registry as get_xa01_registry,
    reset_registry_for_tests as reset_xa01_registry,
)
from market_platform_foundation.xa02.enums import CrossAssetReferenceType, ReferenceSubjectType
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa03.catalog import bootstrap_xa_targets, build_catalog_relationships
from market_platform_foundation.xa03.errors import Xa03Error, Xa03ErrorCode
from market_platform_foundation.xa03.fixtures import admit_fixture
from market_platform_foundation.xa03.registry import PositioningAdmissionRegistry, get_registry, reset_registry_for_tests


class Xa03RelationshipTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_market_report_to_xa_target_resolves(self) -> None:
        admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        market_id = "CFTC_MARKET:13874+:TFF:FUTURES_ONLY"
        relationships = registry.list_relationships_for_market(market_id)
        self.assertEqual(len(relationships), 1)
        rel = relationships[0]
        self.assertEqual(rel.relationship_type, CrossAssetReferenceType.REFERENCE_RELEVANT_TO)
        self.assertEqual(rel.subject_type, ReferenceSubjectType.CFTC_MARKET_REPORT)
        self.assertEqual(rel.domain, AnalyticalDomain.EQUITY)
        record = get_xa01_registry().get(rel.target_xa_canonical_id)
        self.assertEqual(record.descriptor.identity.identity_key["family_root"], "ES")

    def test_family_granularity_not_contract(self) -> None:
        registry = get_registry()
        targets = registry.bootstrap_catalog()
        rel = registry.list_relationships_for_target(targets["CL"])[0]
        record = get_xa01_registry().get(rel.target_xa_canonical_id)
        self.assertEqual(record.descriptor.identity.instrument_kind.value, "FUTURE_FAMILY")

    def test_duplicate_relationship_idempotent(self) -> None:
        registry = PositioningAdmissionRegistry()
        registry.bootstrap_catalog()
        relationships = registry.list_all_relationships()
        first_id = registry.register_relationship(relationships[0])
        second_id = registry.register_relationship(relationships[0])
        self.assertEqual(first_id, second_id)

    def test_unknown_target_fails_closed(self) -> None:
        xa_registry = InstrumentRegistry()
        targets = bootstrap_xa_targets(xa_registry)
        relationships = build_catalog_relationships(xa_targets=targets)
        registry = PositioningAdmissionRegistry(xa_registry=InstrumentRegistry())
        with self.assertRaises(Xa03Error) as ctx:
            registry.register_relationship(relationships[0])
        self.assertEqual(ctx.exception.code, Xa03ErrorCode.UNKNOWN_XA_TARGET)

    def test_no_causal_relationship_types(self) -> None:
        registry = get_registry()
        registry.bootstrap_catalog()
        forbidden = {"CAUSES", "PREDICTS", "BULLISH_FOR", "BEARISH_FOR", "SQUEEZE_SIGNAL_FOR"}
        for rel in registry.list_all_relationships():
            self.assertNotIn(rel.relationship_type.value, forbidden)
