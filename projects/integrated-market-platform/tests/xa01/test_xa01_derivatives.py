"""XA-01 derivative identity tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import (
    from_futures_contract,
    from_option_contract,
    register_future_contract,
    register_option_contract,
)
from market_platform_foundation.xa01.enums import InstrumentKind, RelationshipType
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.contracts.futures import FuturesContract, FuturesFamily
from market_platform_foundation.contracts.options import OptionContract
from decimal import Decimal


class Xa01DerivativeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_future_expiries_distinct_and_root_not_contract(self) -> None:
        registry = InstrumentRegistry()
        first = register_future_contract(
            contract_id="ES202506",
            family_root="ES",
            expiration="2025-06-20",
            registry=registry,
        )
        second = register_future_contract(
            contract_id="ES202509",
            family_root="ES",
            expiration="2025-09-19",
            registry=registry,
        )
        self.assertNotEqual(first, second)
        first_record = registry.get(first)
        root_targets = {
            rel.to_canonical_id
            for rel in first_record.relationships
            if rel.relationship_type == RelationshipType.CONTRACT_ROOT
        }
        self.assertEqual(len(root_targets), 1)
        root_id = next(iter(root_targets))
        root_record = registry.get(root_id)
        self.assertEqual(root_record.descriptor.identity.instrument_kind, InstrumentKind.FUTURE_FAMILY)
        self.assertNotEqual(root_id, first)

    def test_option_underlying_and_distinct_strikes(self) -> None:
        registry = InstrumentRegistry()
        first = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=registry,
        )
        second = register_option_contract(
            option_id="NVDA20250620C00130000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="130",
            call_put="call",
            registry=registry,
        )
        self.assertNotEqual(first, second)
        rel = registry.get(first).relationships[0]
        self.assertEqual(rel.relationship_type, RelationshipType.UNDERLYING)

    def test_futures_and_options_compatibility_adapters(self) -> None:
        registry = InstrumentRegistry()
        future = FuturesContract(
            instrument_family="ES",
            contract_id="ES202506",
            underlying_id="ES",
            asset_class="futures",
            family=FuturesFamily.EQUITY_INDEX,
            expiration="2025-06-20",
        )
        future_id = from_futures_contract(future, registry=registry)
        option = OptionContract(
            underlying_id="NVDA",
            option_id="NVDA20250620C00120000",
            call_put="call",
            strike=Decimal("120"),
            expiration="2025-06-20",
            dte=30,
        )
        option_id = from_option_contract(option, registry=registry)
        self.assertTrue(future_id.startswith("XA01:"))
        self.assertTrue(option_id.startswith("XA01:"))
