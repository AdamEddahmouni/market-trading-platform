"""Snapshot compatibility tests for the canonical L2 book (G5, Checkpoint C).

Canonical incremental state becomes authoritative; snapshot replacement
survives only as an explicit ingestion compatibility mode. Tests prove the
canonical→legacy projection is deterministic, full-snapshot import produces
the same canonical levels, RESET semantics on replace, and round-trip
stability.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    ApplyOutcome,
    BookStatusReason,
    BookValidity,
    DepthOperation,
    DepthSide,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)
from market_platform_foundation.order_flow.order_book.projection import (  # noqa: E402
    ingest_snapshot_dict,
    project_book_snapshot,
)


def ev(book_id: str = "TEST", **kwargs):
    return build_depth_update(instrument_id=book_id, **kwargs)


def build_canonical_book() -> IncrementalOrderBook:
    book = IncrementalOrderBook("TEST")
    book.apply(ev(operation=DepthOperation.RESET))
    book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10"))
    book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="8"))
    book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="7"))
    book.apply(ev(operation=DepthOperation.UPDATE, side=DepthSide.ASK, price="101", size="9"))
    return book


class ProjectionTests(unittest.TestCase):
    def test_canonical_state_projects_to_legacy_shape(self) -> None:
        book = build_canonical_book()
        payload = project_book_snapshot(book)
        self.assertTrue(payload["book_state_valid"])
        self.assertEqual(payload["book_status"], BookValidity.VALID.value)
        self.assertEqual(payload["instrument_id"], "TEST")
        self.assertEqual(payload["level_count"], 2)
        self.assertEqual(payload["best_bid"], 100.0)
        self.assertEqual(payload["best_ask"], 101.0)
        # Bid rows descending, ask rows ascending.
        self.assertEqual([row["price"] for row in payload["bids"]], [100.0, 99.0])
        self.assertEqual([row["price"] for row in payload["asks"]], [101.0])

    def test_projection_is_deterministic(self) -> None:
        book = build_canonical_book()
        self.assertEqual(project_book_snapshot(book), project_book_snapshot(book))

    def test_projection_reports_invalid_book_truthfully(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        payload = project_book_snapshot(book)
        self.assertFalse(payload["book_state_valid"])
        self.assertEqual(payload["book_status"], BookValidity.INVALID.value)
        self.assertEqual(payload["book_status_reason"], BookStatusReason.RESET_PENDING.value)
        self.assertEqual(payload["bids"], [])
        self.assertEqual(payload["asks"], [])


class SnapshotIngestionTests(unittest.TestCase):
    def test_full_snapshot_import_produces_same_canonical_levels(self) -> None:
        canonical = build_canonical_book()
        snapshot = project_book_snapshot(canonical)
        book = IncrementalOrderBook("TEST")
        result = ingest_snapshot_dict(book, snapshot)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertTrue(book.book_state_valid)
        self.assertEqual(book.to_snapshot_rows(), canonical.to_snapshot_rows())
        self.assertEqual(book.best_bid_price, 100)
        self.assertEqual(book.best_ask_price, 101)

    def test_snapshot_replace_clears_prior_state(self) -> None:
        book = build_canonical_book()
        snapshot = {
            "bids": [{"price": 50, "size": 3}],
            "asks": [{"price": 51, "size": 3}],
        }
        result = ingest_snapshot_dict(book, snapshot)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        # Old levels from the incremental build are gone.
        self.assertEqual([level.price for level in book.bids], [50])
        self.assertEqual([level.price for level in book.asks], [51])

    def test_replace_from_snapshot_is_not_incremental_update(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10"))
        result = book.replace_from_snapshot(
            bids=[{"price": 80, "size": 1}],
            asks=[{"price": 81, "size": 1}],
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [80])
        self.assertEqual(len(book.asks), 1)
        self.assertEqual(book.reset_count, 2)  # RESET semantics recorded

    def test_snapshot_round_trip_stable(self) -> None:
        canonical = build_canonical_book()
        snapshot = project_book_snapshot(canonical)
        rebuilt = IncrementalOrderBook("TEST")
        ingest_snapshot_dict(rebuilt, snapshot)
        self.assertEqual(rebuilt.to_snapshot_rows(), canonical.to_snapshot_rows())
        # Projecting the rebuilt book gives the same rows again.
        again = project_book_snapshot(rebuilt)
        self.assertEqual(again["bids"], snapshot["bids"])
        self.assertEqual(again["asks"], snapshot["asks"])

    def test_empty_snapshot_is_invalid_not_valid(self) -> None:
        book = IncrementalOrderBook("TEST")
        result = ingest_snapshot_dict(book, {"bids": [], "asks": []})
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.invalidation_reason, BookStatusReason.RESET_PENDING)

    def test_corrupt_snapshot_row_invalidates_without_partial_state(self) -> None:
        book = IncrementalOrderBook("TEST")
        result = book.replace_from_snapshot(
            bids=[{"price": 100, "size": 5}, {"price": "not-a-number", "size": 5}],
            asks=[],
        )
        self.assertEqual(result.outcome, ApplyOutcome.INVALIDATED)
        self.assertEqual(result.reason, BookStatusReason.STRUCTURALLY_CORRUPT)
        # No half-imported state survives.
        self.assertTrue(book.is_empty)
        self.assertFalse(book.book_state_valid)

    def test_snapshot_sequence_anchors_base(self) -> None:
        book = IncrementalOrderBook("TEST")
        result = book.replace_from_snapshot(
            bids=[{"price": 100, "size": 5}],
            asks=[],
            sequence=77,
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.last_sequence, 77)


if __name__ == "__main__":
    unittest.main()
