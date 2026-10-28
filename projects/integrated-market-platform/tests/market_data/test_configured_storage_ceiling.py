"""The shared DB+WAL ceiling: 512 MiB unless the operator opts in, never above the approved 16 GiB."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from market_platform_foundation.local_state.connection import LocalStateConnection  # noqa: E402
from market_platform_foundation.market_data.capacity import (  # noqa: E402
    APPROVED_MAX_DATABASE_BYTES, DEFAULT_MAX_DATABASE_BYTES, MAX_DATABASE_MIB_ENV, capacity_status,
    configured_max_database_bytes)
from market_platform_foundation.market_data.persistence import MarketStreamWriter  # noqa: E402
from market_platform_foundation.news.collection import CollectionJob, NewsCollector  # noqa: E402

MiB, GiB = 1024**2, 1024**3


class ConfiguredCeilingTests(unittest.TestCase):
    def test_unset_or_blank_keeps_the_shipped_ceiling(self):
        for env in ({}, {MAX_DATABASE_MIB_ENV: ''}, {MAX_DATABASE_MIB_ENV: '  '}):
            self.assertEqual(configured_max_database_bytes(env), DEFAULT_MAX_DATABASE_BYTES)
        self.assertEqual(capacity_status(0, env={})['max_database_bytes'], 512 * MiB)

    def test_operator_may_opt_in_up_to_the_approved_ceiling(self):
        self.assertEqual(APPROVED_MAX_DATABASE_BYTES, 16 * GiB)
        self.assertEqual(configured_max_database_bytes({MAX_DATABASE_MIB_ENV: '8192'}), 8 * GiB)
        # The collector's owner-approved budget (15,872 MiB) is a configured value below the ceiling.
        self.assertEqual(configured_max_database_bytes({MAX_DATABASE_MIB_ENV: '15872'}), 15872 * MiB)
        self.assertEqual(configured_max_database_bytes({MAX_DATABASE_MIB_ENV: '256'}), 256 * MiB)

    def test_malformed_or_unapproved_values_fail_closed(self):
        for value, reason in (('16385', 'CAPACITY_UNAPPROVED_HIGHER_CEILING'), ('99999999', 'CAPACITY_UNAPPROVED_HIGHER_CEILING'),
                              ('8GiB', 'CAPACITY_INVALID_CONFIGURED_CEILING'), ('-1', 'CAPACITY_INVALID_CONFIGURED_CEILING'),
                              ('1', 'CAPACITY_INVALID_CONFIGURED_CEILING'), ('8192.0', 'CAPACITY_INVALID_CONFIGURED_CEILING')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, reason):
                configured_max_database_bytes({MAX_DATABASE_MIB_ENV: value})

    def test_capacity_status_never_exceeds_the_configured_ceiling(self):
        with self.assertRaisesRegex(ValueError, 'CAPACITY_UNAPPROVED_HIGHER_CEILING'):
            capacity_status(0, max_database_bytes=GiB, env={})
        opted = {MAX_DATABASE_MIB_ENV: '8192'}
        status = capacity_status(600 * MiB, env=opted)
        self.assertEqual((status['state'], status['max_database_bytes']), ('READY', 8 * GiB))
        self.assertEqual(status['retention_action'], 'PRESERVE_ALL_STOP_BEFORE_BOUND')
        self.assertEqual(capacity_status(8 * GiB - 7 * MiB, env=opted)['state'], 'STOP_REQUIRED')
        with self.assertRaisesRegex(ValueError, 'CAPACITY_UNAPPROVED_HIGHER_CEILING'):
            capacity_status(0, max_database_bytes=9 * GiB, env=opted)

    def test_writers_take_the_configured_ceiling_from_the_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            LocalStateConnection(path).close()
            job = [CollectionJob('finviz', '', 'US_EQUITIES', 120)]
            for value, expected in (('', 512 * MiB), ('8192', 8 * GiB)):
                with self.subTest(value=value), patch.dict(os.environ, {MAX_DATABASE_MIB_ENV: value}):
                    writer = MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',), acquire=False)
                    self.assertEqual(writer.max_database_bytes, expected)
                    writer.stop()
                    connection = LocalStateConnection(path)
                    try:
                        self.assertEqual(NewsCollector(connection, job, lambda _job: ([], {})).max_database_bytes, expected)
                    finally:
                        connection.close()
            with patch.dict(os.environ, {MAX_DATABASE_MIB_ENV: ''}):
                with self.assertRaisesRegex(ValueError, 'MARKET_CAPTURE_STORAGE_LIMIT_INVALID'):
                    MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',), acquire=False,
                                       max_database_bytes=GiB)
            with patch.dict(os.environ, {MAX_DATABASE_MIB_ENV: '16385'}):
                with self.assertRaisesRegex(ValueError, 'MARKET_CAPTURE_STORAGE_LIMIT_INVALID'):
                    MarketStreamWriter(path, sources=('moomoo',), symbols=('AAPL',), acquire=False)

    def test_supervisor_enforces_the_same_configured_bound(self):
        from market_platform_foundation.news.supervision import CollectionSupervisor
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            db = LocalStateConnection(path)
            try:
                base = {'IMP_PF01_SUPERVISION_ENABLED': '1', 'IMP_NEWS_COLLECTION_ENABLED': '1',
                        'IMP_PERSIST_STATE': '1', 'IMP_STATE_DIR': directory}
                for value, expected in (('', 512 * MiB), ('8192', 8 * GiB)):
                    owner = CollectionSupervisor(db, spawn=lambda: None, env={**base, MAX_DATABASE_MIB_ENV: value})
                    self.assertEqual((owner._max_bytes, owner._storage_fault()), (expected, None))
                    owner.stop()
                with self.assertRaisesRegex(ValueError, 'CAPACITY_UNAPPROVED_HIGHER_CEILING'):
                    CollectionSupervisor(db, spawn=lambda: None, env={**base, MAX_DATABASE_MIB_ENV: '16385'})
                # A ceiling below the existing store plus reserve is a stop, never a deletion.
                with self.assertRaisesRegex(ValueError, 'SUPERVISOR_STORAGE_UNAVAILABLE'):
                    CollectionSupervisor(db, spawn=lambda: None, env={**base, MAX_DATABASE_MIB_ENV: '2'})
                self.assertTrue(path.is_file())
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()
