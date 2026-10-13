"""Exact observable-ingress reconciliation and bounded shutdown, synthetic only."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES
from market_platform_foundation.crypto_market.ws_client import WebSocketClient
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.persistence import MarketStreamWriter
from tests.support.pf01_synthetic_providers import KRAKEN_PAIRS, SyntheticKraken

BTC = sorted(KRAKEN_PAIRS)[0]


class ObservationAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.writer = MarketStreamWriter(self.path, sources=('kraken',), symbols=(BTC,), queue_limit=64, batch_limit=8)
        self.addCleanup(self.writer.stop)
        self.venue = SyntheticKraken()
        self.runtime = KrakenStreamRuntime(resolve=KRAKEN_PAIRS.get, connect=self.venue.connect, start_worker=False)
        self.addCleanup(self.runtime.shutdown)
        self.runtime.subscribe(instrument_id=BTC, capabilities=[TRADES], consumer_id='test')
        self.runtime.step()
        self.runtime.step()
        self.assertIsNotNone(self.runtime.subscriptions.activated_at(instrument_id=BTC, capability=TRADES))
        self.patch = patch('market_platform_foundation.market_data.persistence._WRITER', self.writer)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def count(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0]

    def test_shutdown_drains_exact_38_trade_transport_tail_before_ack(self):
        for _ in range(38):
            self.assertTrue(self.venue.push_trade('BTC/USD'))
        self.assertEqual(self.count(), 0)  # producer enqueue is not process receipt
        self.runtime.shutdown()
        self.writer.stop()
        self.assertEqual(self.count(), 38)
        self.assertFalse(self.venue.connections[0].inbox)

    def test_selected_receipts_reconcile_overflow_duplicates_and_pending(self):
        self.writer.queue_limit = 1
        for _ in range(3):
            self.venue.push_trade('BTC/USD')
            self.runtime.step()
        status = self.writer.status()
        self.assertEqual(status.get('selected_received'), 3)
        self.assertEqual(status.get('accepted'), 1)
        self.assertEqual((status['rejected'], status['backlog']), (2, 1))
        self.assertEqual(status.get('unreconciled'), 0)
        self.writer.stop()
        status = self.writer.status()
        self.assertEqual(status['accepted'], status['committed'] + status['duplicates'] + status['backlog'])
        self.assertEqual(status['selected_received'], status['accepted'] + status['rejected'])

    def test_shutdown_ack_failure_marks_unknown_tail_without_inventing_drop_count(self):
        connection = self.venue.connections[0]
        self.venue.push_trade('BTC/USD')
        connection.broken = True
        self.runtime.shutdown()
        self.writer.stop()
        with closing(sqlite3.connect(self.path)) as db:
            reasons = dict(db.execute('SELECT reason,SUM(observations) FROM market_stream_gaps GROUP BY reason'))
        self.assertIn('KRAKEN_SHUTDOWN_TAIL_UNVERIFIED', reasons)
        self.assertEqual(self.count(), 0)  # one unreceived inbox item is not a received trade gap
        self.assertEqual(self.writer.status()['rejected'], 0)

    def test_partial_batch_failure_keeps_every_accepted_receipt_pending_then_reconciles(self):
        for _ in range(3):
            self.venue.push_trade('BTC/USD')
            self.runtime.step()
        self.writer.connection.execute("CREATE TRIGGER reject_fixture BEFORE INSERT ON market_stream_records BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        self.assertEqual(self.writer.flush(), 0)
        status = self.writer.status()
        self.assertEqual((status['accepted'], status['committed'], status['backlog'], status['unreconciled']), (3, 0, 3, 0))
        self.assertEqual(self.writer.checkpoints(), [])
        self.writer.connection.execute('DROP TRIGGER reject_fixture')
        self.assertEqual(self.writer.flush(), 3)
        status = self.writer.status()
        self.assertEqual((status['accepted'], status['committed'], status['backlog'], status['unreconciled']), (3, 3, 0, 0))

    def test_replayed_native_trade_counts_duplicate_without_extra_durable_row(self):
        self.venue.push_trade('BTC/USD')
        connection = self.venue.connections[0]
        text = connection.inbox[0]
        connection.deliver(json.loads(text))
        self.runtime.step()
        self.runtime.step()
        self.writer.flush()
        status = self.writer.status()
        self.assertEqual((status['selected_received'], status['accepted'], status['committed'], status['duplicates'], status['unreconciled']),
                         (2, 2, 1, 1, 0))

    def test_real_websocket_frame_buffer_tail_is_drained_before_unsubscribe_ack(self):
        import struct
        self.venue.push_trade('BTC/USD')
        text = self.venue.connections[0].inbox[0]
        trade = json.loads(text)
        def frame(message):
            raw = json.dumps(message).encode()
            return b'\x81' + (bytes([len(raw)]) if len(raw) < 126 else b'\x7e' + struct.pack('!H', len(raw))) + raw
        buffered = b''
        for trade_id in range(38):
            trade['data'][0]['trade_id'] = trade_id
            buffered += frame(trade)
        buffered += frame({'method': 'unsubscribe', 'req_id': self.runtime._request_id+1, 'success': True})
        class Socket:
            def sendall(self, data):
                pass
            def close(self):
                pass
            def recv(self, size):
                raise AssertionError('All complete frames are already in the client buffer')
        self.runtime._connection = WebSocketClient(Socket(), initial=buffered)
        result = self.runtime.shutdown()
        self.writer.stop()
        self.assertEqual((result['state'], result['messages_drained'], self.count()), ('ACKNOWLEDGED', 39, 38))

    def test_missing_ack_has_a_bounded_unknown_tail(self):
        with patch.object(self.venue.connections[0], 'send_text'):
            result = self.runtime.shutdown(drain_seconds=.01)
        self.assertEqual((result['state'], result['reason']), ('UNVERIFIED', 'DRAIN_DEADLINE'))
        self.assertEqual(self.writer.status()['selected_received'], 0)


class ReceiveDeadlineTests(unittest.TestCase):
    def test_ping_stream_cannot_extend_receive_deadline(self):
        clock = [0.0]
        class Socket:
            calls = 0
            def settimeout(self, timeout):
                pass
            def recv(self, size):
                self.calls += 1
                clock[0] += .1
                return b'\x89\x00' if self.calls < 10 else b'\x81\x02{}'
            def sendall(self, data):
                pass
        sock = Socket()
        client = WebSocketClient(sock)
        with patch('time.monotonic', lambda: clock[0]):
            self.assertIsNone(client.receive(.25))
        self.assertLessEqual(sock.calls, 3)


class OpenDDrainTests(unittest.TestCase):
    def test_stop_waits_for_ingest_processor_and_drains_36_callback_receipts(self):
        import sys
        import threading
        tools = str(Path(__file__).resolve().parents[2] / 'tools/moomoo')
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import push_feed
        from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager
        from market_platform_foundation.market_data.bounded_queue import drain_queue_worker
        received = []
        release, entered = threading.Event(), threading.Event()
        feed = push_feed.MoomooPushFeed(subscriptions=LiveSubscriptionManager(), on_record=received.append)
        for sequence in range(36):
            feed._enqueue_from_payload(capability='US_EQUITY_TICKS', generation=1,
                payload={'code': 'US.AAPL', 'price': 190, 'volume': 5, 'sequence': sequence}, sequence=sequence)
        def gated(**kwargs):
            entered.set()
            release.wait(2)
            drain_queue_worker(**kwargs)
        with patch.object(push_feed, 'drain_queue_worker', gated), \
                patch.object(feed, '_connection_loop', lambda: feed._stop_event.wait(2)):
            feed.start()
            self.assertTrue(entered.wait(2))
            stopper = threading.Thread(target=feed.stop)
            stopper.start()
            release.set()
            stopper.join(3)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(len(received), 36)
        self.assertEqual(feed.queue.depth(), 0)
        self.assertFalse(feed._processor_thread.is_alive())


class IngressFailureTests(unittest.TestCase):
    def test_synthetic_sdk_cleanup_preserves_modules_imported_by_real_runtime(self):
        import sys, types
        from tests.support.pf01_synthetic_providers import SyntheticOpenD
        module = types.ModuleType('pf01_imported_during_transport_fixture')
        patches = SyntheticOpenD().install()
        try:
            sys.modules[module.__name__] = module
        finally:
            for item in reversed(patches):
                item.stop()
        try:
            self.assertIs(sys.modules.get(module.__name__), module)
        finally:
            sys.modules.pop(module.__name__, None)

    def test_ingest_handler_failure_records_received_observation_gap(self):
        import sys
        tools = str(Path(__file__).resolve().parents[2] / 'tools/moomoo')
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import push_feed
        from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            LocalStateConnection(path).close()
            writer = MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',))
            def fail(record):
                raise ValueError('fixture')
            feed = push_feed.MoomooPushFeed(subscriptions=LiveSubscriptionManager(), on_record=fail)
            with patch('market_platform_foundation.market_data.persistence._WRITER', writer):
                feed._enqueue_from_payload(capability='US_EQUITY_TICKS', generation=1,
                    payload={'code': 'US.AAPL', 'price': 190, 'volume': 5, 'sequence': 1}, sequence=1)
                feed._process_envelope(feed.queue.dequeue_batch(timeout=0)[0])
                writer.stop()
            with closing(sqlite3.connect(path)) as db:
                gap = db.execute("SELECT SUM(observations) FROM market_stream_gaps WHERE reason='MOOMOO_INGEST_FAILURE'").fetchone()[0]
            self.assertEqual(gap, 1)
            self.assertEqual(feed.metrics()['handler_errors'], 1)
            self.assertEqual(writer.status()['selected_received'], 0)  # failure precedes writer admission


class ShutdownResultTests(unittest.TestCase):
    def test_collection_only_refuses_success_when_final_writer_drain_failed(self):
        import os, threading
        from unittest.mock import MagicMock
        from tools.ui1 import run_ui_api
        stop = threading.Event()
        stop.set()
        writer = MagicMock()
        writer.status.return_value = {'state': 'FAILED', 'error': 'MARKET_CAPTURE_UNPERSISTED_AT_SHUTDOWN'}
        with patch.dict(os.environ, {}, clear=True), \
                patch('market_platform_foundation.news.supervision.collection_only_reason', return_value=None), \
                patch('market_platform_foundation.news.supervision.require_current_schema'), \
                patch('market_platform_foundation.news.collection.start_collection', return_value=None), \
                patch('market_platform_foundation.market_data.headless_supply.validate_supply', return_value=()), \
                patch('market_platform_foundation.market_data.headless_supply.start_supply', return_value=None), \
                patch('market_platform_foundation.market_data.persistence.start_persistence', return_value=writer), \
                patch('market_platform_foundation.market_data.persistence.stop_persistence') as finish:
            with self.assertRaisesRegex(ValueError, 'MARKET_CAPTURE_UNPERSISTED_AT_SHUTDOWN'):
                run_ui_api.collect_only(stop)
            finish.assert_called_once()

    def test_collection_only_refuses_success_when_producer_drain_is_incomplete(self):
        import os, threading
        from unittest.mock import MagicMock
        from tools.ui1 import run_ui_api
        stop = threading.Event()
        stop.set()
        writer, supply = MagicMock(), MagicMock()
        writer.status.return_value = {'state': 'STOPPED'}
        supply.shutdown_error = 'SUPPLY_SHUTDOWN_INCOMPLETE'
        with patch.dict(os.environ, {}, clear=True), \
                patch('market_platform_foundation.news.supervision.collection_only_reason', return_value=None), \
                patch('market_platform_foundation.news.supervision.require_current_schema'), \
                patch('market_platform_foundation.news.collection.start_collection', return_value=None), \
                patch('market_platform_foundation.market_data.headless_supply.validate_supply', return_value=()), \
                patch('market_platform_foundation.market_data.headless_supply.start_supply', return_value=supply), \
                patch('market_platform_foundation.market_data.headless_supply.stop_supply') as quiesce, \
                patch('market_platform_foundation.market_data.persistence.start_persistence', return_value=writer), \
                patch('market_platform_foundation.market_data.persistence.stop_persistence') as finish:
            with self.assertRaisesRegex(ValueError, 'SUPPLY_SHUTDOWN_INCOMPLETE'):
                run_ui_api.collect_only(stop)
            quiesce.assert_called_once()
            finish.assert_called_once()
