"""PF-01 combined failure and recovery scenarios A-F.

Real supervisor, real ``--collect-only`` child processes, real worker threads and
real SQLite, all on disposable state. Provider gates are off: no network, no
subscription, no AI, no execution. The supervisor clock is real time plus an
offset, so backoffs are skipped without ever letting a lease look expired.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data import persistence
from market_platform_foundation.market_data.persistence import OWNER_LOCK_SUFFIX, _OwnerLock
from market_platform_foundation.news import collection
from market_platform_foundation.news.supervision import (HEALTHY_RESET_SECONDS, RESTART_LIMIT, SUPERVISION_JOB,
    CollectionSupervisor)
from tools.platform.pf01_supervisor import ROOT, OwnedProcess

GATES_OFF = {name: '0' for name in (
    'IMP_PAPER_EXECUTION', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_MOOMOO_PAPER_EXECUTION', 'IMP_LIVE_EXECUTION',
    'IMP_BROKER_LIVE_EXECUTION', 'IMP_LIVE_INTERNAL_SIMULATION', 'IMP_NEWS_RSS_LIVE', 'IMP_MOOMOO_LIVE',
    'IMP_FINVIZ_LIVE', 'IMP_NEWSAPI_LIVE', 'IMP_FINNHUB_LIVE', 'IMP_EDGAR_LIVE', 'IMP_LIVE_OBSERVATIONAL')}


def tick_record(index=1):
    return {'provider': 'moomoo', 'instrument_id': 'AAPL', 'provider_symbol': 'US.AAPL', 'capability': 'US_EQUITY_TICKS',
            'clocks': {'event_time_ns': 1700000000000000000 + index, 'received_time_ns': 1700000001000000000 + index},
            'raw_payload': {'price': 190, 'volume': 5, 'sequence': index}}


class ScenarioCase(unittest.TestCase):
    NEWS, MARKET = '1', '1'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.db = LocalStateConnection(self.path)
        self.db.execute('PRAGMA busy_timeout=50')
        self.addCleanup(self.db.close)
        self.offset = 0.0
        self.processes: list[subprocess.Popen] = []
        self.failing = False
        self.env = {**GATES_OFF, 'IMP_STATE_DIR': self.temp.name, 'IMP_PERSIST_STATE': '1',
                    'IMP_PF01_SUPERVISION_ENABLED': '1',
                    'IMP_NEWS_COLLECTION_ENABLED': self.NEWS, 'IMP_NEWS_COLLECTION_PROVIDERS': 'rss',
                    'IMP_NEWS_COLLECTION_UNIVERSES': 'CRYPTO',
                    'IMP_MARKET_PERSISTENCE_ENABLED': self.MARKET, 'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo',
                    'IMP_MARKET_PERSISTENCE_SYMBOLS': 'AAPL'}

    def clock(self):
        return time.time() + self.offset

    def spawn(self):
        """The supervisor CLI's own child command, or a process that fails at once."""
        env = {**{k: v for k, v in os.environ.items() if not k.startswith('IMP_')}, **self.env,
               'IMP_PF01_SUPERVISOR_OWNER': self.owner.owner}
        command = [sys.executable, '-c', 'raise SystemExit(1)'] if self.failing else \
            [sys.executable, '-B', str(ROOT / 'tools/ui1/run_ui_api.py'), '--collect-only']
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, text=True)
        self.processes.append(process)
        self.addCleanup(self.reap, process)
        return OwnedProcess(process)

    @staticmethod
    def reap(process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=30)
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()

    def supervisor(self):
        self.owner = CollectionSupervisor(self.db, spawn=self.spawn, env=self.env, clock=self.clock)
        self.addCleanup(self.owner.stop)
        return self.owner

    def wait_for(self, condition, seconds=60, message='condition'):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.owner.tick()
            if condition():
                return
            time.sleep(0.2)
        self.fail(f'timed out waiting for {message}: {json.dumps(self.owner.status())}')

    def skip_to_next_start(self):
        """Advance the supervisor clock in steps shorter than the lease, ticking as the CLI loop does."""
        while self.clock() < self.owner.status()['next_start']:
            self.offset += 30
            self.owner.tick()

    def read(self, sql, params=()):
        with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            return db.execute(sql, params).fetchall()

    def child_working(self):
        """The child's news worker has selected and written at least one job: it is past startup."""
        rows = self.read('SELECT payload_json FROM news_collection_jobs WHERE job_id<>?', (SUPERVISION_JOB,))
        return any('last_attempt' in json.loads(row[0]) for row in rows)

    def running(self):
        return self.owner.status()['state'] == 'RUNNING' and self.processes[-1].poll() is None


class ScenarioA(ScenarioCase):
    def test_transient_database_failure_recovers_without_restart_or_supervisor_shutdown(self):
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.child_working(), message='child working')
        child = self.processes[-1]
        blocker = sqlite3.connect(self.path, isolation_level=None)
        try:
            blocker.execute('BEGIN IMMEDIATE')  # every writer in both processes now fails with SQLITE_BUSY
            held = time.monotonic()
            while time.monotonic() - held < 8:  # longer than the child's 5 s busy timeout: its step really fails
                owner.tick()
                time.sleep(0.5)
            self.assertIsNone(child.poll(), 'child exited on a transient lock')
            self.assertEqual(owner.status()['state'], 'RUNNING')
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        released = time.time()
        # The same child keeps working after the lock: its supervised lease is renewed and it is still alive.
        self.wait_for(lambda: self.read('SELECT lease_until FROM news_collection_jobs WHERE job_id=?',
                                        (SUPERVISION_JOB,))[0][0] > released + 100, message='lease renewal')
        for _ in range(8):
            owner.tick(); time.sleep(0.5)
        status = owner.status()
        self.assertIs(self.processes[-1], child)
        self.assertIsNone(child.poll())
        self.assertEqual((status['state'], status['crashes'], status['restarts'], len(self.processes)),
                         ('RUNNING', 0, [], 1))
        owner.stop()
        self.assertEqual(child.wait(timeout=30), 0)  # clean operator stop


class ScenarioB(ScenarioCase):
    PRODUCER = '''import os,sys,time
from pathlib import Path
from market_platform_foundation.market_data import persistence
env={'IMP_MARKET_PERSISTENCE_ENABLED':'1','IMP_STATE_DIR':sys.argv[1],
     'IMP_MARKET_PERSISTENCE_SOURCES':'moomoo','IMP_MARKET_PERSISTENCE_SYMBOLS':'AAPL'}
writer=persistence.start_persistence('LIVE_OBSERVATIONAL',env)
i=int(sys.argv[2])
writer.submit({'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL','capability':'US_EQUITY_TICKS',
    'clocks':{'event_time_ns':i,'received_time_ns':time.time_ns()},'raw_payload':{'price':190,'volume':5,'sequence':i}})
deadline=time.monotonic()+20
while not writer.status()['committed'] and time.monotonic()<deadline: time.sleep(0.02)
print(writer.status()['state'],writer.status()['committed'],flush=True)
sys.stdin.readline()
persistence.stop_persistence()
'''

    def producer(self, index):
        process = subprocess.Popen([sys.executable, '-c', self.PRODUCER, self.temp.name, str(index)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def reap():
            self.reap(process); process.stdout.close()
        self.addCleanup(reap)
        return process, process.stdout.readline().split()

    def test_crash_while_the_writer_lease_is_active_then_safe_restart(self):
        first, result = self.producer(1)
        self.assertEqual(result, ['READY', '1'])
        first.kill(); first.wait(timeout=30)  # abrupt: no shutdown path runs
        (run, lease), = self.read('SELECT run_id,lease_until_ns FROM market_stream_runs WHERE closed_ns IS NULL')
        self.assertGreater(lease, time.time_ns())  # the dead writer's lease is still active
        started = time.monotonic()
        second, result = self.producer(2)
        self.assertEqual(result, ['READY', '1'])
        self.assertLess(time.monotonic() - started, 30)  # not the 120 s lease interval
        self.assertEqual(self.read("SELECT run_id FROM market_stream_gaps WHERE reason='UNCLEAN_RESTART_NO_REPLAY'"), [(run,)])
        # A third process started while the second is alive never becomes a second writer.
        third, result = self.producer(3)
        self.assertEqual(result, ['WAITING_FOR_OWNERSHIP', '0'])
        self.assertEqual(len(self.read('SELECT 1 FROM market_stream_runs WHERE closed_ns IS NULL')), 1)
        second.stdin.write('stop\n'); second.stdin.flush(); second.wait(timeout=30)
        deadline = time.monotonic() + 30
        while len(self.read('SELECT 1 FROM market_stream_records')) < 3 and time.monotonic() < deadline:
            time.sleep(0.2)
        third.stdin.write('stop\n'); third.stdin.flush(); third.wait(timeout=30)
        self.assertEqual(sorted(row[0] for row in self.read('SELECT event_ns FROM market_stream_records')), [1, 2, 3])
        self.assertEqual(self.read('SELECT 1 FROM market_stream_runs WHERE closed_ns IS NULL'), [])


class ScenarioC(ScenarioCase):
    NEWS = '0'

    def test_headless_market_only_process_never_blocks_the_serving_backend_writer(self):
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime

        owner = self.supervisor()
        self.wait_for(self.running, message='headless child')
        for _ in range(12):  # well past child startup: an eager writer would hold the lease by now
            owner.tick(); time.sleep(0.5)
        child = self.processes[-1]
        self.assertIsNone(child.poll())
        self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_runs')[0][0], 0)
        probe = _OwnerLock(Path(str(self.path) + OWNER_LOCK_SUFFIX))
        self.assertTrue(probe.acquire(), 'the idle headless process holds the owner lock')
        probe.release()
        # The serving backend's startup path and its existing admission boundary.
        env = {key: value for key, value in self.env.items() if key.startswith(('IMP_MARKET_', 'IMP_STATE_DIR'))}
        with patch.object(persistence, '_WRITER', None):
            writer = persistence.start_persistence('LIVE_OBSERVATIONAL', env)
            try:
                row = tick_record()
                row.update(capability='US_EQUITY_L1', raw_payload={'ask_price': 191, 'ask_vol': 1, 'bid_price': 190,
                                                                  'bid_vol': 1, 'last_price': 190.5})
                LiveObservationalRuntime().ingest_record(row, wall_now_ns=row['clocks']['received_time_ns'])
                deadline = time.monotonic() + 10
                while not persistence.persistence_status()['committed'] and time.monotonic() < deadline:
                    time.sleep(0.05)
                status = persistence.persistence_status()
                self.assertEqual((status['state'], status['committed'], status['collecting']), ('READY', 1, True))
            finally:
                persistence.stop_persistence()
        owner.tick()
        self.assertIsNone(child.poll())
        self.assertEqual((owner.status()['state'], owner.status()['crashes']), ('RUNNING', 0))
        self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_records')[0][0], 1)


class ScenarioD(ScenarioCase):
    def test_one_unavailable_feed_while_the_others_stay_healthy_through_the_real_worker(self):
        from market_platform_foundation.news.rss_feeds import FEEDS, RssNewsSource
        from market_platform_foundation.ui_api.screener_news import ScreenerNewsService

        requests = []

        def http(url, headers, timeout):
            feed = next(feed.id for feed in FEEDS if feed.url == url)
            requests.append(feed)
            if feed == 'coindesk':
                raise OSError('unreachable')
            return (b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>' + feed.encode() +
                    b' headline</title><link>https://example.test/' + feed.encode() + b'</link><guid>' + feed.encode() +
                    b'</guid></item></channel></rss>')

        rss_env = {'IMP_NEWS_RSS_LIVE': '1', 'SEC_USER_AGENT': 'Fixture Collector fixture@example.test'}
        service = ScreenerNewsService(rss=RssNewsSource(fetch=http, env=rss_env.get),
                                      finviz=lambda: self.fail('finviz polled'), catalog=lambda _: self.fail('universe polled'),
                                      synthesizer_factory=lambda: self.fail('AI constructed'))
        with patch.object(collection, '_COLLECTOR', None), patch.object(collection, '_STARTUP_STATUS', {}), \
             patch('market_platform_foundation.ui_api.screener_news.news_service', return_value=service):
            worker = collection.start_collection('LIVE_OBSERVATIONAL', env=self.env)
            try:
                self.assertIsNotNone(worker)
                deadline = time.monotonic() + 30
                while collection.collection_status()['sources']['PENDING'] and time.monotonic() < deadline:
                    time.sleep(0.2)
                status = collection.collection_status()
                jobs = {job['id'].split(':')[1]: job for job in status['jobs']}
                self.assertEqual(jobs['coindesk']['state'], 'BACKOFF')
                healthy = [feed for feed in jobs if feed != 'coindesk']
                self.assertGreaterEqual(len(healthy), 2)
                for feed in healthy:
                    self.assertEqual(jobs[feed]['state'], 'HEALTHY', feed)
                    self.assertEqual(jobs[feed]['next_due'] - jobs[feed]['last_success'], 300, feed)
                self.assertGreater(jobs['coindesk']['next_due'], max(jobs[feed]['next_due'] for feed in healthy))
                self.assertEqual((status['coverage'], status['sources']['BACKOFF'], status['worker_alive']),
                                 ('PARTIAL', 1, True))
                self.assertEqual(status['state'], 'WAITING')  # partial coverage is not a blocked collector
            finally:
                collection.stop_collection()
        stored = sorted(row[0] for row in self.read('SELECT source_id FROM news_collection_records'))
        self.assertEqual(stored, sorted(healthy))
        self.assertEqual(requests.count('coindesk'), 1)


class ScenarioE(ScenarioCase):
    def test_exhausted_restart_allowance_cools_down_then_recovers_and_resets(self):
        owner = self.supervisor()
        self.failing = True
        owner.tick()
        for _ in range(RESTART_LIMIT):
            self.wait_for(lambda: owner.status()['state'] == 'BACKOFF', message='backoff')
            self.skip_to_next_start()
        self.wait_for(lambda: owner.status()['state'] == 'COOLDOWN', message='cooldown')
        self.assertEqual(len(self.processes), 1 + RESTART_LIMIT)
        self.assertEqual(owner.status()['reason'], 'RESTART_LIMIT_EXCEEDED')
        for _ in range(10):  # cooling down: alive, owning, starting nothing
            self.offset += 30; owner.tick()
        self.assertEqual(len(self.processes), 1 + RESTART_LIMIT)
        self.assertEqual(self.read('SELECT lease_owner FROM news_collection_jobs WHERE job_id=?',
                                   (SUPERVISION_JOB,))[0][0], owner.owner)
        self.failing = False  # whatever was failing is fixed
        self.skip_to_next_start()
        self.wait_for(lambda: self.running() and self.child_working(), message='recovered child')
        recovered = self.processes[-1]
        healthy_from = self.clock()
        while self.clock() - healthy_from < HEALTHY_RESET_SECONDS + 30:
            self.offset += 30; owner.tick()
        status = owner.status()
        self.assertIsNone(recovered.poll())
        self.assertEqual((status['state'], status['restarts'], status['cooldowns']), ('RUNNING', [], 0))
        reasons = [event['reason'] for event in status['events']]
        self.assertIn('RESTART_LIMIT_EXCEEDED', reasons)
        self.assertIn('RESTART_BUDGET_RESET_AFTER_HEALTHY_PERIOD', reasons)
        self.assertEqual(status['crashes'], 1 + RESTART_LIMIT)  # history survives the reset


class ScenarioF(ScenarioCase):
    def test_storage_outage_with_pending_news_and_market_work_then_recovery(self):
        from market_platform_foundation.news.normalize import normalize_raw_item

        fetched = []

        def fetch(job):
            fetched.append(job.id)
            article = normalize_raw_item({'headline': 'Synthetic update', 'url': 'https://example.test/' + job.query,
                                          'provider_native_id': job.query, 'published_time': '2026-10-13T00:00:00Z'},
                                         provider_id='rss', source_id=job.query, retrieved_time='2026-10-13T01:00:00Z')
            return [(article, {'fixture': True})], {'state': 'CURRENT'}

        jobs = [collection.CollectionJob('rss', feed, 'CRYPTO', 300) for feed in ('coindesk', 'cointelegraph')]
        news_db = LocalStateConnection(self.path, require_existing=True)
        collector = collection.NewsCollector(news_db, jobs, fetch)
        collector._owns_connection = True
        writer = persistence.MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',), acquire=False)
        self.addCleanup(writer.stop)
        self.addCleanup(collector.stop)
        available = [False]
        before = sorted(p.name for p in self.path.parent.iterdir())
        with patch.object(writer, '_storage_fault', side_effect=lambda: None if available[0] else 'MARKET_STORAGE_UNAVAILABLE'), \
             patch.object(collector, '_storage_fault', side_effect=lambda: None if available[0] else 'UNAVAILABLE'):
            for index in range(5):
                self.assertTrue(writer.submit(tick_record(index)))  # pending market work
            writer.start(); collector.start()                      # pending news work: both jobs are due
            time.sleep(3.5)
            market, news = writer.status(), collector.status()
            self.assertEqual((market['state'], market['committed'], market['backlog']), ('RETRYING', 0, 5))
            self.assertIsNone(market['last_commit_ns'])
            self.assertEqual((news['state'], news['worker_alive']), ('RETRYING', True))
            self.assertEqual(fetched, [])  # no provider call while nothing could be stored
            self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_records')[0][0], 0)
            self.assertEqual(self.read('SELECT COUNT(*) FROM news_collection_records')[0][0], 0)
            self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), before)  # nothing created elsewhere
            available[0] = True
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and (writer.status()['committed'] < 5 or
                    self.read('SELECT COUNT(*) FROM news_collection_records')[0][0] < 2):
                time.sleep(0.2)
            market, news = writer.status(), collector.status()
        self.assertEqual((market['state'], market['committed'], market['backlog'], market['worker_alive']),
                         ('READY', 5, 0, True))
        self.assertEqual((news['coverage'], news['storage_failures'], news['worker_alive']), ('COMPLETE', 0, True))
        self.assertEqual(sorted(fetched), sorted(job.id for job in jobs))  # each source fetched exactly once
        self.assertEqual(self.read("SELECT COUNT(*) FROM market_stream_gaps WHERE reason IN ('WRITER_FAILURE','QUEUE_OVERFLOW')")[0][0], 0)
        checkpoint = writer.checkpoints()[0]
        self.assertEqual(checkpoint['event_ns'], 1700000000000000000 + 4)


if __name__ == '__main__':
    unittest.main()
