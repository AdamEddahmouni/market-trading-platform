"""Freshness / staleness tests for the canonical L2 book (G5, ARCH-009).

Freshness is a pure function of explicit state and ``as_of_time_ns`` — never a
wall-clock read inside deterministic paths. STALE is not silently collapsed
into INVALID, and an INVALID book is never FRESH.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    DepthOperation,
    DepthSide,
    FreshnessStatus,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)
from market_platform_foundation.order_flow.order_book.freshness import (  # noqa: E402
    FreshnessPolicy,
    evaluate_book_freshness,
)

NS = 1_000_000_000
POLICY = FreshnessPolicy(stale_after_ns=5 * NS, name="test")


def ev(book_id: str = "TEST", **kwargs):
    return build_depth_update(instrument_id=book_id, **kwargs)


def valid_fresh_book(now_ns: int = 1_000 * NS) -> IncrementalOrderBook:
    book = IncrementalOrderBook("TEST")
    book.apply(ev(operation=DepthOperation.RESET, received_time_ns=now_ns - 100))
    book.apply(
        ev(
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price="100",
            size="5",
            received_time_ns=now_ns - 50,
        )
    )
    book.apply(
        ev(
            operation=DepthOperation.INSERT,
            side=DepthSide.ASK,
            price="101",
            size="5",
            received_time_ns=now_ns - 25,
        )
    )
    return book


class FreshnessTests(unittest.TestCase):
    def test_fresh(self) -> None:
        book = valid_fresh_book(now_ns=1_000 * NS)
        result = evaluate_book_freshness(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.FRESH)
        self.assertTrue(book.book_state_valid)  # trust and freshness are separate

    def test_exactly_at_threshold_is_fresh(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET, received_time_ns=0))
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", received_time_ns=0)
        )
        book.apply(
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="1", received_time_ns=0)
        )
        result = evaluate_book_freshness(book, as_of_time_ns=5 * NS, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.FRESH)

    def test_stale_is_stale_not_invalid(self) -> None:
        book = valid_fresh_book(now_ns=1_000 * NS)
        result = evaluate_book_freshness(book, as_of_time_ns=1_006 * NS, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.STALE)
        # A stale-but-valid book keeps trust validity while carrying the stale
        # qualifier downstream safety logic can consume.
        self.assertTrue(book.book_state_valid)
        self.assertGreater(result.age_ns or 0, 5 * NS)

    def test_invalid_book_never_fresh(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET, received_time_ns=0))
        result = evaluate_book_freshness(book, as_of_time_ns=0, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.INVALID)

    def test_invalid_beats_stale(self) -> None:
        book = valid_fresh_book(now_ns=1_000 * NS)
        # Introduce an INVALIDATING event far in the past.
        book.apply(
            ev(
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="105",
                size="1",
                received_time_ns=1_000 * NS - 10,
                sequence=5,
            )
        )
        book.apply(
            ev(
                operation=DepthOperation.INSERT,
                side=DepthSide.ASK,
                price="106",
                size="1",
                received_time_ns=1_000 * NS - 5,
                sequence=99,
            )
        )  # GAP: book INVALID
        self.assertFalse(book.book_state_valid)
        far_future = 1_000 * NS + 600 * NS
        result = evaluate_book_freshness(book, as_of_time_ns=far_future, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.INVALID)

    def test_deterministic_in_as_of_time(self) -> None:
        book = valid_fresh_book(now_ns=1_000 * NS)
        a = evaluate_book_freshness(book, as_of_time_ns=1_006 * NS, policy=POLICY)
        b = evaluate_book_freshness(book, as_of_time_ns=1_006 * NS, policy=POLICY)
        self.assertEqual(a.status, b.status)
        self.assertEqual(a.to_dict(), b.to_dict())
        stale_now = evaluate_book_freshness(book, as_of_time_ns=1_006 * NS, policy=POLICY)
        fresh_now = evaluate_book_freshness(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertEqual(stale_now.status, FreshnessStatus.STALE)
        self.assertEqual(fresh_now.status, FreshnessStatus.FRESH)

    def test_no_received_time_is_unavailable_not_stale(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="1"))
        self.assertTrue(book.book_state_valid)
        result = evaluate_book_freshness(book, as_of_time_ns=999_999 * NS, policy=POLICY)
        self.assertEqual(result.status, FreshnessStatus.UNAVAILABLE)

    def test_policy_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            FreshnessPolicy(stale_after_ns=-1)


if __name__ == "__main__":
    unittest.main()
