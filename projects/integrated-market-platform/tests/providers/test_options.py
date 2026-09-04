"""Phase 11 options provider and whale ledger tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.features.institutional import (
    NO_ENTITLED_SOURCE,
    OPTIONS_FAMILY,
    configure_institutional_ledger,
    get_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_options import (
    DEFAULT_OPTIONS_FIXTURE,
    FixtureOptionsProvider,
)
from market_platform_foundation.providers.whale_ledger import (
    WHALE_ENTITLED_OPTIONS,
    build_combined_fixture_ledger,
)
from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore


class OptionsAdapterTests(unittest.TestCase):
    def test_fixture_ingest_is_deterministic(self) -> None:
        first = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        second = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        first_result = first.fetch_options_activity("BIYA")
        second_result = second.fetch_options_activity("BIYA")
        self.assertEqual(first_result.status, "available")
        self.assertEqual(len(first_result.events), len(second_result.events))
        self.assertEqual(
            [row["normalized_event_id"] for row in first_result.events],
            [row["normalized_event_id"] for row in second_result.events],
        )

    def test_pit_cutoff_excludes_future_activity(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:02.000000000Z")
        provider = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        result = provider.fetch_options_activity("BIYA", as_of_time_ns=cutoff)
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 3)

    def test_liquidity_gate_surfaces_failures(self) -> None:
        provider = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        envelopes = provider.build_envelopes()
        low_oi = [
            row["whale_event"]
            for row in envelopes
            if isinstance(row.get("whale_event"), dict)
            and row["whale_event"].get("open_interest") == 50
        ]
        self.assertEqual(len(low_oi), 1)
        self.assertFalse(low_oi[0].get("liquidity_ok"))

    def test_nvda_symbol_unavailable(self) -> None:
        provider = FixtureOptionsProvider(fixture_path=DEFAULT_OPTIONS_FIXTURE)
        result = provider.fetch_options_activity("NVDA")
        self.assertEqual(result.status, "unavailable")


class OptionsLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(None)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_options_available_for_biya(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-21T21:01:09.000000000Z")
        row = query_institutional_evidence(
            OPTIONS_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="BIYA",
        )
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["reason_code"], WHALE_ENTITLED_OPTIONS)

    def test_options_unavailable_for_nvda(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-21T21:01:09.000000000Z")
        row = query_institutional_evidence(
            OPTIONS_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="NVDA",
        )
        self.assertEqual(row["status"], "unavailable")
        self.assertEqual(row["reason_code"], NO_ENTITLED_SOURCE)


class OptionsUiTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=ROOT.parent)
        cls.store.load()

    def test_capabilities_show_options_available(self) -> None:
        caps = build_capabilities(self.store)
        by_id = {row["capability_id"]: row for row in caps}
        self.assertEqual(by_id["whale.options"]["state"], "AVAILABLE")

    def test_workspace_options_payload(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_options_payload

        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertGreater(payload["activity_count"], 0)

    def test_workspace_options_unavailable_for_nvda(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_options_payload

        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertFalse(payload["available"])


if __name__ == "__main__":
    unittest.main()
