"""RESET / subscription-generation semantics for the canonical L2 book (G5).

Proves: RESET clears all levels and cannot leave old levels alive, fresh
updates can rebuild after RESET, generation advances on subscription change,
and late events from an old generation are explicitly rejected so they can
never contaminate the new generation's state.
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


class ResetSemanticsTests(unittest.TestCase):
    def test_reset_clears_all_levels(self) -> None:
        book = IncrementalOrderBook("TEST")
        reset = book.apply(ev(operation=DepthOperation.RESET))
        self.assertEqual(reset.outcome, ApplyOutcome.RESET_APPLIED)
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="5"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="5"))
        self.assertEqual(book.level_counts, (1, 1))
        result = book.apply(ev(operation=DepthOperation.RESET))
        self.assertEqual(result.outcome, ApplyOutcome.RESET_APPLIED)
        # RESET is not a delete: no old levels survive.
        self.assertTrue(book.is_empty)
        self.assertFalse(book.book_state_valid)
        self.assertEqual(book.invalidation_reason, BookStatusReason.RESET_PENDING)
        self.assertEqual(book.level_counts, (0, 0))

    def test_fresh_updates_after_reset_rebuild(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="5"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="5"))
        book.apply(ev(operation=DepthOperation.RESET))
        self.assertFalse(book.book_state_valid)
        bid = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="90", size="3")
        )
        self.assertEqual(bid.outcome, ApplyOutcome.APPLIED)
        ask = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="91", size="3")
        )
        self.assertEqual(ask.outcome, ApplyOutcome.APPLIED)
        self.assertTrue(book.book_state_valid)
        self.assertEqual(book.best_bid_price, 90)
        self.assertEqual(book.best_ask_price, 91)

    def test_reset_advances_generation_and_reset_count(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        first_gen = book.generation
        book.apply(ev(operation=DepthOperation.RESET))
        self.assertEqual(book.generation, first_gen + 1)
        self.assertEqual(book.reset_count, 2)

    def test_reset_clears_sequence_continuity(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", sequence=100)
        )
        book.apply(ev(operation=DepthOperation.RESET))
        self.assertIsNone(book.last_sequence)


class GenerationSemanticsTests(unittest.TestCase):
    def test_generation_change_requires_reset(self) -> None:
        book = IncrementalOrderBook("TEST")
        # Generation A established via RESET with subscription A.
        book.apply(ev(operation=DepthOperation.RESET, subscription_id="A"))
        self.assertEqual(book.generation, 1)
        self.assertEqual(book.subscription_id, "A")
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", subscription_id="A")
        )
        # A non-RESET event from a different subscription is rejected.
        other = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="1", subscription_id="B")
        )
        self.assertEqual(other.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(other.reason, BookStatusReason.GENERATION_MISMATCH)
        self.assertEqual(len(book.bids), 1)

    def test_reset_with_new_subscription_starts_new_generation(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET, subscription_id="A"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", subscription_id="A"))
        book.apply(ev(operation=DepthOperation.RESET, subscription_id="B"))
        self.assertEqual(book.generation, 2)
        self.assertEqual(book.subscription_id, "B")
        self.assertTrue(book.is_empty)

    def test_late_old_generation_event_rejected(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET, subscription_id="A"))
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", subscription_id="A")
        )
        # Switch to generation B.
        book.apply(ev(operation=DepthOperation.RESET, subscription_id="B"))
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="90", size="1", subscription_id="B")
        )
        # Late A event must be ignored explicitly and must not contaminate B.
        late = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="95", size="99", subscription_id="A")
        )
        self.assertEqual(late.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(late.reason, BookStatusReason.GENERATION_MISMATCH)
        prices = [level.price for level in book.bids]
        self.assertEqual(prices, [90])
        self.assertNotIn(95, prices)
        # Generation B state remains correct and valid.
        self.assertTrue(book.book_state_valid)
        self.assertEqual(book.generation, 2)

    def test_book_without_subscription_metadata_accepts_events(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        first = book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1")
        )
        self.assertEqual(first.outcome, ApplyOutcome.APPLIED)
        self.assertEqual(book.subscription_id, None)


if __name__ == "__main__":
    unittest.main()
