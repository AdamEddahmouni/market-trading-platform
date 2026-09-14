"""PIT reconciliation for congressional PTR rows (five-clock prep)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.market_trackers.congressional_disclosure.reconcile import (
    reconcile_congressional_clocks,
)

_MT_FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "market_trackers" / "congressional_disclosure"
)
_PTR_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "congressional_disclosure"
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000


def _load_mt(name: str) -> dict:
    return json.loads((_MT_FIXTURES / name).read_text(encoding="utf-8"))


def _load_ptr(name: str) -> dict:
    return json.loads((_PTR_FIXTURES / name).read_text(encoding="utf-8"))


class CongressionalDisclosurePitReconcileTests(unittest.TestCase):
    def test_aggregator_only_flags(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        clocks = reconcile_congressional_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertIn("PTR_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", clocks.reconcile_flags)
        self.assertIn("AGGREGATOR_FILING_PUBLICATION_ONLY", clocks.reconcile_flags)
        self.assertNotIn("PRIMARY_SOURCE_PTR_WINS", clocks.reconcile_flags)
        self.assertEqual(clocks.ptr_primary_publication_time_ns, 0)
        self.assertGreater(clocks.available_time_ns, clocks.economic_event_time_ns)

    def test_primary_ptr_wins_publication_clock(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        primary = _load_ptr("ptr_primary_senate_example.json")
        clocks = reconcile_congressional_clocks(
            row,
            platform_received_time_ns=_PLATFORM_RECEIVED_NS,
            ptr_primary=primary,
        )
        self.assertIn("PRIMARY_SOURCE_PTR_WINS", clocks.reconcile_flags)
        self.assertIn("PTR_PUBLICATION_FROM_PRIMARY", clocks.reconcile_flags)
        self.assertGreater(clocks.ptr_primary_publication_time_ns, 0)
        self.assertNotEqual(clocks.available_time_ns, clocks.economic_event_time_ns)

    def test_available_basis_not_transaction_start_of_day(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        clocks = reconcile_congressional_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertNotIn("transactedAt", clocks.available_time_basis)
        self.assertGreater(clocks.available_time_ns, clocks.economic_event_time_ns)


if __name__ == "__main__":
    unittest.main()
