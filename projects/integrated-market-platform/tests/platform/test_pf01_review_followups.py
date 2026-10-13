"""Defects found by the independent review of the PF-01 supervision hardening. Disposable state, no network."""
from __future__ import annotations

import errno
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection, transient_storage_error
from market_platform_foundation.market_data import persistence
from market_platform_foundation.news import collection, supervision
from market_platform_foundation.news.collection import CollectionJob, NewsCollector, configured_jobs
from market_platform_foundation.news.rss_feeds import FEEDS, RssNewsSource
from market_platform_foundation.news.supervision import CHILD_EXIT_PERMANENT
from market_platform_foundation.ui_api.screener_news import ScreenerNewsService
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache
from tools.ui1 import run_ui_api

RSS = (b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>Headline</title>'
       b'<link>https://example.test/a</link><guid>a</guid></item></channel></rss>')


class ReviewCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.env = {'IMP_STATE_DIR': self.temp.name, 'IMP_PERSIST_STATE': '1', 'IMP_NEWS_COLLECTION_ENABLED': '1',
                    'IMP_NEWS_COLLECTION_PROVIDERS': 'rss', 'IMP_NEWS_COLLECTION_UNIVERSES': 'CRYPTO'}


class ChildExitClassificationTests(ReviewCase):
    def child_exit(self, env):
        args = type('Args', (), {'collect_only': True, 'serve': False})()
        with patch.dict(os.environ, env, clear=True), patch.object(run_ui_api, 'parse_args', return_value=args), \
             patch.object(run_ui_api.sys, 'stdin'), patch('builtins.print') as out:
            return run_ui_api.main(), out.call_args.args[0]

    def test_unreadable_store_at_child_start_is_an_ordinary_failure_not_a_latch(self):
        with patch.object(supervision.sqlite3, 'connect', side_effect=sqlite3.OperationalError('disk I/O error')):
            with self.assertRaisesRegex(ValueError, 'SCHEMA_CHECK_STORAGE_UNAVAILABLE'):
                supervision.require_current_schema(self.path)
            code, printed = self.child_exit(self.env)
        self.assertEqual(code, 1)
        self.assertIn('SCHEMA_CHECK_STORAGE_UNAVAILABLE', printed)

    def test_store_read_at_the_wrong_schema_exits_with_the_permanent_code(self):
        db = sqlite3.connect(self.path)
        db.execute('DELETE FROM schema_meta WHERE schema_version > 11'); db.commit(); db.close()
        code, printed = self.child_exit(self.env)
        self.assertEqual(code, CHILD_EXIT_PERMANENT)
        self.assertIn('APPROVED_SCHEMA_MIGRATION_REQUIRED', printed)

    def test_invalid_news_selection_exits_permanent_before_any_worker_starts(self):
        for change in ({'IMP_NEWS_COLLECTION_PROVIDERS': 'invented'}, {'IMP_NEWS_COLLECTION_RSS_SECONDS': 'soon'},
                       {'IMP_NEWS_COLLECTION_PROVIDERS': 'finnhub'}):
            with self.subTest(change=change), patch.object(collection, 'start_collection') as start:
                code, printed = self.child_exit({**self.env, **change})
                self.assertEqual(code, CHILD_EXIT_PERMANENT, printed)
                start.assert_not_called()
                self.assertNotIn('soon', printed)

    def test_execution_gate_still_refuses_the_child(self):
        code, printed = self.child_exit({**self.env, 'IMP_PAPER_EXECUTION': '1'})
        self.assertEqual(code, CHILD_EXIT_PERMANENT)
        self.assertIn('EXECUTION_GATE_ENABLED', printed)

    def test_per_feed_jobs_stay_inside_the_job_bound(self):
        symbols = ','.join(f'S{index}' for index in range(17))
        everything = {'IMP_NEWS_COLLECTION_PROVIDERS': 'rss,finviz,newsapi,finnhub,sec_filings', 'IMP_NEWS_COLLECTION_SYMBOLS': symbols}
        self.assertEqual(len(configured_jobs(everything)), len(FEEDS) + 1 + 3 * 17)
        with self.assertRaisesRegex(ValueError, 'COLLECTION_TARGET_BOUND_EXCEEDED'):
            configured_jobs({**everything, 'IMP_NEWS_COLLECTION_SYMBOLS': symbols + ',S17'})


class FailureClassTests(ReviewCase):
    def test_disk_full_is_not_retried(self):
        self.assertFalse(transient_storage_error(sqlite3.OperationalError('database or disk is full')))

    def test_feed_that_worked_then_hits_a_rate_limit_keeps_the_operator_backoff(self):
        now = [1791867600.0]
        failure = []

        def http(url, headers, timeout):
            if failure:
                raise failure[0]
            return RSS

        service = ScreenerNewsService(rss=RssNewsSource(fetch=http, env={'IMP_NEWS_RSS_LIVE': '1'}.get, clock=lambda: now[0]),
                                      clock=lambda: now[0], wait_s=0, cache=BackgroundCache(clock=lambda: now[0], spawn=lambda job: job()))
        connection = LocalStateConnection(self.path, require_existing=True)
        self.addCleanup(connection.close)
        collector = NewsCollector(connection, [CollectionJob('rss', 'coindesk', 'CRYPTO', 300)],
                                  lambda job: (lambda records, status: ([(r.event, {}) for r in records], status))(
                                      *service.collect_raw(job.provider, job.query, job.universe)), clock=lambda: now[0])
        self.addCleanup(collector.stop)
        collector.step()
        self.assertEqual(collector.status()['jobs'][0]['state'], 'HEALTHY')
        for code, expected in ((429, 'PROVIDER_RATE_LIMITED'), (403, 'PROVIDER_AUTH_FAILED')):
            failure[:] = [urllib.error.HTTPError('https://example.test', code, 'refused', {}, None)]
            now[0] = collector.status()['jobs'][0]['next_due'] + 1
            collector.step()
            job = collector.status()['jobs'][0]
            self.assertEqual((job['state'], job['reason']), ('BACKOFF', expected))
        failure[:] = [OSError('down')]
        now[0] = collector.status()['jobs'][0]['next_due'] + 1
        collector.step()
        self.assertEqual(collector.status()['jobs'][0]['reason'], 'PROVIDER_UNAVAILABLE')

    def test_lock_fault_that_is_not_contention_is_retried_as_storage_not_reported_as_an_owner(self):
        writer = persistence.MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',), acquire=False)
        self.addCleanup(writer.stop)
        writer.gap('FIXTURE')
        module = 'msvcrt.locking' if os.name == 'nt' else 'fcntl.flock'
        with patch(module, side_effect=OSError(errno.ENOSYS, 'locking not supported')):
            self.assertEqual(writer.flush(), 0)
        status = writer.status()
        self.assertEqual((status['state'], status['ownership_waits'], status['consecutive_failures']), ('RETRYING', 0, 1))
        self.assertIsNone(writer._owner_lock._handle)
        with patch(module, side_effect=OSError(errno.EACCES, 'locked')):
            writer.flush()
        self.assertEqual(writer.status()['state'], 'WAITING_FOR_OWNERSHIP')
        writer.flush()
        self.assertEqual(writer.status()['ownership'], 'HELD')


class CollectorBlockTests(ReviewCase):
    def collector(self):
        connection = LocalStateConnection(self.path, require_existing=True)
        self.addCleanup(connection.close)
        self.calls, self.now = [], 1000.0
        collector = NewsCollector(connection, [CollectionJob('rss', 'coindesk', 'CRYPTO', 300)],
                                  lambda job: (self.calls.append(job.id), ([], {'state': 'CURRENT'}))[1], clock=lambda: self.now)
        self.addCleanup(collector.stop)
        self.now = 1000.0
        return collector, connection

    def test_busy_status_read_reports_the_last_known_rows_not_a_blocked_collector(self):
        collector, connection = self.collector()
        collector.step()
        known = collector.status()
        with patch.object(connection, 'execute', side_effect=sqlite3.OperationalError('database is locked')):
            busy = collector.status()
        self.assertEqual((busy['state'], busy['jobs']), (known['state'], known['jobs']))
        with patch.object(connection, 'execute', side_effect=sqlite3.DatabaseError('database disk image is malformed')):
            self.assertEqual(collector.status()['reason'], 'COLLECTION_STATUS_STORAGE_FAILED')

    def test_unrecoverable_storage_failure_stays_blocked_and_stops_polling(self):
        collector, connection = self.collector()
        with patch.object(connection, 'execute', side_effect=sqlite3.DatabaseError('database disk image is malformed')):
            collector.step()
        for _ in range(5):
            self.now += 400
            collector.step()
        status = collector.status()
        self.assertEqual((status['state'], status['reason']), ('BLOCKED', 'COLLECTION_STORAGE_OR_CHECKPOINT_FAILED'))
        self.assertEqual(self.calls, [])

    def test_coverage_ignores_a_poll_in_flight(self):
        collector, connection = self.collector()
        collector.step()
        self.assertEqual(collector.status()['coverage'], 'COMPLETE')
        release, entered = threading.Event(), threading.Event()
        collector.fetch = lambda job: (entered.set(), release.wait(5), ([], {'state': 'CURRENT'}))[2]
        self.now += 301
        thread = threading.Thread(target=collector.step)
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(collector.status()['jobs'][0]['state'], 'COLLECTING')
            self.assertEqual(collector.status()['coverage'], 'UNKNOWN')
        finally:
            release.set(); thread.join(timeout=5)
        self.assertEqual(collector.status()['coverage'], 'COMPLETE')


if __name__ == '__main__':
    unittest.main()
