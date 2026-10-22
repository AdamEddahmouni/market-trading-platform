from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.bounded_queue import BoundedIngestQueue
from market_platform_foundation.market_data.capability_registry import VerifiedCapabilityRegistry
from market_platform_foundation.market_data.execution_event_buffer import LiveExecutionEventBuffer
from market_platform_foundation.market_data.internal_simulation_gate import evaluate_internal_simulation_gates
from market_platform_foundation.market_data.live_admission import ADMISSION_EXECUTION, LiveAdmissionEngine
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime

FIXTURE = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"
LIVE_CAPTURE = ROOT / "evidence/market_data/moomoo/captured-aapl-live.jsonl"
PROBE = ROOT / "evidence/market_data/moomoo/capability-report.json"


class CapabilityRegistryTests(unittest.TestCase):
    def test_probe_report_loads_without_inferring_from_config(self) -> None:
        registry = VerifiedCapabilityRegistry.from_probe_file(PROBE, moomoo_configured=True)
        self.assertTrue(registry.capabilities)
        self.assertIsNotNone(registry.verified_at)
        l1 = registry.get("US_EQUITY_L1")
        self.assertIsNotNone(l1)

    def test_stale_probe_zeroes_entitlement(self) -> None:
        registry = VerifiedCapabilityRegistry.from_probe_file(PROBE, max_staleness_seconds=0)
        self.assertTrue(registry.is_stale)
        l1 = registry.get("US_EQUITY_L1")
        assert l1 is not None
        self.assertFalse(l1.account_entitled)


class BoundedQueueTests(unittest.TestCase):
    def test_overflow_is_explicit(self) -> None:
        queue: BoundedIngestQueue[dict[str, str]] = BoundedIngestQueue(max_size=2)
        self.assertTrue(queue.enqueue({"id": "1"}))
        self.assertTrue(queue.enqueue({"id": "2"}))
        self.assertFalse(queue.enqueue({"id": "3"}))
        metrics = queue.metrics()
        self.assertEqual(metrics["events_dropped"], 1)
        self.assertEqual(metrics["queue_overflows"], 1)


class ExecutionBufferTests(unittest.TestCase):
    def test_execution_buffer_uses_available_time(self) -> None:
        buffer = LiveExecutionEventBuffer()
        engine = LiveAdmissionEngine()
        record = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 200},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"bid_price": 1, "ask_price": 2, "bid_vol": 1, "ask_vol": 1, "last_price": 1.5},
            "sequence": 1,
        }
        result = engine.evaluate_record(record, wall_now_ns=250)
        self.assertEqual(result["admission"]["execution"], ADMISSION_EXECUTION)
        buffer.append_admitted(result, provider_generation=1)
        bars = buffer.bars_for_execution(observation_time_ns=200, price_scale=4, instrument_id="AAPL")
        self.assertEqual(len(bars), 1)
        self.assertIn("bar_payload", bars[0])
        late = buffer.bars_for_execution(observation_time_ns=150, price_scale=4, instrument_id="AAPL")
        self.assertEqual(len(late), 0)


class InternalSimulationGateTests(unittest.TestCase):
    def test_gate_deferred_without_env(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        with mock.patch.dict(os.environ, {"IMP_PAPER_EXECUTION": "0", "IMP_LIVE_INTERNAL_SIMULATION": "0"}):
            gate = evaluate_internal_simulation_gates(runtime=runtime, probe_stale=False)
        self.assertEqual(gate.status, "DEFERRED_FOR_SAFETY")
        self.assertIn("PAPER_EXECUTION_GATE", gate.blocking)


class LiveCaptureReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_live_runtime()

    def tearDown(self) -> None:
        reset_live_runtime()

    @unittest.skipUnless(LIVE_CAPTURE.is_file(), "live capture fixture missing")
    def test_real_capture_replay_equivalence(self) -> None:
        runtime_a = LiveObservationalRuntime()
        runtime_b = LiveObservationalRuntime()
        count_a = runtime_a.feed_fixture_path(LIVE_CAPTURE)
        count_b = runtime_b.feed_fixture_path(LIVE_CAPTURE)
        self.assertEqual(count_a, count_b)
        self.assertGreater(count_a, 0)
        self.assertEqual(
            runtime_a.state.metrics["events_admitted"],
            runtime_b.state.metrics["events_admitted"],
        )


class LiveMarkTests(unittest.TestCase):
    def test_fixture_quote_produces_moomoo_mark(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        mark = runtime.live_mark_for("AAPL")
        self.assertIsNotNone(mark)
        assert mark is not None
        self.assertEqual(mark["mark_provider"], "MOOMOO")
        runtime.simulate_disconnect()
        stale = runtime.live_mark_for("AAPL")
        assert stale is not None
        self.assertEqual(stale["mark_quality"], "DISCONNECTED")

    def test_paper_unrealized_inherits_mark_quality(self) -> None:
        from market_platform_foundation.paper.ledger import PaperExecutionLedger

        ledger = PaperExecutionLedger.open_session(
            replay_session_id="live-mark",
            instrument_id="AAPL",
            symbol="AAPL",
            data_mode="LIVE_OBSERVATIONAL",
            data_provider="MOOMOO",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        ledger._append = ledger._append  # keep type checkers quiet
        fill = {
            "fill_id": "f1",
            "order_id": "o1",
            "fill_quantity": 1,
            "fill_price_minor": 1901000,
            "direction": "long",
            "instrument_id": "AAPL",
        }
        ledger.append_fill(fill, order={"order_id": "o1"})
        ledger.apply_live_mark(
            mark_minor=1910000,
            mark_provider="MOOMOO",
            mark_as_of_ns=250,
            mark_quality="STALE",
        )
        positions = ledger.project_positions()
        self.assertEqual(positions[0]["mark_quality"], "STALE")
        self.assertEqual(positions[0]["average_fill_minor"], 1901000)
        self.assertNotEqual(positions[0]["mark_minor"], positions[0]["average_fill_minor"])


class MoomooSafetyRegressionTests(unittest.TestCase):
    def test_moomoo_modules_have_no_trade_context(self) -> None:
        from tools.moomoo.probe import FORBIDDEN_TRADE_NAMES

        modules = [
            ROOT / "src/market_platform_foundation/market_data/live_runtime.py",
            ROOT / "tools/moomoo/push_feed.py",
            ROOT / "tools/moomoo/opend_quote_transport.py",
        ]
        for path in modules:
            source = path.read_text(encoding="utf-8")
            for name in FORBIDDEN_TRADE_NAMES:
                if name.startswith("Open") and "Trade" in name:
                    self.assertNotIn(name, source)

    def test_check_live_environment_reports_unreachable_opend(self) -> None:
        from tools.moomoo.check_live_environment import run_check

        report = run_check(host="127.0.0.1", port=59999)
        self.assertFalse(report["ready_for_live_observational"])
        self.assertIn(
            report.get("status"),
            {"PORT_UNREACHABLE", "OPEN_D_NOT_RUNNING", "OPEN_D_NOT_INSTALLED"},
        )


class OpenDStartupRecoveryTests(unittest.TestCase):
    def test_unreachable_opend_at_startup_still_starts_the_reconnecting_feed(self) -> None:
        # OpenD down (or not yet accepting) when the API starts must not leave the runtime dead until a
        # restart: the push feed's connection loop owns retry/backoff and connects once OpenD is up.
        env = {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1", "IMP_IBKR_LIVE": "0"}
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch("market_platform_foundation.market_data.live_runtime.opend_reachable", return_value=False), \
                mock.patch.object(LiveObservationalRuntime, "_start_moomoo_push_feed") as start_feed:
            runtime = LiveObservationalRuntime()
            runtime.configure()
        start_feed.assert_called_once_with()
        self.assertEqual(str(getattr(runtime.lifecycle.connection_state, "value", runtime.lifecycle.connection_state)),
                         "DISCONNECTED")
        self.assertIn("OpenD is not reachable", runtime.lifecycle.last_error or "")


class CrossThreadIngestTests(unittest.TestCase):
    def test_quote_enqueued_on_callback_thread_reaches_state_through_processor_thread(self) -> None:
        # Regression: RT-01 queue/receive spans bound a contextvar on the OpenD callback thread and
        # reset it on the processor thread; the ValueError was swallowed by the queue worker and every
        # live quote was dropped before ingestion (grid stuck at AWAITING_QUOTE).
        import threading
        import time as _time

        sys.path.insert(0, str(ROOT / "tools" / "moomoo"))
        import push_feed

        runtime = LiveObservationalRuntime()
        feed = push_feed.MoomooPushFeed(subscriptions=runtime.subscriptions, on_record=runtime._on_feed_record)
        feed._connection_loop = lambda: None  # no OpenD: drive the queue only
        feed.start()
        try:
            payload = {"code": "US.MSFT", "data_date": "2026-09-30", "data_time": "16:00:00",
                       "last_price": 512.9, "bid_price": 512.5, "ask_price": 513.0, "volume": 27223264.0}
            callback = threading.Thread(target=lambda: feed._enqueue_from_payload(
                capability="US_EQUITY_L1", payload=payload, generation=1))
            callback.start()
            callback.join()
            deadline = _time.monotonic() + 5
            while runtime.state.quote_for("MSFT") is None and _time.monotonic() < deadline:
                _time.sleep(0.02)
        finally:
            feed.stop()
        quote = runtime.state.quote_for("MSFT")
        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual((quote.bid_price, quote.ask_price, quote.last_price), (512.5, 513.0, 512.9))
        self.assertEqual(feed.metrics()["handler_errors"], 0)


class SnapshotQuotePollTests(unittest.TestCase):
    def _feed(self):
        sys.path.insert(0, str(ROOT / "tools" / "moomoo"))
        import push_feed

        runtime = LiveObservationalRuntime()
        runtime.subscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE"], consumer_id="t")
        clock = [10_000_000_000]
        feed = push_feed.MoomooPushFeed(subscriptions=runtime.subscriptions, on_record=runtime._on_feed_record,
                                        clock=lambda: clock[0])
        enqueued: list[dict] = []
        feed._enqueue_from_payload = lambda **kw: enqueued.append(kw)
        return push_feed, feed, clock, enqueued

    def _ctx(self, snapshot_ok: bool):
        calls: list[str] = []
        ft = mock.Mock(RET_OK=0)
        ft.SubType.QUOTE, ft.SubType.TICKER, ft.SubType.ORDER_BOOK = "Q", "T", "B"
        ctx = mock.Mock()
        ctx.subscribe.return_value = (0, "")
        snap = [{"code": "US.AAPL", "update_time": "2026-09-30 21:44:48.564", "bid_price": 334.25, "ask_price": 334.3}]
        ctx.get_market_snapshot.side_effect = lambda codes: (calls.append("snapshot"), (0 if snapshot_ok else -1, snap if snapshot_ok else "limit"))[1]
        ctx.get_stock_quote.side_effect = lambda codes: (calls.append("quote"), (0, [{"code": "US.AAPL", "last_price": 333.0}]))[1]
        return ft, ctx, calls

    def test_snapshot_supplies_bid_ask_on_a_rate_limited_cadence(self) -> None:
        push_feed, feed, clock, enqueued = self._feed()
        ft, ctx, calls = self._ctx(snapshot_ok=True)
        feed._sync_subscriptions(ctx, ft)
        feed._sync_subscriptions(ctx, ft)  # same instant: no second snapshot call
        self.assertEqual(calls, ["snapshot"])
        self.assertEqual(enqueued[0]["payload"]["bid_price"], 334.25)
        clock[0] += push_feed.SNAPSHOT_INTERVAL_NS
        feed._sync_subscriptions(ctx, ft)
        self.assertEqual(calls, ["snapshot", "snapshot"])

    def test_snapshot_refusal_falls_back_to_stock_quote(self) -> None:
        _, feed, _, enqueued = self._feed()
        ft, ctx, calls = self._ctx(snapshot_ok=False)
        feed._sync_subscriptions(ctx, ft)
        self.assertEqual(calls, ["snapshot", "quote"])
        self.assertEqual(enqueued[0]["payload"]["last_price"], 333.0)

    def test_session_price_follows_the_snapshot_update_time(self) -> None:
        from market_platform_foundation.market_data.observational_state import _session_last_price

        prices = {"last_price": 333.02, "pre_price": 330.43, "after_price": 334.25, "overnight_price": 334.16}
        at = lambda clock: _session_last_price({**prices, "update_time": f"2026-09-30 {clock}:00.000"})
        self.assertEqual(at("21:44"), 334.16)
        self.assertEqual(at("02:10"), 334.16)
        self.assertEqual(at("17:05"), 334.25)
        self.assertEqual(at("07:15"), 330.43)
        self.assertEqual(at("11:00"), 333.02)
        self.assertEqual(_session_last_price({"last_price": 333.02, "update_time": "2026-09-30 21:44:00"}), 333.02)

    def test_quote_push_keeps_the_recent_snapshot_book(self) -> None:
        from market_platform_foundation.market_data.observational_state import BOOK_CARRY_NS, ObservationalStateStore

        state = ObservationalStateStore()
        second = 1_000_000_000

        def l1(payload: dict, at_ns: int) -> None:
            state.apply_admitted({
                "admission": {"display": "DISPLAY_ADMITTED"},
                "envelope": {"instrument_id": "NVDA", "event_time": at_ns, "available_time": at_ns},
                "record": {"capability": "US_EQUITY_L1", "raw_payload": payload,
                           "clocks": {"received_time_ns": at_ns}},
            })

        book = {"bid_price": 230.2, "ask_price": 230.3, "bid_vol": 100.0, "ask_vol": 200.0}
        l1({"last_price": 230.24, "overnight_price": 0.0, "update_time": "2026-10-01 12:17:00.000", **book}, 10 * second)
        # Live OpenD, regular session: the QUOTE push has no bid/ask and used to blank the book.
        # It does carry overnight_price (0 by day), so that field alone does not mark a snapshot.
        l1({"last_price": 230.3, "overnight_price": 0.0, "data_time": "12:17:01"}, 11 * second)
        quote = state.quote_for("NVDA")
        self.assertEqual((quote.last_price, quote.bid_price, quote.ask_price, quote.ask_size), (230.3, 230.2, 230.3, 200.0))
        self.assertEqual(quote.book_received_ns, 10 * second)
        # Snapshot polling stopped: the book is dropped, never carried indefinitely.
        l1({"last_price": 230.4, "overnight_price": 0.0}, 10 * second + BOOK_CARRY_NS + 1)
        quote = state.quote_for("NVDA")
        self.assertEqual((quote.last_price, quote.bid_price, quote.ask_price), (230.4, None, None))

    def _l1_store(self):
        from market_platform_foundation.market_data.observational_state import ObservationalStateStore

        state = ObservationalStateStore()

        def l1(payload: dict, received_ns: int, *, event_ns: int | None = None) -> None:
            # The push feed stamps event == received when the payload has no clock it can parse.
            state.apply_admitted({
                "admission": {"display": "DISPLAY_ADMITTED"},
                "envelope": {"instrument_id": "NVDA", "event_time": event_ns or received_ns, "available_time": received_ns},
                "record": {"capability": "US_EQUITY_L1", "raw_payload": payload,
                           "clocks": {"received_time_ns": received_ns}},
            })

        return state, l1

    def test_quote_push_dates_its_regular_session_last_price_from_data_time(self) -> None:
        from market_platform_foundation.market_data.provider_time import parse_provider_datetime_ns

        state, l1 = self._l1_store()
        polled = parse_provider_datetime_ns("2026-10-06 14:12:29.000")
        traded = parse_provider_datetime_ns("2026-10-06 14:12:30.250")
        received = traded + 300_000_000
        book = {"bid_price": 240.22, "ask_price": 240.24, "bid_vol": 100.0, "ask_vol": 200.0}
        l1({"last_price": 240.20, "overnight_price": 0.0, "update_time": "2026-10-06 14:12:29.000", **book},
           polled + 200_000_000, event_ns=polled)
        # Live OpenD, regular session (2026-10-06 14:12 ET): the QUOTE push for an actively traded
        # symbol has data_date/data_time and no update_time. It used to leave the quote with no
        # provider clock, so NVDA, INTC and MRVL were BLOCKED: NO_OBSERVATION_TIME between polls.
        l1({"last_price": 240.23, "overnight_price": 0.0, "data_date": "2026-10-06", "data_time": "14:12:30.250"}, received)
        quote = state.quote_for("NVDA")
        self.assertEqual(quote.last_price, 240.23)
        self.assertEqual(quote.event_time_ns, traded)
        self.assertEqual(quote.received_ns, received)
        # The carried book keeps its own receipt clock; it does not borrow the push's trade time.
        self.assertEqual(quote.book_received_ns, polled + 200_000_000)
        # Second resolution is still a provider clock.
        l1({"last_price": 240.25, "data_date": "2026-10-06", "data_time": "14:12:31"}, received + 1_000_000_000)
        self.assertEqual(state.quote_for("NVDA").event_time_ns, parse_provider_datetime_ns("2026-10-06 14:12:31"))

    def test_quote_push_never_dates_an_extended_hours_price_or_a_clock_it_cannot_trust(self) -> None:
        from market_platform_foundation.market_data.provider_time import parse_provider_datetime_ns

        state, l1 = self._l1_store()
        received = parse_provider_datetime_ns("2026-10-07 08:51:38.000")
        undated = lambda: state.quote_for("NVDA").event_time_ns == state.quote_for("NVDA").received_ns
        # Live OpenD, 08:51 ET pre-market: data_time is still yesterday's close. The price shown is the
        # after-hours print, which that clock does not describe.
        l1({"last_price": 239.24, "pre_price": 237.17, "after_price": 239.86, "overnight_price": 239.84,
            "data_date": "2026-10-06", "data_time": "16:00:00"}, received)
        self.assertEqual(state.quote_for("NVDA").last_price, 239.86)
        self.assertTrue(undated())
        # A clock ahead of receipt, a bare time with no date, and an unreadable time stay undated.
        for clock in ({"data_date": "2026-10-07", "data_time": "08:51:39.500"}, {"data_time": "08:51:37"},
                      {"data_date": "2026-10-07", "data_time": "N/A"}):
            with self.subTest(clock=clock):
                l1({"last_price": 239.24, **clock}, received)
                self.assertTrue(undated())
        # Yesterday's regular-session print is dated as yesterday's, so it reads stale, not live.
        l1({"last_price": 0.1116, "pre_price": 0.2527, "data_date": "2026-10-06", "data_time": "14:47:40.142"}, received)
        self.assertEqual(state.quote_for("NVDA").event_time_ns, parse_provider_datetime_ns("2026-10-06 14:47:40.142"))
        # A snapshot's own update_time is never replaced.
        polled = parse_provider_datetime_ns("2026-10-07 08:51:37.500")
        l1({"last_price": 239.24, "pre_price": 237.17, "update_time": "2026-10-07 08:51:37.500",
            "data_date": "2026-10-06", "data_time": "16:00:00"}, received, event_ns=polled)
        self.assertEqual(state.quote_for("NVDA").event_time_ns, polled)

    def test_overnight_snapshot_drops_the_frozen_after_hours_book(self) -> None:
        from market_platform_foundation.market_data.observational_state import _overnight_snapshot

        # Live OpenD, 02:26 ET: overnight trades at 231.99, bid/ask still the 20:00 after-hours book.
        snapshot = {"last_price": 228.38, "after_price": 229.6092, "overnight_price": 231.99,
                    "bid_price": 229.61, "ask_price": 229.62, "bid_vol": 100.0, "ask_vol": 1900.0}
        self.assertTrue(_overnight_snapshot({**snapshot, "update_time": "2026-10-01 02:26:22.047"}))
        self.assertTrue(_overnight_snapshot({**snapshot, "update_time": "2026-09-30 20:00:01.000"}))
        self.assertFalse(_overnight_snapshot({**snapshot, "update_time": "2026-09-30 17:05:00.000"}))
        self.assertFalse(_overnight_snapshot({**snapshot, "update_time": "2026-10-01 04:00:00.000"}))
        # A push quote (no overnight_price field) keeps its book.
        self.assertFalse(_overnight_snapshot({"bid_price": 1.0, "update_time": "2026-10-01 02:26:22.047"}))

        import time as _time

        sys.path.insert(0, str(ROOT / "tools" / "moomoo"))
        import push_feed

        runtime = LiveObservationalRuntime()
        feed = push_feed.MoomooPushFeed(subscriptions=runtime.subscriptions, on_record=runtime._on_feed_record)
        feed._connection_loop = lambda: None
        feed.start()
        try:
            feed._enqueue_from_payload(capability="US_EQUITY_L1", generation=1,
                                       payload={"code": "US.NVDA", **snapshot, "update_time": "2026-10-01 02:26:22.047"})
            deadline = _time.monotonic() + 5
            while runtime.state.quote_for("NVDA") is None and _time.monotonic() < deadline:
                _time.sleep(0.02)
        finally:
            feed.stop()
        quote = runtime.state.quote_for("NVDA")
        self.assertEqual(quote.last_price, 231.99)
        self.assertEqual((quote.bid_price, quote.ask_price, quote.bid_size, quote.ask_size), (None, None, None, None))


class QuoteContextOpenTests(unittest.TestCase):
    """OpenD accepting TCP but not answering InitConnect must not accumulate SDK connections."""

    class _Ctx:
        instances: list = []

        def __init__(self, *, host, port, is_async_connect=False, ready=True):
            self.is_async_connect, self.closed, self._ready = is_async_connect, False, ready
            type(self).instances.append(self)

        @property
        def status(self):
            return "READY" if self._ready else "WAIT_RECONNECT"

        def close(self):
            self.closed = True

    def _ft(self, ready: bool):
        ctx_type = self._Ctx
        ctx_type.instances = []
        return mock.Mock(OpenQuoteContext=lambda **kw: ctx_type(ready=ready, **kw)), ctx_type

    def test_ready_context_is_returned_and_constructed_async(self) -> None:
        sys.path.insert(0, str(ROOT / "tools" / "moomoo"))
        from opend_quote_transport import open_quote_context

        ft, ctx_type = self._ft(ready=True)
        ctx = open_quote_context(ft, host="127.0.0.1", port=11111, ready_timeout=0.2)
        self.assertIs(ctx, ctx_type.instances[0])
        self.assertTrue(ctx.is_async_connect)  # the sync constructor leaks a socket per failed retry
        self.assertFalse(ctx.closed)

    def test_context_that_never_becomes_ready_is_closed(self) -> None:
        sys.path.insert(0, str(ROOT / "tools" / "moomoo"))
        from opend_quote_transport import open_quote_context

        ft, ctx_type = self._ft(ready=False)
        self.assertIsNone(open_quote_context(ft, host="127.0.0.1", port=11111, ready_timeout=0.1))
        self.assertTrue(ctx_type.instances[0].closed)


class ProviderNeutralityTests(unittest.TestCase):
    def test_live_state_payload_has_no_vendor_classes(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        quote = runtime.state.quote_for("AAPL")
        payload = quote.to_dict() if quote else {}
        forbidden = ("US.AAPL", "OpenQuoteContext", "StockQuoteHandlerBase")
        for token in forbidden:
            self.assertNotIn(token, str(payload))


if __name__ == "__main__":
    unittest.main()
