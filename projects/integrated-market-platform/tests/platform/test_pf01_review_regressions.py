"""Independent PF-01 review defects; synthetic workers/disposable SQLite only."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data import persistence
from market_platform_foundation.news import collection
from market_platform_foundation.news.supervision import CollectionSupervisor, SUPERVISION_JOB
from tools.ui1 import run_ui_api


class ControlledStop:
    def __init__(self):
        self.calls = 0

    def is_set(self):
        return False

    def wait(self, seconds):
        self.calls += 1
        return self.calls > 1


class Worker:
    def __init__(self, state='WAITING'):
        self.state = state

    def status(self):
        return {'state': self.state, 'worker_alive': True}


class OwnedChild:
    def poll(self):
        return None

    def stop(self):
        pass


class IndependentReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.env = {'IMP_STATE_DIR': self.temp.name, 'IMP_PERSIST_STATE': '1',
                    'IMP_NEWS_COLLECTION_ENABLED': '1',
                    'IMP_NEWS_COLLECTION_PROVIDERS': 'rss',
                    'IMP_NEWS_COLLECTION_UNIVERSES': 'US_EQUITIES',
                    'IMP_MARKET_PERSISTENCE_ENABLED': '1',
                    'IMP_PF01_SUPERVISION_ENABLED': '1'}

    def run_child(self, writer, collector):
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(persistence, 'start_persistence', return_value=writer), \
             patch.object(persistence, 'stop_persistence') as stop_market, \
             patch.object(collection, 'start_collection', return_value=collector), \
             patch.object(collection, 'stop_collection') as stop_news:
            try:
                run_ui_api.collect_only(ControlledStop())
            finally:
                if writer is not None:
                    stop_market.assert_called_once()
                if collector is not None:
                    stop_news.assert_called_once()

    def test_requested_news_failure_cannot_hide_behind_started_market_writer(self):
        with self.assertRaisesRegex(ValueError, 'COLLECTION_WORKERS_BLOCKED'):
            self.run_child(Worker('READY'), None)

    def test_requested_market_failure_cannot_hide_behind_started_news_collector(self):
        with self.assertRaisesRegex(ValueError, 'COLLECTION_WORKERS_BLOCKED'):
            self.run_child(None, Worker())

    def test_alive_failed_writer_is_rejected_without_waiting_for_thread_exit(self):
        writer = persistence.MarketStreamWriter(self.path, sources=('kraken',), symbols=('BTC/USD',))
        try:
            with patch.object(writer, '_storage_ok', return_value=False):
                writer.start()
                writer.flush()
                self.assertEqual(writer.status()['state'], 'FAILED')
                self.assertTrue(writer.status()['worker_alive'])
                with self.assertRaisesRegex(ValueError, 'COLLECTION_WORKER_UNHEALTHY'):
                    self.run_child(writer, Worker())
        finally:
            writer.stop()

    def test_alive_blocked_or_stale_news_worker_is_rejected(self):
        for state in ('BLOCKED', 'STALE'):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'COLLECTION_WORKER_UNHEALTHY'):
                self.run_child(Worker('READY'), Worker(state))

    def test_cleanup_retains_durable_blocker_reason(self):
        with LocalStateConnection(self.path, require_existing=True) as db:
            supervisor = CollectionSupervisor(db, spawn=OwnedChild, env=self.env)
            supervisor.tick()
            self.env.update(IMP_NEWS_COLLECTION_ENABLED='0', IMP_MARKET_PERSISTENCE_ENABLED='0')
            supervisor.tick()
            supervisor.stop()
            row = db.execute('SELECT payload_json,lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?',
                             (SUPERVISION_JOB,)).fetchone()
            evidence = json.loads(row['payload_json'])
            self.assertEqual(evidence['state'], 'BLOCKED')
            self.assertEqual(evidence['reason'], 'COLLECTION_DISABLED')
            self.assertIsNone(row['lease_owner'])
            self.assertEqual(row['lease_until'], 0)

    def test_news_storage_lost_after_validation_is_never_recreated(self):
        original_jobs = collection.configured_jobs

        def lose_storage(values):
            jobs = original_jobs(values)
            self.path.unlink()
            return jobs

        with patch.object(collection, '_COLLECTOR', None), \
             patch.object(collection, '_STARTUP_STATUS', {}), \
             patch.object(collection, 'configured_jobs', side_effect=lose_storage), \
             patch.object(collection.NewsCollector, 'start') as start, \
             patch('market_platform_foundation.ui_api.screener_news.news_service') as service:
            worker = collection.start_collection('LIVE_OBSERVATIONAL', env=self.env)
            self.assertIsNone(worker)
            self.assertFalse(self.path.exists())
            self.assertEqual(collection.collection_status()['state'], 'BLOCKED')
            start.assert_not_called()
            service.assert_not_called()

    def test_news_replacement_after_validation_is_not_migrated(self):
        replacement = self.path.with_name('replacement.sqlite3')
        db = sqlite3.connect(replacement)
        try:
            db.execute('CREATE TABLE preserved_marker(value TEXT)')
            db.execute("INSERT INTO preserved_marker VALUES ('synthetic')")
            db.commit()
        finally:
            db.close()
        original_jobs = collection.configured_jobs

        def replace_storage(values):
            jobs = original_jobs(values)
            self.path.unlink()
            replacement.rename(self.path)
            return jobs

        with patch.object(collection, '_COLLECTOR', None), \
             patch.object(collection, '_STARTUP_STATUS', {}), \
             patch.object(collection, 'configured_jobs', side_effect=replace_storage), \
             patch.object(collection.NewsCollector, 'start') as start, \
             patch('market_platform_foundation.ui_api.screener_news.news_service') as service:
            self.assertIsNone(collection.start_collection('LIVE_OBSERVATIONAL', env=self.env))
            start.assert_not_called()
            service.assert_not_called()
        db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            self.assertEqual(db.execute('SELECT value FROM preserved_marker').fetchone()[0], 'synthetic')
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),
                             [('preserved_marker',)])
        finally:
            db.close()

    def test_read_only_supervisor_connections_are_closed_explicitly(self):
        from market_platform_foundation.news import supervision
        from tools.platform import pf01_supervisor
        original_connect = sqlite3.connect
        connections = []

        class TrackedConnection(sqlite3.Connection):
            was_closed = False

            def close(self):
                self.was_closed = True
                return super().close()

        def track(*args, **kwargs):
            connection = original_connect(*args, **kwargs, factory=TrackedConnection)
            connections.append(connection)
            return connection

        try:
            with patch.object(sqlite3, 'connect', side_effect=track):
                supervision.supervision_status(self.env)
                pf01_supervisor.storage_path(self.env)
            self.assertEqual(len(connections), 2)
            self.assertTrue(all(db.was_closed for db in connections))
        finally:
            for db in connections:
                db.close()

    def test_headless_entrypoint_refuses_store_needing_migration(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute('DELETE FROM schema_meta WHERE schema_version > 11')
            db.commit()
        finally:
            db.close()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(persistence, 'start_persistence') as market, \
             patch.object(collection, 'start_collection') as news:
            with self.assertRaisesRegex(ValueError, 'APPROVED_SCHEMA_MIGRATION_REQUIRED'):
                run_ui_api.collect_only(ControlledStop())
            market.assert_not_called()
            news.assert_not_called()
        db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            self.assertEqual(db.execute('SELECT MAX(schema_version) FROM schema_meta').fetchone()[0], 11)
        finally:
            db.close()

    def test_market_background_storage_failures_stop_after_six_attempts(self):
        writer = persistence.MarketStreamWriter(self.path, sources=('kraken',), symbols=('BTC/USD',))
        try:
            self.assertTrue(writer.submit({'provider': 'KRAKEN', 'instrument_id': 'BTC/USD',
                'provider_symbol': 'BTC/USD', 'capability': 'CRYPTO_TRADES',
                'clocks': {'received_time_ns': time.time_ns()},
                'raw_payload': {'trade_id': 1, 'price': '100', 'qty': '1'}}))
            with patch.object(writer, '_storage_ok', return_value=False), \
                 patch.object(writer._wake, 'wait', return_value=True), \
                 patch.object(writer._stop, 'wait', return_value=False):
                writer.start()
                writer._thread.join(timeout=2)
                status = writer.status()
                self.assertFalse(status['worker_alive'])
                self.assertEqual(status['consecutive_failures'], 6)
                self.assertEqual(status['error'], 'WRITER_RETRY_LIMIT_EXCEEDED')
                self.assertFalse(status['accepting'])
                self.assertEqual(status['backlog'], 1)
                self.assertEqual(status['committed'], 0)
        finally:
            writer.stop()


if __name__ == '__main__':
    unittest.main()
