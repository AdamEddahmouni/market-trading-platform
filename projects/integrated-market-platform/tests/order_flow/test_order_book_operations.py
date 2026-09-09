"""Incremental mutation semantics tests for the canonical L2 book (G5).

Covers explicit INSERT / UPDATE / DELETE at head, middle and tail with
deterministic price ordering, position/rank cross-checks, corrupt-input
fail-closed behavior, and the invariant that a DELETE cannot remove an
unrelated rank.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
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
    DepthUpdate,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)


def ev(book_id: str = "TEST", **kwargs):
    return build_depth_update(instrument_id=book_id, **kwargs)


def bid_book(book: IncrementalOrderBook, *prices: str) -> None:
    for index, price in enumerate(prices):
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price=price, size="1", position=index)
        )
        assert result.outcome is ApplyOutcome.APPLIED, (price, result)


def ask_book(book: IncrementalOrderBook, *prices: str) -> None:
    for index, price in enumerate(prices):
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price=price, size="1", position=index)
        )
        assert result.outcome is ApplyOutcome.APPLIED, (price, result)


def fresh_book() -> IncrementalOrderBook:
    book = IncrementalOrderBook("TEST")
    book.apply(ev(operation=DepthOperation.RESET))
    return book


class InsertSemanticsTests(unittest.TestCase):
    def test_insert_head(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="101", size="2", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.best_bid_price, 101)
        self.assertEqual([level.price for level in book.bids], [101, 100, 99])

    def test_insert_middle_shifts_lower_priority(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "98")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="2", position=1)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [100, 99, 98])

    def test_insert_tail(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="98", size="2", position=2)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [100, 99, 98])

    def test_identical_duplicate_insert_is_benign_noop(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.NOOP)
        self.assertFalse(result.state_changed)
        self.assertEqual(len(book.bids), 1)

    def test_conflicting_duplicate_insert_invalidates(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="999", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.INVALIDATED)
        self.assertEqual(result.reason, BookStatusReason.STRUCTURALLY_CORRUPT)
        self.assertFalse(book.book_state_valid)
        # Duplicate ranks are impossible: only one level exists at the price.
        self.assertEqual(len([lvl for lvl in book.bids if lvl.price == 100]), 1)

    def test_insert_rank_mismatch_rejected(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "98")
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="2", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.STRUCTURALLY_CORRUPT)
        self.assertEqual([level.price for level in book.bids], [100, 98])


class UpdateSemanticsTests(unittest.TestCase):
    def test_update_head(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="100", size="50", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.best_bid_size, 50)
        self.assertEqual([level.price for level in book.bids], [100, 99, 98])

    def test_update_middle_replaces_only_that_level(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="99", size="77", position=1)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        sizes = [level.size for level in book.bids]
        self.assertEqual(sizes, [1, 77, 1])

    def test_update_is_not_snapshot_replacement(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99")
        ask_book(book, "101")
        book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="99", size="77", position=1)
        )
        # A blind snapshot replacement would have destroyed the other levels.
        self.assertEqual(len(book.bids), 2)
        self.assertEqual(len(book.asks), 1)

    def test_update_of_missing_level_fails_closed(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        result = book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="95", size="5")
        )
        self.assertEqual(result.outcome, ApplyOutcome.INVALIDATED)
        self.assertEqual(result.reason, BookStatusReason.LEVEL_NOT_FOUND)
        self.assertFalse(book.book_state_valid)
        # Recovery required: later events cannot silently restore trust.
        followup = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="95", size="5")
        )
        self.assertEqual(followup.outcome, ApplyOutcome.REJECTED)

    def test_update_rank_mismatch_rejected(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99")
        result = book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="99", size="7", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.STRUCTURALLY_CORRUPT)


class DeleteSemanticsTests(unittest.TestCase):
    def test_delete_head(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="100", position=0)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.best_bid_price, 99)
        self.assertEqual([level.price for level in book.bids], [99, 98])

    def test_delete_middle_closes_rank_gap(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="99", position=1)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [100, 98])
        self.assertEqual(len(book.asks), 0)
        self.assertTrue(book.book_state_valid)

    def test_delete_tail(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="98", position=2)
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [100, 99])

    def test_delete_by_position_only(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99")
        result = book.apply(ev(operation=DepthOperation.DELETE, side=DepthSide.BID, position=1))
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual([level.price for level in book.bids], [100])

    def test_delete_of_absent_level_is_benign(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="90")
        )
        self.assertEqual(result.outcome, ApplyOutcome.NOOP)
        self.assertFalse(result.state_changed)
        self.assertEqual(len(book.bids), 1)
        self.assertTrue(book.book_state_valid)

    def test_delete_price_rank_mismatch_cannot_delete_unrelated_rank(self) -> None:
        book = fresh_book()
        bid_book(book, "100", "99", "98")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="100", position=2)
        )
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.STRUCTURALLY_CORRUPT)
        # Nothing was deleted.
        self.assertEqual([level.price for level in book.bids], [100, 99, 98])

    def test_delete_position_out_of_range_rejected(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        result = book.apply(
            ev(operation=DepthOperation.DELETE, side=DepthSide.BID, position=5)
        )
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(len(book.bids), 1)

    def test_deleting_all_levels_leaves_clean_invalid_book(self) -> None:
        book = fresh_book()
        bid_book(book, "100")
        book.apply(ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="100", position=0))
        self.assertTrue(book.is_empty)
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.invalidation_reason, BookStatusReason.RESET_PENDING)
        # Fresh inserts can rebuild a clean (non-corrupt) empty book.
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="1")
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertTrue(book.book_state_valid)


class RejectionSemanticsTests(unittest.TestCase):
    def test_zero_size_insert_rejected(self) -> None:
        book = fresh_book()
        result = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="0")
        )
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.ZERO_SIZE)
        self.assertTrue(book.is_empty)

    def test_negative_price_direct_event_rejected(self) -> None:
        book = fresh_book()
        event = DepthUpdate(
            instrument_id="TEST",
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price=Decimal("-5"),
            size=Decimal("1"),
        )
        result = book.apply(event)
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.NEGATIVE_PRICE)

    def test_negative_size_direct_event_rejected(self) -> None:
        book = fresh_book()
        event = DepthUpdate(
            instrument_id="TEST",
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price=Decimal("100"),
            size=Decimal("-1"),
        )
        result = book.apply(event)
        self.assertEqual(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason, BookStatusReason.NEGATIVE_SIZE)
        self.assertTrue(book.is_empty)

    def test_non_depthupdate_rejected_with_type_error(self) -> None:
        book = fresh_book()
        with self.assertRaises(TypeError):
            book.apply({"operation": "INSERT"})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
