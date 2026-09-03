"""Fixture ingestion conformance tests for F1 FuturesContract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures import (  # noqa: E402
    futures_contract_from_dict,
    futures_contract_to_dict,
)
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)


class FuturesFixtureIngestionTests(unittest.TestCase):
    def test_es_chain_round_trip(self) -> None:
        provider = FixtureFuturesChainProvider()
        result = provider.fetch_chain("ES")
        self.assertEqual(result.status, "available")
        first = result.events[0]
        self.assertIn("provider_metadata", first)
        self.assertIn("entitlement", first)
        restored = futures_contract_from_dict(first)
        self.assertEqual(restored.instrument_family, "ES")
        payload = futures_contract_to_dict(restored)
        self.assertEqual(payload["contract_id"], first["contract_id"])

    def test_from_dict_missing_fields(self) -> None:
        with self.assertRaises(ValueError):
            futures_contract_from_dict({"instrument_family": "ES"})


if __name__ == "__main__":
    unittest.main()
