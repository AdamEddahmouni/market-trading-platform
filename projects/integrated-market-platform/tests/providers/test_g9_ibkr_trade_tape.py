"""G9 IBKR tick-by-tick trade tape — mapping, classification, replay, entitlement."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import build_replay_composition
from market_platform_foundation.providers.ibkr_observational.adapter import IbkrOfflineError
from market_platform_foundation.providers.ibkr_observational.capture import replay_records
from market_platform_foundation.providers.ibkr_observational.constants import (
    ERROR_CODE_354_NOT_SUBSCRIBED,
    TICK_BID,
    TICK_ASK,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (
    CapabilityKind,
    EntitlementState,
)
from market_platform_foundation.providers.ibkr_observational.trades import (
    QuoteContext,
    classify_trade_print,
    facts_from_tick_by_tick_all_last,
    replay_dedup_key,
)

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_adapter, make_record


AAPL = make_record("AAPL")


class G9TradeMappingTests(unittest.TestCase):
    def test_subscribe_trades_uses_tick_by_tick_transport(self) -> None:
        composition = build_replay_composition(transport=FakeTransport(), lookup=FakeLookup(AAPL))
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        result = adapter.subscribe_trades(instrument_id="AAPL")
        self.assertTrue(result.accepted)
        self.assertEqual(len(transport.tick_by_tick_requests), 1)
        self.assertEqual(transport.mkt_data_requests, [])

    def test_offline_gate_blocks_tick_by_tick(self) -> None:
        adapter, transport = make_adapter(live=False, lookup=FakeLookup(AAPL))
        with self.assertRaises(IbkrOfflineError):
            adapter.subscribe_trades(instrument_id="AAPL")
        self.assertEqual(transport.tick_by_tick_requests, [])

    def test_cancel_trades_cancels_transport(self) -> None:
        adapter, transport = connected_adapter(lookup=FakeLookup(AAPL))
        adapter.subscribe_trades(instrument_id="AAPL")
        req_id = transport.tick_by_tick_requests[0][0]
        adapter.cancel_trades("AAPL")
        self.assertIn(req_id, transport.tick_by_tick_cancels)


class G9TradeClassificationTests(unittest.TestCase):
    def test_inferred_buy_at_ask(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s1",
            req_id=1,
            generation=1,
            price=101.0,
            size=10.0,
            source_time_ns=1_000_000_000,
            received_time_ns=1_100_000_000,
        )
        quote = QuoteContext(bid=100.0, ask=101.0, provider="IBKR", received_ns=1_000_000_000, quality="PASS")
        trade, kind, reason = classify_trade_print(facts, quote=quote, provider="IBKR")
        self.assertEqual(kind.value, "INFERRED")
        self.assertEqual(trade.aggressor_side.value.upper(), "BUY")
        self.assertGreater(trade.signed_volume, 0)

    def test_inferred_sell_at_bid(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s1",
            req_id=1,
            generation=1,
            price=100.0,
            size=5.0,
            source_time_ns=2_000_000_000,
            received_time_ns=2_100_000_000,
        )
        quote = QuoteContext(bid=100.0, ask=101.0, provider="IBKR", received_ns=2_000_000_000, quality="PASS")
        trade, kind, _ = classify_trade_print(facts, quote=quote, provider="IBKR")
        self.assertEqual(kind.value, "INFERRED")
        self.assertEqual(trade.aggressor_side.value.upper(), "SELL")
        self.assertLess(trade.signed_volume, 0)

    def test_unknown_without_quote(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s1",
            req_id=1,
            generation=1,
            price=100.0,
            size=1.0,
            source_time_ns=None,
            received_time_ns=3_000_000_000,
        )
        trade, kind, reason = classify_trade_print(facts, quote=None, provider="IBKR")
        self.assertEqual(kind.value, "UNKNOWN")
        self.assertEqual(trade.aggressor_side.value.upper(), "UNKNOWN")
        self.assertEqual(trade.signed_volume, 0.0)
        self.assertEqual(reason, "MISSING_QUOTE_CONTEXT")

    def test_stale_quote_yields_unknown(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s1",
            req_id=1,
            generation=1,
            price=100.5,
            size=2.0,
            source_time_ns=10_000_000_000,
            received_time_ns=20_000_000_000,
        )
        quote = QuoteContext(bid=100.0, ask=101.0, provider="IBKR", received_ns=1_000_000_000, quality="PASS")
        trade, kind, reason = classify_trade_print(facts, quote=quote, provider="IBKR", stale_after_ms=1000)
        self.assertEqual(kind.value, "UNKNOWN")
        self.assertEqual(reason, "QUOTE_STALE")

    def test_provider_mismatch_fails_closed(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s1",
            req_id=1,
            generation=1,
            price=100.5,
            size=2.0,
            source_time_ns=10_000_000_000,
            received_time_ns=10_100_000_000,
        )
        quote = QuoteContext(bid=100.0, ask=101.0, provider="MOOMOO", received_ns=10_000_000_000, quality="PASS")
        _, kind, reason = classify_trade_print(facts, quote=quote, provider="IBKR")
        self.assertEqual(kind.value, "UNKNOWN")
        self.assertEqual(reason, "PROVIDER_MISMATCH")

    def test_replay_dedup_key_not_provider_event_id(self) -> None:
        key = replay_dedup_key(req_id=7, source_time_ns=1, price=1.0, size=1.0, exchange="NASDAQ")
        self.assertTrue(key.startswith("ibkr:tbt:"))


class G9TradeRuntimeTests(unittest.TestCase):
    def _seed_l1(self, adapter, transport, *, bid: float = 100.0, ask: float = 101.0) -> None:
        sub = adapter.subscribe_l1(instrument_id="AAPL")
        req_id = transport.mkt_data_requests[0][0]
        adapter.on_tick_price(req_id, TICK_BID, bid)
        adapter.on_tick_price(req_id, TICK_ASK, ask)

    def test_trade_print_updates_store_and_cvd(self) -> None:
        composition = build_replay_composition(transport=FakeTransport(), lookup=FakeLookup(AAPL))
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        self._seed_l1(adapter, transport)
        trade_sub = adapter.subscribe_trades(instrument_id="AAPL")
        req_id = transport.tick_by_tick_requests[0][0]
        adapter.on_tick_by_tick_all_last(req_id, 2, 101.0, 10.0, source_time_ns=5_000_000_000)
        trades = composition.store.trades_for("AAPL")
        self.assertEqual(len(trades), 1)
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))

    def test_duplicate_trade_deduped(self) -> None:
        composition = build_replay_composition(transport=FakeTransport(), lookup=FakeLookup(AAPL))
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        self._seed_l1(adapter, transport)
        adapter.subscribe_trades(instrument_id="AAPL")
        req_id = transport.tick_by_tick_requests[0][0]
        adapter.on_tick_by_tick_all_last(req_id, 2, 101.0, 10.0, source_time_ns=6_000_000_000)
        adapter.on_tick_by_tick_all_last(req_id, 2, 101.0, 10.0, source_time_ns=6_000_000_000)
        self.assertEqual(len(composition.store.trades_for("AAPL")), 1)

    def test_capture_replay_deterministic_cvd(self) -> None:
        composition = build_replay_composition(transport=FakeTransport(), lookup=FakeLookup(AAPL))
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        self._seed_l1(adapter, transport)
        sub = adapter.register_replay_subscription(
            instrument_id="AAPL", capability=CapabilityKind.TRADES, req_id=9001
        )
        adapter.on_tick_by_tick_all_last(sub.req_id, 2, 101.0, 4.0, source_time_ns=7_000_000_000, received_ns=7_100_000_000)
        records = adapter.capture_records()
        composition2 = build_replay_composition(transport=FakeTransport(), lookup=FakeLookup(AAPL))
        adapter2, _ = connected_adapter(store=composition2.store, lookup=FakeLookup(AAPL))
        adapter2.register_replay_subscription(
            instrument_id="AAPL", capability=CapabilityKind.TRADES, req_id=9001
        )
        adapter2.register_replay_subscription(
            instrument_id="AAPL", capability=CapabilityKind.L1, req_id=9002
        )
        adapter2.on_tick_price(9002, TICK_BID, 100.0, received_ns=7_000_000_000)
        adapter2.on_tick_price(9002, TICK_ASK, 101.0, received_ns=7_000_000_000)
        replay_records(records, dispatch=adapter2.on_captured_record)
        a = composition.lanes.build_cvd_payload("AAPL")
        b = composition2.lanes.build_cvd_payload("AAPL")
        self.assertEqual(a.get("cvd"), b.get("cvd"))


class G9EntitlementReadinessTests(unittest.TestCase):
    def test_trades_readiness_before_subscription(self) -> None:
        adapter, _ = connected_adapter(lookup=FakeLookup(AAPL))
        readiness = adapter.readiness()
        self.assertIn("TRADES", readiness["capability_readiness"])

    def test_trades_entitlement_delayed_on_354(self) -> None:
        adapter, transport = connected_adapter(lookup=FakeLookup(AAPL))
        sub = adapter.subscribe_trades(instrument_id="AAPL")
        adapter.on_error(sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "delayed")
        record = adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.DELAYED.value)


if __name__ == "__main__":
    unittest.main()
