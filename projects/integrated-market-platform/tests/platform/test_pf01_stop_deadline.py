"""PF-01 stop path: one coordinated deadline, bounded escalation and accurate drain verdicts.

Offline. Child processes are tiny local scripts; provider transports are the
synthetic ones. Nothing opens a socket.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.crypto_market import kraken_stream
from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data import headless_supply, persistence
from market_platform_foundation.market_data.headless_supply import HeadlessMarketSupply, SupplyTarget
from market_platform_foundation.market_data.persistence import MarketStreamWriter
from market_platform_foundation.news import collection, supervision
from market_platform_foundation.news.supervision import SUPERVISION_JOB, CollectionSupervisor, child_stop_bound_seconds
from tests.support.pf01_synthetic_providers import KRAKEN_PAIRS, SyntheticKraken
from tools.platform import pf01_supervisor
from tools.platform.pf01_supervisor import OwnedProcess

BTC, ETH = sorted(KRAKEN_PAIRS)
TOOLS = str(Path(__file__).resolve().parents[2] / 'tools/moomoo')
# Reads the parent's stop line, then takes argv[1] seconds to finish its drain. A negative value ignores the stop.
CHILD = ('import sys,time\n'
         'sys.stdin.readline()\n'
         'delay=float(sys.argv[1])\n'
         'time.sleep(3600 if delay<0 else delay)\n'
         'raise SystemExit(int(sys.argv[2]))\n')


def push_feed_module():
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import push_feed

    return push_feed


class StopBoundContractTests(unittest.TestCase):
    """The supervisor's wait is the child's own bound, not a separately chosen number."""

    def test_supervisor_wait_is_the_sum_of_the_child_stage_bounds(self):
        feed = push_feed_module()
        self.assertEqual(headless_supply.MOOMOO_STOP_SECONDS, feed.CONNECTION_JOIN_SECONDS + feed.PROCESSOR_JOIN_SECONDS)
        self.assertGreaterEqual(feed.PROCESSOR_JOIN_SECONDS, feed.PROCESSOR_DRAIN_SECONDS)
        stages = (headless_supply.RECONCILE_JOIN_SECONDS + headless_supply.STALLED_LOCK_SECONDS
                  + headless_supply.MOOMOO_STOP_SECONDS
                  + kraken_stream.RECEIVER_JOIN_SECONDS + kraken_stream.DRAIN_SECONDS
                  + collection.WORKER_JOIN_SECONDS
                  + persistence.WORKER_JOIN_SECONDS + persistence.FINAL_DRAIN_SECONDS)
        self.assertEqual(child_stop_bound_seconds(), stages + supervision.CHILD_STOP_MARGIN_SECONDS)
        process = subprocess.Popen([sys.executable, '-c', 'pass'], stdin=subprocess.PIPE, text=True)
        self.addCleanup(process.stdin.close)
        process.wait(timeout=30)
        self.assertEqual(OwnedProcess(process).stop_seconds, child_stop_bound_seconds())

    def test_bound_is_finite_and_inside_the_parent_lease(self):
        # A stop can run inside tick(); the parent's lease must outlast it and the termination that may follow.
        self.assertLess(child_stop_bound_seconds() + pf01_supervisor.TERMINATE_WAIT_SECONDS, supervision.LEASE_SECONDS)
        self.assertGreater(child_stop_bound_seconds(), 15)  # the previous wait was shorter than the child's own stages


class OwnedProcessTests(unittest.TestCase):
    def child(self, delay, code=0, **kwargs):
        process = subprocess.Popen([sys.executable, '-c', CHILD, str(delay), str(code)], stdin=subprocess.PIPE, text=True)

        def reap():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
        self.addCleanup(reap)
        return OwnedProcess(process, **kwargs)

    def test_immediate_clean_stop(self):
        owned = self.child(0)
        started = time.monotonic()
        owned.stop()
        self.assertEqual(owned.poll(), 0)
        self.assertLess(time.monotonic() - started, 10)
        owned.stop()  # already exited: nothing to do

    def test_slow_but_successful_drain_is_not_terminated_inside_the_bound(self):
        owned = self.child(2, stop_seconds=20)
        owned.stop()
        self.assertEqual(owned.poll(), 0)

    def test_wait_shorter_than_the_drain_terminates_a_healthy_child(self):
        # The defect this suite guards against: the same child, a parent that waits less than the drain needs.
        owned = self.child(2, stop_seconds=0.3)
        owned.stop()
        self.assertNotIn(owned.poll(), (None, 0))

    def test_child_ignoring_stop_is_terminated_after_the_bound(self):
        owned = self.child(-1, stop_seconds=0.5)
        started = time.monotonic()
        owned.stop()
        self.assertNotIn(owned.poll(), (None, 0))
        self.assertLess(time.monotonic() - started, 0.5 + pf01_supervisor.TERMINATE_WAIT_SECONDS + 5)


class SupervisorEscalationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.db = LocalStateConnection(self.path)
        self.addCleanup(self.db.close)
        self.env = {'IMP_PF01_SUPERVISION_ENABLED': '1', 'IMP_NEWS_COLLECTION_ENABLED': '1', 'IMP_PERSIST_STATE': '1',
                    'IMP_STATE_DIR': self.temp.name}
        self.processes = []

    def supervisor(self, delay, code=0, stop_seconds=20.0):
        def spawn():
            process = subprocess.Popen([sys.executable, '-c', CHILD, str(delay), str(code)], stdin=subprocess.PIPE, text=True)
            self.processes.append(process)
            return OwnedProcess(process, stop_seconds=stop_seconds)
        owner = CollectionSupervisor(self.db, spawn=spawn, env=self.env)
        self.addCleanup(self.reap)
        self.addCleanup(owner.stop)
        owner.tick()
        self.assertEqual(owner.status()['state'], 'RUNNING')
        return owner

    def reap(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)

    def saved(self):
        row = self.db.execute('SELECT payload_json,lease_owner FROM news_collection_jobs WHERE job_id=?', (SUPERVISION_JOB,)).fetchone()
        return json.loads(row[0]), row[1]

    def test_slow_successful_drain_is_a_plain_operator_stop_with_the_lease_released(self):
        owner = self.supervisor(2)
        owner.stop()
        saved, lease = self.saved()
        self.assertEqual((saved['state'], saved['reason'], lease), ('STOPPED', 'OPERATOR_STOP', None))
        self.assertEqual(self.processes[-1].poll(), 0)

    def test_stalled_child_is_terminated_and_recorded_as_an_unknown_tail(self):
        owner = self.supervisor(-1, stop_seconds=0.5)
        owner.stop()
        saved, lease = self.saved()
        self.assertEqual((saved['state'], saved['reason'], lease), ('STOPPED', 'OPERATOR_STOP_CHILD_EXIT_UNVERIFIED', None))
        self.assertEqual(saved['events'][-1]['reason'], 'CHILD_STOP_EXIT_GAP_UNVERIFIED')
        self.assertIsNotNone(self.processes[-1].poll())

    def test_child_reporting_an_incomplete_drain_is_not_a_clean_stop(self):
        owner = self.supervisor(0, code=1)
        owner.stop()
        saved, _ = self.saved()
        self.assertEqual(saved['reason'], 'OPERATOR_STOP_CHILD_EXIT_UNVERIFIED')
        self.assertEqual(saved['events'][-1]['exit_code'], 1)

    def test_handle_that_observed_no_exit_is_not_accepted_as_a_drain(self):
        class Silent:
            def poll(self):
                return None

            def stop(self):
                pass
        owner = CollectionSupervisor(self.db, spawn=Silent, env=self.env)
        owner.tick()
        owner.stop()
        saved, lease = self.saved()
        self.assertEqual((saved['reason'], lease), ('OPERATOR_STOP_CHILD_EXIT_UNVERIFIED', None))

    def test_interrupt_during_an_in_loop_child_stop_is_not_recorded_as_a_clean_stop(self):
        class Child:
            def __init__(self, final):
                self.final, self.exit, self.stops = final, None, 0

            def poll(self):
                return self.exit

            def stop(self):
                self.stops += 1
                if self.stops == 1:
                    raise KeyboardInterrupt  # Ctrl+C lands while the supervisor is already stopping this child
                self.exit = self.final
        for final, reason in ((None, 'OPERATOR_STOP_CHILD_EXIT_UNVERIFIED'), (1, 'OPERATOR_STOP_CHILD_EXIT_UNVERIFIED'),
                              (0, 'OPERATOR_STOP')):
            child = Child(final)
            owner = CollectionSupervisor(self.db, spawn=lambda: child, env=self.env)
            owner.tick()
            with self.assertRaises(KeyboardInterrupt):
                owner._stop_child()
            self.assertIs(owner.child, child)  # the handle survives, so the operator stop can finish it
            self.assertEqual(owner._evidence['events'][-1]['reason'], 'CHILD_STOP_EXIT_GAP_UNVERIFIED')
            owner.stop()
            saved, lease = self.saved()
            self.assertEqual((child.stops, saved['reason'], lease), (2, reason, None))

    def test_owned_process_whose_stdin_was_closed_by_an_interrupted_stop_is_still_terminated(self):
        process = subprocess.Popen([sys.executable, '-c', CHILD, '-1', '0'], stdin=subprocess.PIPE, text=True)
        self.addCleanup(process.kill)
        process.stdin.close()
        OwnedProcess(process, stop_seconds=0.5).stop()
        self.assertIsNotNone(process.poll())

    def run_cli(self, child):
        """The supervisor CLI's run loop with a synthetic child, interrupted once as Ctrl+C would."""
        LocalStateConnection(self.path).close()
        env = {**self.env, 'IMP_PF01_SUPERVISION_ENABLED': '1'}
        real_own = pf01_supervisor.own

        def own(connection, _spawn):
            return real_own(connection, lambda: child)
        with patch.dict(pf01_supervisor.os.environ, env), patch.object(pf01_supervisor, 'own', own), \
                patch.object(pf01_supervisor.time, 'sleep', side_effect=KeyboardInterrupt), \
                patch('builtins.print'):
            return pf01_supervisor.main(['--run'])

    def test_cli_exit_code_reflects_an_unverified_child_stop(self):
        class Child:
            def __init__(self, code):
                self.code, self.exit = code, None

            def poll(self):
                return self.exit

            def stop(self):
                self.exit = self.code
        self.assertEqual(self.run_cli(Child(0)), 0)
        self.assertEqual(self.saved()[0]['reason'], 'OPERATOR_STOP')
        self.assertEqual(self.run_cli(Child(1)), 1)
        self.assertEqual(self.saved()[0]['reason'], 'OPERATOR_STOP_CHILD_EXIT_UNVERIFIED')


class SupplyCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.writer = MarketStreamWriter(self.path, sources=('moomoo', 'kraken'), symbols=('AAPL', BTC, ETH), acquire=False)
        self.addCleanup(self.writer.stop)
        item = patch.object(persistence, '_WRITER', self.writer)
        item.start()
        self.addCleanup(item.stop)

    def rows(self, sql, *args):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(sql, args).fetchall()


class StalledReconcileTests(SupplyCase):
    def test_stop_is_bounded_when_a_provider_call_never_returns(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        class Stalled:
            closed = prepared = 0

            def entitlement(self, capability):
                return None

            def open(self):
                return True

            def connection(self):
                return 'CONNECTED'

            def request(self, symbol, capability):
                entered.set()
                release.wait(30)
                return 'ACTIVE', None

            def release(self, symbol, capability):
                pass

            def prepare_stop(self):
                Stalled.prepared += 1

            def close(self):
                Stalled.closed += 1
        supply = HeadlessMarketSupply(self.path, (SupplyTarget('kraken', BTC, ('CRYPTO_TRADES',)),), writer=self.writer,
                                      providers={'kraken': Stalled()}, entitled_sources=('kraken',))
        supply.start()
        self.assertTrue(entered.wait(5))
        with patch.object(headless_supply, 'RECONCILE_JOIN_SECONDS', 0.3):
            stopper = threading.Thread(target=supply.stop)
            started = time.monotonic()
            stopper.start()
            stopper.join(5)
        self.assertFalse(stopper.is_alive(), 'stop() waited on a lock held by a stalled provider call')
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')
        # The sessions still belong to the stalled call: they were not drained or closed beside it.
        self.assertEqual((Stalled.prepared, Stalled.closed), (0, 0))
        started = time.monotonic()
        supply.stop()  # one attempt only
        self.assertLess(time.monotonic() - started, 0.2)
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps WHERE reason=?', 'SUPPLY_SHUTDOWN_INCOMPLETE'), [(1,)])


class KrakenUnansweredSubscribeTests(SupplyCase):
    """A subscribe that was sent but not yet read back still has a tail on the socket."""

    def setUp(self):
        super().setUp()
        self.venue = SyntheticKraken()
        self.runtime = KrakenStreamRuntime(resolve=KRAKEN_PAIRS.get, connect=self.venue.connect, start_worker=False,
                                           jitter=lambda: 0.5, wait=lambda _seconds: None)

    def subscribe_without_reading(self, *instruments):
        for instrument in instruments:
            self.runtime.subscribe(instrument_id=instrument, capabilities=['CRYPTO_TRADES'], consumer_id='test')
        self.runtime.step()  # opens the connection
        self.runtime._reconcile(self.runtime._desired())  # sends subscribe; the acknowledgement stays unread
        self.assertTrue(self.runtime._sent)
        self.assertFalse(self.runtime._acked)

    def test_unread_acknowledgement_and_trades_are_drained_before_a_clean_verdict(self):
        self.subscribe_without_reading(BTC)
        for _ in range(2):
            self.assertTrue(self.venue.push_trade('BTC/USD'))
        connection = self.venue.connection
        status = self.runtime.shutdown()
        self.assertEqual(status['state'], 'ACKNOWLEDGED')
        self.assertEqual([request['method'] for request in connection.sent], ['subscribe', 'unsubscribe'])
        self.assertEqual(connection.inbox, [])
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_records'), [(2,)])

    def test_unanswered_subscribe_that_is_never_acknowledged_is_an_unknown_tail(self):
        self.subscribe_without_reading(BTC)
        connection = self.venue.connection
        connection.inbox.clear()  # the venue's answers have not arrived

        def silent(text):
            connection.sent.append(json.loads(text))
        with patch.object(connection, 'send_text', silent):
            status = self.runtime.shutdown(drain_seconds=0.3)
        self.assertEqual((status['state'], status['reason'], status['tail_observations']),
                         ('UNVERIFIED', 'DRAIN_DEADLINE', 'UNKNOWN'))

    def test_subscribe_refused_during_the_drain_is_not_a_live_channel(self):
        self.venue.refuse = {('trade', 'ETH/USD')}
        self.subscribe_without_reading(BTC, ETH)
        self.assertTrue(self.venue.push_trade('BTC/USD'))
        status = self.runtime.shutdown()
        self.assertEqual(status['state'], 'ACKNOWLEDGED')
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_records'), [(1,)])
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps WHERE reason=?', 'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'), [(0,)])


class OpenDFeedStopTests(SupplyCase):
    def feed(self):
        from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager

        module = push_feed_module()
        return module, module.MoomooPushFeed(subscriptions=LiveSubscriptionManager(), on_record=lambda _record: None)

    def test_stop_during_an_unreachable_backoff_is_a_clean_stop(self):
        module, feed = self.feed()
        with patch.object(module, 'opend_reachable', return_value=False), \
                patch.object(module, 'reconnect_backoff_seconds', return_value=30.0):
            feed.start()
            deadline = time.monotonic() + 5
            while feed.last_error is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIsNotNone(feed.last_error)  # inside the reconnect backoff
            started = time.monotonic()
            feed.stop()
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(feed._shutdown_state, 'DRAINED')
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps'), [(0,)])

    def test_repeated_stop_after_an_incomplete_one_neither_waits_again_nor_counts_the_gap_twice(self):
        module, feed = self.feed()
        release = threading.Event()
        self.addCleanup(release.set)
        with patch.object(feed, '_connection_loop', lambda: release.wait(30)), \
                patch.object(module, 'CONNECTION_JOIN_SECONDS', 0.3):
            feed.start()
            with self.assertRaisesRegex(RuntimeError, 'MOOMOO_SHUTDOWN_INCOMPLETE'):
                feed.stop()
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, 'MOOMOO_SHUTDOWN_INCOMPLETE'):
                feed.stop()  # headless supply closes the runtime after draining it
            self.assertLess(time.monotonic() - started, 0.2)
        self.writer.flush()
        self.assertEqual(self.rows('SELECT observations FROM market_stream_gaps WHERE reason=?', 'MOOMOO_SHUTDOWN_INCOMPLETE'), [(1,)])


if __name__ == '__main__':
    unittest.main()
