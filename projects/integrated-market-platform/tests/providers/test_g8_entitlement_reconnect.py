"""G8 entitlement / reconnect lifecycle tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.constants import (
    ERROR_CODE_1100_CONNECTIVITY_LOST,
    ERROR_CODE_1101_RESTORED_DATA_LOST,
    ERROR_CODE_1102_RESTORED_DATA_MAINTAINED,
    ERROR_CODE_316_DEPTH_HALTED,
    ERROR_CODE_317_DEPTH_RESET,
    ERROR_CODE_354_NOT_SUBSCRIBED,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (
    EntitlementState,
    IbkrSubscriptionState,
)

from ibkr_observational_support import FakeLookup, connected_adapter, make_record


AAPL = make_record("AAPL")


class G8EntitlementReconnectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter, self.transport = connected_adapter(lookup=FakeLookup(AAPL))

    def test_entitlement_unknown_before_evidence(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.UNKNOWN.value)

    def test_realtime_entitlement_only_after_evidence(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_tick_price(sub.req_id, 1, 100.0)
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertIn(record["entitlement"], {EntitlementState.UNKNOWN.value, EntitlementState.ENTITLED.value})

    def test_delayed_preserved(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "delayed")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.DELAYED.value)

    def test_not_entitled_explicit_l2(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "no depth")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.NOT_ENTITLED.value)

    def test_l2_book_reset_on_entitlement_failure(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        self.adapter.on_error(sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "no depth")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.FAILED.value)

    def test_error_317_causes_reset(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, ERROR_CODE_317_DEPTH_RESET, "reset")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.SUBSCRIBING.value)

    def test_error_316_degrades_safely(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, ERROR_CODE_316_DEPTH_HALTED, "halted")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)

    def test_pacing_error_degrades(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, 100, "max rate")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)

    def test_1100_disconnect_state(self) -> None:
        self.adapter.on_error(None, ERROR_CODE_1100_CONNECTIVITY_LOST, "lost")
        self.assertEqual(self.adapter.diagnostics()["connection_state"], "DISCONNECTED")

    def test_1101_reconnect_requires_resubscribe(self) -> None:
        first = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_error(None, ERROR_CODE_1101_RESTORED_DATA_LOST, "lost")
        statuses = self.adapter.subscription_status()
        self.assertTrue(any(row["req_id"] != first.req_id for row in statuses.values()))

    def test_1102_maintained_data_semantics(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_error(None, ERROR_CODE_1102_RESTORED_DATA_MAINTAINED, "ok")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["req_id"], sub.req_id)

    def test_old_req_id_rejected(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.handle_reconnect()
        result = self.adapter.on_mkt_depth(sub.req_id, 0, 0, 1, 100.0, 10.0)
        self.assertFalse(result.accepted)

    def test_new_generation_applied(self) -> None:
        before = self.adapter.diagnostics()["connection_generation"]
        self.adapter.handle_reconnect()
        after = self.adapter.diagnostics()["connection_generation"]
        self.assertGreater(after, before)

    def test_repeated_cancel_safe(self) -> None:
        self.adapter.subscribe_l1(instrument_id="AAPL")
        first = self.adapter.cancel_l1("AAPL")
        second = self.adapter.cancel_l1("AAPL")
        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)

    def test_no_retry_recursion_in_reconnect(self) -> None:
        for _ in range(5):
            self.adapter.handle_reconnect()
        self.assertLessEqual(self.adapter.diagnostics()["reconnect_count"], 3)


if __name__ == "__main__":
    unittest.main()
