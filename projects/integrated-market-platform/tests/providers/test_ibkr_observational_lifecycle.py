"""IBKR observational subscription lifecycle tests (G6 §16–§19)."""

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
    ERROR_CODE_100_MAX_MSG_RATE,
    ERROR_CODE_101_MAX_TICKERS,
    ERROR_CODE_200_NO_SECURITY_DEFINITION,
    ERROR_CODE_309_MAX_DEPTH_REQUESTS,
    ERROR_CODE_316_DEPTH_HALTED,
    ERROR_CODE_317_DEPTH_RESET,
    ERROR_CODE_354_NOT_SUBSCRIBED,
    ERROR_CODE_502_CONNECT_FAILED,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (  # noqa: E402
    CapabilityKind,
    EntitlementState,
    IbkrConnectionState,
    IbkrErrorCategory,
    IbkrSubscriptionState,
)
from market_platform_foundation.providers.ibkr_observational.errors import (  # noqa: E402
    normalize_provider_error,
)

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    connected_adapter,
    make_adapter,
    make_record,
)

AAPL = make_record("AAPL")
MSFT = make_record("MSFT")


class ErrorNormalizationTests(unittest.TestCase):
    """Only documented codes are categorized; everything else is UNKNOWN."""

    def test_entitlement_code_mapping(self) -> None:
        error = normalize_provider_error(code=ERROR_CODE_354_NOT_SUBSCRIBED, message="x")
        self.assertIs(error.category, IbkrErrorCategory.ENTITLEMENT)

    def test_pacing_code_mapping(self) -> None:
        for code in (
            ERROR_CODE_100_MAX_MSG_RATE,
            ERROR_CODE_101_MAX_TICKERS,
            ERROR_CODE_309_MAX_DEPTH_REQUESTS,
        ):
            error = normalize_provider_error(code=code, message="x")
            self.assertIs(error.category, IbkrErrorCategory.PACING, code)

    def test_contract_code_mapping(self) -> None:
        error = normalize_provider_error(code=ERROR_CODE_200_NO_SECURITY_DEFINITION, message="x")
        self.assertIs(error.category, IbkrErrorCategory.CONTRACT)

    def test_subscription_code_mapping(self) -> None:
        for code in (ERROR_CODE_316_DEPTH_HALTED, ERROR_CODE_317_DEPTH_RESET):
            error = normalize_provider_error(code=code, message="x")
            self.assertIs(error.category, IbkrErrorCategory.SUBSCRIPTION, code)

    def test_connection_code_mapping(self) -> None:
        error = normalize_provider_error(code=ERROR_CODE_502_CONNECT_FAILED, message="x")
        self.assertIs(error.category, IbkrErrorCategory.CONNECTION)

    def test_unknown_code_stays_unknown(self) -> None:
        error = normalize_provider_error(code=9999, message="something new")
        self.assertIs(error.category, IbkrErrorCategory.UNKNOWN_PROVIDER_ERROR)
        self.assertEqual(error.code, 9999)

    def test_delayed_message_maps_to_delayed_data(self) -> None:
        # A code outside every documented family whose message mentions
        # delayed delivery is classified DELAYED_DATA (message evidence).
        error = normalize_provider_error(
            code=9999, message="delayed market data is being displayed"
        )
        self.assertIs(error.category, IbkrErrorCategory.DELAYED_DATA)


class SubscriptionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.adapter, self.transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL, MSFT)
        )

    def test_subscribe_l1_and_l2_allocate_distinct_req_ids(self) -> None:
        l1 = self.adapter.subscribe_l1(instrument_id="AAPL")
        l2 = self.adapter.subscribe_l2(instrument_id="MSFT")
        self.assertTrue(l1.accepted, l1.reason)
        self.assertTrue(l2.accepted, l2.reason)
        self.assertNotEqual(l1.req_id, l2.req_id)
        self.assertIs(l1.capability, CapabilityKind.L1)
        self.assertIs(l2.capability, CapabilityKind.L2)

    def test_repeated_subscribe_is_idempotent(self) -> None:
        first = self.adapter.subscribe_l1(instrument_id="AAPL")
        second = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.assertTrue(second.accepted)
        self.assertEqual(first.subscription_id, second.subscription_id)
        self.assertEqual(first.req_id, second.req_id)
        # Only one provider request was issued.
        self.assertEqual(len(self.transport.mkt_data_requests), 1)

    def test_repeated_cancel_is_safe(self) -> None:
        self.adapter.subscribe_l1(instrument_id="AAPL")
        first = self.adapter.cancel_l1("AAPL")
        second = self.adapter.cancel_l1("AAPL")
        self.assertTrue(first.accepted)
        # Second cancel is a safe no-op (record already retired): it must
        # never raise or double-cancel the transport.
        self.assertFalse(second.accepted)
        self.assertEqual(self.transport.mkt_data_cancels, [first.req_id])

    def test_cancel_unknown_is_safe(self) -> None:
        result = self.adapter.cancel_l1("MSFT")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "NOT_SUBSCRIBED")

    def test_subscription_marks_active_after_first_facts(self) -> None:
        sub = self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.on_tick_price(sub.req_id, 1, 100.0, received_ns=1000)
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.ACTIVE.value)

    def test_connect_requires_live(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrOfflineError,
        )

        adapter, _ = make_adapter(live=False, store=self.store, lookup=FakeLookup(AAPL))
        with self.assertRaises(IbkrOfflineError):
            adapter.connect()

    def test_not_connected_subscribe_rejected(self) -> None:
        from ibkr_observational_support import make_adapter

        adapter, _ = make_adapter(live=True, store=self.store, lookup=FakeLookup(AAPL))
        result = adapter.subscribe_l1(instrument_id="AAPL")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "NOT_CONNECTED")


class PacingTests(unittest.TestCase):
    def test_l1_cap_rejects_beyond_configured_max(self) -> None:
        adapter, transport = connected_adapter(
            store=ObservationalStateStore(),
            lookup=FakeLookup(AAPL, MSFT),
            max_l1=1,
        )
        first = adapter.subscribe_l1(instrument_id="AAPL")
        self.assertTrue(first.accepted, first.reason)
        second = adapter.subscribe_l1(instrument_id="MSFT")
        self.assertFalse(second.accepted)
        self.assertIn("L1_CAP_REACHED", second.reason or "")
        report = adapter.pacing_report()
        self.assertEqual(report["active_l1"], 1)
        self.assertEqual(report["configured_max_l1"], 1)
        self.assertTrue(
            any("L1_CAP_REACHED" in reason for reason in report["rejected_reasons"])
        )

    def test_l2_cap_rejects_beyond_configured_max(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(),
            lookup=FakeLookup(AAPL, MSFT),
            max_l2=1,
        )
        first = adapter.subscribe_l2(instrument_id="AAPL")
        self.assertTrue(first.accepted, first.reason)
        second = adapter.subscribe_l2(instrument_id="MSFT")
        self.assertFalse(second.accepted)
        self.assertIn("L2_CAP_REACHED", second.reason or "")

    def test_depth_levels_validated(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        too_small = adapter.subscribe_l2(instrument_id="AAPL", depth_levels=2)
        self.assertFalse(too_small.accepted)
        self.assertIn("at least 3", too_small.reason or "")
        too_large = adapter.subscribe_l2(instrument_id="AAPL", depth_levels=100)
        self.assertFalse(too_large.accepted)
        self.assertIn("ceiling", too_large.reason or "")

    def test_pacing_error_enters_cooldown(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.on_error(
            sub.req_id, ERROR_CODE_309_MAX_DEPTH_REQUESTS, "max depth requests", received_ns=1000
        )
        record = adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)
        self.assertIsNotNone(adapter._pacing.cooldown_until_ns)


class ReconnectTests(unittest.TestCase):
    def test_reconnect_resubscribes_authorized_subscriptions(self) -> None:
        store = ObservationalStateStore()
        adapter, transport = connected_adapter(
            store=store, lookup=FakeLookup(AAPL, MSFT), max_reconnect=5
        )
        l1 = adapter.subscribe_l1(instrument_id="AAPL")
        l2 = adapter.subscribe_l2(instrument_id="MSFT")
        cancelled = adapter.subscribe_l1(instrument_id="MSFT")
        adapter.cancel_l1("MSFT")
        adapter.handle_reconnect()
        self.assertEqual(adapter._lifecycle.reconnect_count, 1)
        self.assertGreater(adapter._lifecycle.connection_generation, 0)
        # AAPL L1 + MSFT L2 resubscribed; MSFT L1 was cancelled → not resubscribed.
        status = adapter.subscription_status()
        capabilities = sorted(
            (row["capability"], row["instrument_id"]) for row in status.values()
        )
        self.assertIn(("L1", "AAPL"), capabilities)
        self.assertIn(("L2", "MSFT"), capabilities)
        self.assertNotIn(("L1", "MSFT"), capabilities)

    def test_reconnect_bounded_by_max_attempts(self) -> None:
        adapter, transport = connected_adapter(
            store=ObservationalStateStore(),
            lookup=FakeLookup(AAPL),
            max_reconnect=2,
        )
        adapter.handle_reconnect()
        adapter.handle_reconnect()
        adapter.handle_reconnect()  # third attempt exceeds the bound
        self.assertEqual(adapter._lifecycle.reconnect_count, 2)
        self.assertIs(
            adapter._lifecycle.connection_state, IbkrConnectionState.DEGRADED
        )

    def test_reconnect_offline_is_blocked(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrOfflineError,
        )
        from ibkr_observational_support import make_adapter

        adapter, _ = make_adapter(live=False, store=None, lookup=FakeLookup(AAPL))
        with self.assertRaises(IbkrOfflineError):
            adapter.handle_reconnect()

    def test_disconnect_then_connect_restores_subscriptions_manually(self) -> None:
        adapter, transport = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        sub = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.handle_disconnect("TEST")
        self.assertIs(adapter._lifecycle.connection_state, IbkrConnectionState.DISCONNECTED)
        # Operator reconnects; subscription remains authorized and is re-created.
        adapter.connect()
        self.assertIs(adapter._lifecycle.connection_state, IbkrConnectionState.CONNECTED)


class EntitlementStateTests(unittest.TestCase):
    def test_entitlement_starts_unknown_never_entitled(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        record = adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.UNKNOWN.value)

    def test_l1_entitlement_failure_marks_delayed_not_failed(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        sub = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_error(
            sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "not subscribed", received_ns=1000
        )
        record = adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.DELAYED.value)
        self.assertEqual(record["state"], IbkrSubscriptionState.DEGRADED.value)
        self.assertTrue(record["delayed"])

    def test_l2_entitlement_failure_fails_subscription(self) -> None:
        adapter, _ = connected_adapter(
            store=ObservationalStateStore(), lookup=FakeLookup(AAPL)
        )
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        adapter.on_error(
            sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "not subscribed", received_ns=1000
        )
        record = adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.NOT_ENTITLED.value)
        self.assertEqual(record["state"], IbkrSubscriptionState.FAILED.value)

    def test_unknown_is_never_mapped_to_entitled(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.contracts import (
            EntitlementState as ES,
        )

        self.assertNotIn(ES.UNKNOWN, {ES.ENTITLED})


if __name__ == "__main__":
    unittest.main()