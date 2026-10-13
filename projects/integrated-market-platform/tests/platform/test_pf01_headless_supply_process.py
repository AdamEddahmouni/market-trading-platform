"""PF-01 headless market supply through real processes.

Real supervisor, the real ``--collect-only`` entry point in a child process,
real runtimes, admission, writer and news worker on disposable SQLite. Only the
vendor transports are synthetic (tests/support/pf01_synthetic_child.py), and
that child logs and refuses every socket use. The entitlement fixtures simulate
an entitled configuration; they verify the gates, never an account.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from market_platform_foundation.market_data.headless_supply import supply_status
from market_platform_foundation.market_data.persistence import MarketStreamWriter
from market_platform_foundation.news.supervision import SUPERVISION_JOB
from tests.platform import test_pf01_supervision_scenarios as scenarios
from tests.support.pf01_synthetic_providers import KRAKEN_PAIRS, synthetic_probe
from tools.platform.pf01_supervisor import ROOT, OwnedProcess

BTC = sorted(KRAKEN_PAIRS)[0]
CHILD = ROOT / 'tests/support/pf01_synthetic_child.py'


class SupplyProcessCase(scenarios.ScenarioCase):
    NEWS = '0'
    TARGETS = f'moomoo:AAPL@US_EQUITY_L1+US_EQUITY_TICKS,kraken:{BTC}@CRYPTO_TRADES'
    ENTITLED = 'moomoo,kraken'
    RATE = '10'

    def setUp(self):
        super().setUp()
        self.control = Path(self.temp.name) / 'control'
        self.control.mkdir()
        probe = synthetic_probe(Path(self.temp.name) / 'probe.json')
        self.env.update({
            'IMP_LIVE_OBSERVATIONAL': '1', 'IMP_MOOMOO_LIVE': '1', 'IMP_CRYPTO_LIVE': '1',
            'IMP_OBSERVATIONAL_PROVIDER': 'moomoo', 'IMP_MOOMOO_PROBE_REPORT': str(probe),
            'IMP_LIVE_RECONNECT_BACKOFF_SEC': '0.2',
            'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo,kraken', 'IMP_MARKET_PERSISTENCE_SYMBOLS': f'AAPL,{BTC}',
            'IMP_MARKET_SUPPLY_ENABLED': '1', 'IMP_MARKET_SUPPLY_TARGETS': self.TARGETS,
            'IMP_MARKET_SUPPLY_ENTITLED_SOURCES': self.ENTITLED,
            'PF01_SYNTHETIC_DIR': str(self.control), 'PF01_SYNTHETIC_RATE': self.RATE,
            'PF01_SYNTHETIC_NEWS': '1' if self.NEWS == '1' else '0'})

    def spawn(self):
        env = {**{k: v for k, v in os.environ.items() if not k.startswith(('IMP_', 'PF01_'))}, **self.env,
               'IMP_PF01_SUPERVISOR_OWNER': self.owner.owner}
        process = subprocess.Popen([sys.executable, '-B', str(CHILD)], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        self.processes.append(process)
        self.addCleanup(self.reap, process)
        return OwnedProcess(process)

    def counts(self):
        try:
            return json.loads((self.control / 'counts.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def stored(self):
        return dict(self.read('SELECT provider||":"||capability,COUNT(*) FROM market_stream_records GROUP BY 1'))

    def supply(self):
        return supply_status({'IMP_STATE_DIR': self.temp.name})

    def gaps(self):
        return {row[0] for row in self.read('SELECT reason FROM market_stream_gaps')}

    def assert_no_network(self):
        log = self.control / 'network.log'
        self.assertFalse(log.exists(), log.read_text(encoding='utf-8') if log.exists() else '')

    def collecting(self):
        stored = self.stored()
        return stored.get('moomoo:US_EQUITY_TICKS', 0) >= 5 and stored.get('KRAKEN:CRYPTO_TRADES', 0) >= 5


class SupervisedSupplyTests(SupplyProcessCase):
    NEWS = '1'

    def test_supervised_child_subscribes_collects_reports_and_stops_cleanly_with_news_running(self):
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.collecting(), message='both providers committed')
        self.wait_for(lambda: self.supply().get('state') == 'COLLECTING', message='supply evidence')
        self.wait_for(lambda: self.read('SELECT COUNT(*) FROM news_collection_records')[0][0] > 0, message='news stored')
        status = self.supply()
        self.assertEqual((status['enabled'], status['summary']['active'], status['summary']['blocked']), (True, 3, 0))
        self.assertEqual((status['writer']['ownership'], status['execution_authority']), ('HELD', 'NONE'))
        counts = self.counts()
        self.assertEqual(sorted(map(tuple, counts['opend_subscribed'])), [('US.AAPL', 'QUOTE'), ('US.AAPL', 'TICKER')])
        self.assertEqual(counts['kraken_subscribed'], [['trade', 'BTC/USD']])
        self.assertEqual((counts['opend_sessions'], counts['kraken_connections']), (1, 1))
        child = self.processes[-1]
        owner.stop()
        self.assertEqual(child.wait(timeout=60), 0)
        # A clean stop drains: everything the synthetic providers delivered is stored exactly once.
        delivered, stored = self.counts(), self.stored()
        self.assertGreaterEqual(stored['moomoo:US_EQUITY_TICKS'], delivered['moomoo_ticks'] - 10)
        self.assertLessEqual(stored['moomoo:US_EQUITY_TICKS'], delivered['moomoo_ticks'] + 10)
        self.assertEqual(self.read('SELECT COUNT(*),COUNT(DISTINCT record_id) FROM market_stream_records')[0][0],
                         self.read('SELECT COUNT(DISTINCT record_id) FROM market_stream_records')[0][0])
        self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_runs WHERE closed_ns IS NULL')[0][0], 0)
        self.assertEqual(self.supply()['state'], 'STOPPED')
        self.assertFalse(self.gaps() & {'QUEUE_OVERFLOW', 'WRITER_FAILURE', 'UNCLEAN_RESTART_NO_REPLAY'})
        self.assertEqual((owner.status()['crashes'], len(self.processes)), (0, 1))
        self.assert_no_network()


class RecoveryTests(SupplyProcessCase):
    def test_crashed_child_is_restarted_and_its_subscriptions_are_restored_from_configuration(self):
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.collecting(), message='first child collecting')
        first = self.counts()['pid']
        before = self.stored()
        (self.control / 'crash').touch()
        self.wait_for(lambda: owner.status()['state'] == 'BACKOFF', message='crash noticed')
        self.assertEqual(self.processes[-1].poll(), 3)
        self.assertEqual(len(self.read('SELECT 1 FROM market_stream_runs WHERE closed_ns IS NULL')), 1)  # died owning
        self.skip_to_next_start()
        self.wait_for(lambda: self.running() and self.counts().get('pid') not in (None, first)
                      and self.stored().get('KRAKEN:CRYPTO_TRADES', 0) > before['KRAKEN:CRYPTO_TRADES'] + 5
                      and self.stored().get('moomoo:US_EQUITY_TICKS', 0) > before['moomoo:US_EQUITY_TICKS'] + 5,
                      message='second child collecting')
        counts = self.counts()
        self.assertEqual(sorted(map(tuple, counts['opend_subscribed'])), [('US.AAPL', 'QUOTE'), ('US.AAPL', 'TICKER')])
        self.assertEqual(counts['kraken_subscribed'], [['trade', 'BTC/USD']])
        self.assertIn('UNCLEAN_RESTART_NO_REPLAY', self.gaps())
        self.assertEqual(self.read('PRAGMA integrity_check'), [('ok',)])
        self.assertEqual(len(self.read('SELECT 1 FROM market_stream_runs WHERE closed_ns IS NULL')), 1)
        status = owner.status()
        self.assertEqual((status['crashes'], status['restarts_in_window'], status['unhealthy_failures']), (1, 1, 1))
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        self.assert_no_network()

    def test_one_provider_failing_leaves_the_other_collecting_and_recovers_without_a_restart(self):
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.collecting(), message='collecting')
        (self.control / 'drop-opend').touch()
        self.wait_for(lambda: 'MOOMOO_DISCONNECT_NO_REPLAY' in self.gaps(), message='moomoo gap recorded')
        kraken, moomoo = self.stored()['KRAKEN:CRYPTO_TRADES'], self.stored()['moomoo:US_EQUITY_TICKS']
        self.wait_for(lambda: self.stored()['KRAKEN:CRYPTO_TRADES'] > kraken + 20, message='kraken still collecting')
        self.assertLessEqual(self.stored()['moomoo:US_EQUITY_TICKS'], moomoo + 10)
        self.wait_for(lambda: self.supply().get('state') == 'RECOVERY_PENDING', message='recovery pending reported')
        (self.control / 'restore-opend').touch()
        self.wait_for(lambda: self.stored()['moomoo:US_EQUITY_TICKS'] > moomoo + 20, message='moomoo restored')
        self.assertEqual(self.counts()['opend_sessions'], 2)
        (self.control / 'drop-kraken').touch()
        self.wait_for(lambda: 'KRAKEN_DISCONNECT_NO_REPLAY' in self.gaps() and self.counts()['kraken_connections'] == 2,
                      message='kraken reconnected')
        status = owner.status()
        self.assertEqual((status['state'], status['crashes'], len(self.processes)), ('RUNNING', 0, 1))
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        self.assert_no_network()

    def test_database_lock_under_active_supply_is_bounded_backpressure_not_a_crash(self):
        self.env['PF01_SYNTHETIC_RATE'] = '60'
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.collecting(), message='collecting')
        import sqlite3

        blocker = sqlite3.connect(self.path, isolation_level=None)
        try:
            blocker.execute('BEGIN IMMEDIATE')
            held = time.monotonic()
            while time.monotonic() - held < 8:
                owner.tick()
                time.sleep(0.5)
            self.assertIsNone(self.processes[-1].poll(), 'child exited on a transient lock')
        finally:
            blocker.execute('ROLLBACK')
            blocker.close()
        stored = sum(self.stored().values())
        self.wait_for(lambda: sum(self.stored().values()) > stored + 100 and 'QUEUE_OVERFLOW' in self.gaps(),
                      message='commits resume and the overflow is recorded')
        self.wait_for(lambda: (self.supply().get('writer') or {}).get('rejected', 0) > 0, message='rejections reported')
        status = owner.status()
        self.assertEqual((status['state'], status['crashes'], len(self.processes)), ('RUNNING', 0, 1))
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        delivered = self.counts()
        rejected = self.read("SELECT SUM(observations) FROM market_stream_gaps WHERE reason='QUEUE_OVERFLOW'")[0][0]
        ticks = self.stored()['moomoo:US_EQUITY_TICKS'] + self.stored()['KRAKEN:CRYPTO_TRADES']
        # Every delivered trade is either stored or counted in the overflow gap; none vanishes silently.
        self.assertLessEqual(delivered['moomoo_ticks'] + delivered['kraken_trades'] - 2 * 60, ticks + rejected)
        self.assert_no_network()


class GateTests(SupplyProcessCase):
    NEWS = '1'
    ENTITLED = ''

    def test_unconfirmed_entitlement_runs_news_but_requests_no_subscription_and_owns_nothing(self):
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.supply().get('state') == 'BLOCKED', message='supply blocked')
        self.wait_for(lambda: self.read('SELECT COUNT(*) FROM news_collection_records')[0][0] > 0, message='news stored')
        for _ in range(12):
            owner.tick()
            time.sleep(0.5)
        counts = self.counts()
        self.assertEqual((counts['opend_subscribed'], counts['kraken_subscribed']), ([], []))
        self.assertEqual((counts['opend_sessions'], counts['kraken_connections']), (0, 0))  # no provider session at all
        self.assertEqual((counts['moomoo_ticks'], counts['kraken_trades']), (0, 0))
        status = self.supply()
        self.assertEqual({row['reason'] for row in status['targets']}, {'ENTITLEMENT_NOT_CONFIRMED'})
        self.assertEqual((status['summary']['active'], status['writer']['ownership']), (0, 'NOT_HELD'))
        self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_runs')[0][0], 0)
        self.assertEqual((owner.status()['state'], owner.status()['crashes']), ('RUNNING', 0))
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        self.assert_no_network()


class ConfigurationProcessTests(SupplyProcessCase):
    def test_rejected_target_list_latches_without_spending_restarts(self):
        self.env['IMP_MARKET_SUPPLY_TARGETS'] = 'moomoo:TSLA@US_EQUITY_L1'  # not selected for persistence
        owner = self.supervisor()
        self.wait_for(lambda: owner.status()['state'] == 'BLOCKED', message='latched')
        status = owner.status()
        self.assertEqual((status['reason'], status['latched'], status['restarts'], len(self.processes)),
                         ('CHILD_CONFIGURATION_REJECTED', 'CHILD_CONFIGURATION_REJECTED', [], 1))
        self.assertEqual(self.processes[-1].poll(), 78)
        counts = self.counts()  # the entry point refused before any worker or provider session existed
        self.assertEqual((counts.get('opend_sessions', 0), counts.get('kraken_connections', 0)), (0, 0))
        self.assertEqual(self.read('SELECT COUNT(*) FROM news_collection_jobs WHERE job_id<>?', (SUPERVISION_JOB,))[0][0], 0)

    def test_supply_disabled_is_the_default_and_matches_the_previous_headless_behaviour(self):
        for key in ('IMP_MARKET_SUPPLY_ENABLED', 'IMP_MARKET_SUPPLY_TARGETS', 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES'):
            self.env.pop(key)
        owner = self.supervisor()
        self.wait_for(self.running, message='child running')
        for _ in range(14):
            owner.tick()
            time.sleep(0.5)
        counts = self.counts()
        self.assertEqual((counts['opend_sessions'], counts['kraken_connections'], counts['opend_subscribed']), (0, 0, []))
        self.assertEqual(self.supply(), {'enabled': False, 'state': 'DISABLED'})
        self.assertEqual(self.read('SELECT COUNT(*) FROM market_stream_runs')[0][0], 0)
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        self.assert_no_network()


class SharedWriterTests(SupplyProcessCase):
    def test_collector_stands_by_while_another_process_owns_the_writer_then_takes_over(self):
        serving = MarketStreamWriter(self.path, sources=('moomoo', 'kraken'), symbols=('AAPL', BTC))  # owns now
        self.addCleanup(serving.stop)
        owner = self.supervisor()
        self.wait_for(lambda: self.running() and self.supply().get('state') == 'STANDBY', message='standby')
        for _ in range(12):
            owner.tick()
            time.sleep(0.5)
        counts = self.counts()
        self.assertEqual((counts['opend_subscribed'], counts['kraken_subscribed']), ([], []))
        self.assertEqual(sum(self.stored().values()), 0)
        self.assertEqual(serving.status()['ownership'], 'HELD')  # never displaced
        serving.stop()
        self.wait_for(self.collecting, message='collector took over')
        self.assertEqual(len(self.read('SELECT 1 FROM market_stream_runs WHERE closed_ns IS NULL')), 1)
        self.assertEqual((owner.status()['crashes'], len(self.processes)), (0, 1))
        owner.stop()
        self.assertEqual(self.processes[-1].wait(timeout=60), 0)
        self.assert_no_network()
