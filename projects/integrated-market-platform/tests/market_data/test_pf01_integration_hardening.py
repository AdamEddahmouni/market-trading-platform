"""PF-01 lifecycle, ingress and storage regressions; offline disposable state."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.persistence import MarketStreamWriter
from market_platform_foundation.news.collection import CollectionJob, NewsCollector
from market_platform_foundation.news.normalize import normalize_raw_item


class PF01IntegrationHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(self.connection.close)
        self.now = [1000.0]
        self.job = CollectionJob('finviz', '', 'US_EQUITIES', 120)

    def writer(self, *, symbols=('AAPL', 'BTC/USD'), sources=('moomoo', 'kraken')):
        writer = MarketStreamWriter(self.path, sources=sources, symbols=symbols)
        self.addCleanup(writer.stop)
        return writer

    @staticmethod
    def record(index):
        return {'provider': 'moomoo', 'instrument_id': 'AAPL', 'provider_symbol': 'US.AAPL',
                'capability': 'US_EQUITY_TICKS',
                'clocks': {'event_time_ns': 1700000000000000000 + index,
                           'received_time_ns': 1700000001000000000 + index},
                'raw_payload': {'price': 190, 'volume': 5, 'sequence': index}}

    @staticmethod
    def article():
        raw = {'headline': 'Synthetic issuer announces update', 'url': 'https://example.test/pf01',
               'tickers': ['AAPL'], 'published_time': '2026-10-13T00:00:00Z',
               'received_time': '2026-10-13T01:00:00Z'}
        return normalize_raw_item(raw, provider_id='finviz', source_id='finviz',
                                  retrieved_time=raw['received_time'])

    def test_repeated_start_retains_one_live_writer_worker(self):
        writer = self.writer()
        writer.start()
        first = writer._thread
        writer.start()
        self.assertIs(writer._thread, first)
        self.assertTrue(first.is_alive())
        writer.stop()
        self.assertFalse(first.is_alive())

    def test_queue_overflow_counter_agrees_with_durable_gap(self):
        writer = self.writer()
        self.assertEqual(sum(writer.submit(self.record(i)) for i in range(513)), 512)
        self.assertEqual(writer.status()['rejected'], 1)
        writer.flush()
        gap = self.connection.execute(
            "SELECT observations FROM market_stream_gaps WHERE reason='QUEUE_OVERFLOW'").fetchone()
        self.assertEqual(gap['observations'], 1)
        self.assertEqual(writer.status()['backlog'], 512 - writer.batch_limit)  # one bounded batch committed

    def test_closed_writer_reports_stopped_and_refuses_restart(self):
        writer = self.writer()
        writer.stop()
        self.assertEqual(writer.status()['state'], 'STOPPED')
        self.assertFalse(writer.status()['accepting'])
        with self.assertRaises(ValueError):
            writer.start()

    def test_news_expired_lease_never_commits_or_advances_success(self):
        def delayed_fetch(_job):
            self.now[0] += 121
            return [(self.article(), {'fixture': True})], {'state': 'CURRENT'}

        collector = NewsCollector(self.connection, [self.job], delayed_fetch, clock=lambda: self.now[0])
        self.addCleanup(collector.stop)
        collector.step()
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM news_collection_records').fetchone()[0], 0)
        saved = collector.status()['jobs'][0]
        self.assertEqual(saved['reason'], 'COLLECTION_LEASE_EXPIRED')
        self.assertNotEqual(saved['state'], 'HEALTHY')
        self.assertNotIn('last_success', saved)
        self.assertEqual(saved['lease_until'], 0)

    def test_news_incomplete_shutdown_reports_blocked_while_worker_alive(self):
        collector = NewsCollector(self.connection, [self.job], lambda _: ([], {'state': 'CURRENT'}))
        worker = MagicMock()
        worker.is_alive.return_value = True
        collector._thread = worker
        collector.stop()
        status = collector.status()
        self.assertTrue(status['worker_alive'])
        self.assertEqual(status['state'], 'BLOCKED')
        self.assertEqual(status['reason'], 'COLLECTION_SHUTDOWN_INCOMPLETE')
        worker.join.assert_called_once()
        collector._thread = None
        collector.stop()

    def test_news_storage_reserve_prevents_near_limit_batch_breach(self):
        article = self.article()
        fixed = len(json.dumps({'article': article.to_dict(), 'provenance': {'padding': ''}}, sort_keys=True).encode())
        padding = 'x' * (2 * 1024 * 1024 - fixed - 16)
        fetched = []

        def fetch(job):
            fetched.append(job.id)
            return [(article, {'padding': padding})], {'state': 'CURRENT'}

        collector = NewsCollector(self.connection, [self.job], fetch, clock=lambda: self.now[0])
        self.addCleanup(collector.stop)
        self.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        size = self.path.stat().st_size
        collector.max_database_bytes = size + 2 * 1024 * 1024 + 16 * 1024
        collector.step()
        self.assertEqual(fetched, [])
        self.assertEqual(collector.status()['state'], 'BLOCKED')
        self.assertEqual(collector.status()['reason'], 'STORAGE_UNAVAILABLE_OR_BOUND_EXCEEDED')
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM news_collection_records').fetchone()[0], 0)
        wal = Path(str(self.path) + '-wal')
        total = self.path.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
        self.assertLessEqual(total, collector.max_database_bytes)

    def test_malformed_selected_kraken_trades_leave_exact_rejection_evidence(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES

        writer = self.writer(sources=('kraken',), symbols=('BTC/USD',))
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
        runtime.subscribe(instrument_id='BTC/USD', capabilities=[TRADES], consumer_id='fixture')
        runtime._acked[('trade', 'BTC/USD')] = 1
        base = {'symbol': 'BTC/USD', 'price': 60000, 'qty': 1, 'trade_id': 1,
                'timestamp': '2026-10-13T01:00:00Z'}
        cases = [{**base, 'price': -1}, {**base, 'timestamp': 'invalid'},
                 {key: value for key, value in base.items() if key != 'price'},
                 {**base, 'price': 'NaN'}, {**base, 'qty': 'Infinity'}, {**base, 'trade_id': True}]
        with patch('market_platform_foundation.market_data.persistence.active_writer', return_value=writer):
            for index, item in enumerate(cases):
                runtime.handle(json.dumps({'channel': 'trade', 'type': 'update', 'data': [item]}),
                               received_ns=1700000001000000000 + index)
        self.assertEqual(writer.flush(), 0)
        gap = self.connection.execute(
            "SELECT * FROM market_stream_gaps WHERE reason='INVALID_OBSERVATION'").fetchone()
        self.assertEqual(gap['stream_id'], 'KRAKEN:BTC/USD:CRYPTO_TRADES')
        self.assertEqual(gap['observations'], len(cases))
        self.assertEqual(gap['end_ns'] - gap['start_ns'], len(cases) - 1)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0], 0)

    def test_malformed_kraken_trade_selected_by_provider_symbol_leaves_gap(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES

        # Target chosen by provider pair while the canonical instrument ID differs.
        writer = self.writer(sources=('kraken',), symbols=('BTC/USD',))
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
        runtime.subscribe(instrument_id='CRYPTO:BTC-USD', capabilities=[TRADES], consumer_id='fixture')
        runtime._acked[('trade', 'BTC/USD')] = 1
        with patch('market_platform_foundation.market_data.persistence.active_writer', return_value=writer):
            runtime.handle(json.dumps({'channel': 'trade', 'type': 'update', 'data': [
                {'symbol': 'BTC/USD', 'price': -1, 'qty': 1, 'trade_id': 1, 'timestamp': '2026-10-13T01:00:00Z'}]}),
                received_ns=1700000001000000000)
        writer.flush()
        gap = self.connection.execute(
            "SELECT * FROM market_stream_gaps WHERE reason='INVALID_OBSERVATION'").fetchone()
        self.assertIsNotNone(gap)
        self.assertEqual(gap['stream_id'], 'KRAKEN:CRYPTO:BTC-USD:CRYPTO_TRADES')
        self.assertEqual(gap['observations'], 1)

    def test_repeated_bar_window_only_enqueues_unaccepted_bars(self):
        from market_platform_foundation.market_data.current_bars import Bar

        writer = self.writer()
        minute = 60_000_000_000
        base = 1700000000000000000

        def bar(index):
            return Bar(base + index * minute, base + (index + 1) * minute, 10, 12, 9, 11, 4, 'REGULAR')

        window = [bar(index) for index in range(600)]
        writer.submit_bars('AAPL', window, base + 700 * minute)
        # The bounded queue keeps the newest bars; the older remainder is counted, not hidden.
        self.assertEqual(writer.status()['backlog'], 512)
        self.assertEqual(writer.status()['rejected'], 88)
        while writer.status()['backlog']:
            writer.flush()
        newest = self.connection.execute('SELECT MAX(event_ns) FROM market_stream_records').fetchone()[0]
        self.assertEqual(newest, window[-1].end_ns)
        # The provider returns the same rolling window on the next refresh.
        writer.submit_bars('AAPL', window, base + 701 * minute)
        self.assertEqual(writer.status()['backlog'], 88)
        self.assertEqual(writer.status()['rejected'], 88)
        while writer.status()['backlog']:
            writer.flush()
        writer.submit_bars('AAPL', window + [bar(600)], base + 702 * minute)
        self.assertEqual(writer.status()['backlog'], 1)
        writer.flush()
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0], 601)
        self.assertEqual(writer.status()['duplicates'], 0)
        writer.submit_bars('MSFT', window, base + 703 * minute)
        self.assertEqual(writer.status()['backlog'], 0)
        self.assertNotIn('MSFT', writer._bars_seen)

    def test_disconnect_gap_is_limited_to_selected_sources(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime

        for sources, symbols, expected in ((('moomoo',), ('AAPL',), 0), (('kraken',), ('BTC/USD',), 1)):
            with self.subTest(sources=sources):
                writer = self.writer(sources=sources, symbols=symbols)
                runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
                runtime._connection = MagicMock()
                with patch('market_platform_foundation.market_data.persistence.active_writer', return_value=writer):
                    runtime._disconnect('IDLE')
                writer.flush()
                self.assertEqual(self.connection.execute(
                    "SELECT COUNT(*) FROM market_stream_gaps WHERE reason='KRAKEN_DISCONNECT_NO_REPLAY' AND run_id=?",
                    (writer.run_id,)).fetchone()[0], expected)
                writer.stop()

    def test_malformed_unselected_kraken_trade_does_not_report_capture_gap(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES

        writer = self.writer(sources=('kraken',), symbols=('ETH/USD',))
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
        runtime.subscribe(instrument_id='BTC/USD', capabilities=[TRADES], consumer_id='fixture')
        runtime._acked[('trade', 'BTC/USD')] = 1
        with patch('market_platform_foundation.market_data.persistence.active_writer', return_value=writer):
            runtime.handle(json.dumps({'channel': 'trade', 'data': [{'symbol': 'BTC/USD'}]}),
                           received_ns=1700000001000000000)
        writer.flush()
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM market_stream_gaps WHERE reason='INVALID_OBSERVATION'").fetchone()[0], 0)
