"""Market stream store split (2026-10-27): its own compressed file, readers that follow it, and the one-time split."""
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state import integrity_receipt as receipts
from market_platform_foundation.local_state import payload_codec as codec
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.schema import SCHEMA_VERSION
from market_platform_foundation.market_data import stream_store
from tools.platform import split_stream_store as split


def quote(i, symbol='AAPL'):
    return {'provider': 'moomoo', 'instrument_id': symbol, 'provider_symbol': f'US.{symbol}',
            'capability': 'US_EQUITY_L1',
            'clocks': {'event_time_ns': 1700000000000000000 + i, 'provider_time_ns': None,
                       'received_time_ns': 1700000001000000000 + i},
            'raw_payload': {'code': f'US.{symbol}', 'last_price': 190 + i / 100, 'bid_price': 189.9, 'ask_price': 190.1,
                            'volume': 1000 + i, 'delta': 'N/A', 'gamma': 'N/A', 'vega': 'N/A', 'theta': 'N/A',
                            'data_time': f'16:00:{i % 60:02d}'}}


class StreamStoreTestBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.state = self.dir / 'imp-state.sqlite3'
        with LocalStateConnection(self.state):
            pass
        self.writer = None

    def tearDown(self):
        if self.writer is not None:
            self.writer.stop()
        self.temp.cleanup()

    def open_writer(self, **kwargs):
        from market_platform_foundation.market_data.persistence import MarketStreamWriter
        self.writer = MarketStreamWriter(self.state, sources=('moomoo',), symbols=('AAPL', 'MSFT'), **kwargs)
        return self.writer

    def rows(self, path):
        with closing(sqlite3.connect(path)) as db:
            return db.execute('SELECT rowid, record_id, payload_json FROM market_stream_records ORDER BY rowid').fetchall()


class StreamStoreFileTests(StreamStoreTestBase):
    def test_open_never_creates_and_checks_version(self):
        path = stream_store.stream_store_path(self.state)
        self.assertEqual(path.name, 'imp-market-stream.sqlite3')
        self.assertEqual(stream_store.stream_data_path(self.state), self.state)  # not split yet: the state store
        with self.assertRaises(FileNotFoundError):
            stream_store.open_stream_store(path)
        self.assertFalse(path.exists())
        stream_store.create_stream_store(path)
        with self.assertRaises(FileExistsError):
            stream_store.create_stream_store(path)
        self.assertEqual(stream_store.stream_data_path(self.state), path)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA auto_vacuum').fetchone()[0], 2)  # INCREMENTAL
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('paper_events', tables)
            db.execute("UPDATE stream_store_meta SET value='99' WHERE key='version'")
            db.commit()
        with self.assertRaises(ValueError):
            stream_store.open_stream_store(path, verify=False)

    def test_open_does_not_migrate_state_schema_into_it(self):
        path = stream_store.stream_store_path(self.state)
        stream_store.create_stream_store(path)
        stream_store.open_stream_store(path, verify=True).close()
        with closing(sqlite3.connect(path)) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {*stream_store.STREAM_TABLES, 'payload_dictionaries', 'stream_store_meta'})
        self.assertEqual(receipts.read_receipt(path)['result'], 'ok')

    def test_footprint_counts_both_stores(self):
        alone = stream_store.footprint_bytes(self.state)
        stream_store.create_stream_store(stream_store.stream_store_path(self.state))
        self.assertGreater(stream_store.footprint_bytes(self.state), alone)


class SplitWriterTests(StreamStoreTestBase):
    def test_unsplit_store_keeps_plain_rows_in_state_store(self):
        writer = self.open_writer()
        self.assertFalse(writer.split)
        self.assertTrue(writer.submit(quote(1)))
        self.assertEqual(writer.flush(), 1)
        self.assertIsInstance(self.rows(self.state)[0][2], str)

    def test_split_store_compresses_after_dictionary_and_decodes_exactly(self):
        path = stream_store.stream_store_path(self.state)
        stream_store.create_stream_store(path)
        writer = self.open_writer()
        self.assertTrue(writer.split)
        self.assertEqual(writer.connection.path, path)
        for i in range(codec.SAMPLE_ROWS):
            self.assertTrue(writer.submit(quote(i)))
        while writer.flush():
            pass
        self.assertEqual(self.rows(self.state), [])  # nothing lands in the state store
        self.assertTrue(all(isinstance(r[2], str) for r in self.rows(path)))  # no dictionary yet: plain
        for i in range(100, 140):
            self.assertTrue(writer.submit(quote(i)))
        while writer.flush():
            pass
        rows = self.rows(path)
        compressed = [r for r in rows if isinstance(r[2], bytes)]
        self.assertEqual(len(compressed), 40)
        writer.stop()
        self.writer = None
        with closing(sqlite3.connect(path)) as db:
            reader = codec.PayloadCodec(db)
            for _, record_id, value in compressed:
                text = reader.decode(value)
                body = json.loads(text)
                self.assertEqual(body['capability'], 'US_EQUITY_L1')
                self.assertLess(len(value), len(text.encode()))
        # The same receipt written plain has the same record_id: identity never depends on storage.
        plain_writer_dir = tempfile.TemporaryDirectory()
        try:
            other = Path(plain_writer_dir.name) / 'imp-state.sqlite3'
            with LocalStateConnection(other):
                pass
            from market_platform_foundation.market_data.persistence import MarketStreamWriter
            w = MarketStreamWriter(other, sources=('moomoo',), symbols=('AAPL',))
            w.submit(quote(120))
            w.flush()
            w.stop()
            plain_id = self.rows(other)[0][1]
        finally:
            plain_writer_dir.cleanup()
        self.assertIn(plain_id, {r[1] for r in rows})

    def test_codec_switch_off_keeps_split_rows_plain(self):
        stream_store.create_stream_store(stream_store.stream_store_path(self.state))
        with patch.dict(os.environ, {'IMP_MARKET_PAYLOAD_CODEC': '0'}):
            writer = self.open_writer()
        for i in range(codec.SAMPLE_ROWS + 10):
            writer.submit(quote(i))
        while writer.flush():
            pass
        rows = self.rows(stream_store.stream_store_path(self.state))
        self.assertEqual(len(rows), codec.SAMPLE_ROWS + 10)
        self.assertTrue(all(isinstance(r[2], str) for r in rows))

    def test_failed_dictionary_commit_leaves_rows_plain_and_decodable(self):
        stream_store.create_stream_store(stream_store.stream_store_path(self.state))
        writer = self.open_writer()
        for i in range(codec.SAMPLE_ROWS):
            writer.submit(quote(i))
        while writer.flush():
            pass
        with patch.object(codec.PayloadCodec, 'create', side_effect=sqlite3.OperationalError('disk I/O error')):
            for i in range(100, 110):
                writer.submit(quote(i))
            while writer.flush():
                pass
        self.assertTrue(all(isinstance(r[2], str) for r in self.rows(stream_store.stream_store_path(self.state))))


class CoverageDecodeTests(unittest.TestCase):
    def test_coverage_reader_decodes_compressed_and_plain_records(self):
        with tempfile.TemporaryDirectory() as tmp, LocalStateConnection(Path(tmp) / 'imp-state.sqlite3') as conn:
            ledger = CoverageLedger(conn)
            ledger.append('r1', 'run', {'scope': 'CRYPTO', 'rows': 621})
            pc = codec.PayloadCodec(conn)
            samples = [json.dumps({'kind': 'batch', 'i': i, 'evidence': 'x' * 200}) for i in range(40)]
            with conn.transaction():
                pc.create('coverage', samples)
                blob = pc.encode('coverage', json.dumps({'kind': 'batch', 'i': 99, 'evidence': 'x' * 200},
                                                        sort_keys=True, separators=(',', ':')))
                self.assertTrue(codec.is_encoded(blob))
                conn.execute('INSERT INTO ai_screener_coverage_records VALUES (?,?,?,?)', ('r1', 1, 'batch', blob))
            records = CoverageLedger(conn).records('r1')
        self.assertEqual([r['kind'] for r in records], ['run', 'batch'])
        self.assertEqual(records[1]['i'], 99)


class SplitToolTests(StreamStoreTestBase):
    def fill(self, count=300):
        writer = self.open_writer()
        for i in range(count):
            writer.submit(quote(i, 'AAPL' if i % 3 else 'MSFT'))
            if i % 200 == 199:
                writer.flush()
        while writer.flush():
            pass
        writer.stop()
        self.writer = None
        with closing(sqlite3.connect(self.state)) as db:
            self.source = db.execute('SELECT rowid,* FROM market_stream_records ORDER BY rowid').fetchall()
            self.small = {t: db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall() for t in split.SMALL_TABLES}
        LocalStateConnection(self.state, verify=True).close()  # a fresh receipt, as the night tool requires

    def test_split_moves_rows_compressed_and_compacts_state_in_place(self):
        self.check_split()

    def test_in_memory_split_gives_the_same_result_and_keeps_wal(self):
        result = self.check_split(in_memory=True)
        self.assertEqual(result['shrink']['journal_mode'], 'wal')
        self.assertEqual(result['load']['bytes'], result['shrink']['bytes_before'])
        self.assertGreater(result['shrink']['table_counts']['schema_meta'], 0)

    def test_in_memory_split_can_reuse_an_untouched_backup(self):
        self.fill(120)
        backup = split._copy_with_hash(self.state, self.dir / 'earlier' / self.state.name)
        result = split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None,
                           in_memory=True, reuse_backup=Path(backup['path']), reuse_backup_sha256=backup['sha256'])
        self.assertTrue(result['backup']['reused'])
        self.assertEqual(result['copy']['rows'], len(self.source))

    def test_reused_backup_is_refused_once_the_store_was_written_after_it(self):
        self.fill(30)
        copy = self.dir / 'earlier' / self.state.name
        split._copy_with_hash(self.state, copy)
        stat = copy.stat()
        os.utime(self.state, (stat.st_atime, stat.st_ctime + 10))
        with self.assertRaisesRegex(split.SplitError, 'STATE_STORE_WRITTEN_AFTER_BACKUP'):
            split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None,
                      in_memory=True, reuse_backup=copy)

    def test_in_memory_verify_mismatch_leaves_the_file_untouched(self):
        self.fill(120)
        before = self.state.read_bytes()
        real = codec.PayloadCodec.decode

        def damaged(self_, value):
            return real(self_, value).replace('N/A', 'n/a', 1)

        with patch.object(codec.PayloadCodec, 'decode', damaged):
            with self.assertRaises(split.SplitError):
                split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None,
                          in_memory=True)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse(stream_store.stream_store_path(self.state).exists())

    def check_split(self, **options):
        self.fill()
        identity = split._identity(self.state)
        evidence = self.dir / 'evidence.json'
        result = split.run(self.state, backup_dir=self.dir / 'backup', evidence=evidence, any_time=True,
                           log=lambda *a, **k: None, **options)
        self.assertEqual(json.loads(evidence.read_text())['stage'], 'COMPLETE')
        self.assertEqual(result['copy']['rows'], len(self.source))
        self.assertGreater(result['copy']['encoded_rows'], 0)
        stream = stream_store.stream_store_path(self.state)
        self.assertFalse((self.dir / split.PARTIAL_NAME).exists())
        with closing(sqlite3.connect(stream)) as db:
            copied = db.execute('SELECT rowid,* FROM market_stream_records ORDER BY rowid').fetchall()
            small = {t: db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall() for t in split.SMALL_TABLES}
            reader = codec.PayloadCodec(db)
            decoded = [(*row[:11], reader.decode(row[11])) for row in copied]
        self.assertEqual(decoded, self.source)  # every column, every rowid, byte-exact payloads
        self.assertEqual(small, self.small)
        with closing(sqlite3.connect(self.state)) as db:
            for table in stream_store.STREAM_TABLES:
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)
        self.assertEqual(split._identity(self.state), identity)  # same file: the collector's pin still holds
        with LocalStateConnection(self.state, require_existing=True) as conn:
            self.assertEqual(conn.schema_version(), SCHEMA_VERSION)
            self.assertEqual(conn.verification['mode'], 'RECEIPT')
        self.assertIsNone(receipts.receipt_problem(stream))
        backup = Path(result['backup']['path'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0], len(self.source))
        # The writer now follows the split file and keeps the rowid series going.
        writer = self.open_writer()
        self.assertTrue(writer.split)
        writer.submit(quote(999))
        writer.flush()
        self.assertGreater(self.rows(stream)[-1][0], self.source[-1][0])
        self.assertTrue(codec.is_encoded(self.rows(stream)[-1][2]))
        return result

    def test_verify_mismatch_aborts_before_state_store_changes(self):
        self.fill(120)
        real = codec.PayloadCodec.decode

        def damaged(self_, value):
            text = real(self_, value)
            return text.replace('N/A', 'n/a', 1)

        with patch.object(codec.PayloadCodec, 'decode', damaged):
            with self.assertRaises(split.SplitError):
                split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None)
        self.assertFalse(stream_store.stream_store_path(self.state).exists())
        with closing(sqlite3.connect(self.state)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM market_stream_records').fetchone()[0], len(self.source))

    def test_refuses_without_fresh_receipt_or_with_running_writer(self):
        self.fill(10)
        receipts.invalidate(self.state, 'TEST')
        with self.assertRaisesRegex(split.SplitError, 'STATE_RECEIPT_NOT_FRESH'):
            split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None)
        LocalStateConnection(self.state, verify=True).close()
        writer = self.open_writer()
        writer.submit(quote(500))
        writer.flush()  # holds the owner lock and an open run
        with self.assertRaises(split.SplitError):
            split.run(self.state, backup_dir=None, evidence=None, any_time=True, log=lambda *a, **k: None)

    def test_night_window(self):
        import datetime
        self.assertTrue(split.in_night_window(datetime.datetime(2026, 10, 27, 20, 1)))
        self.assertTrue(split.in_night_window(datetime.datetime(2026, 10, 28, 3, 44)))
        self.assertFalse(split.in_night_window(datetime.datetime(2026, 10, 28, 3, 45)))
        self.assertFalse(split.in_night_window(datetime.datetime(2026, 10, 27, 19, 59)))


if __name__ == '__main__':
    unittest.main()
