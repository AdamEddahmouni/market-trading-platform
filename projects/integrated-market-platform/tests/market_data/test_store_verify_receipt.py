"""One whole-store integrity scan per boot, recorded in a receipt (2026-10-27 outage: a full scan on every open).

A receipt is trusted only for the same file, the same boot and a bounded age, and an open that trusts it still
checks the trading-critical tables. Anything else, or any damage found, runs the full check and fails closed.
"""
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state import integrity_receipt as receipts
from market_platform_foundation.local_state.connection import CorruptStateError, LocalStateConnection
from tools.platform import verify_state_store

UNSUPERVISED = {key: value for key, value in os.environ.items()
                if key not in ('IMP_PF01_SUPERVISOR_OWNER', 'IMP_STATE_VERIFY_MAX_AGE_HOURS')}


class ReceiptCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'imp-state.sqlite3'
        environment = patch.dict('os.environ', UNSUPERVISED, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        with LocalStateConnection(self.path, verify=False) as connection:
            connection.execute('CREATE TABLE bulk_rows (id INTEGER PRIMARY KEY, body TEXT)')
            connection.executemany('INSERT INTO bulk_rows (body) VALUES (?)', [('x' * 400,) for _ in range(400)])
        self.full = self.critical = 0

    def open(self, **kwargs):
        real_full, real_critical = receipts.full_check, receipts.critical_check

        def full(conn):
            self.full += 1
            return real_full(conn)

        def critical(conn, *args):
            self.critical += 1
            return real_critical(conn, *args)

        with patch.object(receipts, 'full_check', full), patch.object(receipts, 'critical_check', critical):
            connection = LocalStateConnection(self.path, require_existing=True, **kwargs)
        connection.close()
        return connection.verification

    def receipt(self):
        return json.loads(receipts.receipt_path(self.path).read_text(encoding='utf-8'))

    def rewrite_receipt(self, **changes):
        body = self.receipt()
        for key, value in changes.items():
            if key in ('st_dev', 'st_ino', 'size_bytes'):
                body['identity'][key] = value
            else:
                body[key] = value
        receipts.receipt_path(self.path).write_text(json.dumps(body), encoding='utf-8')

    def damage_table(self, table):
        """Overwrite the header of ``table``'s root page in place (same file, same size)."""
        connection = sqlite3.connect(self.path)
        try:
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            page_size = connection.execute('PRAGMA page_size').fetchone()[0]
            root = connection.execute('SELECT rootpage FROM sqlite_schema WHERE name = ?', (table,)).fetchone()[0]
        finally:
            connection.close()
        with open(self.path, 'r+b') as handle:
            handle.seek((root - 1) * page_size)
            handle.write(b'\xff' * 64)


class ReceiptPolicyTests(ReceiptCase):
    def test_first_open_runs_the_full_check_and_writes_the_receipt(self):
        verification = self.open()
        self.assertEqual((verification['mode'], verification['reason']), ('FULL', 'NO_RECEIPT'))
        self.assertEqual(self.full, 1)
        receipt = self.receipt()
        self.assertEqual((receipt['schema'], receipt['result']), (receipts.RECEIPT_SCHEMA, 'ok'))
        stat = self.path.stat()
        self.assertEqual((receipt['identity']['st_dev'], receipt['identity']['st_ino']), (stat.st_dev, stat.st_ino))
        self.assertEqual(receipts.read_status(self.path)['state'], 'DONE')
        self.assertIsNone(receipts.verification_in_progress(self.path))

    def test_a_later_open_trusts_the_receipt_and_checks_only_the_critical_tables(self):
        self.open()
        self.full = self.critical = 0
        verification = self.open()
        self.assertEqual(verification['mode'], 'RECEIPT')
        self.assertEqual((self.full, self.critical), (0, 1))

    def test_the_full_check_runs_again_whenever_the_receipt_does_not_stand(self):
        cases = {
            'REBOOTED_SINCE_CHECK': lambda: self.rewrite_receipt(boot_epoch=self.receipt()['boot_epoch'] - 3600),
            'RECEIPT_EXPIRED': lambda: self.rewrite_receipt(checked_at_epoch=time.time() - 49 * 3600),
            'STORE_REPLACED': lambda: self.rewrite_receipt(st_ino=self.receipt()['identity']['st_ino'] + 1),
            'STORE_SHRANK': lambda: self.rewrite_receipt(size_bytes=self.path.stat().st_size + 10 ** 9),
            'RECEIPT_SCHEMA_UNKNOWN': lambda: self.rewrite_receipt(schema='imp-store-verified/0.0.1'),
            'RECEIPT_INVALIDATED': lambda: receipts.invalidate(self.path, 'test'),
            'NO_RECEIPT': lambda: receipts.receipt_path(self.path).write_text('{', encoding='utf-8'),
        }
        for reason, spoil in cases.items():
            with self.subTest(reason):
                self.open()
                spoil()
                self.full = 0
                verification = self.open()
                self.assertEqual((verification['mode'], verification['reason']), ('FULL', reason))
                self.assertEqual(self.full, 1)

    def test_a_shorter_configured_age_expires_the_receipt_sooner(self):
        self.open()
        self.rewrite_receipt(checked_at_epoch=time.time() - 2 * 3600)
        with patch.dict('os.environ', {'IMP_STATE_VERIFY_MAX_AGE_HOURS': '1'}):
            self.assertEqual(self.open()['reason'], 'RECEIPT_EXPIRED')
        self.rewrite_receipt(checked_at_epoch=time.time() - 2 * 3600)
        with patch.dict('os.environ', {'IMP_STATE_VERIFY_MAX_AGE_HOURS': '0'}):  # clamped to one hour, never zero
            self.assertEqual(self.open()['reason'], 'RECEIPT_EXPIRED')

    def test_verify_true_always_runs_the_full_check(self):
        self.open()
        self.full = 0
        verification = self.open(verify=True)
        self.assertEqual((verification['mode'], verification['reason']), ('FULL', 'FULL_CHECK_REQUESTED'))
        self.assertEqual(self.full, 1)

    def test_verify_false_and_a_supervised_child_check_nothing(self):
        self.assertEqual(self.open(verify=False)['mode'], 'SKIPPED')
        with patch.dict('os.environ', {'IMP_PF01_SUPERVISOR_OWNER': 'owner-1'}):
            self.assertEqual(self.open()['mode'], 'SUPERVISED')
            self.assertEqual(self.open(verify=True)['mode'], 'FULL')
        self.assertEqual(self.full, 1)


class DamageTests(ReceiptCase):
    def test_damage_in_a_critical_table_fails_closed_despite_a_valid_receipt(self):
        self.open()
        self.assertIsNone(receipts.receipt_problem(self.path))
        self.damage_table('paper_sessions')
        self.assertIsNone(receipts.receipt_problem(self.path))  # same file, same size, same boot
        with self.assertRaises((CorruptStateError, sqlite3.DatabaseError)):
            self.open()
        self.assertEqual(self.receipt()['result'], receipts.INVALIDATED)
        self.full = 0
        with self.assertRaises((CorruptStateError, sqlite3.DatabaseError)):
            self.open()
        self.assertEqual(self.full, 1)  # the next open scans the whole file again, and still refuses

    def test_damage_elsewhere_is_found_by_the_nightly_check_and_then_every_open_refuses(self):
        self.open()
        self.damage_table('bulk_rows')
        self.assertEqual(self.open()['mode'], 'RECEIPT')  # the documented trade-off: a big table waits for the scan
        code, body = verify_state_store.verify(self.path, label='test')
        self.assertEqual((code, body['result']), (verify_state_store.EXIT_NOT_OK, receipts.INVALIDATED))
        self.assertEqual(self.receipt()['result'], receipts.INVALIDATED)
        with self.assertRaises((CorruptStateError, sqlite3.DatabaseError)):
            self.open()

    def test_damage_met_while_running_invalidates_the_receipt(self):
        self.open()
        connection = LocalStateConnection(self.path, require_existing=True)
        try:
            self.assertEqual(connection.verification['mode'], 'RECEIPT')
            self.damage_table('bulk_rows')
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute('SELECT count(*), max(length(body)) FROM bulk_rows').fetchone()
        finally:
            connection.close()
        self.assertEqual(self.receipt()['result'], receipts.INVALIDATED)
        self.assertTrue(self.receipt()['reason'].startswith('RUNTIME:'))

    def test_integrity_ok_false_invalidates_the_receipt(self):
        self.open()
        connection = LocalStateConnection(self.path, require_existing=True)
        try:
            with patch.object(receipts, 'full_check', return_value='*** in database main ***'):
                self.assertFalse(connection.integrity_ok())
        finally:
            connection.close()
        self.assertEqual(self.receipt()['result'], receipts.INVALIDATED)


class SingleFlightTests(ReceiptCase):
    def test_openers_at_the_same_time_share_one_full_check(self):
        real_full, seen_running = receipts.full_check, []

        def slow_full(conn):
            self.full += 1
            seen_running.append(receipts.verification_in_progress(self.path) is not None)
            time.sleep(1.0)
            return real_full(conn)

        results, errors = [], []

        def opener():
            try:
                connection = LocalStateConnection(self.path, require_existing=True)
                results.append(dict(connection.verification))
                connection.close()
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

        with patch.object(receipts, 'full_check', slow_full):
            threads = [threading.Thread(target=opener) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertEqual(self.full, 1)
        self.assertEqual(sorted(result['mode'] for result in results), ['FULL', 'RECEIPT', 'RECEIPT'])
        self.assertEqual({result['reason'] for result in results if result['mode'] == 'RECEIPT'},
                         {'VERIFIED_WHILE_WAITING'})
        self.assertEqual(seen_running, [True])

    def test_a_stale_heartbeat_is_not_a_running_check(self):
        receipts.status_path(self.path).write_text(json.dumps(
            {'schema': receipts.STATUS_SCHEMA, 'state': receipts.VERIFYING, 'pid': 1,
             'heartbeat_epoch': time.time() - receipts.STALE_HEARTBEAT_SECONDS - 5}), encoding='utf-8')
        self.assertIsNone(receipts.verification_in_progress(self.path))
        receipts.status_path(self.path).write_text(json.dumps(
            {'schema': receipts.STATUS_SCHEMA, 'state': receipts.VERIFYING, 'pid': 1,
             'heartbeat_epoch': time.time()}), encoding='utf-8')
        self.assertIsNotNone(receipts.verification_in_progress(self.path))


class VerifierToolTests(ReceiptCase):
    def test_ok_writes_a_receipt_that_a_later_open_trusts(self):
        code, body = verify_state_store.verify(self.path, label='test')
        self.assertEqual((code, body['result'], body['receipt_before']), (0, 'ok', 'NO_RECEIPT'))
        self.assertEqual(self.receipt()['checker']['label'], 'test')
        self.assertEqual(self.open()['mode'], 'RECEIPT')

    def test_busy_and_missing(self):
        lock = receipts.VerifyLock(self.path)
        self.assertTrue(lock.acquire(blocking=False))
        try:
            code, body = verify_state_store.verify(self.path, label='test')
        finally:
            lock.release()
        self.assertEqual((code, body['result']), (verify_state_store.EXIT_BUSY, 'BUSY'))
        code, _ = verify_state_store.verify(self.path.with_name('absent.sqlite3'), label='test')
        self.assertEqual(code, verify_state_store.EXIT_MISSING)

    def test_the_tool_never_writes_the_store(self):
        before = self.path.read_bytes()
        verify_state_store.verify(self.path, label='test')
        self.assertEqual(self.path.read_bytes(), before)

    def test_several_stores_are_each_checked_and_the_worst_code_is_returned(self):
        stream = self.path.with_name('imp-market-stream.sqlite3')
        connection = sqlite3.connect(stream)
        connection.execute('CREATE TABLE stream_store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        connection.commit()
        connection.close()
        with patch('builtins.print'):
            code = verify_state_store.main(['--store', str(self.path), '--store', str(stream), '--label', 'test'])
        self.assertEqual(code, verify_state_store.EXIT_OK)
        self.assertEqual(self.receipt()['result'], 'ok')
        self.assertEqual(json.loads(receipts.receipt_path(stream).read_text(encoding='utf-8'))['result'], 'ok')
        with patch('builtins.print'):
            code = verify_state_store.main(['--store', str(self.path), '--store', str(stream.with_name('absent.sqlite3'))])
        self.assertEqual(code, verify_state_store.EXIT_MISSING)
        self.assertEqual(verify_state_store.worst([0, 4, 3, 2]), verify_state_store.EXIT_NOT_OK)
        self.assertEqual(verify_state_store.worst([0, 4, 3]), verify_state_store.EXIT_BUSY)

    def test_the_keeper_checks_the_stream_store_once_it_exists(self):
        from tools.platform.imp_keeper import KeeperPaths, WindowsOperations

        portable = self.path.parent
        (portable / 'NORMAL-CONFIG.json').write_text(json.dumps({'state_directory': '.'}), encoding='utf-8')
        ops = WindowsOperations(KeeperPaths(app=Path(__file__).resolve().parents[2], portable=portable))
        self.assertEqual([p.name for p in ops._stores()], ['imp-state.sqlite3'])
        verify_state_store.verify(self.path, label='test')
        self.assertIsNotNone(ops.store_receipt_age())
        stream = self.path.with_name('imp-market-stream.sqlite3')
        connection = sqlite3.connect(stream)
        connection.execute('CREATE TABLE stream_store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        connection.commit()
        connection.close()
        self.assertEqual([p.name for p in ops._stores()], ['imp-state.sqlite3', 'imp-market-stream.sqlite3'])
        self.assertIsNone(ops.store_receipt_age())  # the stream store has no receipt yet: the nightly check runs
        verify_state_store.verify(stream, label='test')
        self.assertIsNotNone(ops.store_receipt_age())
        self.assertFalse(ops.store_verifying())


class StartupReportTests(unittest.TestCase):
    def test_the_startup_report_says_how_the_store_was_verified_and_passes_the_leak_audit(self):
        from market_platform_foundation.local_state import startup
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload

        with tempfile.TemporaryDirectory() as directory, \
                patch.dict('os.environ', dict(UNSUPERVISED, IMP_STATE_DIR=directory), clear=True):
            startup.reset_local_state_for_tests()
            try:
                first = startup.startup_report()
                startup.reset_local_state_for_tests()
                second = startup.startup_report()
            finally:
                startup.reset_local_state_for_tests()
        self.assertEqual(first['state_verification']['mode'], 'FULL')
        self.assertEqual(second['state_verification']['mode'], 'RECEIPT')
        assert_no_secrets_in_payload(second)


class BootEpochTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows boot clock')
    def test_boot_epoch_is_derived_from_uptime_since_boot(self):
        # boot_epoch relies on time.monotonic() being GetTickCount64 (uptime since boot) on Windows.
        self.assertEqual(time.get_clock_info('monotonic').implementation, 'GetTickCount64()')
        expected = time.time() - time.monotonic()
        self.assertAlmostEqual(receipts.boot_epoch(), expected, delta=1.0)

    def test_boot_epoch_is_stable_between_calls(self):
        first = receipts.boot_epoch()
        if first is None:
            self.skipTest('no uptime source on this platform')
        self.assertAlmostEqual(receipts.boot_epoch(), first, delta=1.0)


if __name__ == '__main__':
    unittest.main()
