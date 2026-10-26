"""A slow disk or a busy neighbour is waited out, not turned into an outage (2026-10-21..23 'database is locked').

The market writer and the news collector retry lock contention for a window instead of six attempts; the writer
no longer flushes the disk inside its commit; a supervised child skips the whole-store integrity scan its
supervisor already ran; the supervisor can keep the child's output.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from market_platform_foundation.local_state.connection import (LocalStateConnection, lock_contention_error,
                                                               transient_storage_error)
from market_platform_foundation.market_data.persistence import (BUSY_TIMEOUT_MS, WAL_SIZE_LIMIT_BYTES,
                                                                MarketStreamWriter)
from market_platform_foundation.news.collection import RETRY_LIMIT, CollectionJob, NewsCollector
from tools.platform import pf01_supervisor

TICK = {'provider': 'moomoo', 'instrument_id': 'AAPL', 'provider_symbol': 'US.AAPL', 'capability': 'US_EQUITY_TICKS',
        'clocks': {'received_time_ns': 1700000000000000000}, 'raw_payload': {'price': 10, 'volume': 1, 'sequence': 1}}


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.state = LocalStateConnection(self.path)
        self.addCleanup(self.state.close)

    def hold_lock(self):
        blocker = sqlite3.connect(self.path, isolation_level=None)
        blocker.execute('BEGIN IMMEDIATE')
        return blocker

    def count(self, sql):
        return self.state.execute(sql).fetchone()[0]


class ContentionClassTests(unittest.TestCase):
    def test_only_busy_and_locked_are_contention(self):
        self.assertTrue(lock_contention_error(sqlite3.OperationalError('database is locked')))
        self.assertTrue(lock_contention_error(sqlite3.OperationalError('database table is locked')))
        self.assertFalse(lock_contention_error(sqlite3.OperationalError('disk I/O error')))
        self.assertFalse(lock_contention_error(OSError('device not ready')))
        self.assertFalse(lock_contention_error(ValueError('MARKET_STORAGE_UNAVAILABLE')))
        # Every contention error is also transient, so the classes nest.
        self.assertTrue(transient_storage_error(sqlite3.OperationalError('database is locked')))


class WriterConnectionTests(StoreCase):
    def test_writer_commits_without_a_disk_flush_inside_the_lock(self):
        writer = MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',))
        try:
            self.assertEqual(writer.connection.execute('PRAGMA synchronous').fetchone()[0], 1)  # NORMAL
            self.assertEqual(writer.connection.execute('PRAGMA busy_timeout').fetchone()[0], BUSY_TIMEOUT_MS)
            self.assertEqual(writer.connection.execute('PRAGMA journal_size_limit').fetchone()[0], WAL_SIZE_LIMIT_BYTES)
            self.assertEqual(writer.batch_limit, 256)
        finally:
            writer.stop()


class WriterLockWindowTests(StoreCase):
    def run_writer(self, writer, on_wait):
        """Run the writer loop on this thread; on_wait(seconds, calls) decides when contention ends."""
        targets, waits = [], []

        def thread(**kwargs):
            targets.append(kwargs['target'])
            value = MagicMock()
            value.is_alive.return_value = False
            return value

        def stop_wait(seconds):
            waits.append(seconds)
            on_wait(len(waits))
            return False

        def wake_wait(_seconds):
            if writer.status()['committed']:
                writer._stop.set()  # the loop has stored the record: end the test run
            return True

        with patch('market_platform_foundation.market_data.persistence.threading.Thread', side_effect=thread), \
             patch.object(writer._wake, 'wait', side_effect=wake_wait), \
             patch.object(writer._stop, 'wait', side_effect=stop_wait):
            writer.start()
            targets[0]()
        return waits

    def test_contention_past_six_attempts_keeps_retrying_then_stores_everything(self):
        writer = MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',), busy_timeout_ms=50)
        self.assertTrue(writer.submit(dict(TICK)))
        blocker = self.hold_lock()
        seen = {}

        def on_wait(calls):
            if calls == 8:
                # The stand-in thread reads as dead, so status() would say FAILED; read the loop's own state.
                seen.update(writer.status(), loop_state=writer._state)
                blocker.execute('ROLLBACK')
                blocker.close()

        waits = self.run_writer(writer, on_wait)
        self.assertEqual(waits, [1, 2, 4, 5, 5, 5, 5, 5])  # short backoff: commits resume soon after release
        self.assertEqual((seen['loop_state'], seen['consecutive_failures'], seen['lock_contention']),
                         ('RETRYING', 8, True))
        self.assertGreaterEqual(seen['retrying_seconds'], 0)
        status = writer.status()
        self.assertEqual((status['state'], status['committed'], status['accepting']), ('READY', 1, True))
        self.assertIsNone(status['retrying_seconds'])
        writer._thread = None
        writer.stop()
        self.assertEqual(self.count('SELECT COUNT(*) FROM market_stream_records'), 1)
        self.assertEqual(self.count("SELECT COUNT(*) FROM market_stream_gaps WHERE reason LIKE 'WRITER_%'"), 0)

    def test_contention_past_the_window_still_gives_up_visibly(self):
        writer = MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',), busy_timeout_ms=50,
                                    lock_retry_window=0)
        self.assertTrue(writer.submit(dict(TICK)))
        blocker = self.hold_lock()
        try:
            waits = self.run_writer(writer, lambda calls: None)
        finally:
            blocker.execute('ROLLBACK')
            blocker.close()
        self.assertEqual(waits, [1, 2, 4, 5, 5])
        status = writer.status()
        self.assertEqual((status['state'], status['error'], status['accepting']),
                         ('FAILED', 'WRITER_RETRY_LIMIT_EXCEEDED', False))
        writer._thread = None
        writer.stop()

    def test_window_comes_from_the_environment(self):
        with patch.dict('os.environ', {'IMP_MARKET_WRITER_RETRY_WINDOW_SEC': '42'}):
            writer = MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',))
        try:
            self.assertEqual(writer.status()['lock_retry_window_seconds'], 42.0)
        finally:
            writer.stop()


class NewsLockWindowTests(StoreCase):
    def collector(self):
        self.now = 1_800_000_000.0
        self.fetched = []

        def fetch(job):
            self.fetched.append(job.id)
            return [], {'state': 'CURRENT'}

        self.state.execute('PRAGMA busy_timeout=50')
        return NewsCollector(self.state, [CollectionJob('rss', 'coindesk', 'CRYPTO', 300)], fetch,
                             clock=lambda: self.now)

    def attempts(self, collector, count):
        states = []
        for _ in range(count):
            collector.step()
            states.append(collector.status()['state'])
            self.now += 6  # past the 5 s contention backoff
        return states

    def test_contention_past_six_attempts_is_retried_not_blocked(self):
        collector = self.collector()
        blocker = self.hold_lock()
        try:
            states = self.attempts(collector, RETRY_LIMIT + 4)
        finally:
            blocker.execute('ROLLBACK')
            blocker.close()
        self.assertEqual(set(states), {'RETRYING'})
        self.assertEqual(self.fetched, [])  # no provider call while the job cannot be selected
        collector.step()
        self.assertEqual(collector.status()['storage_failures'], 0)
        self.assertEqual(len(self.fetched), 1)

    def test_contention_past_the_window_blocks(self):
        with patch.dict('os.environ', {'IMP_NEWS_STORAGE_RETRY_WINDOW_SEC': '0'}):
            collector = self.collector()
        blocker = self.hold_lock()
        try:
            states = self.attempts(collector, RETRY_LIMIT)
        finally:
            blocker.execute('ROLLBACK')
            blocker.close()
        self.assertEqual(states[-1], 'BLOCKED')
        self.assertEqual(collector.status()['reason'], 'COLLECTION_STORAGE_RETRY_LIMIT_EXCEEDED')


class SupervisedIntegrityTests(StoreCase):
    def opened_with_check(self, owner, verify=None):
        env = {key: value for key, value in os.environ.items() if key != 'IMP_PF01_SUPERVISOR_OWNER'}
        if owner:
            env['IMP_PF01_SUPERVISOR_OWNER'] = owner
        with patch.dict('os.environ', env, clear=True), \
             patch.object(LocalStateConnection, '_verify_or_raise') as check:
            LocalStateConnection(self.path, require_existing=True, verify=verify).close()
        return check.called

    def test_supervised_child_skips_the_whole_store_scan_and_others_keep_it(self):
        self.assertTrue(self.opened_with_check(None))
        self.assertFalse(self.opened_with_check('owner-1'))
        self.assertTrue(self.opened_with_check('owner-1', verify=True))

    def test_a_corrupt_store_still_fails_closed_for_the_first_opener(self):
        self.state.close()
        data = bytearray(self.path.read_bytes())
        Path(str(self.path) + '-wal').unlink(missing_ok=True)
        data[4096:4096 + 64] = b'\xff' * 64  # damage the first table page; the header stays valid
        self.path.write_bytes(bytes(data))
        with self.assertRaises(Exception):
            LocalStateConnection(self.path, require_existing=True, verify=True)


class ChildOutputTests(unittest.TestCase):
    def test_unset_keeps_output_discarded(self):
        self.assertIs(pf01_supervisor.child_output({}), subprocess.DEVNULL)
        self.assertIsNone(pf01_supervisor.child_log_dir({}))

    def test_relative_directory_is_refused(self):
        with self.assertRaises(ValueError) as error:
            pf01_supervisor.child_log_dir({'IMP_PF01_CHILD_LOG_DIR': 'logs'})
        self.assertEqual(str(error.exception), 'CHILD_LOG_DIR_NOT_ABSOLUTE')

    def test_child_reason_reaches_the_daily_log(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {'IMP_PF01_CHILD_LOG_DIR': str(Path(directory) / 'logs')}
            for line in ('first', 'MOOMOO_FEED_UNRECOVERABLE'):
                output = pf01_supervisor.child_output(env)
                try:
                    subprocess.run([sys.executable, '-c', f'import sys; sys.stderr.write({line!r} + "\\n")'],
                                   stdout=output, stderr=output, timeout=30, check=True)
                finally:
                    output.close()
            log = Path(directory) / 'logs' / time.strftime('child-%Y%m%d.log', time.gmtime())
            self.assertEqual(log.read_text(encoding='utf-8').split(), ['first', 'MOOMOO_FEED_UNRECOVERABLE'])


if __name__ == '__main__':
    unittest.main()
