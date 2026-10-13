"""PF-01 operational preflight: disposable SQLite, no provider, no process."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.capacity import capacity_status
from market_platform_foundation.news.supervision import CollectionSupervisor
from tools.platform import pf01_preflight, pf01_supervisor
from tools.platform.pf01_preflight import preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.env = {'IMP_STATE_DIR': self.temp.name, 'IMP_PERSIST_STATE': '1', 'IMP_PF01_SUPERVISION_ENABLED': '1',
                    'IMP_NEWS_COLLECTION_ENABLED': '1', 'IMP_NEWS_COLLECTION_PROVIDERS': 'rss',
                    'IMP_NEWS_COLLECTION_UNIVERSES': 'CRYPTO'}
        self.market = {'IMP_MARKET_PERSISTENCE_ENABLED': '1', 'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo,kraken',
                       'IMP_MARKET_PERSISTENCE_SYMBOLS': 'AAPL,XA01:0123456789ABCDEF', 'IMP_MARKET_SUPPLY_ENABLED': '1',
                       'IMP_MARKET_SUPPLY_TARGETS': 'moomoo:AAPL@US_EQUITY_L1,kraken:XA01:0123456789ABCDEF@CRYPTO_TRADES',
                       'IMP_LIVE_OBSERVATIONAL': '1', 'IMP_MOOMOO_LIVE': '1', 'IMP_CRYPTO_LIVE': '1'}

    def states(self, env=None):
        report = preflight(self.env if env is None else env)
        return report, {check['check']: (check['state'], check['reason']) for check in report['checks']}

    def test_news_only_configuration_is_ready_except_what_was_not_inspected(self):
        report, states = self.states()
        self.assertEqual({name: state for name, (state, _) in states.items()},
                         {'build_identity': 'NOT VERIFIED', 'execution_gates': 'READY', 'supervision_gate': 'READY', 'collection_mode': 'READY', 'storage': 'READY',
                          'schema': 'READY', 'capacity': 'READY', 'supervisor_owner': 'READY', 'market_writer_owner': 'READY',
                          'news_jobs': 'READY', 'news_provider_access': 'NOT VERIFIED', 'market_targets': 'READY'})
        # Nothing was unreadable, so the result is the operator's list, never UNKNOWN and never READY.
        self.assertEqual((report['overall'], report['activation_requested'], report['providers_contacted']), ('NOT VERIFIED', False, False))
        self.assertIn('HOST_POWER_AND_SLEEP_POLICY', report['not_inspected'])
        self.assertEqual(tuple(report['ai_credential_prefixes_withheld']), pf01_supervisor.AI_CREDENTIAL_PREFIXES)
        self.assertEqual((report['ai_credentials_forwarded_to_child'], report['emergency_stop']),
                         (False, 'CTRL_C_ONCE_IN_SUPERVISOR_TERMINAL'))
        self.assertLess(report['child_stop_bound_seconds'], report['supervisor_lease_seconds'])

    def test_it_changes_nothing_opens_no_socket_and_starts_no_process(self):
        self.states()  # a read-only WAL reader may create the shared-memory sidecar once
        before = {item.name: (item.stat().st_size, item.stat().st_mtime_ns) for item in Path(self.temp.name).iterdir()}
        refuse = AssertionError('preflight must not reach a provider or start a process')
        with patch.object(socket, 'socket', side_effect=refuse), patch.object(socket, 'create_connection', side_effect=refuse), \
                patch.object(subprocess, 'Popen', side_effect=refuse):
            self.states({**self.env, **self.market, 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES': 'moomoo,kraken'})
        after = {item.name: (item.stat().st_size, item.stat().st_mtime_ns) for item in Path(self.temp.name).iterdir()
                 if not item.name.endswith('-shm')}
        self.assertEqual(after, {name: value for name, value in before.items() if not name.endswith('-shm')})
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM news_collection_jobs').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM market_stream_runs').fetchone()[0], 0)

    def test_build_identity_is_ready_only_when_every_manifest_hash_matches(self):
        source = Path(pf01_preflight.__file__)
        relative = source.relative_to(pf01_preflight.ROOT).as_posix()
        manifest = Path(self.temp.name) / 'manifest.json'
        for files, expected in (({relative: hashlib.sha256(source.read_bytes()).hexdigest()}, ('READY', None)),
                                ({relative: '0' * 64}, ('BLOCKED', 'RELEASE_MANIFEST_MISMATCH')),
                                ({'absent.py': '0' * 64}, ('BLOCKED', 'RELEASE_MANIFEST_MISMATCH')),
                                ({'../outside.py': '0' * 64}, ('BLOCKED', 'RELEASE_MANIFEST_MISMATCH')),
                                ({'absent.py': None}, ('UNKNOWN', 'RELEASE_MANIFEST_UNREADABLE')),
                                ({relative: 'not-a-hash'}, ('UNKNOWN', 'RELEASE_MANIFEST_UNREADABLE')),
                                ({}, ('UNKNOWN', 'RELEASE_MANIFEST_UNREADABLE'))):
            manifest.write_text(json.dumps({'files': files}), encoding='utf-8')
            _, states = self.states({**self.env, 'IMP_PF01_RELEASE_MANIFEST': str(manifest)})
            self.assertEqual(states['build_identity'], expected)
        _, states = self.states({**self.env, 'IMP_PF01_RELEASE_MANIFEST': str(manifest) + '.absent'})
        self.assertEqual(states['build_identity'], ('UNKNOWN', 'RELEASE_MANIFEST_UNREADABLE'))

    def test_schedule_reports_each_source_session_without_blocking_a_closed_market(self):
        env = {**self.env, **self.market, 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES': 'moomoo,kraken'}
        saturday = 1792238400.0  # Saturday 2026-10-17 12:00 UTC
        report = preflight(env, clock=lambda: saturday)
        schedule = next(check for check in report['checks'] if check['check'] == 'collection_schedule')
        self.assertEqual((schedule['state'], schedule['sessions']), ('READY', {'kraken': 'CONTINUOUS', 'moomoo': 'CLOSED'}))
        report = preflight(env, clock=lambda: saturday + 5 * 365 * 86400)
        schedule = next(check for check in report['checks'] if check['check'] == 'collection_schedule')
        self.assertEqual((schedule['state'], schedule['reason']), ('UNKNOWN', 'CALENDAR_UNAVAILABLE'))

    def test_open_trading_gate_blocks(self):
        report, states = self.states({**self.env, 'IMP_PAPER_EXECUTION': '1'})
        self.assertEqual(states['execution_gates'], ('BLOCKED', 'EXECUTION_GATE_ENABLED'))
        self.assertEqual(report['overall'], 'BLOCKED')

    def test_disabled_or_non_durable_configuration_blocks(self):
        _, states = self.states({**self.env, 'IMP_PF01_SUPERVISION_ENABLED': '0', 'IMP_PERSIST_STATE': '0'})
        self.assertEqual((states['supervision_gate'], states['collection_mode']),
                         (('BLOCKED', 'SUPERVISION_DISABLED'), ('BLOCKED', 'DURABLE_STATE_REQUIRED')))

    def test_missing_or_relative_storage_blocks_and_is_never_created(self):
        missing = str(Path(self.temp.name) / 'absent')
        for directory, reason in ((missing, 'EXISTING_STORAGE_REQUIRED'), ('relative', 'EXPLICIT_STATE_DIR_REQUIRED')):
            _, states = self.states({**self.env, 'IMP_STATE_DIR': directory})
            self.assertEqual(states['storage'], ('BLOCKED', reason))
            self.assertNotIn('schema', states)
        self.assertFalse(Path(missing).exists())

    def test_store_at_an_older_schema_requires_the_approved_migration_and_is_not_migrated(self):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute('DELETE FROM schema_meta WHERE schema_version>11')
            db.commit()
        _, states = self.states()
        self.assertEqual(states['schema'], ('BLOCKED', 'APPROVED_SCHEMA_MIGRATION_REQUIRED'))
        self.assertNotIn('supervisor_owner', states)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT MAX(schema_version) FROM schema_meta').fetchone()[0], 11)

    def test_active_supervisor_and_active_market_writer_block(self):
        class Child:
            def poll(self): return None
            def stop(self): pass

        with LocalStateConnection(self.path, require_existing=True) as db:
            owner = CollectionSupervisor(db, spawn=Child, env=self.env)
            now_ns = time.time_ns()
            db.execute('INSERT INTO market_stream_runs VALUES (?,?,?,?,NULL)', ('run', now_ns, now_ns, now_ns + 60 * 10**9))
            _, states = self.states()
            self.assertEqual((states['supervisor_owner'], states['market_writer_owner']),
                             (('BLOCKED', 'SUPERVISOR_OWNER_ACTIVE'), ('BLOCKED', 'MARKET_CAPTURE_OWNER_ACTIVE')))
            owner.stop()
            db.execute('UPDATE market_stream_runs SET closed_ns=?', (now_ns,))
        _, states = self.states()
        self.assertEqual((states['supervisor_owner'][0], states['market_writer_owner'][0]), ('READY', 'READY'))

    def test_capacity_stop_blocks_and_warning_is_not_ready(self):
        for used, expected in ((511 * 1024**2, ('BLOCKED', 'CAPACITY_STOP_REQUIRED')),
                               (450 * 1024**2, ('NOT VERIFIED', 'CAPACITY_WARNING_OPERATOR_REVIEW'))):
            with patch.object(pf01_preflight, 'capacity_status',
                              side_effect=lambda size, used=used, **limits: capacity_status(used, **limits)):
                _, states = self.states()
            self.assertEqual(states['capacity'], expected)

    def test_invalid_market_targets_block(self):
        _, states = self.states({**self.env, **self.market, 'IMP_MARKET_SUPPLY_TARGETS': 'moomoo:MSFT@US_EQUITY_L1'})
        self.assertEqual(states['market_targets'], ('BLOCKED', 'MARKET_SUPPLY_TARGET_NOT_PERSISTED'))

    def test_stored_selection_the_writer_would_refuse_blocks(self):
        _, states = self.states({**self.env, **self.market})
        self.assertEqual(states['market_persistence'][0], 'READY')
        many = ','.join(f'S{index}' for index in range(21))
        for change in ({'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo,kraken,ibkr'}, {'IMP_MARKET_PERSISTENCE_SYMBOLS': 'AAPL,' + many},
                       {'IMP_MARKET_PERSISTENCE_SYMBOLS': ''}):
            report, states = self.states({**self.env, **self.market, **change})
            self.assertEqual(states['market_persistence'], ('BLOCKED', 'MARKET_CAPTURE_TARGETS_INVALID'))
            self.assertEqual(report['overall'], 'BLOCKED')

    def test_unreadable_probe_report_is_unknown_not_a_crash(self):
        env = {**self.env, **self.market, 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES': 'moomoo,kraken'}
        with patch('market_platform_foundation.market_data.capability_registry.VerifiedCapabilityRegistry.from_probe_file',
                   side_effect=AttributeError('malformed report')):
            _, states = self.states(env)
        self.assertEqual(states['moomoo_entitlement'], ('UNKNOWN', 'ENTITLEMENT_PROBE_UNREADABLE'))

    def test_configured_targets_without_confirmed_rights_block(self):
        _, states = self.states({**self.env, **self.market})
        self.assertEqual(states['data_rights'], ('BLOCKED', 'ENTITLEMENT_NOT_CONFIRMED'))

    def test_attested_rights_and_a_missing_probe_report_are_never_reported_ready(self):
        env = {**self.env, **self.market, 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES': 'moomoo,kraken'}
        with patch.dict(os.environ, {'IMP_MOOMOO_PROBE_REPORT': str(Path(self.temp.name) / 'no-report.json')}):
            report, states = self.states(env)
        self.assertEqual(states['data_rights'], ('NOT VERIFIED', 'OPERATOR_ATTESTATION_NOT_CHECKABLE_BY_TOOL'))
        self.assertEqual(states['moomoo_entitlement'], ('BLOCKED', 'ENTITLEMENT_PROBE_MISSING'))
        self.assertEqual(states['provider_connectivity'], ('NOT VERIFIED', 'NOT_CONTACTED_BY_PREFLIGHT'))
        self.assertEqual(report['overall'], 'BLOCKED')

    def test_cli_prints_the_report_and_exits_by_overall_state(self):
        unreadable = {**self.env, 'IMP_PF01_RELEASE_MANIFEST': str(self.path) + '.absent'}
        for env, code in ((self.env, 3), (unreadable, 2), ({**self.env, 'IMP_LIVE_EXECUTION': '1'}, 1)):
            output = io.StringIO()
            with patch.dict(os.environ, env), contextlib.redirect_stdout(output):
                self.assertEqual(pf01_supervisor.main(['--preflight']), code)
            self.assertEqual(json.loads(output.getvalue())['kind'], 'PF01_OPERATIONAL_PREFLIGHT')


if __name__ == '__main__':
    unittest.main()
