"""PF-01 raw collection: isolated SQLite and synthetic provider receipts only."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.ui_api.screener_news import ScreenerNewsService
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache

NOW = 1791867600.0  # outside US regular trading hours
RAW = {'headline': 'AAPL announces update', 'url': 'https://example.test/a', 'tickers': ['AAPL'],
       'provider_native_id': 'wire-1', 'published_time': '2026-10-13T00:00:00Z',
       'received_time': '2026-10-13T01:00:00Z'}


class RawCollectionTests(unittest.TestCase):
    def service(self, result=None):
        return ScreenerNewsService(finviz=lambda: result or {'success': True, 'items': [RAW]},
            cache=BackgroundCache(clock=lambda: NOW, spawn=lambda job: job()), clock=lambda: NOW,
            synthesizer_factory=lambda: self.fail('collection constructed AI'),
            catalog=lambda _: self.fail('collection polled the universe'), wait_s=0)

    def test_raw_collection_outside_rth_never_scores_or_synthesizes(self):
        service = self.service()
        with patch.object(service, '_score', side_effect=AssertionError('AI/sentiment invoked')):
            records, status = service.collect_raw('finviz', '', 'US_EQUITIES')
        self.assertEqual(status['state'], 'CURRENT')
        self.assertEqual(records[0].event.published_time, RAW['published_time'])
        self.assertEqual(service.provider_requests['finviz'], 1)

    def test_valid_duplicates_are_not_rejected_payloads(self):
        service = self.service({'success': True, 'items': [RAW, RAW]})
        records, status = service.collect_raw('finviz', '', 'US_EQUITIES')
        self.assertEqual(len(records), 1)
        self.assertEqual(status['rejected_count'], 0)

    def test_expired_receipt_during_refresh_is_not_success(self):
        now = [NOW]
        pending = []
        cache = BackgroundCache(clock=lambda: now[0], spawn=pending.append)
        service = ScreenerNewsService(finviz=lambda: {'success': True, 'items': [RAW]},
            cache=cache, clock=lambda: now[0], wait_s=0)
        service.collect_raw('finviz', '', 'US_EQUITIES')
        pending.pop(0)()
        now[0] += 121
        _, status = service.collect_raw('finviz', '', 'US_EQUITIES')
        self.assertEqual(status['state'], 'PENDING')

    def test_http_429_is_rate_limited_even_when_transport_raises(self):
        import urllib.error
        from market_platform_foundation.news.providers import FinnhubNewsClient
        def failure(*args, **kwargs):
            raise urllib.error.HTTPError('https://example.test', 429, 'limit', {}, None)
        client = FinnhubNewsClient(api_key='synthetic', live_enabled=True, http_getter=failure, min_interval_s=0)
        self.assertEqual(client.fetch_news('AAPL')['error'], 'HTTP_429')


class DurableCollectionTests(unittest.TestCase):
    def setUp(self):
        from market_platform_foundation.news.collection import CollectionJob, NewsCollector
        self.Job, self.Collector = CollectionJob, NewsCollector
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(self.connection.close)
        self.now = NOW
        self.calls = []
        self.response = ([RAW], {'state': 'CURRENT', 'fetched_at': RAW['received_time']})
        self.job = self.Job('finviz', '', 'US_EQUITIES', 120)

    def fetch(self, job):
        self.calls.append(job.id)
        return self.response

    def collector(self, jobs=None, **kwargs):
        from market_platform_foundation.news.normalize import normalize_raw_item
        def fetch(job):
            raw, status = self.fetch(job)
            articles = [normalize_raw_item(r, provider_id=job.provider, source_id=job.provider,
                retrieved_time=r.get('received_time') or RAW['received_time']) for r in raw]
            return [(a, {'source_type': 'NEWS'}) for a in articles], status
        return self.Collector(self.connection, jobs or [self.job], fetch, clock=lambda: self.now, **kwargs)

    def records(self):
        return self.connection.execute('SELECT payload_json FROM news_collection_records').fetchall()

    def test_restart_duplicate_preserves_original_clocks_and_source(self):
        collector = self.collector()
        collector.step()
        first = self.records()[0]['payload_json']
        self.now += 180
        self.response = ([{**RAW, 'received_time': '2026-10-13T01:03:00Z'}], {'state': 'CURRENT'})
        self.collector().step()
        self.connection.close()
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(self.connection.close)
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(first, self.records()[0]['payload_json'])
        self.assertEqual(json.loads(first)['article']['provider_id'], 'finviz')

    def test_unknown_publication_stays_unknown(self):
        self.response = ([{**RAW, 'published_time': ''}], {'state': 'CURRENT'})
        self.collector().step()
        article = json.loads(self.records()[0]['payload_json'])['article']
        self.assertEqual(article['published_time'], '')
        self.assertEqual(article['published_time_quality'], 'UNKNOWN')

    def test_failure_backoff_is_persisted_and_other_provider_runs(self):
        self.response = ([], {'state': 'RATE_LIMITED', 'reason': 'HTTP_429'})
        collector = self.collector([self.job, self.Job('rss', '', 'CRYPTO', 300)])
        collector.step()
        restarted = self.collector([self.job, self.Job('rss', '', 'CRYPTO', 300)])
        restarted.step()
        restarted.step()
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(j['next_due'] > self.now for j in restarted.status()['jobs']))

    def test_database_failure_never_advances_success_checkpoint(self):
        collector = self.collector()
        with patch.object(self.connection, 'execute', side_effect=OSError('private credential text')):
            collector.step()
        self.assertNotIn('private', json.dumps(collector.status()))
        self.assertEqual(self.records(), [])

    def test_missing_storage_stops_before_provider_call_and_creates_nothing(self):
        collector = self.collector()
        with patch.object(Path, 'is_file', return_value=False):
            collector.step()
            self.assertEqual(collector.status()['state'], 'RETRYING')
            for _ in range(5):
                self.now += 31
                collector.step()
            self.assertEqual(collector.status()['state'], 'BLOCKED')
            self.assertEqual(collector.status()['reason'], 'COLLECTION_STORAGE_RETRY_LIMIT_EXCEEDED')
        self.assertEqual(self.calls, [])
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir() if not p.name.endswith(('-wal', '-shm'))),
                         ['imp-state.sqlite3'])

    def test_restart_gap_is_explicit_and_only_one_catchup_attempt_runs(self):
        self.collector().step()
        self.now += 86400 * 8
        restarted = self.collector()
        restarted.step()
        restarted.step()
        state = restarted.status()['jobs'][0]
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(state['gap']['state'], 'UNVERIFIED_ROLLING_WINDOW')

    def test_batch_write_and_success_are_atomic(self):
        collector = self.collector()
        original = self.connection.execute
        def fail_checkpoint(sql, params=()):
            if 'UPDATE news_collection_jobs' in sql and 'next_due=' in sql:
                raise OSError('disk full')
            return original(sql, params)
        with patch.object(self.connection, 'execute', side_effect=fail_checkpoint):
            collector.step()
        self.assertEqual(self.records(), [])
        status = collector.status()['jobs'][0]
        self.assertNotIn('last_success', status)

    def test_storage_cap_blocks_without_deleting_records(self):
        collector = self.collector(max_database_bytes=1)
        collector.step()
        self.assertEqual(self.calls, [])
        self.assertEqual(collector.status()['state'], 'BLOCKED')

    def test_stop_prevents_next_job(self):
        collector = self.collector()
        collector.stop()
        collector.step()
        self.assertEqual(self.calls, [])
        self.assertEqual(collector.status()['state'], 'PAUSED')

    def test_interrupted_lease_delays_restart_then_recovers_once(self):
        collector = self.collector()
        self.connection.execute('UPDATE news_collection_jobs SET lease_owner=?,lease_until=?', ('lost-worker', self.now + 120))
        collector.step()
        self.assertEqual(self.calls, [])
        self.now += 121
        collector.step()
        collector.step()
        self.assertEqual(len(self.calls), 1)

    def test_same_database_workers_do_not_refetch_a_fresh_checkpoint(self):
        first, second = self.collector(), self.collector()
        first.step()
        second.step()
        self.assertEqual(len(self.calls), 1)

    def test_pending_adapter_request_retains_lease_against_other_worker(self):
        self.response = ([], {'state': 'PENDING'})
        first, second = self.collector(), self.collector()
        first.step()
        self.now += 6
        second.step()
        self.assertEqual(len(self.calls), 1)
        self.response = ([RAW], {'state': 'CURRENT'})
        first.step()
        self.assertEqual(len(self.records()), 1)

    def test_pending_refresh_preserves_exponential_failure_count(self):
        self.response = ([], {'state': 'RATE_LIMITED'})
        first = self.collector()
        first.step()
        self.now += 241
        self.response = ([], {'state': 'PENDING'})
        first.step()
        self.now += 6
        self.response = ([], {'state': 'RATE_LIMITED'})
        first.step()
        state = first.status()['jobs'][0]
        self.assertEqual(state['failures'], 2)
        self.assertEqual(state['next_due'] - self.now, 480)

    def test_pending_owner_is_renewed_while_other_due_target_runs(self):
        self.response = ([], {'state': 'PENDING'})
        first = self.collector([self.job, self.Job('rss', '', 'CRYPTO', 300)])
        first.step()
        self.now += 119
        first.step()  # new RSS job outranks the pending Finviz poll
        self.now += 2
        second = self.collector()
        second.step()
        self.assertEqual(self.calls.count(self.job.id), 1)

    def test_first_failure_followed_by_restart_retains_initial_coverage_gap(self):
        self.response = ([], {'state': 'AUTH_FAILED'})
        self.collector().step()
        initial = self.now
        self.now += 86400 * 8
        self.response = ([RAW], {'state': 'CURRENT'})
        restarted = self.collector()
        restarted.step()
        state = restarted.status()['jobs'][0]
        self.assertEqual(state['gap']['start'], initial)
        self.assertEqual(state['gap']['state'], 'UNVERIFIED_ROLLING_WINDOW')

    def test_provider_outage_does_not_block_healthy_provider(self):
        collector = self.collector([self.job, self.Job('rss', '', 'CRYPTO', 300)])
        collector.step()
        self.response = ([], {'state': 'AUTH_FAILED'})
        collector.step()
        states = {j['provider']: j['state'] for j in collector.status()['jobs']}
        self.assertEqual(states, {'finviz': 'HEALTHY', 'rss': 'BACKOFF'})

    def test_malformed_payload_and_network_failure_backoff_without_secrets(self):
        for error in (ValueError('malformed private payload'), OSError('network secret token')):
            with self.subTest(error=type(error).__name__):
                self.now += 10000
                collector = self.collector()
                collector.fetch = lambda _: (_ for _ in ()).throw(error)
                collector.step()
                status = collector.status()['jobs'][0]
                self.assertEqual(status['state'], 'BACKOFF')
                self.assertNotIn('private', json.dumps(status))
                self.assertNotIn('token', json.dumps(status))

    def test_partial_success_does_not_claim_complete_coverage(self):
        self.response = ([RAW], {'state': 'PARTIAL', 'rejected_count': 1})
        collector = self.collector()
        collector.step()
        status = collector.status()['jobs'][0]
        self.assertEqual(len(self.records()), 1)
        self.assertNotIn('last_success', status)
        self.assertEqual(status['state'], 'PARTIAL')
        self.assertEqual(collector.status()['coverage'], 'PARTIAL')

    def test_changed_native_identity_headline_appends_revision_and_keeps_first_evidence(self):
        self.collector().step()
        original = self.records()[0]['payload_json']
        self.now += 180
        self.response = ([{**RAW, 'headline': 'Changed title'}], {'state': 'CURRENT'})
        self.collector().step()
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(self.records()[0]['payload_json'], original)
        self.assertEqual(json.loads(self.records()[1]['payload_json'])['article']['headline'], 'Changed title')


class CollectionConfigurationTests(unittest.TestCase):
    def test_disabled_and_replay_do_not_construct_collector(self):
        from market_platform_foundation.news.collection import start_collection
        with patch('market_platform_foundation.ui_api.screener_news.news_service', side_effect=AssertionError('constructed')):
            self.assertIsNone(start_collection('LIVE_OBSERVATIONAL', env={}))
            self.assertIsNone(start_collection('FIXTURE_REPLAY', env={'IMP_NEWS_COLLECTION_ENABLED': '1'}))

    def test_invalid_or_unbounded_targets_are_rejected(self):
        from market_platform_foundation.news.collection import configured_jobs
        for values in ({'IMP_NEWS_COLLECTION_PROVIDERS': 'invented'},
                       {'IMP_NEWS_COLLECTION_PROVIDERS': 'finnhub'},
                       {'IMP_NEWS_COLLECTION_PROVIDERS': 'rss', 'IMP_NEWS_COLLECTION_UNIVERSES': 'UNKNOWN'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                configured_jobs(values)

    def test_relocated_explicit_storage_and_missing_path(self):
        from market_platform_foundation.news.collection import validate_collection_storage
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                validate_collection_storage({'IMP_STATE_DIR': str(root / 'missing')})
            self.assertFalse((root / 'missing').exists())
            relocated = root / 'relocated portable' / 'state-normal'
            relocated.mkdir(parents=True)
            (relocated / 'imp-state.sqlite3').touch()
            self.assertEqual(validate_collection_storage({'IMP_STATE_DIR': str(relocated)}), relocated / 'imp-state.sqlite3')

    def test_newsapi_quota_write_failure_refuses_request(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ScreenerNewsService(newsapi_quota_path=Path(directory) / 'quota.json')
            with patch('market_platform_foundation.local_state.external_cache.write_json_atomic', side_effect=OSError('disk full')):
                self.assertFalse(service._newsapi_guard())


class CollectionMigrationTests(unittest.TestCase):
    def test_v11_upgrade_and_empty_collection_rollback_preserve_all_existing_rows(self):
        from market_platform_foundation.local_state.migrations import MIGRATIONS
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            db = sqlite3.connect(path)
            for version in range(1, 12):
                for sql in MIGRATIONS[version]:
                    db.execute(sql)
                db.execute('INSERT INTO schema_meta VALUES (?,?)', (version, 'original-time'))
            db.execute("INSERT INTO operator_preferences VALUES ('fixture', '{}', 1)")
            db.commit()
            def snapshot():
                schema = db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name").fetchall()
                data = {name: db.execute('SELECT * FROM "'+name+'"').fetchall() for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                return schema, data
            before = snapshot()
            db.close()
            connection = LocalStateConnection(path)
            self.assertEqual(connection.schema_version(), 13)
            connection.close()
            db = sqlite3.connect(path)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM news_collection_records').fetchone()[0], 0)
            db.execute('DROP TABLE news_collection_records')
            db.execute('DROP TABLE news_collection_jobs')
            for table in ('market_stream_records', 'market_stream_checkpoints', 'market_stream_runs', 'market_stream_gaps'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
                db.execute('DROP TABLE '+table)
            db.execute('DELETE FROM schema_meta WHERE schema_version>=12')
            db.commit()
            self.assertEqual(before, snapshot())
            db.close()


class CollectionHttpTests(unittest.TestCase):
    def test_existing_health_endpoint_reports_real_collector_without_acquisition(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        from market_platform_foundation.news import collection
        from market_platform_foundation.ui_api.server import UiApiHandler
        with tempfile.TemporaryDirectory() as directory:
            connection = LocalStateConnection(Path(directory) / 'imp-state.sqlite3')
            job = collection.CollectionJob('finviz', '', 'US_EQUITIES', 120)
            collector = collection.NewsCollector(connection, [job], lambda _: self.fail('status fetched news'))
            with patch.object(collection, '_COLLECTOR', collector), \
                    patch.object(UiApiHandler, 'store', SimpleNamespace(data_mode='LIVE_OBSERVATIONAL'), create=True), \
                    patch('market_platform_foundation.ui_api.live_projections.build_provider_health_payload', return_value={'available': False}), \
                    patch.object(UiApiHandler, '_authorize_request', return_value=True):
                server = ThreadingHTTPServer(('127.0.0.1', 0), UiApiHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    client.request('GET', '/provider/health')
                    response = client.getresponse()
                    payload = json.loads(response.read())
                    client.close()
                    self.assertEqual(response.status, 200, payload)
                    self.assertFalse(payload['raw_collection']['worker_alive'])
                    self.assertEqual(len(payload['raw_collection']['jobs']), 1)
                    self.assertEqual(payload['market_persistence'], {'enabled': False, 'state': 'DISABLED'})
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                    connection.close()


if __name__ == '__main__':
    unittest.main()
