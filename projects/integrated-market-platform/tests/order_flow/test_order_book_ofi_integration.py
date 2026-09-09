"""Order-flow / CVD interoperability tests for the canonical L2 book (G5, E).

Proves the canonical engine state feeds the existing snapshot-shaped
order-flow layer through a deterministic projection, and that the OFI
rank-shift risk (ARCH-006) is resolved by the additive price-aligned method:
price-keyed levels can never be mis-paired when an insert/delete shifts
positions between snapshots. CVD session authority is untouched — these tests
exercise only the projection boundary.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.order_flow.ofi import (  # noqa: E402
    OFI_METHOD_MULTILEVEL_PRICE_ALIGNED,
    OFI_VERSION_MULTILEVEL_PRICE_ALIGNED,
    compute_multilevel_ofi,
    compute_multilevel_ofi_price_aligned,
    compute_ofi,
)
from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    DepthOperation,
    DepthSide,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import (  # noqa: E402
    IncrementalOrderBook,
)
from market_platform_foundation.order_flow.order_book.projection import (  # noqa: E402
    project_book_snapshot,
)


def ev(**kwargs):
    return build_depth_update(instrument_id="TEST", **kwargs)


def rows(*levels: tuple[float, float]) -> list[dict[str, float]]:
    return [{"price": price, "size": size} for price, size in levels]


B1 = rows((100.0, 1.0), (99.0, 1.0), (98.0, 1.0))
A1 = rows((101.0, 1.0), (102.0, 1.0), (103.0, 1.0))


class PriceAlignedOfiTests(unittest.TestCase):
    def test_head_insert_does_not_fabricate_rank_paired_events(self) -> None:
        prev_snapshot = {"bids": B1, "asks": A1}
        curr_snapshot = {
            "bids": rows((100.5, 1.0), (100.0, 1.0), (99.0, 1.0)),
            "asks": A1,
        }
        aligned = compute_multilevel_ofi_price_aligned(prev_snapshot, curr_snapshot, level_count=3)
        legacy = compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=3)
        # Only one real depth event: +1 inserted at the new best bid.
        self.assertEqual(aligned.value, 1.0)
        # The rank-based method pairs shifted ranks and double counts.
        self.assertEqual(legacy.value, 3.0)
        self.assertNotEqual(aligned.value, legacy.value)

    def test_middle_delete_does_not_fabricate_rank_paired_events(self) -> None:
        prev_snapshot = {"bids": B1, "asks": A1}
        curr_snapshot = {"bids": rows((100.0, 1.0), (98.0, 1.0)), "asks": A1}
        aligned = compute_multilevel_ofi_price_aligned(prev_snapshot, curr_snapshot, level_count=3)
        legacy = compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=3)
        # One real depth event: -1 removed at price 99.
        self.assertEqual(aligned.value, -1.0)
        self.assertEqual(legacy.value, -2.0)

    def test_ask_insert_contributes_negative(self) -> None:
        prev_snapshot = {"bids": B1, "asks": A1}
        curr_snapshot = {
            "bids": B1,
            "asks": rows((100.5, 1.0), (101.0, 1.0), (102.0, 1.0)),
        }
        aligned = compute_multilevel_ofi_price_aligned(prev_snapshot, curr_snapshot, level_count=3)
        self.assertEqual(aligned.value, -1.0)

    def test_pure_update_without_rank_shift_agrees_with_legacy(self) -> None:
        prev_snapshot = {
            "bids": rows((100.0, 10.0), (99.0, 5.0)),
            "asks": rows((101.0, 7.0), (102.0, 3.0)),
        }
        curr_snapshot = {
            "bids": rows((100.0, 8.0), (99.0, 9.0)),
            "asks": rows((101.0, 6.0), (102.0, 4.0)),
        }
        aligned = compute_multilevel_ofi_price_aligned(prev_snapshot, curr_snapshot, level_count=2)
        legacy = compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=2)
        # Bid contrib: (8-10)+(9-5)=2. Ask contrib: -(6-7)-(4-3)=1-1=0.
        self.assertEqual(aligned.value, 2.0)
        self.assertEqual(aligned.value, legacy.value)

    def test_invalid_pair_fails_closed(self) -> None:
        result = compute_multilevel_ofi_price_aligned(
            {"bids": B1, "asks": []}, {"bids": B1, "asks": A1}
        )
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.value, 0.0)

    def test_method_routes_through_compute_ofi(self) -> None:
        prev_snapshot = {"bids": B1, "asks": A1}
        curr_snapshot = {
            "bids": rows((100.5, 1.0), (100.0, 1.0), (99.0, 1.0)),
            "asks": A1,
        }
        result = compute_ofi(
            prev_snapshot,
            curr_snapshot,
            method=OFI_METHOD_MULTILEVEL_PRICE_ALIGNED,
            level_count=3,
        )
        self.assertTrue(result.book_state_valid)
        self.assertEqual(result.ofi_method, OFI_METHOD_MULTILEVEL_PRICE_ALIGNED)
        self.assertEqual(result.ofi_version, OFI_VERSION_MULTILEVEL_PRICE_ALIGNED)
        self.assertEqual(result.value, 1.0)


class CanonicalProjectionOfiTests(unittest.TestCase):
    def test_engine_snapshots_feed_existing_ofi(self) -> None:
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="5"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="7"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="102", size="3"))
        t0 = project_book_snapshot(book)
        # A canonical incremental insert at the head of the bid side.
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100.5", size="1"))
        t1 = project_book_snapshot(book)
        aligned = compute_multilevel_ofi_price_aligned(t0, t1, level_count=3)
        self.assertEqual(aligned.value, 1.0)
        self.assertEqual(t1["book_state_valid"], True)

    def test_engine_projection_consumed_by_default_legacy_method(self) -> None:
        """Legacy consumers keep working unchanged on canonical projections."""
        book = IncrementalOrderBook("TEST")
        book.apply(ev(operation=DepthOperation.RESET))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="100", size="10"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.BID, price="99", size="5"))
        book.apply(ev(operation=DepthOperation.INSERT, side=DepthSide.ASK, price="101", size="7"))
        t0 = project_book_snapshot(book)
        book.apply(ev(operation=DepthOperation.UPDATE, side=DepthSide.BID, price="100", size="12"))
        t1 = project_book_snapshot(book)
        legacy = compute_ofi(t0, t1)  # default rank-based method still valid
        self.assertTrue(legacy.book_state_valid)
        self.assertIsNotNone(legacy.value)


if __name__ == "__main__":
    unittest.main()
