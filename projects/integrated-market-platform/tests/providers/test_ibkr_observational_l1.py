"""IBKR L1 observational adapter tests (G6 §24 matrix).

Covers the required L1 behaviors: partial-fact accumulation without
fabrication, callback-order independence, delayed/entitlement semantics,
staleness, disconnect/reconnect generation safety, instrument isolation,
reqId mapping, and unknown-reqId rejection.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.providers.ibkr_observational.constants import (  # noqa: E402
    ERROR_CODE_354_NOT_SUBSCRIBED,
    TICK_ASK,
    TICK_ASK_SIZE,
    TICK_BID,
    TICK_BID_SIZE,
    TICK_DELAYED_BID,
    TICK_DELAYED_BID_SIZE,
    TICK_LAST,
    TICK_LAST_SIZE,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (  # noqa: E402
    EntitlementState,
    IbkrConnectionState,
    IbkrSubscriptionState,
)

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    connected_adapter,
    make_record,
)

AAPL = make_record("AAPL")
MSFT = make_record("MSFT")


class IbkrL1AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.adapter, self.transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL, MSFT)
        )
        self.result = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.assertTrue(self.result.accepted, self.result.reason)
        self.req_id = self.result.req_id

    def _quote(self, instrument_id: str = "AAPL"):
        return self.store.quote_for(instrument_id)

    # 1. bid price only → quote incomplete/not fabricated
    def test_bid_price_only_is_incomplete_not_fabricated(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        quote = self._quote()
        self.assertIsNotNone(quote)
        self.assertEqual(quote.bid_price, 100.0)
        # No side/size is invented.
        self.assertIsNone(quote.ask_price)
        self.assertIsNone(quote.bid_size)
        self.assertIsNone(quote.ask_size)

    # 2. bid + bid size
    def test_bid_and_bid_size_accumulate(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_BID_SIZE, 11.0, received_ns=1001)
        quote = self._quote()
        self.assertEqual(quote.bid_price, 100.0)
        self.assertEqual(quote.bid_size, 11.0)
        self.assertIsNone(quote.ask_price)

    # 3. ask + ask size
    def test_ask_and_ask_size_accumulate(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_ASK, 101.0, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_ASK_SIZE, 7.0, received_ns=1001)
        quote = self._quote()
        self.assertEqual(quote.ask_price, 101.0)
        self.assertEqual(quote.ask_size, 7.0)
        self.assertIsNone(quote.bid_price)

    # 4. full bid/ask quote
    def test_full_bid_ask_quote(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_BID_SIZE, 11.0, received_ns=1001)
        self.adapter.on_tick_price(self.req_id, TICK_ASK, 101.0, received_ns=1002)
        self.adapter.on_tick_size(self.req_id, TICK_ASK_SIZE, 7.0, received_ns=1003)
        quote = self._quote()
        self.assertEqual(quote.bid_price, 100.0)
        self.assertEqual(quote.ask_price, 101.0)
        self.assertEqual(quote.bid_size, 11.0)
        self.assertEqual(quote.ask_size, 7.0)

    # 5. last + last size
    def test_last_and_last_size(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_LAST, 100.5, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_LAST_SIZE, 3.0, received_ns=1001)
        quote = self._quote()
        self.assertEqual(quote.last_price, 100.5)
        self.assertEqual(quote.last_size, 3.0)

    # 6. callback order variation
    def test_callback_order_variation_yields_same_quote(self) -> None:
        # Size before price on both sides.
        self.adapter.on_tick_size(self.req_id, TICK_ASK_SIZE, 7.0, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_BID_SIZE, 11.0, received_ns=1001)
        self.adapter.on_tick_price(self.req_id, TICK_ASK, 101.0, received_ns=1002)
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1003)
        quote = self._quote()
        self.assertEqual(quote.bid_price, 100.0)
        self.assertEqual(quote.ask_price, 101.0)
        self.assertEqual(quote.bid_size, 11.0)
        self.assertEqual(quote.ask_size, 7.0)

    # 7. duplicate callback
    def test_duplicate_callback_is_stable(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1005)
        quote = self._quote()
        self.assertEqual(quote.bid_price, 100.0)
        self.assertIsNone(quote.ask_price)
        # A duplicate does not fabricate other fields.
        self.assertIsNone(quote.ask_size)

    # 8. delayed market-data state
    def test_delayed_ticks_are_labeled_delayed(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_DELAYED_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_size(self.req_id, TICK_DELAYED_BID_SIZE, 11.0, received_ns=1001)
        quote = self._quote()
        self.assertEqual(quote.bid_price, 100.0)
        self.assertEqual(quote.quality, "DELAYED")
        record = self.adapter.subscription_status()["ibkr:L1:1"]
        self.assertTrue(record["delayed"])
        self.assertEqual(record["entitlement"], EntitlementState.DELAYED.value)

    # 9. entitlement failure (delayed-data error path)
    def test_entitlement_failure_degrades_not_fabricates(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_error(
            self.req_id,
            ERROR_CODE_354_NOT_SUBSCRIBED,
            "market data is not subscribed",
            received_ns=2000,
        )
        record = self.adapter.subscription_status()["ibkr:L1:1"]
        self.assertEqual(record["entitlement"], EntitlementState.DELAYED.value)
        self.assertTrue(record["delayed"])
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)
        # The quote must not be presented as real-time.
        self.assertEqual(self._quote().quality, "DELAYED")

    # 10. stale quote
    def test_stale_quote_freshness(self) -> None:
        # received at t=1s (in ns); evaluated at t=6s → 5000ms stale.
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1_000_000_000)
        self.assertGreaterEqual(
            self.store.freshness_ms("AAPL", wall_now_ns=6_000_000_000), 5000
        )

    # 11. disconnect invalidates/degrades subscriptions
    def test_disconnect_degrades_subscriptions(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.handle_disconnect("TEST_DISCONNECT")
        self.assertEqual(
            self.adapter._lifecycle.connection_state, IbkrConnectionState.DISCONNECTED
        )
        record = self.adapter.subscription_status()["ibkr:L1:1"]
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)
        self.assertEqual(record["reason"], "CONNECTION_LOST")

    # 12. reconnect creates a new generation
    def test_reconnect_advances_generation(self) -> None:
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        old_generation = self.adapter._lifecycle.connection_generation
        self.adapter.handle_reconnect()
        self.assertGreater(
            self.adapter._lifecycle.connection_generation, old_generation
        )
        # Old subscription retired; new reqId issued.
        status = self.adapter.subscription_status()
        self.assertIn("ibkr:L1:2", status)
        self.assertEqual(len(self.transport.mkt_data_requests), 2)
        # Old reqId callbacks can no longer mutate state.
        rejected = self.adapter.on_tick_price(self.req_id, TICK_BID, 99.0, received_ns=2000)
        self.assertFalse(rejected.accepted)
        self.assertIn("unknown req_id", rejected.reason or "")

    # 13. two instruments remain isolated
    def test_two_instruments_isolated(self) -> None:
        other = self.adapter.subscribe_l1(instrument_id="MSFT")
        self.assertTrue(other.accepted, other.reason)
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_price(other.req_id, TICK_BID, 200.0, received_ns=1001)
        self.adapter.on_tick_price(other.req_id, TICK_ASK, 201.0, received_ns=1002)
        self.assertEqual(self._quote("AAPL").bid_price, 100.0)
        self.assertIsNone(self._quote("AAPL").ask_price)
        self.assertEqual(self._quote("MSFT").bid_price, 200.0)
        self.assertEqual(self._quote("MSFT").ask_price, 201.0)

    # 14. reqId maps to correct canonical instrument
    def test_req_id_maps_to_canonical_instrument(self) -> None:
        other = self.adapter.subscribe_l1(instrument_id="MSFT")
        # Callback for AAPL reqId must land on AAPL even after MSFT exists.
        self.adapter.on_tick_price(self.req_id, TICK_BID, 100.0, received_ns=1000)
        self.adapter.on_tick_price(other.req_id, TICK_ASK, 201.0, received_ns=1001)
        self.assertEqual(self._quote("AAPL").bid_price, 100.0)
        self.assertIsNone(self._quote("AAPL").ask_price)
        self.assertIsNone(self._quote("MSFT").bid_price)
        self.assertEqual(self._quote("MSFT").ask_price, 201.0)

    # 15. unknown reqId rejected/logged explicitly
    def test_unknown_req_id_rejected(self) -> None:
        rejected = self.adapter.on_tick_price(999999, TICK_BID, 100.0, received_ns=1000)
        self.assertFalse(rejected.accepted)
        self.assertIn("unknown req_id", rejected.reason or "")
        # No state was touched.
        self.assertIsNone(self._quote())


if __name__ == "__main__":
    unittest.main()