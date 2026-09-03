"""PIT alignment and chain envelope tests for O1/F1."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_option_chain import (  # noqa: E402
    FixtureOptionChainProvider,
)
from market_platform_foundation.providers.adapters.fixture_options import (  # noqa: E402
    DEFAULT_OPTIONS_FIXTURE,
    FixtureOptionsProvider,
)
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)
from market_platform_foundation.providers.envelope import enrich_chain_contract_event  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402
from market_platform_foundation.providers.composition import get_provider_composition  # noqa: E402


class PitAlignmentTests(unittest.TestCase):
    def test_biya_chain_and_activity_counts_align_at_cutoff(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:02.000000000Z")
        chain = FixtureOptionChainProvider().fetch_chain("BIYA", as_of_time_ns=cutoff)
        activity_provider = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        activity_result = activity_provider.fetch_options_activity("BIYA", as_of_time_ns=cutoff)
        self.assertEqual(chain.status, "available")
        self.assertEqual(activity_result.status, "available")
        self.assertEqual(len(chain.events), len(activity_result.events))

    def test_futures_chain_uses_cme_venue(self) -> None:
        result = FixtureFuturesChainProvider().fetch_chain("ES")
        self.assertEqual(result.status, "available")
        metadata = result.events[0].get("provider_metadata", {})
        symbol_mapping = metadata.get("symbol_mapping", {})
        self.assertEqual(symbol_mapping.get("venue_id"), "CME")

    def test_bootstrap_configures_chain_providers(self) -> None:
        bootstrap_default_providers()
        composition = get_provider_composition()
        biya = composition.option_chain.fetch_chain("BIYA")
        es = composition.futures_chain.fetch_chain("ES")
        self.assertEqual(biya.status, "available")
        self.assertEqual(es.status, "available")


class ChainEnvelopeTests(unittest.TestCase):
    def test_enrich_chain_contract_event_accepts_venue_id(self) -> None:
        enriched = enrich_chain_contract_event(
            {"underlying_id": "ES", "quality_flags": []},
            provider_id="test",
            entitlement="TEST",
            instrument_id="ES",
            event_time_ns=1,
            receive_time_ns=1,
            raw_source_reference="fixture:1",
            venue_id="CME",
        )
        venue = enriched["provider_metadata"]["symbol_mapping"]["venue_id"]
        self.assertEqual(venue, "CME")


if __name__ == "__main__":
    unittest.main()
