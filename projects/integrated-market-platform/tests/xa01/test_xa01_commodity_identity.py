"""XA-01 commodity / gold / silver identity tests (G1 / BL-0104)."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    register_commodity_economic,
    register_commodity_proxy,
    register_commodity_spot,
    register_continuous_futures_series,
    register_future_contract,
)
from market_platform_foundation.xa01.enums import (
    InstrumentKind,
    RelationshipType,
    Tradability,
    XaAssetClass,
)
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


class Xa01CommodityIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_gold_and_silver_distinct(self) -> None:
        registry = InstrumentRegistry()
        gold = register_commodity_economic(
            commodity_code="GOLD",
            commodity_sector="PRECIOUS_METALS",
            registry=registry,
        )
        silver = register_commodity_economic(
            commodity_code="SILVER",
            commodity_sector="PRECIOUS_METALS",
            registry=registry,
        )
        self.assertNotEqual(gold, silver)

    def test_commodity_identity_differs_from_futures_contract(self) -> None:
        registry = InstrumentRegistry()
        gold = register_commodity_economic(commodity_code="GOLD", registry=registry)
        gc_contract = register_future_contract(
            contract_id="GC202612",
            contract_multiplier="100",
            family_root="GC",
            underlying_commodity_code="GOLD",
            expiration="2026-12-29",
            registry=registry,
        )
        self.assertNotEqual(gold, gc_contract)
        self.assertEqual(registry.get(gold).descriptor.identity.asset_class, XaAssetClass.COMMODITY)
        self.assertEqual(registry.get(gc_contract).descriptor.identity.asset_class, XaAssetClass.FUTURE)
        # Economic commodity is reference-only; specific future is tradable.
        self.assertEqual(registry.get(gold).descriptor.tradability, Tradability.REFERENCE_ONLY)
        self.assertEqual(registry.get(gc_contract).descriptor.tradability, Tradability.TRADABLE)

    def test_futures_contract_differs_from_continuous_series(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="GC202612",
            contract_multiplier="100",
            family_root="GC",
            expiration="2026-12-29",
            registry=registry,
        )
        continuous = register_continuous_futures_series(
            family_root="GC",
            methodology="additive_back_adjusted",
            registry=registry,
        )
        self.assertNotEqual(contract, continuous)
        self.assertEqual(registry.get(continuous).descriptor.identity.instrument_kind, InstrumentKind.CONTINUOUS_SERIES)
        self.assertEqual(registry.get(continuous).descriptor.tradability, Tradability.CONTINUOUS_SERIES)

    def test_spot_reference_distinct_from_economic_and_futures(self) -> None:
        registry = InstrumentRegistry()
        gold = register_commodity_economic(commodity_code="GOLD", registry=registry)
        spot = register_commodity_spot(
            commodity_code="GOLD",
            quote_currency="USD",
            registry=registry,
        )
        gc_contract = register_future_contract(
            contract_id="GC202612",
            contract_multiplier="100",
            family_root="GC",
            underlying_commodity_code="GOLD",
            expiration="2026-12-29",
            registry=registry,
        )
        # Three distinct identities for one economic exposure.
        self.assertEqual(len({gold, spot, gc_contract}), 3)
        self.assertEqual(registry.get(spot).descriptor.tradability, Tradability.REFERENCE_ONLY)
        spot_record = registry.get(spot)
        benchmark_targets = {
            rel.to_canonical_id
            for rel in spot_record.relationships
            if rel.relationship_type == RelationshipType.BENCHMARK_OF
        }
        self.assertIn(gold, benchmark_targets)

    def test_gld_proxy_over_gold(self) -> None:
        registry = InstrumentRegistry()
        proxy = register_commodity_proxy(
            symbol="GLD",
            commodity_code="GOLD",
            commodity_sector="PRECIOUS_METALS",
            registry=registry,
        )
        gold = register_commodity_economic(
            commodity_code="GOLD",
            commodity_sector="PRECIOUS_METALS",
            registry=registry,
        )
        self.assertNotEqual(proxy, gold)
        # GLD is a tradable security whose underlying is the economic commodity.
        self.assertEqual(registry.get(proxy).descriptor.identity.instrument_kind, InstrumentKind.TRADABLE_SECURITY)
        self.assertEqual(registry.get(proxy).descriptor.tradability, Tradability.TRADABLE)
        underlying_targets = {
            rel.to_canonical_id
            for rel in registry.get(proxy).relationships
            if rel.relationship_type == RelationshipType.UNDERLYING
        }
        self.assertIn(gold, underlying_targets)

    def test_energy_and_agriculture_expansion(self) -> None:
        registry = InstrumentRegistry()
        crude = register_commodity_economic(
            commodity_code="CRUDE_OIL",
            commodity_sector="ENERGY",
            registry=registry,
        )
        natural_gas = register_commodity_economic(
            commodity_code="NATURAL_GAS",
            commodity_sector="ENERGY",
            registry=registry,
        )
        wheat = register_commodity_economic(
            commodity_code="WHEAT",
            commodity_sector="AGRICULTURE",
            registry=registry,
        )
        self.assertEqual(len({crude, natural_gas, wheat}), 3)
        self.assertEqual(registry.get(crude).descriptor.commodity_sector, "ENERGY")
        self.assertEqual(registry.get(wheat).descriptor.commodity_sector, "AGRICULTURE")

    def test_gc_family_root_not_a_contract(self) -> None:
        registry = InstrumentRegistry()
        contract = register_future_contract(
            contract_id="GC202612",
            contract_multiplier="100",
            family_root="GC",
            expiration="2026-12-29",
            registry=registry,
        )
        root_ids = {
            rel.to_canonical_id
            for rel in registry.get(contract).relationships
            if rel.relationship_type == RelationshipType.CONTRACT_ROOT
        }
        self.assertEqual(len(root_ids), 1)
        root_id = next(iter(root_ids))
        root_record = registry.get(root_id)
        self.assertEqual(root_record.descriptor.identity.instrument_kind, InstrumentKind.FUTURE_FAMILY)
        self.assertEqual(root_record.descriptor.tradability, Tradability.REFERENCE_ONLY)
        self.assertNotEqual(root_id, contract)


if __name__ == "__main__":
    unittest.main()