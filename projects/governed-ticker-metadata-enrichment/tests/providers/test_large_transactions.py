"""Phase 12 large_transactions provider and whale ledger tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.features.institutional import (
    LARGE_TRANSACTIONS_FAMILY,
    NO_ENTITLED_SOURCE,
    configure_institutional_ledger,
    get_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_large_transactions import (
    DEFAULT_LARGE_TRANSACTIONS_FIXTURE,
    FixtureLargeTransactionsProvider,
)
from market_platform_foundation.providers.whale_ledger import (
    WHALE_ENTITLED_LARGE_TRANSACTIONS,
    build_combined_fixture_ledger,
)
from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore


class LargeTransactionsAdapterTests(unittest.TestCase):
    def test_fixture_ingest_is_deterministic(self) -> None:
        first = FixtureLargeTransactionsProvider(fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE)
        second = FixtureLargeTransactionsProvider(fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE)
        first_result = first.fetch_large_transactions("NVDA")
        second_result = second.fetch_large_transactions("NVDA")
        self.assertEqual(first_result.status, "available")
        self.assertEqual(len(first_result.events), len(second_result.events))
        self.assertEqual(
            [row["normalized_event_id"] for row in first_result.events],
            [row["normalized_event_id"] for row in second_result.events],
        )

    def test_pit_cutoff_excludes_future_prints(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:02.000000000Z")
        provider = FixtureLargeTransactionsProvider(fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE)
        result = provider.fetch_large_transactions("NVDA", as_of_time_ns=cutoff)
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 3)

    def test_threshold_gate_surfaces_failures(self) -> None:
        provider = FixtureLargeTransactionsProvider(fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE)
        envelopes = provider.build_envelopes()
        below_threshold = [
            row["whale_event"]
            for row in envelopes
            if isinstance(row.get("whale_event"), dict)
            and row["whale_event"].get("print_size") == 250
        ]
        self.assertEqual(len(below_threshold), 1)
        self.assertFalse(below_threshold[0].get("threshold_gate_ok"))

    def test_biya_symbol_unavailable(self) -> None:
        provider = FixtureLargeTransactionsProvider(fixture_path=DEFAULT_LARGE_TRANSACTIONS_FIXTURE)
        result = provider.fetch_large_transactions("BIYA")
        self.assertEqual(result.status, "unavailable")


class LargeTransactionsLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(None)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_large_transactions_available_for_nvda(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-21T21:01:09.000000000Z")
        row = query_institutional_evidence(
            LARGE_TRANSACTIONS_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="NVDA",
        )
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["reason_code"], WHALE_ENTITLED_LARGE_TRANSACTIONS)

    def test_large_transactions_unavailable_for_biya(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-21T21:01:09.000000000Z")
        row = query_institutional_evidence(
            LARGE_TRANSACTIONS_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="BIYA",
        )
        self.assertEqual(row["status"], "unavailable")
        self.assertEqual(row["reason_code"], NO_ENTITLED_SOURCE)


class LargeTransactionsUiTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=ROOT.parent)
        cls.store.load()

    def test_capabilities_show_large_transactions_available(self) -> None:
        caps = build_capabilities(self.store)
        by_id = {row["capability_id"]: row for row in caps}
        self.assertEqual(by_id["whale.large_transactions"]["state"], "AVAILABLE")

    def test_workspace_large_transactions_payload(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_large_transactions_payload

        payload = build_workspace_large_transactions_payload(
            "NVDA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertGreater(payload["print_count"], 0)

    def test_workspace_large_transactions_unavailable_for_biya(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_large_transactions_payload

        payload = build_workspace_large_transactions_payload(
            "BIYA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertFalse(payload["available"])


if __name__ == "__main__":
    unittest.main()
