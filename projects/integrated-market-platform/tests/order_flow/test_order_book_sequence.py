"""Sequence correctness tests for the canonical L2 book (G5, Checkpoint D).

Proves all five sequence states plus NO_SEQUENCE: BASE anchoring, CONTIGUOUS
application, DUPLICATE no-op, GAP fail-closed invalidation, and REGRESSION /
out-of-order fail-closed behavior. Gaps and regressions cannot be silently
repaired by later events.
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
    SequenceState,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)


def ev(book_id: str = "TEST", **kwargs):
    return build_depth_update(instrument_id=book_id, **kwargs)


def bid(book: IncrementalOrderBook, price: str, size: str = "1", **kw) -> object:
    return book.apply(
        ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price=price, size=size, **kw)
    )


def reset_book(book: IncrementalOrderBook) -> None:
    result = book.apply(ev(operation=DepthOperation.RESET))
    assert result.outcome is ApplyOutcome.RESET_APPLIED


class NoSequenceTests(unittest.TestCase):
    def test_no_sequence_provider_reports_no_sequence_truthfully(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        self.assertEqual(book.sequence_state, SequenceState.NO_SEQUENCE)
        bid(book, "100")
        bid(book, "99")
        # Book works under ordered delivery, but protection is honestly absent.
        self.assertEqual(book.sequence_state, SequenceState.NO_SEQUENCE)
        self.assertIsNone(book.last_sequence)
        self.assertTrue(book.book_state_valid)


class SequenceApplicationTests(unittest.TestCase):
    def test_first_sequence_anchors_base(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        result = bid(book, "100", sequence=100)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.sequence_state, SequenceState.BASE)
        self.assertEqual(book.last_sequence, 100)

    def test_contiguous_sequence_applies(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        result = bid(book, "99", sequence=101)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.sequence_state, SequenceState.CONTIGUOUS)
        self.assertEqual(book.last_sequence, 101)
        self.assertEqual(len(book.bids), 2)

    def test_duplicate_sequence_is_explicit_duplicate_noop(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        result = bid(book, "99", sequence=100)
        self.assertEqual(result.outcome, ApplyOutcome.DUPLICATE)
        self.assertEqual(result.sequence_state, SequenceState.DUPLICATE)
        self.assertFalse(result.state_changed)
        # Not double-applied.
        self.assertEqual(len(book.bids), 1)

    def test_duplicate_content_event_does_not_double_apply(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", size="5", sequence=100)
        result = bid(book, "100", size="5", sequence=100)
        self.assertEqual(result.outcome, ApplyOutcome.DUPLICATE)
        self.assertEqual(book.best_bid_size, 5)
        self.assertEqual(len(book.bids), 1)

    def test_gap_invalidates_and_fails_closed(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        result = bid(book, "99", sequence=103)
        self.assertEqual(result.outcome, ApplyOutcome.INVALIDATED)
        self.assertEqual(result.reason, BookStatusReason.SEQUENCE_GAP)
        self.assertEqual(result.sequence_state, SequenceState.GAP)
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.validity, BookValidity.INVALID)
        # A later contiguous event cannot silently restore trust.
        followup = bid(book, "98", sequence=104)
        self.assertEqual(followup.outcome, ApplyOutcome.REJECTED)

    def test_gap_requires_explicit_reset_recovery(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        bid(book, "99", sequence=103)  # GAP
        self.assertFalse(book.book_state_valid)
        reset = book.apply(ev(operation=DepthOperation.RESET, sequence=None))
        self.assertEqual(reset.outcome, ApplyOutcome.RESET_APPLIED)
        # Fresh state re-anchors as BASE.
        result = bid(book, "98", sequence=1)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.sequence_state, SequenceState.BASE)

    def test_regression_invalidates_without_mutating_state(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        result = bid(book, "95", size="9", sequence=50)
        self.assertEqual(result.outcome, ApplyOutcome.INVALIDATED)
        self.assertEqual(result.reason, BookStatusReason.SEQUENCE_REGRESSION)
        self.assertEqual(result.sequence_state, SequenceState.REGRESSION)
        # Authoritative state was NOT silently mutated by the regression.
        self.assertEqual(len(book.bids), 1)
        self.assertNotIn(95, [level.price for level in book.bids])
        self.assertFalse(book.book_state_valid)

    def test_reset_clears_sequence_continuity(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset_book(book)
        bid(book, "100", sequence=100)
        bid(book, "99", sequence=101)
        reset_book(book)
        self.assertIsNone(book.last_sequence)
        self.assertEqual(book.sequence_state, SequenceState.NO_SEQUENCE)
        # Provider renumbered after reconnect: new anchor accepted as BASE.
        result = bid(book, "98", sequence=1)
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.sequence_state, SequenceState.BASE)


if __name__ == "__main__":
    unittest.main()
