"""Tests for O1/F1 fixture chain providers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)
from market_platform_foundation.providers.adapters.fixture_option_chain import (  # noqa: E402
    FixtureOptionChainProvider,
)
from market_platform_foundation.providers.composition import configure_fixture_provider_composition  # noqa: E402


class ChainProviderTests(unittest.TestCase):
    def test_fixture_option_chain_biya(self) -> None:
        provider = FixtureOptionChainProvider()
        result = provider.fetch_chain("BIYA")
        self.assertEqual(result.status, "available")
        self.assertGreater(len(result.events), 0)
        first = result.events[0]
        self.assertEqual(first["underlying_id"], "BIYA")
        self.assertIn(first["call_put"], {"call", "put"})

    def test_fixture_option_chain_nvda_second_fixture(self) -> None:
        provider = FixtureOptionChainProvider()
        result = provider.fetch_chain("NVDA")
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 2)

    def test_fixture_futures_chain_es(self) -> None:
        provider = FixtureFuturesChainProvider()
        result = provider.fetch_chain("ES")
        self.assertEqual(result.status, "available")
        self.assertGreater(len(result.events), 0)
        self.assertEqual(result.events[0]["instrument_family"], "ES")

    def test_configure_fixture_provider_composition(self) -> None:
        composition = configure_fixture_provider_composition()
        biya = composition.option_chain.fetch_chain("BIYA")
        es = composition.futures_chain.fetch_chain("ES")
        self.assertEqual(biya.status, "available")
        self.assertEqual(es.status, "available")


if __name__ == "__main__":
    unittest.main()
