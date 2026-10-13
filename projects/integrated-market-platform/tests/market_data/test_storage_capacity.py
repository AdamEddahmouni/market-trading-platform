"""Offline capacity decisions and read-only accounting in disposable stores."""
import hashlib
import importlib.util
from contextlib import closing, redirect_stdout
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.local_state.connection import LocalStateConnection


class StorageCapacityTests(unittest.TestCase):
    def test_capacity_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('market_platform_foundation.market_data.capacity'))

    def test_wal_and_shared_database_use_the_same_ceiling(self):
        from market_platform_foundation.market_data.capacity import capacity_status
        status = capacity_status(400 * 1024**2, wal_bytes=30 * 1024**2)
        self.assertEqual(status['state'], 'WARNING')
        self.assertEqual(status['remaining_bytes'], 74 * 1024**2)
        self.assertEqual(status['retention_action'], 'PRESERVE_ALL_STOP_BEFORE_BOUND')
        stop = capacity_status(505 * 1024**2)
        self.assertEqual(stop['state'], 'STOP_REQUIRED')
        self.assertEqual(stop['remaining_bytes'], 0)

    def test_free_disk_reserve_can_be_the_binding_limit(self):
        from market_platform_foundation.market_data.capacity import capacity_status
        status = capacity_status(20 * 1024**2, free_disk_bytes=7 * 1024**2)
        self.assertEqual(status['state'], 'STOP_REQUIRED')
        self.assertEqual(status['binding_limit'], 'DISK_FREE')
        status = capacity_status(20 * 1024**2, free_disk_bytes=20 * 1024**2)
        self.assertEqual(status['remaining_bytes'], 12 * 1024**2)

    def test_invalid_numbers_or_unapproved_higher_ceiling_fail_closed(self):
        from market_platform_foundation.market_data.capacity import capacity_status, Workload
        for value in (-1, True, float('nan'), '512'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                capacity_status(value)
        with self.assertRaises(ValueError):
            capacity_status(0, max_database_bytes=1024**3)
        for changes in ({'targets': 21}, {'records_per_second': float('inf')},
                        {'active_seconds_per_day': 86401}, {'bytes_per_record': 0},
                        {'targets': True}, {'source': ''}):
            row = dict(source='kraken', capability='CRYPTO_TRADES', targets=1,
                       records_per_second=5, bytes_per_record=1500, active_seconds_per_day=86400)
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Workload(**row)

    def test_forecast_has_per_source_type_and_session_bounds(self):
        from market_platform_foundation.market_data.capacity import capacity_status, forecast, Workload
        rows = (Workload('moomoo', 'US_EQUITY_L1', 20, 0.5, 1500, 23400),
                Workload('kraken', 'CRYPTO_TRADES', 1, 5, 1500, 86400))
        result = forecast(rows, duration_seconds=86400, capacity=capacity_status(0), growth_margin=1)
        self.assertEqual(result['projected_growth_bytes'], 999000000)
        self.assertEqual(result['state'], 'INSUFFICIENT_CAPACITY')
        self.assertEqual(result['workloads'][0]['projected_records'], 234000)
        self.assertEqual(result['workloads'][1]['projected_records'], 432000)
        self.assertEqual(result['workloads'][0]['source'], 'moomoo')
        overnight = forecast(rows[:1], duration_seconds=12*3600, capacity=capacity_status(0), growth_margin=1)
        self.assertEqual(overnight['projected_growth_bytes'], 351000000)
        self.assertEqual(overnight['continuous_peak_growth_bytes'], 648000000)
        self.assertEqual(overnight['state'], 'FITS_MODELED_WINDOW')

    def test_forecast_does_not_call_idle_or_missing_workload_sustainable(self):
        from market_platform_foundation.market_data.capacity import capacity_status, forecast, Workload
        with self.assertRaises(ValueError):
            forecast((), duration_seconds=3600, capacity=capacity_status(0))
        idle = forecast((Workload('moomoo', 'US_EQUITY_L1', 1, 0, 1500, 23400),),
                        duration_seconds=3600, capacity=capacity_status(0))
        self.assertEqual(idle['state'], 'NO_ACTIVITY_MODELED')
        self.assertIsNone(idle['seconds_to_bound_at_peak_rate'])
        with self.assertRaises(ValueError):
            forecast((Workload('kraken', 'CRYPTO_TRADES', 1, 5, 1500, 86400),),
                     duration_seconds=float('nan'), capacity=capacity_status(0))

    def test_other_shared_growth_and_margin_are_not_omitted(self):
        from market_platform_foundation.market_data.capacity import capacity_status, forecast, Workload
        row = Workload('rss', 'NEWS', 1, 1/3600, 4000, 86400)
        result = forecast((row,), duration_seconds=7*86400, capacity=capacity_status(0),
                          growth_margin=1.25, other_bytes_per_day=1000000)
        self.assertEqual(result['projected_growth_bytes'], 9590000)
        self.assertEqual(result['growth_margin'], 1.25)

    def test_finite_inputs_that_overflow_the_model_fail_closed(self):
        from market_platform_foundation.market_data.capacity import capacity_status, forecast, Workload
        with self.assertRaises((ValueError, OverflowError)) as caught:
            forecast((Workload('kraken', 'CRYPTO_TRADES', 20, 1e308, 1500, 86400),),
                     duration_seconds=3600, capacity=capacity_status(0))
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(str(caught.exception), 'CAPACITY_MODEL_OVERFLOW')

    def test_inspection_preserves_schema_payloads_and_attributes_utf8_bytes(self):
        from market_platform_foundation.market_data.capacity import inspect_storage
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.sqlite3'
            with LocalStateConnection(path) as conn:
                payload = json.dumps({'headline': 'é'}, ensure_ascii=False)
                conn.execute('INSERT INTO news_collection_records VALUES (?,?,?,?,?,?,?)',
                             ('n1', 'rss', 'feed', 'p', 'r', 1.0, payload))
                conn.execute('INSERT INTO market_stream_records VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                             ('r1', 'kraken', 'BTC/USD', 'CRYPTO_TRADES', 1, 1, 2, 3, 4, 'native:1', '{}'))
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            report = inspect_storage(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
            self.assertEqual(report['schema_version'], 13)
            groups = {row['capability']: row for row in report['groups']}
            self.assertEqual(groups['NEWS']['payload_bytes'], len(payload.encode('utf-8')))
            self.assertEqual(groups['CRYPTO_TRADES']['records'], 1)
            self.assertEqual(report['capacity']['max_database_bytes'], 512 * 1024**2)
            self.assertGreater(report['table_storage_bytes']['market_stream_records'], 0)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(conn.execute('SELECT payload_json FROM news_collection_records').fetchone()[0], payload)

    def test_inspection_never_creates_missing_store_and_bounds_query_work(self):
        from market_platform_foundation.market_data.capacity import inspect_storage
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'absent' / 'state.sqlite3'
            with self.assertRaises(FileNotFoundError):
                inspect_storage(missing)
            self.assertFalse(missing.parent.exists())
            path = Path(tmp) / 'state.sqlite3'
            with LocalStateConnection(path) as conn:
                for i in range(100):
                    conn.execute('INSERT INTO market_stream_records VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                 (str(i), 'kraken', 'BTC/USD', 'CRYPTO_TRADES', i, i, i, i, i, str(i), '{}'))
            with self.assertRaisesRegex(ValueError, 'CAPACITY_INSPECTION_LIMIT'):
                inspect_storage(path, max_vm_steps=1)

    def test_inspection_does_not_migrate_legacy_schema_or_create_collection_tables(self):
        from market_platform_foundation.market_data.capacity import inspect_storage
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'legacy.sqlite3'
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE schema_meta (schema_version INTEGER, applied_at TEXT)')
                conn.execute("INSERT INTO schema_meta VALUES (11,'before')")
                conn.commit()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            report = inspect_storage(path)
            self.assertEqual(report['schema_version'], 11)
            self.assertEqual(report['groups'], [])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_readonly_inspection_sees_uncheckpointed_wal(self):
        from market_platform_foundation.market_data.capacity import inspect_storage
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.sqlite3'
            with LocalStateConnection(path) as conn:
                conn.execute('INSERT INTO market_stream_records VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                             ('r1', 'kraken', 'BTC/USD', 'CRYPTO_TRADES', 1, 1, 2, 3, 4, 'native:1', '{}'))
                wal = Path(str(path)+'-wal')
                before = hashlib.sha256(wal.read_bytes()).hexdigest()
                report = inspect_storage(path)
                self.assertEqual(report['groups'][0]['records'], 1)
                self.assertGreater(report['wal_bytes'], 0)
                self.assertEqual(hashlib.sha256(wal.read_bytes()).hexdigest(), before)

    def test_capacity_cli_exists_before_its_contract_is_implemented(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.market_data_capacity'))

    def test_cli_requires_explicit_profile_and_returns_capacity_block(self):
        from tools.market_data_capacity import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'profile.json'
            path.write_text(json.dumps({'name': 'synthetic-raw', 'evidence_basis': 'SYNTHETIC_ASSUMPTION',
                'workloads': [{'source': 'kraken', 'capability': 'CRYPTO_TRADES', 'targets': 20,
                              'records_per_second': 5, 'bytes_per_record': 1500,
                              'active_seconds_per_day': 86400}]}), encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['--profile', str(path), '--hours', '12'])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(result['forecast']['state'], 'INSUFFICIENT_CAPACITY')
            self.assertFalse(result['activation_authorized'])
            self.assertEqual(result['profile']['evidence_basis'], 'SYNTHETIC_ASSUMPTION')
            self.assertEqual(result['storage_basis'], 'DECLARED_EMPTY_STORE_NOT_MEASURED')

    def test_cli_rejects_sampling_or_retention_fields_and_oversize_profiles(self):
        from tools.market_data_capacity import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'profile.json'
            for contents in (json.dumps({'name': 'bad', 'workloads': [], 'expire_days': 7}), 'x' * (1024**2 + 1)):
                path.write_text(contents, encoding='utf-8')
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(['--profile', str(path)])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(output.getvalue())['state'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
