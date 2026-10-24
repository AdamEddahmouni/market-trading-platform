"""PF-01 news collection: one source per job, independent backoff, storage retries. Synthetic feeds only."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.news import collection
from market_platform_foundation.news.collection import (OPERATOR_BACKOFF_CAP, OUTAGE_BACKOFF_CAP, RETRY_LIMIT,
    CollectionJob, NewsCollector, configured_jobs)
from market_platform_foundation.news.rss_feeds import FEEDS, FEEDS_BY_ID, RssNewsSource
from market_platform_foundation.ui_api.screener_news import ScreenerNewsService
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache

NOW = 1791867600.0
RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>fixture</title>
<item><title>%s</title><link>https://example.test/%s</link><guid>%s</guid>
<pubDate>Tue, 13 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''


class FeedIsolationCase(unittest.TestCase):
    """The real RSS source, news service and collector, with only the HTTP fetch replaced."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(self.connection.close)
        self.now = NOW
        self.requests: list[str] = []
        self.failing: dict[str, Exception] = {}
        self.bodies: dict[str, bytes] = {}
        self.rss_env = {'IMP_NEWS_RSS_LIVE': '1', 'SEC_USER_AGENT': 'Fixture Collector fixture@example.test'}
        self.source = RssNewsSource(fetch=self.http, env=lambda name: self.rss_env.get(name), clock=lambda: self.now)
        self.service = ScreenerNewsService(rss=self.source, clock=lambda: self.now, wait_s=0,
            cache=BackgroundCache(clock=lambda: self.now, spawn=lambda job: job()),
            finviz=lambda: self.fail('finviz polled'), catalog=lambda _: self.fail('universe polled'),
            synthesizer_factory=lambda: self.fail('AI constructed'))
        self.jobs = configured_jobs({'IMP_NEWS_COLLECTION_PROVIDERS': 'rss', 'IMP_NEWS_COLLECTION_UNIVERSES': 'CRYPTO'})

    def http(self, url, headers, timeout):
        feed = next(feed.id for feed in FEEDS if feed.url == url)
        self.requests.append(feed)
        if feed in self.failing:
            raise self.failing[feed]
        return self.bodies.get(feed, RSS % (feed.encode() + b' headline', feed.encode(), feed.encode() + b'-1'))

    def fetch(self, job):
        records, status = self.service.collect_raw(job.provider, job.query, job.universe)
        return [(r.event, {'source_type': r.source_type}) for r in records], status

    def collector(self, jobs=None, connection=None):
        collector = NewsCollector(connection or self.connection, jobs or self.jobs, self.fetch, clock=lambda: self.now)
        self.addCleanup(collector.stop)
        return collector

    def drain(self, collector, steps=None):
        for _ in range(steps or len(collector.jobs) + 1):
            collector.step()

    def jobs_by_feed(self, collector):
        return {job['id'].split(':')[1]: job for job in collector.status()['jobs']}

    def stored(self):
        return [row[0] for row in self.connection.execute('SELECT source_id FROM news_collection_records ORDER BY source_id')]


class FeedIsolationTests(FeedIsolationCase):
    def test_every_catalog_feed_is_its_own_job_and_no_feed_is_polled_twice(self):
        jobs = configured_jobs({'IMP_NEWS_COLLECTION_PROVIDERS': 'rss'})
        self.assertEqual(sorted(job.query for job in jobs), sorted(feed.id for feed in FEEDS))
        self.assertTrue(all(job.universe in FEEDS_BY_ID[job.query].universes for job in jobs))
        self.assertEqual({job.interval for job in jobs}, {collection.INTERVALS['rss']})
        crypto = [job.query for job in self.jobs]
        self.assertEqual(sorted(crypto), sorted(f.id for f in FEEDS if 'CRYPTO' in f.universes))
        self.assertIn('coindesk', crypto)

    def test_one_healthy_feed(self):
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['state'], job['failures'], job['inserted_count']), ('HEALTHY', 0, 1))
        self.assertEqual(job['next_due'] - self.now, 300)
        self.assertEqual(collector.status()['coverage'], 'COMPLETE')
        self.assertEqual(self.stored(), ['coindesk'])

    def test_one_failed_feed(self):
        self.failing['coindesk'] = OSError('connection reset by private-host')
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['state'], job['reason'], job['failures']), ('BACKOFF', 'PROVIDER_UNAVAILABLE', 1))
        self.assertNotIn('last_success', job)
        self.assertEqual(collector.status()['coverage'], 'NONE')
        self.assertNotIn('private-host', json.dumps(collector.status()))
        self.assertEqual(self.stored(), [])

    def test_one_failing_feed_does_not_delay_the_healthy_ones(self):
        self.failing['coindesk'] = OSError('down')
        collector = self.collector()
        for _round in range(4):
            self.drain(collector)
            self.now += 300
        jobs = self.jobs_by_feed(collector)
        healthy = [feed for feed in jobs if feed != 'coindesk']
        self.assertTrue(healthy)
        for feed in healthy:
            self.assertEqual((jobs[feed]['state'], jobs[feed]['failures']), ('HEALTHY', 0), feed)
            self.assertEqual(self.requests.count(feed), 4, feed)  # every scheduled poll happened
            self.assertEqual(jobs[feed]['next_due'] - (self.now - 300), 300)
        self.assertEqual(jobs['coindesk']['state'], 'BACKOFF')
        self.assertLess(self.requests.count('coindesk'), 4)  # the failing feed alone is polled less
        status = collector.status()
        self.assertEqual(status['coverage'], 'PARTIAL')
        self.assertEqual(status['sources']['BACKOFF'], 1)
        self.assertEqual(status['sources']['HEALTHY'], len(healthy))
        self.assertNotIn('coindesk', self.stored())

    def test_multiple_failing_feeds_back_off_independently(self):
        failing = [job.query for job in self.jobs][:2]
        self.failing[failing[0]] = OSError('down')
        collector = self.collector()
        self.drain(collector)
        self.now += 300
        self.failing[failing[1]] = OSError('down')
        self.drain(collector)
        jobs = self.jobs_by_feed(collector)
        self.assertEqual(jobs[failing[1]]['failures'], 1)
        self.assertEqual(jobs[failing[1]]['next_due'] - self.now, 600)
        self.assertEqual(jobs[failing[0]]['failures'], 1)  # still inside its own backoff: not polled again
        self.assertNotEqual(jobs[failing[0]]['next_due'], jobs[failing[1]]['next_due'])
        self.assertEqual(collector.status()['sources']['BACKOFF'], 2)

    def test_authentication_failure_backs_off_to_the_operator_cap_only_for_that_feed(self):
        self.failing['coindesk'] = urllib.error.HTTPError('https://example.test', 403, 'forbidden', {}, None)
        collector = self.collector()
        for _ in range(12):
            self.drain(collector)
            self.now = max(self.now + 300, self.jobs_by_feed(collector)['coindesk']['next_due'])
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['provider_state'], job['reason']), ('AUTH_FAILED', 'PROVIDER_AUTH_FAILED'))
        wait = job['next_due'] - job['last_attempt']
        self.assertGreater(wait, OUTAGE_BACKOFF_CAP)  # operator faults may wait far longer than an outage
        self.assertLessEqual(wait, OPERATOR_BACKOFF_CAP)
        others = [other for feed, other in self.jobs_by_feed(collector).items() if feed != 'coindesk']
        self.assertTrue(all(other['state'] == 'HEALTHY' for other in others))

    def test_unconfigured_sec_feed_does_not_hold_back_the_other_feeds(self):
        del self.rss_env['SEC_USER_AGENT']
        collector = self.collector()
        for _round in range(3):
            self.drain(collector)
            self.now += 300
        jobs = self.jobs_by_feed(collector)
        self.assertEqual((jobs['sec_press']['provider_state'], jobs['sec_press']['reason']),
                         ('NOT_CONFIGURED', 'PROVIDER_NOT_CONFIGURED'))
        self.assertNotIn('sec_press', self.requests)  # no declared identity: the SEC is never contacted
        for feed in (feed for feed in jobs if feed != 'sec_press'):
            self.assertEqual(jobs[feed]['state'], 'HEALTHY', feed)
            self.assertEqual(self.requests.count(feed), 3, feed)

    def test_rate_limit_is_respected_and_never_retried_inside_its_backoff(self):
        self.failing['coindesk'] = urllib.error.HTTPError('https://example.test', 429, 'limit', {}, None)
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['provider_state'], job['reason']), ('RATE_LIMITED', 'PROVIDER_RATE_LIMITED'))
        for _ in range(20):
            self.now += 29
            collector.step()
        self.assertEqual(self.requests.count('coindesk'), 1)

    def test_transient_outage_backoff_is_capped_and_recovers_on_the_next_success(self):
        self.failing['coindesk'] = OSError('down')
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        waits = []
        for _ in range(8):
            collector.step()
            job = self.jobs_by_feed(collector)['coindesk']
            waits.append(job['next_due'] - self.now)
            self.now = job['next_due']
        self.assertEqual(waits[:3], [600, 1200, 2400])
        self.assertEqual(max(waits), OUTAGE_BACKOFF_CAP)  # never the day-long wait reserved for operator faults
        del self.failing['coindesk']
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['state'], job['failures']), ('HEALTHY', 0))
        self.assertEqual(job['next_due'] - self.now, 300)
        self.assertEqual(job['gap']['state'], 'UNVERIFIED_ROLLING_WINDOW')  # the outage stays visible

    def test_partial_response_is_neither_success_nor_failure(self):
        self.bodies['coindesk'] = b'''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Valid headline</title><link>https://example.test/a</link><guid>a</guid></item>
<item><title></title><link>https://example.test/b</link><guid>b</guid></item></channel></rss>'''
        records, status = self.service.collect_raw('rss', 'coindesk', 'CRYPTO')
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        collector.fetch = lambda job: ([(r.event, {}) for r in records], {**status, 'rejected_count': 1})
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['state'], job['reason'], job['failures']), ('PARTIAL', 'PARTIAL_RESPONSE', 0))
        self.assertEqual((job['inserted_count'], job['rejected_count'], job['rejected_total']), (len(records), 1, 1))
        self.assertNotIn('last_success', job)      # not complete coverage
        self.assertEqual(job['last_partial'], self.now)
        self.assertEqual(job['next_due'] - self.now, 300)  # and not a backoff either
        self.assertEqual(collector.status()['coverage'], 'PARTIAL')

    def test_nothing_usable_in_a_partial_response_is_a_failure(self):
        collector = self.collector([CollectionJob('rss', 'coindesk', 'CRYPTO', 300)])
        collector.fetch = lambda job: ([], {'state': 'CURRENT', 'rejected_count': 3})
        collector.step()
        self.assertEqual(self.jobs_by_feed(collector)['coindesk']['state'], 'BACKOFF')

    def test_restart_preserves_each_feeds_backoff_checkpoint_and_dedupe(self):
        self.failing['coindesk'] = OSError('down')
        self.drain(self.collector())
        before = self.jobs_by_feed(self.collector())
        polled = len(self.requests)
        self.connection.close()
        self.connection = LocalStateConnection(self.path, require_existing=True)
        self.addCleanup(self.connection.close)
        restarted = self.collector()
        self.drain(restarted)
        after = self.jobs_by_feed(restarted)
        self.assertEqual(len(self.requests), polled)  # nothing is due: no feed is refetched on restart
        for feed in before:
            self.assertEqual((after[feed]['state'], after[feed]['next_due'], after[feed].get('last_success')),
                             (before[feed]['state'], before[feed]['next_due'], before[feed].get('last_success')), feed)
        self.now += 300
        self.drain(restarted)
        self.assertEqual(len(self.stored()), len(self.jobs) - 1)  # the same items again: stored once
        healthy = next(feed for feed in after if feed != 'coindesk')
        self.assertEqual(self.jobs_by_feed(restarted)[healthy]['duplicate_count'], 1)

    def test_unknown_feed_and_disabled_gate_never_reach_the_network(self):
        with self.assertRaisesRegex(ValueError, 'COLLECTION_FEED_INVALID'):
            self.service.collect_raw('rss', 'invented', 'CRYPTO')
        disabled = RssNewsSource(fetch=self.http, env={}.get, clock=lambda: self.now)
        service = ScreenerNewsService(rss=disabled, clock=lambda: self.now, wait_s=0,
                                      cache=BackgroundCache(clock=lambda: self.now, spawn=lambda job: job()))
        _, status = service.collect_raw('rss', 'coindesk', 'CRYPTO')
        self.assertEqual(status['state'], 'LIVE_DISABLED')
        self.assertEqual(self.requests, [])


class NewsStorageRecoveryTests(FeedIsolationCase):
    def setUp(self):
        super().setUp()
        self.jobs = [CollectionJob('rss', 'coindesk', 'CRYPTO', 300)]

    def test_locked_write_is_retried_without_refetching_or_provider_backoff(self):
        self.connection.execute('PRAGMA busy_timeout=50')
        collector = self.collector()
        original = collector.fetch
        blocker = sqlite3.connect(self.path, isolation_level=None)

        def fetch_then_lock(job):
            result = original(job)
            blocker.execute('BEGIN IMMEDIATE')  # the lock arrives after the fetch, before the write
            return result

        collector.fetch = fetch_then_lock
        try:
            collector.step()
            status = collector.status()
            self.assertEqual((status['state'], status['reason'], status['unwritten_batch']),
                             ('RETRYING', 'COLLECTION_STORAGE_RETRY', True))
            self.assertEqual(self.stored(), [])
            self.now += 0.5
            collector.step()  # inside the storage backoff: nothing is attempted
            self.assertEqual(collector.status()['storage_failures'], 1)
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        collector.fetch = original
        self.now += 1
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['state'], job['failures'], job['inserted_count']), ('HEALTHY', 0, 1))
        self.assertEqual(self.requests, ['coindesk'])  # one provider call for the whole incident
        self.assertEqual((collector.status()['state'], collector.status()['unwritten_batch']), ('WAITING', False))
        self.assertEqual(self.stored(), ['coindesk'])

    def test_failed_transaction_never_advances_the_checkpoint(self):
        collector = self.collector()
        original = self.connection.execute

        def fail_checkpoint(sql, params=()):
            if 'UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=?' in sql:
                raise sqlite3.OperationalError('disk I/O error')
            return original(sql, params)

        with patch.object(self.connection, 'execute', side_effect=fail_checkpoint):
            collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual(self.stored(), [])  # the record insert rolled back with the checkpoint
        self.assertNotIn('last_success', job)
        self.assertEqual(job['state'], 'COLLECTING')
        self.assertFalse(self.connection.in_transaction)
        self.now += 1
        collector.step()
        self.assertEqual(self.jobs_by_feed(collector)['coindesk']['state'], 'HEALTHY')
        self.assertEqual(self.stored(), ['coindesk'])

    def test_persistent_storage_failure_blocks_after_the_retry_budget_and_stops_polling(self):
        collector = self.collector()
        with patch.object(collector, '_storage_fault', return_value='UNAVAILABLE'):
            for attempt in range(RETRY_LIMIT):
                collector.step()
                self.assertEqual(collector.status()['state'], 'RETRYING' if attempt < RETRY_LIMIT - 1 else 'BLOCKED')
                self.now += 31
            self.assertEqual(collector.status()['reason'], 'COLLECTION_STORAGE_RETRY_LIMIT_EXCEEDED')
            for _ in range(10):
                collector.step(); self.now += 31
        self.assertEqual(self.requests, [])
        collector.step()  # storage is back: the same collector resumes
        self.assertEqual(self.jobs_by_feed(collector)['coindesk']['state'], 'HEALTHY')
        self.assertEqual(collector.status()['storage_failures'], 0)

    def test_replaced_or_corrupt_storage_is_not_retried(self):
        collector = self.collector()
        with patch.object(collector, '_storage_fault', return_value='REPLACED'):
            collector.step()
        self.assertEqual((collector.status()['state'], collector.status()['reason']),
                         ('BLOCKED', 'STORAGE_UNAVAILABLE_OR_BOUND_EXCEEDED'))
        other = self.collector()
        with patch.object(self.connection, 'execute', side_effect=sqlite3.DatabaseError('database disk image is malformed')):
            other.step()
        self.assertEqual((other.status()['state'], other._storage_failures), ('BLOCKED', 0))
        self.assertEqual(self.requests, [])

    def test_batch_that_outlives_its_lease_is_dropped_with_evidence_not_committed(self):
        collector = self.collector()
        original = collector.fetch
        collector.fetch = lambda job: (original(job), setattr(self, 'now', self.now + 121))[0]
        collector.step()
        job = self.jobs_by_feed(collector)['coindesk']
        self.assertEqual((job['reason'], job['unpersisted_count'], job['lease_until']), ('COLLECTION_LEASE_EXPIRED', 1, 0))
        self.assertNotIn('last_success', job)
        self.assertEqual(self.stored(), [])
        self.assertFalse(collector.status()['unwritten_batch'])


if __name__ == '__main__':
    unittest.main()
