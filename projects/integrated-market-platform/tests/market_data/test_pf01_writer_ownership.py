"""PF-01 market writer: failure classification, restart inside the lease interval and idle ownership.

Disposable SQLite and synthetic observations only. No provider, subscription or network.
"""
from __future__ import annotations

import os
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

from market_platform_foundation.local_state.connection import LocalStateConnection, transient_storage_error
from market_platform_foundation.market_data import persistence
from market_platform_foundation.market_data.persistence import LEASE_NS, OWNER_LOCK_SUFFIX, MarketStreamWriter
from market_platform_foundation.local_state.integrity_receipt import SIDECAR_SUFFIXES

NOT_A_DATABASE = ('-wal', '-shm') + SIDECAR_SUFFIXES  # SQLite's and the integrity receipt's own files


def record(index=1, **changes):
    row = {'provider': 'moomoo', 'instrument_id': 'AAPL', 'provider_symbol': 'US.AAPL',
           'capability': 'US_EQUITY_TICKS',
           'clocks': {'event_time_ns': 1700000000000000000 + index, 'received_time_ns': 1700000001000000000 + index},
           'raw_payload': {'price': 190, 'volume': 5, 'sequence': index}}
    row.update(changes)
    return row


class WriterCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()

    def writer(self, path=None, **kwargs):
        writer = MarketStreamWriter(path or self.path, sources=('moomoo', 'kraken'), symbols=('AAPL', 'BTC/USD'), **kwargs)
        self.addCleanup(writer.stop)
        return writer

    def query(self, sql, path=None):
        with closing(sqlite3.connect((path or self.path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
            return db.execute(sql).fetchall()

    def open_runs(self):
        return self.query('SELECT run_id FROM market_stream_runs WHERE closed_ns IS NULL')

    def gaps(self, reason):
        return self.query(f"SELECT run_id,observations FROM market_stream_gaps WHERE reason='{reason}'")


class FailureClassificationTests(WriterCase):
    def test_error_classes_separate_contention_from_corruption(self):
        blocker = sqlite3.connect(self.path, isolation_level=None)
        other = sqlite3.connect(self.path, isolation_level=None, timeout=0)
        try:
            blocker.execute('BEGIN IMMEDIATE')
            with self.assertRaises(sqlite3.OperationalError) as busy:
                other.execute('BEGIN IMMEDIATE')
            self.assertTrue(transient_storage_error(busy.exception))
        finally:
            blocker.close(); other.close()
        self.assertTrue(transient_storage_error(sqlite3.OperationalError('database is locked')))
        self.assertTrue(transient_storage_error(sqlite3.OperationalError('disk I/O error')))
        self.assertTrue(transient_storage_error(OSError('device not ready')))
        self.assertFalse(transient_storage_error(sqlite3.DatabaseError('database disk image is malformed')))
        self.assertFalse(transient_storage_error(sqlite3.IntegrityError('constraint failed')))
        self.assertFalse(transient_storage_error(sqlite3.OperationalError('no such table: market_stream_records')))
        self.assertFalse(transient_storage_error(ValueError('MARKET_STORAGE_REPLACED')))

    def test_temporary_lock_retries_and_commits_once_without_a_loss_gap(self):
        writer = self.writer()
        blocker = sqlite3.connect(self.path, isolation_level=None)
        try:
            blocker.execute('BEGIN IMMEDIATE')
            writer.submit(record())
            self.assertEqual(writer.flush(), 0)
            status = writer.status()
            self.assertEqual((status['state'], status['error'], status['committed'], status['backlog']),
                             ('RETRYING', 'OperationalError', 0, 1))
            self.assertIsNone(status['last_commit_ns'])
            self.assertEqual(writer.checkpoints(), [])
            self.assertEqual(writer.flush(), 0)
            self.assertEqual(writer.status()['consecutive_failures'], 2)
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        self.assertEqual(writer.flush(), 1)
        status = writer.status()
        self.assertEqual((status['state'], status['consecutive_failures'], status['transient_failures']), ('READY', 0, 2))
        self.assertEqual(len(self.query('SELECT 1 FROM market_stream_records')), 1)
        # Nothing was lost, so no loss evidence is manufactured.
        self.assertEqual(self.gaps('WRITER_FAILURE'), [])

    def test_failed_commit_rolls_back_and_the_retry_is_idempotent(self):
        writer = self.writer()
        for index in range(3):
            writer.submit(record(index))
        original = writer.connection._conn
        calls = {'commit': 0}

        class FailingCommit:
            def __getattr__(self, name): return getattr(original, name)
            def execute(self, sql, *args):
                if sql == 'COMMIT' and not calls['commit']:
                    calls['commit'] += 1
                    raise sqlite3.OperationalError('disk I/O error')
                return original.execute(sql, *args)

        writer.connection._conn = FailingCommit()
        try:
            self.assertEqual(writer.flush(), 0)
        finally:
            writer.connection._conn = original
        self.assertFalse(writer.connection.in_transaction)
        self.assertEqual(writer.status()['state'], 'RETRYING')
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 0)
        self.assertEqual(writer.checkpoints(), [])
        self.assertEqual(writer.flush(), 3)
        self.assertEqual(writer.flush(), 0)
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 3)
        self.assertEqual((writer.status()['committed'], writer.status()['duplicates']), (3, 0))

    def test_replaced_store_is_permanent_and_never_written(self):
        writer = self.writer()
        writer.submit(record())
        writer._identity = (writer._identity[0], writer._identity[1] + 1)
        self.assertEqual(writer.flush(), 0)
        self.assertEqual((writer.status()['state'], writer.status()['error']), ('FAILED', 'MARKET_STORAGE_REPLACED'))
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 0)

    def test_missing_storage_is_retried_then_stops_and_creates_no_alternate_database(self):
        writer = self.writer()
        writer.submit(record())
        with patch.object(writer, '_storage_fault', return_value='MARKET_STORAGE_UNAVAILABLE'), \
             patch.object(writer._wake, 'wait', return_value=True), patch.object(writer._stop, 'wait', return_value=False):
            writer.start()
            writer._thread.join(timeout=5)
        status = writer.status()
        self.assertEqual((status['state'], status['error'], status['consecutive_failures']),
                         ('FAILED', 'WRITER_RETRY_LIMIT_EXCEEDED', persistence.RETRY_LIMIT))
        self.assertFalse(status['accepting'])
        self.assertEqual(status['backlog'], 1)  # still held, still reported as not durable
        names = sorted(p.name for p in self.path.parent.iterdir() if not p.name.endswith(NOT_A_DATABASE))
        self.assertEqual(names, ['imp-state.sqlite3', 'imp-state.sqlite3' + OWNER_LOCK_SUFFIX])

    def test_storage_returning_inside_the_retry_budget_recovers_without_restart(self):
        writer = self.writer()
        writer.submit(record())
        available = threading.Event()
        with patch.object(writer, '_storage_fault', side_effect=lambda: None if available.is_set() else 'MARKET_STORAGE_UNAVAILABLE'), \
             patch.object(writer._stop, 'wait', side_effect=lambda seconds: available.set() or False):
            writer.start()
            deadline = time.monotonic() + 5
            while not writer.status()['committed'] and time.monotonic() < deadline:
                time.sleep(0.01)
            status = writer.status()
            self.assertEqual((status['committed'], status['state'], status['worker_alive']), (1, 'READY', True))
            self.assertGreaterEqual(status['transient_failures'], 1)

    def test_backpressure_holds_during_retry_and_overflow_is_counted_not_hidden(self):
        writer = self.writer(queue_limit=4, batch_limit=4)
        with patch.object(writer, '_storage_ok', return_value=False):
            accepted = sum(writer.submit(record(index)) for index in range(7))
            writer.flush()
        self.assertEqual((accepted, writer.status()['backlog'], writer.status()['rejected']), (4, 4, 3))
        self.assertEqual(writer.flush(), 4)
        self.assertEqual(self.gaps('QUEUE_OVERFLOW')[0][1], 3)

    def test_lost_lease_never_commits_on_the_old_run_and_reacquires_through_the_fence(self):
        writer = self.writer()
        writer.submit(record(1)); writer.flush()
        old_run = writer.run_id
        with closing(sqlite3.connect(self.path)) as db:  # the lease lapsed while the process was suspended
            db.execute('UPDATE market_stream_runs SET lease_until_ns=1 WHERE run_id=?', (old_run,)); db.commit()
        writer.submit(record(2))
        self.assertEqual(writer.flush(), 0)
        self.assertEqual((writer.status()['state'], writer.status()['error'], writer.status()['ownership']),
                         ('RETRYING', 'MARKET_CAPTURE_LEASE_LOST', 'NOT_HELD'))
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 1)
        self.assertEqual(writer.flush(), 1)
        self.assertNotEqual(writer.run_id, old_run)
        self.assertEqual([row[0] for row in self.gaps('UNCLEAN_RESTART_NO_REPLAY')], [old_run])
        self.assertEqual(self.open_runs(), [(writer.run_id,)])

    def test_interrupted_process_leaves_committed_watermark_consistent(self):
        script = '''import os,sys
from pathlib import Path
from market_platform_foundation.market_data.persistence import MarketStreamWriter
w=MarketStreamWriter(Path(sys.argv[1]),sources=('moomoo',),symbols=('AAPL',))
def row(i): return {'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL','capability':'US_EQUITY_TICKS',
    'clocks':{'event_time_ns':1700000000000000000+i,'received_time_ns':1700000001000000000+i},'raw_payload':{'price':190,'volume':5,'sequence':i}}
w.submit(row(1)); w.flush(); w.submit(row(2))
os._exit(9)
'''
        self.assertEqual(subprocess.run([sys.executable, '-c', script, str(self.path)], timeout=30).returncode, 9)
        writer = self.writer()
        checkpoint = writer.checkpoints()[0]
        rows = self.query('SELECT record_id,event_ns FROM market_stream_records')
        self.assertEqual(len(rows), 1)
        self.assertEqual((checkpoint['last_record_id'], checkpoint['event_ns']), rows[0])
        self.assertEqual(len(self.gaps('UNCLEAN_RESTART_NO_REPLAY')), 1)


class RestartInsideLeaseIntervalTests(WriterCase):
    CHILD = '''import os,sys,time
from pathlib import Path
from market_platform_foundation.market_data.persistence import MarketStreamWriter
w=MarketStreamWriter(Path(sys.argv[1]),sources=('moomoo',),symbols=('AAPL',))
w.submit({'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL','capability':'US_EQUITY_TICKS',
    'clocks':{'event_time_ns':1,'received_time_ns':time.time_ns()},'raw_payload':{'price':190,'volume':5,'sequence':1}})
w.flush()
print('owning',flush=True)
if sys.argv[2]=='crash': os._exit(7)
sys.stdin.readline()
w.stop()
'''

    def child(self, mode):
        process = subprocess.Popen([sys.executable, '-c', self.CHILD, str(self.path), mode], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True)
        def reap():
            process.kill(); process.wait(timeout=30)
            process.stdin.close(); process.stdout.close()
        self.addCleanup(reap)
        self.assertEqual(process.stdout.readline().strip(), 'owning')
        return process

    def test_clean_shutdown_releases_immediately(self):
        first = self.writer(); first.submit(record()); first.flush(); first.stop()
        self.assertEqual(self.open_runs(), [])
        second = self.writer()
        self.assertEqual(second.status()['state'], 'READY')
        self.assertEqual(self.gaps('UNCLEAN_RESTART_NO_REPLAY'), [])

    def test_abrupt_termination_is_taken_over_inside_the_lease_interval(self):
        process = self.child('crash'); process.wait(timeout=30)
        (run, lease), = self.query('SELECT run_id,lease_until_ns FROM market_stream_runs WHERE closed_ns IS NULL')
        self.assertGreater(lease, time.time_ns() + LEASE_NS // 2)  # the dead writer's lease is far from expiry
        started = time.monotonic()
        writer = self.writer()
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(writer.status()['state'], 'READY')
        self.assertEqual([row[0] for row in self.gaps('UNCLEAN_RESTART_NO_REPLAY')], [run])
        writer.submit(record(2)); self.assertEqual(writer.flush(), 1)
        self.assertEqual(len(self.query('SELECT 1 FROM market_stream_records')), 2)

    def test_live_competing_writer_is_never_overridden_even_with_an_expired_lease(self):
        process = self.child('hold')
        try:
            with self.assertRaisesRegex(ValueError, 'MARKET_CAPTURE_OWNER_ACTIVE'):
                self.writer()
            with closing(sqlite3.connect(self.path)) as db:  # a stalled but living owner
                db.execute('UPDATE market_stream_runs SET lease_until_ns=1'); db.commit()
            with self.assertRaisesRegex(ValueError, 'MARKET_CAPTURE_OWNER_ACTIVE'):
                self.writer()
            self.assertEqual(len(self.open_runs()), 1)
        finally:
            process.stdin.write('stop\n'); process.stdin.flush(); process.wait(timeout=30)

    def test_stale_writer_after_lease_expiry_is_recovered_with_gap(self):
        process = self.child('crash'); process.wait(timeout=30)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE market_stream_runs SET lease_until_ns=1'); db.commit()
        writer = self.writer()
        self.assertEqual(len(self.gaps('UNCLEAN_RESTART_NO_REPLAY')), 1)
        self.assertEqual(self.open_runs(), [(writer.run_id,)])

    def test_concurrent_startup_race_admits_exactly_one_owner(self):
        barrier = threading.Barrier(6)
        owners, refused = [], []

        def start():
            barrier.wait()
            try:
                owners.append(MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',)))
            except ValueError as exc:
                refused.append(str(exc))
            except sqlite3.OperationalError:
                refused.append('BUSY')

        threads = [threading.Thread(target=start) for _ in range(6)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=30)
        for writer in owners: self.addCleanup(writer.stop)
        self.assertEqual(len(owners), 1)
        self.assertEqual(len(refused), 5)
        self.assertEqual(len(self.open_runs()), 1)

    def test_fenced_writer_cannot_commit_after_its_run_was_closed(self):
        writer = self.writer()
        writer.submit(record(1)); writer.flush()
        with closing(sqlite3.connect(self.path)) as db:  # what a takeover does to the previous run
            db.execute('UPDATE market_stream_runs SET closed_ns=1,lease_until_ns=0'); db.commit()
        intruder = sqlite3.connect(self.path, isolation_level=None)
        try:
            intruder.execute("INSERT INTO market_stream_runs VALUES ('other',1,1,?,NULL)", (time.time_ns() + LEASE_NS,))
            writer.submit(record(2))
            self.assertEqual(writer.flush(), 0)
            self.assertEqual(writer.status()['error'], 'MARKET_CAPTURE_LEASE_LOST')
            self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 1)
        finally:
            intruder.close()

    def test_relocated_store_is_owned_at_its_new_location_without_waiting(self):
        process = self.child('crash'); process.wait(timeout=30)
        relocated = Path(self.temp.name) / 'other-drive' / 'state' / 'imp-state.sqlite3'
        relocated.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(relocated)) as target:
            source.backup(target)
        writer = self.writer(relocated)
        self.assertEqual(writer.status()['state'], 'READY')
        self.assertEqual(len(self.query("SELECT 1 FROM market_stream_gaps WHERE reason='UNCLEAN_RESTART_NO_REPLAY'", relocated)), 1)
        # The original location is untouched: its dead run is still there for its own next owner.
        self.assertEqual(len(self.open_runs()), 1)

    def test_sqlite_contention_during_acquisition_is_retried_not_fatal(self):
        writer = self.writer(acquire=False)
        blocker = sqlite3.connect(self.path, isolation_level=None)
        try:
            blocker.execute('BEGIN IMMEDIATE')
            writer.submit(record())
            self.assertEqual(writer.flush(), 0)
            self.assertEqual((writer.status()['state'], writer.status()['ownership']), ('RETRYING', 'NOT_HELD'))
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        # The failed attempt released the owner lock, so anyone may still acquire.
        self.assertEqual(writer.flush(), 1)
        self.assertEqual(writer.status()['ownership'], 'HELD')

    def test_backend_startup_is_not_blocked_by_a_live_owner_and_reports_the_reason(self):
        process = self.child('hold')
        env = {'IMP_MARKET_PERSISTENCE_ENABLED': '1', 'IMP_STATE_DIR': self.temp.name,
               'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo', 'IMP_MARKET_PERSISTENCE_SYMBOLS': 'AAPL'}
        try:
            with patch.object(persistence, '_WRITER', None):
                writer = persistence.start_persistence('LIVE_OBSERVATIONAL', env)
                try:
                    self.assertIsNotNone(writer)
                    self.assertTrue(writer.submit(record()))
                    deadline = time.monotonic() + 5
                    while persistence.persistence_status()['state'] != 'WAITING_FOR_OWNERSHIP' and time.monotonic() < deadline:
                        time.sleep(0.01)
                    status = persistence.persistence_status()
                    self.assertEqual((status['state'], status['error']), ('WAITING_FOR_OWNERSHIP', 'MARKET_CAPTURE_OWNER_ACTIVE'))
                    self.assertFalse(status['collecting'])
                    self.assertEqual((status['committed'], status['backlog']), (0, 1))
                    # Ownership becomes available: recovery is automatic, no restart.
                    process.stdin.write('stop\n'); process.stdin.flush(); process.wait(timeout=30)
                    deadline = time.monotonic() + 10
                    while not persistence.persistence_status()['committed'] and time.monotonic() < deadline:
                        time.sleep(0.05)
                    status = persistence.persistence_status()
                    self.assertEqual((status['state'], status['committed'], status['collecting']), ('READY', 1, True))
                finally:
                    persistence.stop_persistence()
        finally:
            if process.poll() is None:
                process.stdin.write('stop\n'); process.stdin.flush(); process.wait(timeout=30)


class IdleOwnershipTests(WriterCase):
    ENV = {'IMP_MARKET_PERSISTENCE_ENABLED': '1', 'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo,kraken',
           'IMP_MARKET_PERSISTENCE_SYMBOLS': 'AAPL,BTC/USD'}

    def started(self):
        patcher = patch.object(persistence, '_WRITER', None)
        patcher.start()
        self.addCleanup(patcher.stop)
        writer = persistence.start_persistence('LIVE_OBSERVATIONAL', {**self.ENV, 'IMP_STATE_DIR': self.temp.name})
        self.addCleanup(persistence.stop_persistence)
        return writer

    def test_idle_writer_that_owns_nothing_survives_a_storage_outage_and_stores_the_next_record(self):
        writer = self.writer(acquire=False)
        with patch.object(writer, '_storage_fault', return_value='MARKET_STORAGE_UNAVAILABLE'):
            for _ in range(2 * persistence.RETRY_LIMIT):
                self.assertEqual(writer.flush(), 0)
            status = writer.status()
            self.assertEqual((status['state'], status['consecutive_failures'], status['accepting']), ('IDLE', 0, True))
            # With something to store the outage is a real, bounded retry again.
            writer.submit(record(1))
            writer.flush()
            self.assertEqual((writer.status()['state'], writer.status()['consecutive_failures']), ('RETRYING', 1))
        self.assertEqual(writer.flush(), 1)
        self.assertEqual(writer.status()['state'], 'READY')

    def test_idle_market_only_startup_owns_nothing(self):
        writer = self.started()
        time.sleep(0.05)
        writer.flush()
        status = writer.status()
        self.assertEqual((status['state'], status['ownership'], status['collecting'], status['worker_alive']),
                         ('IDLE', 'NOT_HELD', False, True))
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_runs')[0][0], 0)
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_gaps')[0][0], 0)

    def test_serving_backend_owns_while_an_idle_headless_writer_is_running(self):
        self.started()
        backend = self.writer()  # eager acquisition, as a supplied process would do on its first record
        backend.submit(record()); self.assertEqual(backend.flush(), 1)
        self.assertEqual(self.open_runs(), [(backend.run_id,)])

    def test_first_observation_after_idle_acquires_and_commits(self):
        writer = self.started()
        self.assertTrue(writer.submit(record()))
        deadline = time.monotonic() + 5
        while not writer.status()['committed'] and time.monotonic() < deadline:
            time.sleep(0.01)
        status = writer.status()
        self.assertEqual((status['committed'], status['ownership'], status['collecting']), (1, 'HELD', True))
        self.assertEqual(len(self.gaps('INITIAL_COVERAGE_UNVERIFIED')), 1)

    def test_lease_is_released_after_the_idle_period_and_reacquired_on_new_supply(self):
        writer = self.writer(acquire=False, idle_release_seconds=30)
        clock = [1000.0]
        with patch.object(persistence.time, 'monotonic', side_effect=lambda: clock[0]):
            writer.submit(record(1)); self.assertEqual(writer.flush(), 1)
            first_run = writer.run_id
            clock[0] += 29; writer.flush()
            self.assertEqual(writer.status()['ownership'], 'HELD')
            clock[0] += 1; writer.flush()
            self.assertEqual((writer.status()['state'], writer.status()['ownership'], writer.status()['idle_releases']),
                             ('IDLE', 'NOT_HELD', 1))
            self.assertEqual(self.open_runs(), [])  # closed cleanly: nothing to wait for
            other = self.writer(); other.stop()      # another process may own at once
            writer.submit(record(2)); self.assertEqual(writer.flush(), 1)
            self.assertNotEqual(writer.run_id, first_run)
            self.assertEqual(self.gaps('UNCLEAN_RESTART_NO_REPLAY'), [])
            self.assertEqual(len(self.gaps('CAPTURE_DOWNTIME_UNVERIFIED')), 2)

    def test_supply_keeps_ownership_past_the_idle_period(self):
        writer = self.writer(acquire=False, idle_release_seconds=30)
        clock = [1000.0]
        with patch.object(persistence.time, 'monotonic', side_effect=lambda: clock[0]):
            for index in range(4):
                clock[0] += 20
                writer.submit(record(index)); writer.flush()
            self.assertEqual((writer.status()['ownership'], writer.status()['idle_releases']), ('HELD', 0))

    def test_two_lazy_writers_cannot_both_become_active(self):
        first, second = self.writer(acquire=False), self.writer(acquire=False)
        first.submit(record(1)); second.submit(record(2))
        self.assertEqual(first.flush(), 1)
        self.assertEqual(second.flush(), 0)
        self.assertEqual((second.status()['state'], second.status()['backlog']), ('WAITING_FOR_OWNERSHIP', 1))
        self.assertEqual(len(self.open_runs()), 1)
        first.stop()
        self.assertEqual(second.flush(), 1)
        self.assertEqual(len(self.query('SELECT 1 FROM market_stream_records')), 2)

    def test_producer_disconnect_and_reconnect_across_an_idle_release(self):
        from unittest.mock import MagicMock
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime

        writer = self.writer(acquire=False, idle_release_seconds=30)
        clock = [1000.0]
        trade = record(provider='KRAKEN', instrument_id='BTC/USD', provider_symbol='BTC/USD', capability='CRYPTO_TRADES',
                       raw_payload={'trade_id': 1, 'price': 60000, 'qty': 1})
        with patch.object(persistence.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(persistence, 'active_writer', return_value=writer):
            writer.submit(trade); writer.flush()
            runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
            runtime._connection = MagicMock()
            runtime._disconnect('IDLE')
            writer.flush()
            self.assertEqual(len(self.gaps('KRAKEN_DISCONNECT_NO_REPLAY')), 1)
            clock[0] += 31; writer.flush()
            self.assertEqual(writer.status()['ownership'], 'NOT_HELD')
            writer.submit({**trade, 'raw_payload': {'trade_id': 2, 'price': 60001, 'qty': 1}})
            self.assertEqual(writer.flush(), 1)
            self.assertEqual(writer.status()['ownership'], 'HELD')

    def test_shutdown_while_idle_is_clean_and_idempotent(self):
        writer = self.started()
        persistence.stop_persistence(); persistence.stop_persistence()
        self.assertEqual(writer.status()['state'], 'STOPPED')
        self.assertFalse(writer.status()['worker_alive'])
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_runs')[0][0], 0)
        self.assertIsNone(persistence.active_writer())
        second = self.writer()  # the owner lock was not left behind
        self.assertEqual(second.status()['state'], 'READY')

    def test_unstored_records_at_shutdown_without_ownership_are_reported_not_hidden(self):
        owner = self.writer()
        waiting = self.writer(acquire=False)
        waiting.submit(record())
        waiting.stop()
        self.assertEqual((waiting.status()['state'], waiting.status()['error']),
                         ('FAILED', 'MARKET_CAPTURE_UNPERSISTED_AT_SHUTDOWN'))
        self.assertEqual(self.query('SELECT COUNT(*) FROM market_stream_records')[0][0], 0)
        self.assertEqual(self.open_runs(), [(owner.run_id,)])

    def test_idle_startup_opens_no_socket_and_builds_no_provider_runtime(self):
        import socket
        from market_platform_foundation.crypto_market import kraken_stream
        from market_platform_foundation.market_data import live_runtime

        with patch.object(socket, 'socket', side_effect=AssertionError('network')), \
             patch.object(socket, 'create_connection', side_effect=AssertionError('network')), \
             patch.object(kraken_stream.KrakenStreamRuntime, 'subscribe', side_effect=AssertionError('subscription')), \
             patch.object(live_runtime.LiveObservationalRuntime, 'subscribe', side_effect=AssertionError('subscription')), \
             patch.dict(os.environ, {}, clear=False):
            writer = self.started()
            writer.flush()
            persistence.stop_persistence()
        self.assertEqual(writer.status()['state'], 'STOPPED')


if __name__ == '__main__':
    unittest.main()
