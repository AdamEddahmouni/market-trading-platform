"""Basic state tests for the canonical incremental L2 book (G5 / ARCH-003).

Covers: empty book, single levels, multiple levels, deterministic best
bid/ask, side isolation, one-sided and crossed-book semantics, and the
derived-truth ``book_state_valid``.
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


def ev(book_id: str = "TEST", **kwargs):
    return build_depth_update(instrument_id=book_id, **kwargs)


class EmptyBookTests(unittest.TestCase):
    def test_fresh_book_is_unavailable_not_valid(self) -> None:
        book = IncrementalOrderBook("TEST")
        self.assertTrue(book.is_empty)
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.validity, BookValidity.UNAVAILABLE)
        self.assertEqual(book.invalidation_reason, BookStatusReason.UNINITIALIZED)
        self.assertIsNone(book.best_bid_price)
        self.assertIsNone(book.best_ask_price)
        self.assertIsNone(book.spread)
        self.assertEqual(book.level_counts, (0, 0))

    def test_book_identity_is_scoped_by_instrument(self) -> None:
        a = IncrementalOrderBook("AAA")
        b = IncrementalOrderBook("BBB")
        a.apply(ev(operation=DepthOperation.RESET))
        a.apply(
            ev(
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="10",
            )
        )
        self.assertTrue(b.is_empty)
        self.assertNotEqual(a.state_hash(), b.state_hash())


class SingleLevelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.book = IncrementalOrderBook("TEST")
        self.book.apply(ev(operation=DepthOperation.RESET))

    def test_one_bid(self) -> None:
        result = self.book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10")
        )
        self.assertEqual(result.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(self.book.best_bid_price, 100)
        self.assertEqual(self.book.best_bid_size, 10)
        self.assertIsNone(self.book.best_ask_price)
        self.assertTrue(self.book.book_state_valid)
        self.assertTrue(self.book.is_one_sided)
        self.assertFalse(self.book.is_empty)

    def test_one_ask(self) -> None:
        self.book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="5")
        )
        self.assertEqual(self.book.best_ask_price, 101)
        self.assertEqual(self.book.best_ask_size, 5)
        self.assertIsNone(self.book.best_bid_price)
        self.assertTrue(self.book.is_one_sided)

    def test_multi_level_ordering_and_best(self) -> None:
        for price in ("98", "100", "99"):
            self.book.apply(
                ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price=price, size="1")
            )
        for price in ("102", "101", "104", "103"):
            self.book.apply(
                ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price=price, size="1")
            )
        self.assertEqual(self.book.best_bid_price, 100)
        self.assertEqual(self.book.best_ask_price, 101)
        self.assertEqual(self.book.spread, 1)
        self.assertFalse(self.book.is_crossed)
        self.assertFalse(self.book.is_one_sided)
        self.assertEqual(
            [level.price for level in self.book.bids], [100, 99, 98]
        )
        self.assertEqual(
            [level.price for level in self.book.asks], [101, 102, 103, 104]
        )

    def test_side_mutations_are_isolated(self) -> None:
        self.book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10")
        )
        self.book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="11")
        )
        self.book.apply(
            ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="99", size="30")
        )
        self.assertEqual(len(self.book.asks), 0)
        self.assertEqual(self.book.level_counts, (2, 0))


class CrossedBookTests(unittest.TestCase):
    def test_crossed_book_is_explicit(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="105", size="10"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="10"))
        self.assertTrue(book.is_crossed)
        # Structurally consistent but crossed: no normal spread is fabricated.
        self.assertIsNone(book.spread)
        # Crossed state does not by itself make the book untrustworthy.
        self.assertTrue(book.book_state_valid)


class DerivedValidityTests(unittest.TestCase):
    def test_validity_is_derived_not_hardcoded(self) -> None:
        book = IncrementalOrderBook("TEST")
        self.assertFalse(book.book_state_valid)
        book.apply(ev(operation=DepthOperation.RESET))
        self.assertFalse(book.book_state_valid)  # RESET_PENDING, not optimistic
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="10", size="1"))
        self.assertTrue(book.book_state_valid)
        # A sequence gap cannot leave the boolean optimistically true.
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="11", size="1", sequence=1))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="9", size="1", sequence=3))
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.validity, BookValidity.INVALID)


if __name__ == "__main__":
    unittest.main()
