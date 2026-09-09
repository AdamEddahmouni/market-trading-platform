"""Deterministic event-log replay tests for the canonical L2 book (G5, F).

Proves: same events → identical state and hash, replay == live apply, replay
after restart reconstructs the same levels, duplicates do not double-apply,
RESET boundaries replay correctly, and sequence-gap invalidation replays
identically. Replay never reads a wall clock.
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
    DepthOperation,
    DepthSide,
    DepthUpdate,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)
from market_platform_foundation.order_flow.order_book.replay import (  # noqa: E402
    replay,
    replay_state_hash,
    replay_with_results,
)


def ev(book_id: str = "TEST", **kwargs) -> DepthUpdate:
    return build_depth_update(instrument_id=book_id, **kwargs)


def sample_event_log() -> list[DepthUpdate]:
    return [
        ev(operation=DepthOperation.RESET),
        ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100.00", size="10"),
        ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99.50", size="8"),
        ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="100.50", size="7"),
        ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="99.50", size="20"),
        ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100.25", size="4"),
        ev(operation=DepthOperation.DELETE, side=DepthSide.BID, price="100.00"),
        ev(operation=DepthOperation.UPDATE, side=DepthSide.ASK, price="100.50", size="2"),
    ]


class ReplayDeterminismTests(unittest.TestCase):
    def test_replay_equals_live_apply(self) -> None:
        events = sample_event_log()
        live = IncrementalOrderBook("TEST")
        for event in events:
            live.apply(event)
        replayed = replay(events)
        self.assertEqual(replayed.state_hash(), live.state_hash())
        self.assertEqual(replayed.to_snapshot_rows(), live.to_snapshot_rows())
        self.assertEqual(replayed.validity, live.validity)

    def test_same_events_identical_state_and_hash(self) -> None:
        events = sample_event_log()
        first = replay(events)
        second = replay(events)
        self.assertEqual(first.state_hash(), second.state_hash())
        self.assertEqual(first.bids, second.bids)
        self.assertEqual(first.asks, second.asks)
        self.assertEqual(first.generation, second.generation)
        self.assertEqual(first.update_count, second.update_count)
        self.assertEqual(replay_state_hash(events), replay_state_hash(events))

    def test_replay_after_restart_reconstructs_same_levels(self) -> None:
        events = sample_event_log()
        # A brand-new engine instance (restart) sees the same event log.
        book = replay(events)
        self.assertEqual(book.best_bid_price, 100.25)
        self.assertEqual(book.best_ask_price, 100.50)
        self.assertEqual(book.spread, 0.25)
        self.assertEqual(
            [level.price for level in book.bids], [100.25, 99.50]
        )
        self.assertTrue(book.book_state_valid)

    def test_duplicate_events_do_not_double_apply(self) -> None:
        events = sample_event_log()
        duplicate_log = [*events, events[-2], events[-2]]
        base = replay(events)
        dup = replay(duplicate_log)
        # Re-applying a DELETE of an already-absent level is a benign no-op,
        # so levels and update-count are unchanged and the hash is stable.
        self.assertEqual(dup.to_snapshot_rows(), base.to_snapshot_rows())
        self.assertEqual(dup.update_count, base.update_count)
        self.assertEqual(dup.state_hash(), base.state_hash())

    def test_reset_boundaries_replay_correctly(self) -> None:
        events = [
            ev(operation=DepthOperation.RESET),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="5"),
            ev(operation=DepthOperation.RESET),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="90", size="9"),
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="91", size="9"),
        ]
        book = replay(events)
        self.assertEqual([level.price for level in book.bids], [90])
        self.assertEqual(book.generation, 2)
        self.assertEqual(book.best_bid_price, 90)
        self.assertTrue(book.book_state_valid)

    def test_sequence_gap_invalidation_replays_identically(self) -> None:
        events = [
            ev(operation=DepthOperation.RESET),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="1", sequence=1),
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="1", sequence=5),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="1", sequence=6),
        ]
        first = replay(events)
        second = replay(events)
        self.assertEqual(first.state_hash(), second.state_hash())
        self.assertFalse(first.book_state_valid)
        self.assertEqual(first.invalidation_reason, BookStatusReason.SEQUENCE_GAP)
        # The recovery-required state is identical across replays.
        _, results = replay_with_results(events)
        outcomes = [result.outcome for result in results]
        self.assertEqual(
            outcomes,
            [
                ApplyOutcome.RESET_APPLIED,
                ApplyOutcome.APPLIED,
                ApplyOutcome.INVALIDATED,
                ApplyOutcome.REJECTED,
            ],
        )

    def test_replay_rejects_non_depthupdate(self) -> None:
        with self.assertRaises(TypeError):
            replay(["not-an-event"])  # type: ignore[list-item]


class ReplaySequenceTests(unittest.TestCase):
    def test_sequence_duplicate_replay_no_double_mutation(self) -> None:
        events = [
            ev(operation=DepthOperation.RESET),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="5", sequence=1),
            ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="5", sequence=1),
            ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="3", sequence=2),
        ]
        book = replay(events)
        self.assertEqual(len(book.bids), 1)
        self.assertEqual(book.best_bid_size, 5)
        self.assertEqual(len(book.asks), 1)
        self.assertEqual(book.last_sequence, 2)


if __name__ == "__main__":
    unittest.main()
