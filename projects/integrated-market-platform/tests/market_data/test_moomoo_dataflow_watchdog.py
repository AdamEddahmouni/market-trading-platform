"""Moomoo data-flow watchdog: a feed that reads CONNECTED but receives nothing is found and reconnected.

Offline. The judgement tests drive the watchdog with an injected clock over a stand-in feed. The replay
tests run the real runtime, push feed and watchdog over a synthetic OpenD whose snapshot call blocks,
as the vendor SDK did on 2026-10-19..22 after a failed reconnect left it CONNECTED-but-not-READY.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from market_platform_foundation.market_data import feed_watchdog
from market_platform_foundation.market_data.feed_watchdog import MoomooDataFlowWatchdog
from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState, ProviderLifecycle
from tests.support.pf01_synthetic_providers import SyntheticOpenD, SyntheticQuoteContext, synthetic_probe

S = 1_000_000_000
IN_SESSION = staticmethod(lambda now: (True, "REGULAR", False))


class StandInFeed:
    def __init__(self) -> None:
        self.last_receipt_ns: int | None = None
        self.loop_heartbeat_ns: int | None = None
        self._quote_ctx = object()
        self._connection_thread = types.SimpleNamespace(is_alive=lambda: True)
        self._stop_event = threading.Event()
        self.reconnects: list[str] = []
        self.forced_reconnects = self.abandoned_sessions = 0

    def force_reconnect(self, reason: str, **_kwargs) -> str:
        self.reconnects.append(reason)
        return "CLOSED"


class StandInRuntime:
    def __init__(self, capabilities=("US_EQUITY_L1",)) -> None:
        self.feed = StandInFeed()
        self.lifecycle = ProviderLifecycle(connection_state=ProviderConnectionState.CONNECTED)
        rows = [{"capability": capability, "instrument_id": "AAPL"} for capability in capabilities]
        self.subscriptions = types.SimpleNamespace(active_subscriptions=lambda: rows)


class StandInWriter:
    sources = {"moomoo"}

    def __init__(self) -> None:
        self.gaps: list[tuple[str, int | None]] = []

    def gap(self, reason: str, *, stream: str = "*", received_ns: int | None = None) -> None:
        self.gaps.append((reason, received_ns))


class WatchdogJudgementTests(unittest.TestCase):
    def setUp(self) -> None:
        env = patch.dict(os.environ, {"IMP_MOOMOO_SILENCE_SEC": "90", "IMP_MOOMOO_WATCHDOG_RESTARTS_PER_HOUR": "3"})
        env.start()
        self.addCleanup(env.stop)
        self.writer = StandInWriter()
        writer = patch("market_platform_foundation.market_data.persistence.active_writer", return_value=self.writer)
        writer.start()
        self.addCleanup(writer.stop)
        quiet = redirect_stderr(StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.now = 1_000 * S

    def make(self, runtime=None, *, escalate=False, expected=IN_SESSION):
        self.runtime = runtime or StandInRuntime()
        watchdog = MoomooDataFlowWatchdog(self.runtime, clock=lambda: self.now, expected=expected, escalate=escalate)
        watchdog.check()  # the first look opens the window; silence is counted from here
        return watchdog

    def receive(self) -> None:
        self.runtime.feed.last_receipt_ns = self.runtime.feed.loop_heartbeat_ns = self.now

    def events(self, watchdog) -> list[str]:
        return [row["event"] for row in watchdog.events]

    def test_a_feed_that_keeps_receiving_is_left_alone(self) -> None:
        watchdog = self.make()
        for _ in range(20):
            self.receive()
            self.now += 15 * S
            self.assertEqual(watchdog.check(), "WATCHING")
        self.assertEqual(self.runtime.feed.reconnects, [])
        self.assertEqual(self.runtime.lifecycle.connection_state, ProviderConnectionState.CONNECTED)

    def test_connected_but_silent_is_alarmed_degraded_recorded_and_reconnected(self) -> None:
        watchdog = self.make()
        self.receive()
        watchdog.check()
        self.now += 89 * S
        self.assertEqual(watchdog.check(), "WATCHING")  # not yet a full silence interval
        self.now += 1 * S
        self.assertEqual(watchdog.check(), "SILENT")
        self.assertEqual(self.runtime.lifecycle.connection_state, ProviderConnectionState.DEGRADED)
        self.assertTrue(self.runtime.lifecycle.last_error.startswith("MOOMOO_FEED_SILENT"))
        self.assertEqual(self.writer.gaps, [("MOOMOO_FEED_SILENT", self.now - 90 * S)])
        self.assertEqual(self.runtime.feed.reconnects, ["WATCHDOG_NO_RECEIPTS"])
        self.assertEqual(self.events(watchdog), ["MOOMOO_FEED_SILENT", "MOOMOO_WATCHDOG_RECONNECT"])

    def test_receipts_after_the_reconnect_clear_the_alarm(self) -> None:
        watchdog = self.make()
        self.receive()
        self.now += 90 * S
        watchdog.check()
        self.now += 15 * S
        self.assertEqual(watchdog.check(), "SILENT")  # the reconnect has not delivered yet
        self.receive()
        self.assertEqual(watchdog.check(), "WATCHING")
        self.assertEqual(self.events(watchdog)[-1], "MOOMOO_FEED_RECOVERED")
        self.assertEqual(self.runtime.lifecycle.connection_state, ProviderConnectionState.CONNECTED_DEGRADED)
        self.assertIsNone(self.runtime.lifecycle.last_error)
        self.assertEqual(len(self.writer.gaps), 1)

    def test_collector_escalates_to_a_process_restart_after_two_unanswered_reconnects(self) -> None:
        watchdog = self.make(escalate=True)
        self.receive()
        for expected in (1, 2):
            self.now += 90 * S
            watchdog.check()
            self.assertEqual(len(self.runtime.feed.reconnects), expected)
            self.now += 30 * S
            watchdog.check()  # spaced: no reconnect sooner than one silence interval after the last
            self.assertEqual(len(self.runtime.feed.reconnects), expected)
        self.now += 60 * S
        self.assertEqual(watchdog.check(), "UNRECOVERABLE")
        self.assertEqual(watchdog.unrecoverable, "MOOMOO_FEED_UNRECOVERABLE")
        self.assertEqual(len(self.runtime.feed.reconnects), 2)
        self.receive()
        self.assertEqual(watchdog.check(), "UNRECOVERABLE")  # terminal; the supervisor restarts the process

    def test_serving_process_only_reconnects_within_its_hourly_budget(self) -> None:
        watchdog = self.make(escalate=False)
        self.receive()
        for _ in range(6):
            self.now += 90 * S
            watchdog.check()
        self.assertEqual(len(self.runtime.feed.reconnects), 3)
        self.assertIsNone(watchdog.unrecoverable)
        self.assertIn("MOOMOO_WATCHDOG_BUDGET_SPENT", self.events(watchdog))
        self.now += 3_600 * S
        watchdog.check()
        self.assertEqual(len(self.runtime.feed.reconnects), 4)  # budget renewed

    def test_only_a_process_with_a_restarter_escalates(self) -> None:
        # Owner decision 3 (2026-10-23): the keeper restarts a serving process it started, so that process may give
        # up on reconnecting; a serving process nobody restarts keeps reconnecting for ever, as before.
        cases = (({}, False), ({"IMP_MARKET_SUPPLY_ENABLED": "1"}, True), ({"IMP_PLATFORM_RESTARTER": "keeper"}, True),
                 ({"IMP_PLATFORM_RESTARTER": "someone-else"}, False))
        for env, escalates in cases:
            with self.subTest(env=env), patch.dict(os.environ, env):
                for key in ("IMP_MARKET_SUPPLY_ENABLED", "IMP_PLATFORM_RESTARTER"):
                    if key not in env:
                        os.environ.pop(key, None)
                self.assertIs(MoomooDataFlowWatchdog(StandInRuntime()).escalate, escalates)

    def test_a_keeper_started_serving_process_reports_unrecoverable_and_keeps_serving(self) -> None:
        with patch.dict(os.environ, {"IMP_PLATFORM_RESTARTER": "keeper"}):
            os.environ.pop("IMP_MARKET_SUPPLY_ENABLED", None)
            self.runtime = StandInRuntime()
            watchdog = MoomooDataFlowWatchdog(self.runtime, clock=lambda: self.now, expected=IN_SESSION)
        watchdog.check()
        self.receive()
        for _ in range(2):
            self.now += 90 * S
            watchdog.check()
        self.now += 90 * S
        self.assertEqual(watchdog.check(), "UNRECOVERABLE")
        status = watchdog.status()  # what /provider/health shows the keeper as data_flow
        self.assertEqual((status["state"], status["unrecoverable"], status["escalates_to_process_restart"]),
                         ("UNRECOVERABLE", "MOOMOO_FEED_UNRECOVERABLE", True))
        self.assertEqual(self.events(watchdog)[-1], "MOOMOO_FEED_UNRECOVERABLE")

    def test_nothing_is_owed_outside_the_session_or_without_quote_demand(self) -> None:
        closed = [False]
        watchdog = self.make(expected=lambda now: (not closed[0], "CLOSED" if closed[0] else "REGULAR", False))
        closed[0] = True
        self.now += 10_000 * S
        self.assertEqual(watchdog.check(), "IDLE")
        closed[0] = False
        self.assertEqual(watchdog.check(), "WATCHING")  # the window opened just now: silence counts from here
        self.now += 89 * S
        self.assertEqual(watchdog.check(), "WATCHING")
        ticks_only = self.make(StandInRuntime(capabilities=("US_EQUITY_TICKS",)))
        self.now += 1_000 * S
        self.assertEqual(ticks_only.check(), "IDLE")  # trades can be quiet; only polled quotes promise receipts
        self.assertEqual(self.runtime.feed.reconnects, [])

    def test_a_feed_already_reconnecting_is_reported_but_not_raced(self) -> None:
        watchdog = self.make()
        self.runtime.lifecycle.connection_state = ProviderConnectionState.RECONNECTING
        self.now += 120 * S
        self.assertEqual(watchdog.check(), "SILENT")
        self.assertEqual(self.runtime.feed.reconnects, [])
        self.assertEqual(self.runtime.lifecycle.connection_state, ProviderConnectionState.RECONNECTING)

    def test_a_blocked_session_loop_is_a_fault_even_while_late_callbacks_arrive(self) -> None:
        watchdog = self.make()
        self.receive()
        heartbeat = self.now
        for _ in range(6):
            self.now += 15 * S
            self.runtime.feed.last_receipt_ns = self.now  # a push still trickles in
        self.runtime.feed.loop_heartbeat_ns = heartbeat
        self.assertEqual(watchdog.check(), "SILENT")
        self.assertEqual(self.runtime.feed.reconnects, ["WATCHDOG_SESSION_LOOP_BLOCKED"])

    def test_calendar_fallback_keeps_watching_but_never_ends_the_process(self) -> None:
        expected, label, fallback = feed_watchdog.data_expected(int(1_831_474_800 * S))  # Fri 2028-01-14 10:00 ET, past calendar coverage
        self.assertTrue(fallback)
        self.assertEqual((expected, label), (True, "REGULAR"))
        watchdog = self.make(escalate=True, expected=lambda now: (True, "REGULAR", True))
        self.receive()
        for _ in range(4):
            self.now += 90 * S
            watchdog.check()
        self.assertIsNone(watchdog.unrecoverable)
        self.assertEqual(len(self.runtime.feed.reconnects), 3)  # reconnects within the budget, as a serving process does

    def test_automation_health_reads_silence_as_unhealthy(self) -> None:
        from market_platform_foundation.ui_api.paper_automation import PaperAutomationService

        watchdog = self.make()
        self.receive()
        self.now += 90 * S
        watchdog.check()
        self.runtime.feed_watchdog = watchdog
        self.runtime.subscriptions.quota_report = lambda: {}
        service = types.SimpleNamespace(_provider_health=None, store=types.SimpleNamespace(data_mode="LIVE_OBSERVATIONAL"))
        with patch("market_platform_foundation.market_data.live_runtime.get_live_runtime", return_value=self.runtime):
            health = PaperAutomationService.provider_health(service)
        self.assertEqual(health["state"], "UNHEALTHY")
        self.assertIn("LIVE_FEED_SILENT", health["reasons"])

    def test_supply_reports_the_watchdog_last_resort(self) -> None:
        from market_platform_foundation.market_data.headless_supply import HeadlessMarketSupply

        watchdog = types.SimpleNamespace(unrecoverable="MOOMOO_FEED_UNRECOVERABLE")
        supply = types.SimpleNamespace(providers={"moomoo": types.SimpleNamespace(runtime=types.SimpleNamespace(feed_watchdog=watchdog))})
        self.assertEqual(HeadlessMarketSupply.unrecoverable(supply), "MOOMOO_FEED_UNRECOVERABLE")
        self.assertIsNone(HeadlessMarketSupply.unrecoverable(types.SimpleNamespace(providers={})))


class HangingContext(SyntheticQuoteContext):
    """A context whose snapshot call can block, as a CONNECTED-but-not-READY vendor context does."""

    def __init__(self, opend: "HangingOpenD") -> None:
        super().__init__(opend)
        self.blocked = threading.Event()
        self.closed_event = threading.Event()

    def get_market_snapshot(self, codes):
        opend = self.opend
        if opend.hang_target is self:
            self.blocked.set()
            if opend.honor_close:
                self.closed_event.wait(10)  # the bounded SDK returns once its context is closed
                return -1, "Connection closed"
            opend.release.wait(10)  # stays stuck however it is closed
            return super().get_market_snapshot(codes)
        return super().get_market_snapshot(codes)

    def close(self) -> None:
        super().close()
        self.closed_event.set()


class HangingOpenD(SyntheticOpenD):
    def __init__(self, *, honor_close: bool = True) -> None:
        super().__init__()
        self.honor_close = honor_close
        self.hang_target: HangingContext | None = None
        self.release = threading.Event()

    def open(self, _sdk=None, **_kwargs):
        if not self.reachable:
            return None
        context = HangingContext(self)
        self.contexts.append(context)
        return context


class FeedReplayTests(unittest.TestCase):
    """Real runtime, push feed and watchdog; only the OpenD transport is synthetic."""

    ENV = {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1", "IMP_LIVE_RECONNECT_BACKOFF_SEC": "0.05",
           "IMP_OBSERVATIONAL_PROVIDER": "moomoo", "IMP_IBKR_LIVE": "0", "IMP_SHADOW_RECORDING": "0",
           "IMP_MOOMOO_SILENCE_SEC": "0.5", "IMP_MOOMOO_WATCHDOG_INTERVAL_SEC": "3600", "IMP_MOOMOO_OPEND_CHECK_SEC": "0"}

    def runtime(self, opend: SyntheticOpenD, **env: str):
        import push_feed
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        report = synthetic_probe(Path(temp.name) / "probe.json")
        item = patch.dict(os.environ, {**self.ENV, "IMP_MOOMOO_PROBE_REPORT": str(report), **env})
        item.start()
        self.addCleanup(item.stop)
        for started in opend.install():
            self.addCleanup(started.stop)
        cadence = patch.object(push_feed, "SNAPSHOT_INTERVAL_NS", 50_000_000)
        cadence.start()
        self.addCleanup(cadence.stop)
        quiet = redirect_stderr(StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        runtime = LiveObservationalRuntime()
        runtime.configure()
        self.addCleanup(runtime.stop)
        runtime.subscribe(instrument_id="AAPL", capabilities=["US_EQUITY_L1"], consumer_id="watchdog-test")
        runtime.feed_watchdog.expected = IN_SESSION
        runtime.feed_watchdog.escalate = False
        return runtime

    def wait_until(self, condition, seconds: float = 10.0) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail("condition not reached")

    def received_after(self, runtime, moment: int) -> bool:
        return (runtime.feed.last_receipt_ns or 0) > moment

    def test_replay_2026_10_21_a_snapshot_call_that_never_returns_is_closed_and_collection_resumes(self) -> None:
        opend = HangingOpenD(honor_close=True)
        runtime = self.runtime(opend)
        self.addCleanup(opend.release.set)
        watchdog = runtime.feed_watchdog
        self.wait_until(lambda: runtime.feed.last_receipt_ns is not None)
        self.assertEqual(watchdog.check(), "WATCHING")
        stuck = opend.context
        opend.hang_target = stuck
        self.wait_until(stuck.blocked.is_set)
        time.sleep(0.6)
        self.assertNotEqual(str(runtime.lifecycle.connection_state), "DISCONNECTED")  # it still looks connected
        self.assertEqual(watchdog.check(), "SILENT")
        acted = time.time_ns()
        self.assertEqual(watchdog.events[-1]["outcome"], "CLOSED")
        self.wait_until(lambda: len(opend.contexts) == 2 and self.received_after(runtime, acted))
        self.assertEqual(watchdog.check(), "WATCHING")
        self.assertEqual([row["event"] for row in watchdog.events],
                         ["MOOMOO_FEED_SILENT", "MOOMOO_WATCHDOG_RECONNECT", "MOOMOO_FEED_RECOVERED"])
        self.assertEqual(runtime.feed.abandoned_sessions, 0)
        self.assertEqual(runtime.health_payload()["data_flow"]["state"], "WATCHING")

    def test_a_thread_that_stays_stuck_is_abandoned_and_cannot_touch_the_new_session(self) -> None:
        opend = HangingOpenD(honor_close=False)
        runtime = self.runtime(opend)
        watchdog = runtime.feed_watchdog
        watchdog.reconnect_join_seconds = 0.3
        self.addCleanup(opend.release.set)  # runs before the runtime stops, whatever the outcome
        self.wait_until(lambda: runtime.feed.last_receipt_ns is not None)
        self.assertEqual(watchdog.check(), "WATCHING")
        stuck, old_thread = opend.context, runtime.feed._connection_thread
        opend.hang_target = stuck
        self.wait_until(stuck.blocked.is_set)
        time.sleep(0.6)
        self.assertEqual(watchdog.check(), "SILENT")
        acted = time.time_ns()
        self.assertEqual(watchdog.events[-1]["outcome"], "ABANDONED")
        self.assertIsNot(runtime.feed._connection_thread, old_thread)
        self.wait_until(lambda: self.received_after(runtime, acted))
        self.assertEqual(watchdog.check(), "WATCHING")
        current = runtime.feed.provider_generation
        opend.release.set()  # the abandoned call finally returns, into a superseded session
        self.wait_until(lambda: not old_thread.is_alive())
        self.assertEqual(runtime.feed.provider_generation, current)
        self.assertIn(("US.AAPL", "QUOTE"), runtime.feed._subscribed_subtypes)
        self.assertTrue(runtime.feed._connection_thread.is_alive())

    def test_opend_reachability_is_checked_at_most_once_per_interval_inside_a_session(self) -> None:
        import push_feed

        opend = SyntheticOpenD()
        calls = []
        runtime = self.runtime(opend, IMP_MOOMOO_OPEND_CHECK_SEC="15")
        self.wait_until(lambda: runtime.feed.last_receipt_ns is not None)
        with patch.object(push_feed, "opend_reachable", lambda **_k: calls.append(1) or True):
            time.sleep(1.5)  # about three session-loop passes
        self.assertEqual(calls, [])


class TransportBoundTests(unittest.TestCase):
    def test_a_ready_context_gets_a_bounded_synchronous_wait(self) -> None:
        import opend_quote_transport

        class Context:
            status = property(lambda self: "READY")

            def __init__(self, **_kwargs) -> None:
                self.bound = None

            def set_sync_query_connect_timeout(self, seconds) -> None:
                self.bound = seconds

        ft = types.SimpleNamespace(OpenQuoteContext=Context)
        with patch.dict(os.environ, {"IMP_MOOMOO_SYNC_QUERY_TIMEOUT_SEC": "7"}):
            ctx = opend_quote_transport.open_quote_context(ft, host="127.0.0.1", port=11111)
        self.assertEqual(ctx.bound, 7.0)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMP_MOOMOO_SYNC_QUERY_TIMEOUT_SEC", None)
            self.assertEqual(opend_quote_transport.open_quote_context(ft, host="127.0.0.1", port=11111).bound, 10.0)


class ProbeTimeoutTests(unittest.TestCase):
    def test_an_unanswered_question_is_not_a_refusal(self) -> None:
        import probe

        ft = types.SimpleNamespace(RET_OK=0)
        self.assertTrue(probe.entitlement(0, [], ft, ok=True))
        for message in ("PacketErr.Timeout", "Abnormal event timeout", "Connect timeout", "Connection closed"):
            self.assertIsNone(probe.entitlement(-1, message, ft, ok=False), message)
        self.assertFalse(probe.entitlement(-1, "No right to get the quote", ft, ok=False))

    def test_an_inconclusive_report_never_replaces_the_published_one(self) -> None:
        import probe

        output = Path("evidence/capability-report.json")
        answered = {"capabilities": {"US_EQUITY_L1": {"account_entitled": True},
                                     "US_OPTIONS_QUOTE": {"account_entitled": None}}}
        self.assertEqual(probe.report_destination(answered, output), output)  # a non-core gap is only listed
        self.assertTrue(answered["conclusive"])
        self.assertEqual(answered["inconclusive_capabilities"], ["US_OPTIONS_QUOTE"])
        slow = {"capabilities": {"US_EQUITY_L1": {"account_entitled": None}, "US_EQUITY_TICKS": {"account_entitled": False}}}
        self.assertEqual(probe.report_destination(slow, output), Path("evidence/capability-report.inconclusive.json"))
        self.assertFalse(slow["conclusive"])


if __name__ == "__main__":
    unittest.main()
