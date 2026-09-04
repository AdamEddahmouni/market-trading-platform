"""XA-01 alias resolution tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import register_equity
from market_platform_foundation.xa01.contracts import ExternalIdentifier
from market_platform_foundation.xa01.enums import AliasResolutionStatus, ExternalIdentifierType
from market_platform_foundation.xa01.errors import Xa01Error
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests
from market_platform_foundation.xa01.resolver import resolve_alias


class Xa01AliasTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_alias_idempotent_and_conflict(self) -> None:
        registry = InstrumentRegistry()
        canonical_id = register_equity(symbol="AAPL", registry=registry)
        alias = ExternalIdentifier(
            identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
            alias_value="US.AAPL",
            provider_id="MOOMOO",
        )
        registry.add_alias(canonical_id, alias)
        registry.add_alias(canonical_id, alias)
        resolved = resolve_alias(
            provider_id="MOOMOO",
            alias_value="US.AAPL",
            registry=registry,
        )
        self.assertEqual(resolved.status, AliasResolutionStatus.RESOLVED)
        self.assertEqual(resolved.canonical_id, canonical_id)
        other_id = register_equity(symbol="MSFT", registry=registry)
        with self.assertRaises(Xa01Error):
            registry.add_alias(
                other_id,
                ExternalIdentifier(
                    identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                    alias_value="US.AAPL",
                    provider_id="MOOMOO",
                ),
            )

    def test_unknown_alias(self) -> None:
        registry = InstrumentRegistry()
        result = resolve_alias(provider_id="MOOMOO", alias_value="UNKNOWN", registry=registry)
        self.assertEqual(result.status, AliasResolutionStatus.UNKNOWN)
