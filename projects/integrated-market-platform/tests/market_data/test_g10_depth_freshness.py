"""G10 depth TTL / runtime admissibility tests (BL-0303)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.depth_admission import (
    DepthAdmissionContext,
    DepthAdmissibilityStatus,
    evaluate_depth_admissibility,
)
from market_platform_foundation.market_data.live_config import depth_freshness_policy
from market_platform_foundation.market_data.observational_lanes import ObservationalLaneRuntime
from market_platform_foundation.market_data.observational_state import ObservationalStateStore
from market_platform_foundation.order_flow.order_book.contracts import (
    DepthOperation,
    DepthSide,
    FreshnessStatus,
    build_depth_update,
)
from market_platform_foundation.order_flow.order_book.engine import IncrementalOrderBook
from market_platform_foundation.order_flow.order_book.freshness import FreshnessPolicy
from market_platform_foundation.providers.runtime_capability import EntitlementState, ProviderHealth

NS = 1_000_000_000
POLICY = FreshnessPolicy(stale_after_ns=5 * NS, name="g10-test")


def _fresh_book(now: int = 1_000 * NS, instrument_id: str = "AAPL") -> IncrementalOrderBook:
    book = IncrementalOrderBook(instrument_id)
    book.apply(
        build_depth_update(
            instrument_id=instrument_id,
            operation=DepthOperation.RESET,
            received_time_ns=now - 100,
        )
    )
    book.apply(
        build_depth_update(
            instrument_id=instrument_id,
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price="100",
            size="5",
            received_time_ns=now - 50,
        )
    )
    book.apply(
        build_depth_update(
            instrument_id=instrument_id,
            operation=DepthOperation.INSERT,
            side=DepthSide.ASK,
            price="101",
            size="5",
            received_time_ns=now - 25,
        )
    )
    return book


class G10DepthFreshnessTests(unittest.TestCase):
    def test_fresh(self) -> None:
        book = _fresh_book()
        result = evaluate_depth_admissibility(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertTrue(result.admissible)
        self.assertEqual(result.freshness_status, FreshnessStatus.FRESH)

    def test_exactly_at_threshold_is_fresh(self) -> None:
        book = IncrementalOrderBook("AAPL")
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.RESET,
                received_time_ns=0,
            )
        )
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="1",
                received_time_ns=0,
            )
        )
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.ASK,
                price="101",
                size="1",
                received_time_ns=0,
            )
        )
        result = evaluate_depth_admissibility(book, as_of_time_ns=5 * NS, policy=POLICY)
        self.assertTrue(result.admissible)

    def test_stale_after_threshold(self) -> None:
        book = _fresh_book(now=0)
        result = evaluate_depth_admissibility(book, as_of_time_ns=(5 * NS) + 1, policy=POLICY)
        self.assertFalse(result.admissible)
        self.assertEqual(result.status, DepthAdmissibilityStatus.STALE)

    def test_invalid_beats_stale(self) -> None:
        book = IncrementalOrderBook("AAPL")
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.RESET,
                received_time_ns=0,
            )
        )
        result = evaluate_depth_admissibility(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertEqual(result.status, DepthAdmissibilityStatus.INVALID)

    def test_unavailable_distinct_from_stale(self) -> None:
        book = IncrementalOrderBook("AAPL")
        result = evaluate_depth_admissibility(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertEqual(result.status, DepthAdmissibilityStatus.UNAVAILABLE)
        stale = evaluate_depth_admissibility(_fresh_book(now=0), as_of_time_ns=(5 * NS) + 1, policy=POLICY)
        self.assertEqual(stale.status, DepthAdmissibilityStatus.STALE)
        self.assertNotEqual(result.status, stale.status)

    def test_not_entitled_beats_fresh(self) -> None:
        book = _fresh_book()
        result = evaluate_depth_admissibility(
            book,
            as_of_time_ns=1_000 * NS,
            policy=POLICY,
            context=DepthAdmissionContext(entitlement=EntitlementState.NOT_ENTITLED),
        )
        self.assertEqual(result.status, DepthAdmissibilityStatus.NOT_ENTITLED)

    def test_disconnected_provider_beats_fresh(self) -> None:
        book = _fresh_book()
        result = evaluate_depth_admissibility(
            book,
            as_of_time_ns=1_000 * NS,
            policy=POLICY,
            context=DepthAdmissionContext(
                provider_connected=False,
                provider_health=ProviderHealth.DOWN,
            ),
        )
        self.assertEqual(result.status, DepthAdmissibilityStatus.PROVIDER_UNAVAILABLE)

    def test_reconnect_generation_reset_in_context(self) -> None:
        book = _fresh_book()
        result = evaluate_depth_admissibility(
            book,
            as_of_time_ns=1_000 * NS,
            policy=POLICY,
            context=DepthAdmissionContext(generation=2),
        )
        self.assertEqual(result.generation, 2)

    def test_replay_same_state_same_as_of_same_freshness(self) -> None:
        book = _fresh_book()
        first = evaluate_depth_admissibility(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        second = evaluate_depth_admissibility(book, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_two_instruments_independent(self) -> None:
        aapl = _fresh_book()
        msft = IncrementalOrderBook("MSFT")
        msft.apply(
            build_depth_update(
                instrument_id="MSFT",
                operation=DepthOperation.RESET,
                received_time_ns=0,
            )
        )
        aapl_result = evaluate_depth_admissibility(aapl, as_of_time_ns=1_000 * NS, policy=POLICY)
        msft_result = evaluate_depth_admissibility(msft, as_of_time_ns=1_000 * NS, policy=POLICY)
        self.assertTrue(aapl_result.admissible)
        self.assertFalse(msft_result.admissible)

    def test_two_providers_independent_policies(self) -> None:
        ibkr_policy = depth_freshness_policy("ibkr.observational")
        moomoo_policy = depth_freshness_policy("moomoo")
        self.assertNotEqual(ibkr_policy.name, moomoo_policy.name)

    def test_stale_depth_blocks_authoritative_ofi(self) -> None:
        store = ObservationalStateStore()
        book = _fresh_book(now=0)
        for event in (
            build_depth_update(instrument_id="AAPL", operation=DepthOperation.RESET, received_time_ns=0),
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="5",
                received_time_ns=0,
            ),
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.ASK,
                price="101",
                size="5",
                received_time_ns=0,
            ),
        ):
            store.apply_depth_update(event)
        lanes = ObservationalLaneRuntime(store)
        lanes.configure_depth_context(as_of_time_ns=(5 * NS) + 1)
        payload = lanes.build_ofi_payload("AAPL")
        self.assertFalse(payload.get("available", True))
        self.assertEqual(payload.get("state"), DepthAdmissibilityStatus.STALE.value)

    def test_stale_depth_blocks_book_features(self) -> None:
        store = ObservationalStateStore()
        store.apply_depth_update(
            build_depth_update(instrument_id="AAPL", operation=DepthOperation.RESET, received_time_ns=0)
        )
        store.apply_depth_update(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="5",
                received_time_ns=0,
            )
        )
        store.apply_depth_update(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.ASK,
                price="101",
                size="5",
                received_time_ns=0,
            )
        )
        lanes = ObservationalLaneRuntime(store)
        lanes.configure_depth_context(as_of_time_ns=(5 * NS) + 1)
        payload = lanes.build_book_features_payload("AAPL")
        self.assertFalse(payload.get("available", True))


if __name__ == "__main__":
    unittest.main()
