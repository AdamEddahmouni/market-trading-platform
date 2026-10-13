"""PF-01B offline SQLite commit, replay and producer contracts."""
import copy
from contextlib import closing
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection


class StreamPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        with LocalStateConnection(self.path):
            pass
        self.writer = None

    def tearDown(self):
        if self.writer is not None:
            self.writer.stop()
        self.temp.cleanup()

    def open(self, **kwargs):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        self.writer = MarketStreamWriter(self.path, sources=('moomoo', 'kraken'), symbols=('AAPL', 'BTC/USD'), **kwargs)
        return self.writer

    def record(self, **changes):
        row = {'provider': 'moomoo', 'instrument_id': 'AAPL', 'provider_symbol': 'US.AAPL',
               'capability': 'US_EQUITY_TICKS', 'sequence': 41,
               'clocks': {'event_time_ns': 1700000000000000000, 'provider_time_ns': None,
                          'received_time_ns': 1700000001000000000},
               'raw_payload': {'price': 190, 'volume': 5, 'sequence': 41, 'time': '2023-11-14 17:13:20'},
               'provider_generation': 2}
        row.update(changes)
        return row

    def rows(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute('SELECT * FROM market_stream_records ORDER BY received_ns, record_id')]

    def test_real_database_commit_preserves_raw_clocks_and_identity(self):
        writer = self.open()
        record = self.record()
        self.assertTrue(writer.submit(record))
        self.assertEqual(writer.status()['committed'], 0)
        self.assertEqual(writer.flush(), 1)
        row = self.rows()[0]
        self.assertEqual(json.loads(row['payload_json'])['raw_payload'], record['raw_payload'])
        self.assertEqual(row['event_ns'], record['clocks']['event_time_ns'])
        self.assertEqual(row['received_ns'], record['clocks']['received_time_ns'])
        self.assertIsNone(row['provider_ns'])
        self.assertEqual(row['provider'], 'moomoo')
        self.assertEqual(row['symbol'], 'AAPL')
        self.assertGreater(row['persisted_ns'], 0)

    def test_duplicate_trade_replay_dedupes_across_restart(self):
        writer = self.open()
        self.assertTrue(writer.submit(self.record()))
        writer.flush()
        writer.stop()
        writer = self.open()
        replay = self.record(clocks={**self.record()['clocks'], 'received_time_ns': 1700000002000000000})
        writer.submit(replay)
        writer.flush()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(writer.status()['duplicates'], 1)

    def test_quote_receipts_are_distinct_but_exact_replay_is_idempotent(self):
        writer = self.open()
        a = self.record(capability='US_EQUITY_L1', sequence=None, raw_payload={'last_price': 190})
        b = copy.deepcopy(a)
        b['clocks']['received_time_ns'] += 1
        for row in (a, a, b):
            writer.submit(row)
        writer.flush()
        self.assertEqual(len(self.rows()), 2)

    def test_trade_correction_is_append_only(self):
        writer = self.open()
        a = self.record()
        b = copy.deepcopy(a)
        b['raw_payload']['price'] = 191
        b['clocks']['received_time_ns'] += 1
        writer.submit(a)
        writer.submit(b)
        writer.flush()
        self.assertEqual(len(self.rows()), 2)

    def test_partial_batch_failure_rolls_back_records_and_checkpoint(self):
        writer = self.open()
        writer.submit(self.record())
        writer.connection.execute("CREATE TRIGGER reject_records BEFORE INSERT ON market_stream_records BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        self.assertEqual(writer.flush(), 0)
        self.assertEqual(self.rows(), [])
        self.assertEqual(writer.status()['backlog'], 1)
        self.assertEqual(writer.checkpoints(), [])
        self.assertEqual(writer.status()['state'], 'FAILED')
        writer.connection.execute('DROP TRIGGER reject_records')
        self.assertEqual(writer.flush(), 1)
        self.assertEqual(len(writer.checkpoints()), 1)
        self.assertGreater(writer.status()['known_gaps'], 0)

    def test_capacity_overflow_is_bounded_and_gap_is_durable(self):
        writer = self.open(queue_limit=1, batch_limit=1)
        self.assertTrue(writer.submit(self.record()))
        self.assertFalse(writer.submit(self.record(sequence=42)))
        self.assertEqual(writer.status()['backlog'], 1)
        writer.flush()
        self.assertGreater(writer.status()['known_gaps'], 0)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertTrue(conn.execute("SELECT 1 FROM market_stream_gaps WHERE reason='QUEUE_OVERFLOW'").fetchone())

    def test_unknown_source_and_nonfinite_records_are_rejected(self):
        writer = self.open()
        self.assertFalse(writer.submit(self.record(provider='unknown')))
        self.assertFalse(writer.submit(self.record(raw_payload={'price': float('nan')})))
        self.assertEqual(writer.status()['backlog'], 0)

    def test_missing_storage_never_creates_replacement(self):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        missing = Path(self.temp.name) / 'unmounted' / 'imp-state.sqlite3'
        with self.assertRaises((ValueError, FileNotFoundError)):
            MarketStreamWriter(missing, sources=('moomoo',), symbols=('AAPL',))
        self.assertFalse(missing.parent.exists())

    def test_storage_disappearance_fails_without_advancing(self):
        writer = self.open()
        writer.submit(self.record())
        with patch.object(writer, '_storage_ok', return_value=False):
            self.assertEqual(writer.flush(), 0)
        self.assertEqual(writer.checkpoints(), [])
        # A drive that may return is retried, never reported as committed and never recreated.
        self.assertEqual(writer.status()['state'], 'RETRYING')
        self.assertEqual(writer.status()['backlog'], 1)
        self.assertEqual(writer.flush(), 1)

    def test_out_of_order_watermark_never_regresses(self):
        writer = self.open()
        a = self.record()
        b = self.record(sequence=40, clocks={**a['clocks'], 'event_time_ns': a['clocks']['event_time_ns']-1})
        b['raw_payload']['sequence'] = 40
        writer.submit(a)
        writer.flush()
        writer.submit(b)
        writer.flush()
        self.assertEqual(writer.checkpoints()[0]['event_ns'], a['clocks']['event_time_ns'])
        self.assertEqual(len(self.rows()), 2)

    def test_completed_bar_revisions_preserve_as_known_receipt(self):
        from market_platform_foundation.market_data.current_bars import Bar
        writer = self.open()
        a = Bar(1700000000000000000, 1700000060000000000, 10, 12, 9, 11, 4, 'REGULAR')
        b = Bar(a.start_ns, a.end_ns, 10, 13, 9, 12, 5, 'REGULAR')
        writer.submit_bars('AAPL', [a], 1700000070000000000)
        writer.flush()
        writer.submit_bars('AAPL', [a, b], 1700000080000000000)
        writer.flush()
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(self.rows()[0]['received_ns'], 1700000070000000000)

    def test_kraken_trade_native_id_not_receipt_is_identity(self):
        writer = self.open()
        row = self.record(provider='KRAKEN', instrument_id='BTC/USD', provider_symbol='BTC/USD',
                          capability='CRYPTO_TRADES', sequence=10,
                          raw_payload={'trade_id': 10, 'price': 60000, 'qty': 1})
        writer.submit(row)
        row['clocks']['received_time_ns'] += 1
        writer.submit(row)
        writer.flush()
        self.assertEqual(len(self.rows()), 1)

    def test_restart_marks_unclosed_run_gap(self):
        writer = self.open()
        writer.submit(self.record())
        writer.flush()
        writer.connection.execute('UPDATE market_stream_runs SET closed_ns=NULL, lease_until_ns=0')
        writer.connection.close()
        writer._owner_lock.release()  # the operating system does this when a process dies
        writer._closed = True
        writer = self.open()
        self.assertGreater(writer.status()['known_gaps'], 0)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(writer.status()['recovery'], 'NO_PROVIDER_REPLAY')

    def test_competing_writer_refused(self):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        self.open()
        with self.assertRaises(ValueError):
            MarketStreamWriter(self.path, sources=('moomoo',), symbols=('AAPL',))

    def test_live_runtime_ingress_queues_at_existing_admission_boundary(self):
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
        writer = self.open()
        runtime = LiveObservationalRuntime()
        row = self.record(capability='US_EQUITY_L1', raw_payload={'ask_price': 191, 'ask_vol': 1,
                          'bid_price': 190, 'bid_vol': 1, 'last_price': 190.5})
        from market_platform_foundation.market_data import persistence
        with patch.object(persistence, 'active_writer', return_value=writer):
            result = runtime.ingest_record(row, wall_now_ns=row['clocks']['received_time_ns'])
        self.assertGreater(writer.status()['backlog'], 0, result)

    def test_configuration_is_default_off_and_requires_explicit_targets(self):
        from market_platform_foundation.market_data.persistence import start_persistence
        self.assertIsNone(start_persistence('LIVE_OBSERVATIONAL', {}))
        with self.assertRaises(ValueError):
            start_persistence('LIVE_OBSERVATIONAL', {'IMP_MARKET_PERSISTENCE_ENABLED':'1'})

    def test_commit_failure_rolls_back_and_releases_transaction(self):
        writer = self.open()
        writer.connection.execute('CREATE TABLE fixture_parent(id INTEGER PRIMARY KEY)')
        writer.connection.execute('CREATE TABLE fixture_child(id INTEGER REFERENCES fixture_parent(id) DEFERRABLE INITIALLY DEFERRED)')
        writer.connection.execute("CREATE TRIGGER fail_commit AFTER INSERT ON market_stream_records BEGIN INSERT INTO fixture_child VALUES (999); END")
        writer.submit(self.record())
        self.assertEqual(writer.flush(), 0)
        self.assertFalse(writer.connection.in_transaction)
        self.assertEqual(self.rows(), [])
        writer.connection.execute('DROP TRIGGER fail_commit')
        self.assertEqual(writer.flush(), 1)

    def test_relocated_existing_state_works_without_checkout_database(self):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        relocated = Path(self.temp.name) / 'other-drive' / 'state' / 'imp-state.sqlite3'
        with LocalStateConnection(relocated):
            pass
        self.writer = MarketStreamWriter(relocated, sources=('moomoo',), symbols=('AAPL',))
        self.writer.submit(self.record())
        self.assertEqual(self.writer.flush(), 1)
        self.assertEqual(self.writer.connection.path, relocated)

    def test_memory_snapshot_cannot_change_after_enqueue(self):
        writer = self.open()
        record = self.record()
        writer.submit(record)
        record['raw_payload']['price'] = 999
        writer.flush()
        self.assertEqual(json.loads(self.rows()[0]['payload_json'])['raw_payload']['price'], 190)

    def test_kraken_existing_trade_handler_persists_native_message(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES
        from market_platform_foundation.market_data import persistence
        writer = self.open()
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
        runtime.subscribe(instrument_id='BTC/USD', capabilities=[TRADES], consumer_id='fixture')
        runtime._acked[('trade', 'BTC/USD')] = 1
        item = {'symbol': 'BTC/USD', 'trade_id': 9, 'timestamp': '2023-11-14T22:13:20Z',
                'price': 60000, 'qty': 1, 'side': 'buy', 'ord_type': 'market'}
        with patch.object(persistence, 'active_writer', return_value=writer):
            runtime.handle(json.dumps({'channel': 'trade', 'type': 'update', 'data': [item]}), received_ns=1700000001000000000)
        self.assertEqual(writer.flush(), 1)
        self.assertEqual(json.loads(self.rows()[0]['payload_json'])['raw_payload'], item)

    def test_bar_producer_persists_complete_rows_only_and_cache_does_not_requeue(self):
        from market_platform_foundation.market_data.current_bars import CurrentBarsService
        from market_platform_foundation.market_data import persistence
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from types import SimpleNamespace
        writer = self.open()
        now = int(datetime(2026, 10, 12, 9, 31, 30, tzinfo=ZoneInfo('America/New_York')).timestamp()*1e9)
        rows = [{'time_key': f'2026-10-12 09:{minute}:00', 'open': 10, 'high': 12, 'low': 9, 'close': 11, 'volume': 1}
                for minute in ('31', '32')]
        transport = SimpleNamespace(fetch_current_kline_1m=lambda _: {'rows': rows})
        service = CurrentBarsService(transport_factory=lambda: transport, reachable=lambda: True, now_ns=lambda: now)
        with patch.object(persistence, 'active_writer', return_value=writer):
            service.read('AAPL', timeframe='1m')
            service.read('AAPL', timeframe='1m')
        self.assertEqual(writer.status()['backlog'], 1)
        self.assertEqual(writer.flush(), 1)

    def test_process_exit_mid_transaction_preserves_committed_data(self):
        writer = self.open()
        writer.submit(self.record())
        writer.flush()
        writer.stop()
        script = """import sqlite3,sys,os
c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE')
c.execute('DELETE FROM market_stream_records'); c.execute('DELETE FROM market_stream_checkpoints')
os._exit(7)
"""
        result = subprocess.run([sys.executable, '-c', script, str(self.path)], timeout=10)
        self.assertEqual(result.returncode, 7)
        writer = self.open()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(len(writer.checkpoints()), 1)

    def test_database_busy_recovers_without_leaking_transaction_lock(self):
        writer = self.open()
        blocker = sqlite3.connect(self.path, isolation_level=None)
        try:
            blocker.execute('BEGIN IMMEDIATE')
            writer.submit(self.record())
            self.assertEqual(writer.flush(), 0)
        finally:
            blocker.execute('ROLLBACK')
            blocker.close()
        import threading
        done = threading.Event()
        def read():
            writer.connection.execute('SELECT 1')
            done.set()
        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        self.assertTrue(done.wait(2), 'BEGIN failure leaked the connection lock')
        self.assertEqual(writer.flush(), 1)

    def test_negative_trade_is_rejected(self):
        writer = self.open()
        self.assertFalse(writer.submit(self.record(raw_payload={'price': -1, 'volume': 5, 'sequence': 1})))
        self.assertEqual(writer.status()['backlog'], 0)

    def test_unknown_market_event_time_is_preserved_as_unknown(self):
        writer = self.open()
        row = self.record(capability='US_EQUITY_L1', clocks={'event_time_ns': None,
                          'provider_time_ns': None, 'received_time_ns': 1700000001000000000},
                          raw_payload={'last_price': 190})
        writer.submit(row)
        writer.flush()
        self.assertIsNone(self.rows()[0]['event_ns'])
        self.assertIsNone(self.rows()[0]['provider_ns'])

    def test_source_capability_mismatch_rejected(self):
        writer = self.open()
        self.assertFalse(writer.submit(self.record(capability='CRYPTO_BOOK')))

    def test_weekend_holiday_and_dst_receipts_remain_exact(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        writer = self.open()
        times = [datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo('America/New_York'), fold=fold) for fold in (0, 1)]
        times += [datetime(2026, 12, 25, 8, 0, tzinfo=ZoneInfo('America/New_York')),
                  datetime(2026, 10, 17, 20, 30, tzinfo=ZoneInfo('America/New_York'))]
        expected = []
        for moment in times:
            ns = int(moment.timestamp()*1e9)
            row = self.record(capability='US_EQUITY_L1', clocks={'event_time_ns': ns,
                              'provider_time_ns': None, 'received_time_ns': ns+1}, raw_payload={'last_price': 190})
            writer.submit(row)
            expected.append(ns)
        writer.flush()
        self.assertEqual([row['event_ns'] for row in self.rows()], sorted(expected))
        self.assertEqual(expected[1]-expected[0], 3600*1_000_000_000)

    def test_background_worker_commits_without_consumer_blocking(self):
        import time
        writer = self.open()
        writer.start()
        writer.submit(self.record())
        deadline = time.monotonic()+3
        while writer.status()['committed'] == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(writer.status()['committed'], 1)
        self.assertEqual(writer.status()['backlog'], 0)

    def test_kraken_decimal_trade_values_are_lossless(self):
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, TRADES
        from market_platform_foundation.market_data import persistence
        writer = self.open()
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False)
        runtime.subscribe(instrument_id='BTC/USD', capabilities=[TRADES], consumer_id='fixture')
        runtime._acked[('trade', 'BTC/USD')] = 1
        text = '{"channel":"trade","data":[{"symbol":"BTC/USD","trade_id":10,"timestamp":"2023-11-14T22:13:20Z","price":60000.123456789,"qty":0.00000001,"side":"buy"}]}'
        with patch.object(persistence, 'active_writer', return_value=writer):
            runtime.handle(text, received_ns=1700000001000000000)
        self.assertEqual(writer.flush(), 1)
        payload = json.loads(self.rows()[0]['payload_json'])
        self.assertEqual(payload['raw_payload']['price'], '60000.123456789')
        self.assertEqual(payload['raw_payload']['qty'], '1E-8')

    def test_kraken_book_requires_valid_checksum_and_keeps_snapshot_anchor(self):
        from decimal import Decimal
        from market_platform_foundation.crypto_market.kraken_book import book_checksum
        from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime, BOOK
        from market_platform_foundation.order_flow.order_book.contracts import BookLevel
        from market_platform_foundation.market_data import persistence
        writer = self.open()
        runtime = KrakenStreamRuntime(resolve=lambda _: ('BTC/USD', 1, 8), start_worker=False, depth=10)
        runtime.subscribe(instrument_id='BTC/USD', capabilities=[BOOK], consumer_id='fixture')
        runtime._sent.add(('book', 'BTC/USD'))
        runtime.lifecycle.connected_ns = 1700000000000000000
        checksum = book_checksum([BookLevel(Decimal('100'), Decimal('1'))],
                                 [BookLevel(Decimal('101'), Decimal('1'))], price_decimals=1, qty_decimals=8)
        item = {'symbol': 'BTC/USD', 'bids': [{'price': 100.0, 'qty': 1.0}],
                'asks': [{'price': 101.0, 'qty': 1.0}], 'checksum': checksum}
        with patch.object(persistence, 'active_writer', return_value=writer):
            runtime.handle(json.dumps({'channel': 'book', 'type': 'snapshot', 'data': [item]}), received_ns=1700000001000000000)
            runtime.handle(json.dumps({'channel': 'book', 'type': 'update', 'data': [{**item, 'checksum': 0}]}),
                           received_ns=1700000002000000000)
        self.assertEqual(writer.flush(), 1)
        payload = json.loads(self.rows()[0]['payload_json'])
        self.assertEqual(payload['message_type'], 'snapshot')
        self.assertEqual(payload['subscription_id'], 'kraken:1700000000000000000:BTC/USD')
        self.assertGreater(writer.status()['known_gaps'], 1)

    def test_storage_ceiling_stops_writes_without_deletion(self):
        writer = self.open()
        writer.submit(self.record())
        writer.flush()
        writer.max_database_bytes = self.path.stat().st_size
        writer.submit(self.record(sequence=42, raw_payload={'price': 191, 'volume': 1, 'sequence':42}))
        self.assertEqual(writer.flush(), 0)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(writer.status()['state'], 'FAILED')

    def test_queued_data_lost_on_process_exit_is_flagged_on_recovery(self):
        script = '''import os,sys,time
from pathlib import Path
from market_platform_foundation.market_data.persistence import MarketStreamWriter
w=MarketStreamWriter(Path(sys.argv[1]),sources=('moomoo',),symbols=('AAPL',))
w.submit({'provider':'moomoo','instrument_id':'AAPL','provider_symbol':'US.AAPL',
          'capability':'US_EQUITY_L1','clocks':{'received_time_ns':time.time_ns()},'raw_payload':{'last_price':190}})
os._exit(8)
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.path)], timeout=10)
        self.assertEqual(result.returncode, 8)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('UPDATE market_stream_runs SET lease_until_ns=0')
            conn.commit()
        writer = self.open()
        self.assertEqual(self.rows(), [])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertTrue(conn.execute("SELECT 1 FROM market_stream_gaps WHERE reason='UNCLEAN_RESTART_NO_REPLAY'").fetchone())

    def test_backend_startup_failure_closes_owned_writer_and_http_server(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from tools.ui1 import run_ui_api
        server = MagicMock()
        store = SimpleNamespace(data_mode='LIVE_OBSERVATIONAL', instrument_id='AAPL')
        with patch.dict(os.environ, {'IMP_NEWS_COLLECTION_ENABLED':'0', 'IMP_MARKET_PERSISTENCE_ENABLED':'0'}), \
             patch.object(run_ui_api, '_install_process_diagnostics'), patch.object(run_ui_api, '_load_store', return_value=store), \
             patch.object(run_ui_api, 'SingleBindHTTPServer', return_value=server), \
             patch.object(run_ui_api, 'start_screener_warmup'), patch.object(run_ui_api, 'resume_paper_automation'), \
             patch('market_platform_foundation.market_data.persistence.start_persistence', return_value=object()), \
             patch('market_platform_foundation.market_data.persistence.stop_persistence') as stop, \
             patch('market_platform_foundation.news.collection.start_collection', side_effect=ValueError('fixture startup')):
            with self.assertRaises(ValueError):
                run_ui_api.serve(host='127.0.0.1', port=0)
            stop.assert_called_once()
            server.server_close.assert_called_once()

    def test_incomplete_shutdown_preserves_visible_global_owner(self):
        from unittest.mock import MagicMock
        from market_platform_foundation.market_data import persistence
        writer = self.open()
        writer._thread = MagicMock()
        writer._thread.is_alive.return_value = True
        try:
            with patch.object(persistence, '_WRITER', writer):
                persistence.stop_persistence()
                self.assertIs(persistence.active_writer(), writer)
                self.assertEqual(writer.status()['state'], 'FAILED')
        finally:
            writer._thread = None

    def test_shutdown_database_error_always_closes_connection(self):
        writer = self.open()
        original = writer.connection.execute
        def execute(sql, params=()):
            if sql.startswith('UPDATE market_stream_runs SET closed_ns='):
                raise sqlite3.OperationalError('fixture locked')
            return original(sql, params)
        with patch.object(writer.connection, 'execute', side_effect=execute):
            writer.stop()
        self.assertTrue(writer._closed)

    def test_worker_drains_multiple_batches_without_idle_sleep(self):
        import time
        writer = self.open(queue_limit=16, batch_limit=4)
        for index in range(16):
            writer.submit(self.record(sequence=index, raw_payload={'price':190, 'volume':1, 'sequence':index}))
        writer.start()
        deadline = time.monotonic()+0.75
        while writer.status()['backlog'] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(writer.status()['backlog'], 0)

    def test_book_items_sharing_receipt_keep_message_order_and_exact_replay(self):
        writer = self.open()
        row = self.record(provider='KRAKEN', instrument_id='BTC/USD', provider_symbol='BTC/USD', capability='CRYPTO_BOOK',
                          raw_payload={'bids':[{'price':100, 'qty':1}], 'asks':[{'price':101, 'qty':1}], 'checksum':1})
        row.update(message_type='update', subscription_id='fixture-subscription', message_index=0)
        writer.submit(row, {'checksum':'VALID'})
        row['message_index'] = 1
        writer.submit(row, {'checksum':'VALID'})
        writer.submit(row, {'checksum':'VALID'})
        self.assertEqual(writer.flush(), 2)
        self.assertEqual(len(self.rows()), 2)

    def test_v12_news_rows_survive_additive_market_migration(self):
        from market_platform_foundation.local_state.migrations import MIGRATIONS
        path = Path(self.temp.name) / 'news-v12.sqlite3'
        with closing(sqlite3.connect(path)) as conn:
            for version in range(1, 13):
                for statement in MIGRATIONS[version]:
                    conn.execute(statement)
                conn.execute('INSERT INTO schema_meta VALUES (?,?)', (version, 'fixture'))
            conn.execute("INSERT INTO news_collection_records VALUES ('n1','fixture','source','unknown','receipt',1,'{}')")
            conn.execute("INSERT INTO news_collection_jobs VALUES ('j1','{}',1,NULL,0)")
            conn.commit()
        with LocalStateConnection(path, require_existing=True) as conn:
            self.assertEqual(conn.schema_version(), 13)
            self.assertEqual(conn.execute('SELECT record_id FROM news_collection_records').fetchone()[0], 'n1')
            self.assertEqual(conn.execute('SELECT job_id FROM news_collection_jobs').fetchone()[0], 'j1')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0], 0)

    def test_corrupt_storage_is_preserved_and_refused(self):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        path = Path(self.temp.name) / 'corrupt.sqlite3'
        payload = b'not a database'
        path.write_bytes(payload)
        with self.assertRaises(sqlite3.DatabaseError):
            MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',))
        self.assertEqual(path.read_bytes(), payload)
