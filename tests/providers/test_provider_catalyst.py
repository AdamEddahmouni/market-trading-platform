"""Phase 15 catalyst provider and whale ledger tests."""

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
    PUBLIC_CATALYST_FAMILY,
    configure_institutional_ledger,
    get_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_catalyst import (
    DEFAULT_CATALYST_FIXTURE,
    FixtureCatalystProvider,
)
from market_platform_foundation.providers.whale_ledger import (
    WHALE_ENTITLED_CATALYST,
    build_combined_fixture_ledger,
)
from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore


class CatalystAdapterTests(unittest.TestCase):
    def test_fixture_ingest_is_deterministic(self) -> None:
        first = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        second = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        first_result = first.fetch_catalyst_activity("BOXL")
        second_result = second.fetch_catalyst_activity("BOXL")
        self.assertEqual(first_result.status, "available")
        self.assertEqual(len(first_result.events), len(second_result.events))
        self.assertEqual(
            [row["normalized_event_id"] for row in first_result.events],
            [row["normalized_event_id"] for row in second_result.events],
        )

    def test_pit_cutoff_excludes_future_activity(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T17:00:00.000000000Z")
        provider = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        result = provider.fetch_catalyst_activity("BOXL", as_of_time_ns=cutoff)
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 3)

    def test_nvda_symbol_unavailable(self) -> None:
        provider = FixtureCatalystProvider(fixture_path=DEFAULT_CATALYST_FIXTURE)
        result = provider.fetch_catalyst_activity("NVDA")
        self.assertEqual(result.status, "unavailable")


class CatalystLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(None)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_catalyst_available_for_boxl(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        row = query_institutional_evidence(
            PUBLIC_CATALYST_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="BOXL",
        )
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["reason_code"], WHALE_ENTITLED_CATALYST)

    def test_catalyst_unavailable_for_nvda(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
        row = query_institutional_evidence(
            PUBLIC_CATALYST_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="NVDA",
        )
        self.assertEqual(row["status"], "unavailable")
        self.assertEqual(row["reason_code"], NO_ENTITLED_SOURCE)


class CatalystUiTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=ROOT.parent)
        cls.store.load()

    def test_capabilities_show_catalyst_available(self) -> None:
        caps = build_capabilities(self.store)
        by_id = {row["capability_id"]: row for row in caps}
        self.assertEqual(by_id["whale.public_catalyst"]["state"], "AVAILABLE")

    def test_workspace_catalyst_payload(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_catalyst_payload

        payload = build_workspace_catalyst_payload(
            "BOXL",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertGreater(len(payload.get("catalysts", [])), 0)

    def test_workspace_catalyst_unavailable_for_nvda(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_catalyst_payload

        payload = build_workspace_catalyst_payload(
            "NVDA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertFalse(payload["available"])


if __name__ == "__main__":
    unittest.main()
