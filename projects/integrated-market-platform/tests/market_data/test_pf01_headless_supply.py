"""PF-01 headless market supply: default-off demand on the existing subscription authorities.

Offline. The moomoo and Kraken runtimes, feed, admission and writer are real;
only the vendor transport is synthetic. Any real socket use fails the test.
Synthetic entitlement fixtures prove the gate logic, not any account's rights.
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data import headless_supply, persistence
from market_platform_foundation.market_data.headless_supply import (SUPPLY_CONSUMER, SUPPLY_JOB, HeadlessMarketSupply,
    SupplyTarget, _KrakenSupply, _MoomooSupply, collection_session, start_supply, supply_status, validate_supply)
from market_platform_foundation.market_data.persistence import MarketStreamWriter
from market_platform_foundation.news.supervision import CHILD_EXIT_PERMANENT, child_exit_code
from tests.support.pf01_synthetic_providers import KRAKEN_PAIRS, SyntheticKraken, SyntheticOpenD, synthetic_probe

BTC, ETH = sorted(KRAKEN_PAIRS)
BASE = {'IMP_MARKET_SUPPLY_ENABLED': '1', 'IMP_MARKET_PERSISTENCE_ENABLED': '1',
        'IMP_MARKET_PERSISTENCE_SOURCES': 'moomoo,kraken', 'IMP_MARKET_PERSISTENCE_SYMBOLS': f'AAPL,MSFT,{BTC}',
        'IMP_LIVE_OBSERVATIONAL': '1', 'IMP_MOOMOO_LIVE': '1', 'IMP_CRYPTO_LIVE': '1',
        'IMP_MARKET_SUPPLY_TARGETS': f'moomoo:AAPL@US_EQUITY_L1+US_EQUITY_TICKS,kraken:{BTC}@CRYPTO_TRADES'}


def epoch(text: str) -> float:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()


class StubProvider:
    """Records what supply asks of a subscription authority."""

    def __init__(self, *, entitlement=None, state='ACTIVE', available=True):
        self.entitlements, self.state, self.available = entitlement or {}, state, available
        self.opened = self.closed = 0
        self.requests, self.releases = [], []
        self.fail = False

    def open(self):
        self.opened += 1
        return self.available

    def entitlement(self, capability):
        return self.entitlements.get(capability)

    def request(self, symbol, capability):
        if self.fail:
            raise RuntimeError('boom')
        self.requests.append((symbol, capability))
        return (self.state, None if self.state in {'ACTIVE', 'REQUESTED'} else 'STUB_REASON')

    def release(self, symbol, capability):
        self.releases.append((symbol, capability))

    def connection(self):
        return 'CONNECTED'

    def close(self):
        self.closed += 1


class SupplyCase(unittest.TestCase):
    SYMBOLS = ('AAPL', 'MSFT', BTC)

    def setUp(self):
        blocked = AssertionError('real network use in an offline test')
        for target in ('create_connection', 'getaddrinfo'):
            item = patch.object(socket, target, side_effect=blocked)
            item.start()
            self.addCleanup(item.stop)
        item = patch.object(socket.socket, 'connect', side_effect=blocked)
        item.start()
        self.addCleanup(item.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        LocalStateConnection(self.path).close()
        self.writer = MarketStreamWriter(self.path, sources=('moomoo', 'kraken'), symbols=self.SYMBOLS, acquire=False)
        self.addCleanup(self.writer.stop)
        item = patch.object(persistence, '_WRITER', self.writer)
        item.start()
        self.addCleanup(item.stop)
        self.now = [time.time()]

    def supply(self, targets, providers, entitled=('moomoo', 'kraken')):
        supply = HeadlessMarketSupply(self.path, targets, writer=self.writer, providers=providers,
                                      entitled_sources=entitled, clock=lambda: self.now[0])
        self.addCleanup(supply.stop)
        return supply

    def rows(self, sql, *args):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(sql, args).fetchall()

    def states(self, supply):
        return {(row['source'], row['symbol'], row['capability']): (row['state'], row['reason'])
                for row in supply.status()['targets']}

    def wait_until(self, condition, seconds=15.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail('condition not reached')


class ConfigurationTests(unittest.TestCase):
    def reason(self, **changes):
        with self.assertRaises(ValueError) as raised:
            validate_supply({**BASE, **changes})
        return str(raised.exception)

    def test_default_is_off_and_touches_no_provider(self):
        self.assertEqual(validate_supply({}), ())
        self.assertEqual(validate_supply({**BASE, 'IMP_MARKET_SUPPLY_ENABLED': '0'}), ())
        provider = StubProvider()
        self.assertIsNone(start_supply(object(), {}, providers={'moomoo': provider, 'kraken': provider}))
        self.assertEqual((provider.opened, provider.requests), (0, []))
        self.assertEqual(supply_status({}), {'enabled': False, 'state': 'DISABLED'})

    def test_valid_targets_are_exactly_what_was_listed(self):
        self.assertEqual(validate_supply(BASE), (SupplyTarget('moomoo', 'AAPL', ('US_EQUITY_L1', 'US_EQUITY_TICKS')),
                                                 SupplyTarget('kraken', BTC, ('CRYPTO_TRADES',))))

    def test_enabled_without_targets_or_persistence_is_refused(self):
        self.assertEqual(self.reason(IMP_MARKET_SUPPLY_TARGETS=''), 'MARKET_SUPPLY_TARGETS_REQUIRED')
        self.assertEqual(self.reason(IMP_MARKET_PERSISTENCE_ENABLED='0'), 'MARKET_SUPPLY_REQUIRES_PERSISTENCE')

    def test_unsupported_combinations_are_refused(self):
        for targets in ('ibkr:AAPL@US_EQUITY_L1', 'moomoo:aapl@US_EQUITY_L1', 'moomoo:AAPL@CRYPTO_TRADES',
                        f'kraken:{BTC}@US_EQUITY_L1', 'kraken:BTC/USD@CRYPTO_TRADES', 'moomoo:AAPL@CURRENT_BAR_1M',
                        'moomoo:AAPL', 'moomoo:AAPL@', 'moomoo:*@US_EQUITY_L1', 'moomoo:AAPL@US_EQUITY_L1+US_EQUITY_L1',
                        'moomoo:AAPL@US_EQUITY_L1,moomoo:AAPL@US_EQUITY_TICKS'):
            self.assertEqual(self.reason(IMP_MARKET_SUPPLY_TARGETS=targets), 'MARKET_SUPPLY_TARGETS_INVALID', targets)

    def test_dotted_ticker_the_feed_would_store_under_another_name_is_refused(self):
        # The feed keeps only the last segment of US.BRK.B, so the stream would be subscribed and never stored.
        self.assertEqual(self.reason(IMP_MARKET_PERSISTENCE_SYMBOLS='BRK.B', IMP_MARKET_SUPPLY_TARGETS='moomoo:BRK.B@US_EQUITY_L1'),
                         'MARKET_SUPPLY_TARGETS_INVALID')

    def test_target_bound_is_the_writer_selection_bound(self):
        symbols = [f'S{index}' for index in range(21)]
        targets = ','.join(f'moomoo:{symbol}@US_EQUITY_L1' for symbol in symbols)
        stored = {'IMP_MARKET_PERSISTENCE_SYMBOLS': ','.join(symbols)}
        self.assertEqual(self.reason(IMP_MARKET_SUPPLY_TARGETS=targets, **stored), 'MARKET_SUPPLY_TARGETS_INVALID')
        self.assertEqual(len(validate_supply({**BASE, **stored, 'IMP_MARKET_SUPPLY_TARGETS': targets.rsplit(',', 1)[0]})), 20)

    def test_supply_never_exceeds_what_is_selected_for_persistence(self):
        self.assertEqual(self.reason(IMP_MARKET_SUPPLY_TARGETS='moomoo:TSLA@US_EQUITY_L1'), 'MARKET_SUPPLY_TARGET_NOT_PERSISTED')
        self.assertEqual(self.reason(IMP_MARKET_PERSISTENCE_SOURCES='moomoo'), 'MARKET_SUPPLY_TARGET_NOT_PERSISTED')

    def test_provider_live_gates_are_required_and_other_feeds_conflict(self):
        for change in ({'IMP_MOOMOO_LIVE': '0'}, {'IMP_LIVE_OBSERVATIONAL': '0'}, {'IMP_CRYPTO_LIVE': '0'}):
            self.assertEqual(self.reason(**change), 'MARKET_SUPPLY_PROVIDER_GATE_CLOSED', change)
        for change in ({'IMP_IBKR_LIVE': '1'}, {'IMP_OBSERVATIONAL_PROVIDER': 'ibkr'}, {'IMP_SHADOW_RECORDING': 'true'},
                       # No OpenD feed would start, or a fixture file would be replayed into the store.
                       {'IMP_OBSERVATIONAL_PROVIDER': 'none'}, {'IMP_LIVE_FIXTURE_FEED': 'fixture.jsonl'}):
            self.assertEqual(self.reason(**change), 'MARKET_SUPPLY_PROVIDER_CONFLICT', change)
        self.assertEqual(len(validate_supply({**BASE, 'IMP_OBSERVATIONAL_PROVIDER': 'Auto'})), 2)
        # A Kraken-only selection needs neither OpenD gate.
        kraken = {**BASE, 'IMP_MOOMOO_LIVE': '0', 'IMP_LIVE_OBSERVATIONAL': '0',
                  'IMP_MARKET_SUPPLY_TARGETS': f'kraken:{BTC}@CRYPTO_TRADES'}
        self.assertEqual(len(validate_supply(kraken)), 1)

    def test_every_configuration_refusal_is_permanent_for_the_supervisor(self):
        for reason in ('MARKET_SUPPLY_TARGETS_REQUIRED', 'MARKET_SUPPLY_TARGETS_INVALID', 'MARKET_SUPPLY_REQUIRES_PERSISTENCE',
                       'MARKET_SUPPLY_TARGET_NOT_PERSISTED', 'MARKET_SUPPLY_PROVIDER_GATE_CLOSED',
                       'MARKET_SUPPLY_PROVIDER_CONFLICT'):
            self.assertEqual(child_exit_code(reason), CHILD_EXIT_PERMANENT, reason)

    def test_collection_eligibility_follows_the_market_not_an_ai_window(self):
        self.assertEqual(collection_session('kraken', epoch('2026-10-17T03:00:00')), {'label': 'CONTINUOUS', 'data_expected': True})
        for stamp, label, expected in (('2026-10-13T15:00:00', 'REGULAR', True),      # Tuesday 11:00 ET
                                       ('2026-10-13T09:00:00', 'PREMARKET', True),    # 05:00 ET
                                       ('2026-10-13T22:00:00', 'AFTER_HOURS', True),  # 18:00 ET
                                       ('2026-10-14T02:00:00', 'OVERNIGHT', False),   # 22:00 ET
                                       ('2026-10-17T15:00:00', 'CLOSED', False),      # Saturday
                                       ('2026-11-26T16:00:00', 'CLOSED', False),      # Thanksgiving
                                       ('2031-03-04T16:00:00', 'CALENDAR_UNAVAILABLE', False)):
            self.assertEqual(collection_session('moomoo', epoch(stamp)), {'label': label, 'data_expected': expected}, stamp)
        # 07:00 UTC is 03:00 ET: inside no AI window anyone proposed, and still collected.
        self.assertTrue(collection_session('kraken', epoch('2026-10-13T07:00:00'))['data_expected'])


class LifecycleTests(SupplyCase):
    TARGETS = (SupplyTarget('moomoo', 'AAPL', ('US_EQUITY_L1', 'US_EQUITY_TICKS')), SupplyTarget('kraken', BTC, ('CRYPTO_TRADES',)))

    def test_unconfirmed_entitlement_requests_nothing(self):
        moomoo, kraken = StubProvider(), StubProvider()
        supply = self.supply(self.TARGETS, {'moomoo': moomoo, 'kraken': kraken}, entitled=())
        supply.step()
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_NOT_CONFIRMED')})
        self.assertEqual((moomoo.opened, kraken.opened, moomoo.requests, kraken.requests), (0, 0, [], []))
        status = supply.status()
        self.assertEqual((status['state'], status['summary']['active'], status['summary']['blocked']), ('BLOCKED', 0, 3))
        self.assertFalse(status['providers']['moomoo']['entitlement_confirmed'])

    def test_confirmation_is_per_source(self):
        moomoo, kraken = StubProvider(), StubProvider()
        supply = self.supply(self.TARGETS, {'moomoo': moomoo, 'kraken': kraken}, entitled=('kraken',))
        supply.step()
        self.assertEqual((moomoo.requests, kraken.requests), ([], [(BTC, 'CRYPTO_TRADES')]))
        self.assertEqual(supply.status()['state'], 'DEGRADED')

    def test_unverified_capability_is_blocked_while_verified_ones_are_requested(self):
        moomoo = StubProvider(entitlement={'US_EQUITY_TICKS': 'ENTITLEMENT_NOT_VERIFIED'})
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        supply.step()
        self.assertEqual(moomoo.requests, [('AAPL', 'US_EQUITY_L1')])
        self.assertEqual(self.states(supply)[('moomoo', 'AAPL', 'US_EQUITY_TICKS')], ('BLOCKED', 'ENTITLEMENT_NOT_VERIFIED'))

    def test_source_with_nothing_verified_opens_no_provider_session(self):
        blocked = {name: 'ENTITLEMENT_PROBE_STALE' for name in ('US_EQUITY_L1', 'US_EQUITY_TICKS')}
        moomoo = StubProvider(entitlement=blocked)
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        supply.step()
        supply.step()
        self.assertEqual((moomoo.opened, moomoo.requests), (0, []))
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_PROBE_STALE')})
        self.assertEqual(supply.status()['providers']['moomoo']['connection'], 'NOT_OPENED')

    def test_request_that_fails_part_way_is_still_released(self):
        moomoo = StubProvider()
        moomoo.fail = True
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        supply.step()
        supply.stop()
        self.assertEqual(sorted(moomoo.releases), [('AAPL', 'US_EQUITY_L1'), ('AAPL', 'US_EQUITY_TICKS')])

    def test_checkpoint_from_before_this_demand_is_not_reported_as_collecting(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        stream = f'KRAKEN:{BTC}:CRYPTO_TRADES'
        def checkpoint(seconds):
            stamp = int((self.now[0] + seconds) * 1e9)
            with closing(sqlite3.connect(self.path)) as db:
                db.execute('INSERT OR REPLACE INTO market_stream_checkpoints VALUES (?,?,?,?,?)', (stream, stamp, stamp, stamp, 'r'))
                db.commit()
        checkpoint(-10)  # a previous run, or another process, committed ten seconds ago
        supply.step()
        status = supply.status()
        self.assertEqual((status['targets'][0]['state'], status['targets'][0]['committed_recently'], status['state']),
                         ('ACTIVE_NO_DATA', False, 'SUBSCRIBED_NO_DATA'))
        checkpoint(1)
        self.now[0] += 2
        self.assertEqual((supply.status()['targets'][0]['state'], supply.status()['state']), ('COLLECTING', 'COLLECTING'))

    def test_year_without_a_calendar_is_not_labelled_a_closed_session(self):
        moomoo = StubProvider()
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        self.now[0] = epoch('2027-03-01T15:00:00')
        supply.step()
        self.now[0] += headless_supply.STALE_SECONDS + 1
        status = supply.status()
        self.assertEqual(status['providers']['moomoo']['session']['label'], 'CALENDAR_UNAVAILABLE')
        self.assertEqual({row['state'] for row in status['targets']}, {'ACTIVE_NO_DATA'})

    def test_writer_that_acquires_during_the_owner_probe_is_not_mistaken_for_another_process(self):
        from types import SimpleNamespace

        owner = MarketStreamWriter(self.path, sources=('kraken',), symbols=(BTC,))  # the open run and the held lock
        self.addCleanup(owner.stop)
        writer = SimpleNamespace(run_id=None)
        supply = HeadlessMarketSupply(self.path, self.TARGETS[1:], writer=writer, providers={'kraken': StubProvider()})
        self.assertTrue(supply._foreign_writer())
        def acquired(_path):
            writer.run_id = owner.run_id  # the writer thread recorded its run while the lock was being probed
            return True
        with patch.object(persistence, 'owner_lock_held', acquired):
            self.assertFalse(supply._foreign_writer())

    def test_step_that_outlives_stop_does_not_overwrite_the_final_evidence(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        supply.step()
        supply._stop.set()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DELETE FROM news_collection_jobs WHERE job_id=?', (SUPPLY_JOB,))
            db.commit()
        supply.step()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM news_collection_jobs WHERE job_id=?', SUPPLY_JOB), [(0,)])

    def test_entitlement_withdrawn_later_releases_the_held_subscription(self):
        moomoo = StubProvider()
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        supply.step()
        moomoo.entitlements['US_EQUITY_L1'] = 'ENTITLEMENT_PROBE_STALE'
        supply.step()
        self.assertEqual(moomoo.releases, [('AAPL', 'US_EQUITY_L1')])
        self.assertEqual(self.states(supply)[('moomoo', 'AAPL', 'US_EQUITY_L1')], ('BLOCKED', 'ENTITLEMENT_PROBE_STALE'))

    def test_one_failing_provider_does_not_stop_the_other(self):
        moomoo, kraken = StubProvider(), StubProvider()
        moomoo.fail = True
        supply = self.supply(self.TARGETS, {'moomoo': moomoo, 'kraken': kraken})
        supply.step()
        states = self.states(supply)
        self.assertEqual(states[('moomoo', 'AAPL', 'US_EQUITY_L1')], ('BLOCKED', 'PROVIDER_REQUEST_FAILED'))
        self.assertEqual(states[('kraken', BTC, 'CRYPTO_TRADES')][1], None)
        unavailable = StubProvider(available=False)
        other = self.supply(self.TARGETS, {'moomoo': unavailable, 'kraken': kraken})
        other.step()
        self.assertEqual(self.states(other)[('moomoo', 'AAPL', 'US_EQUITY_TICKS')], ('BLOCKED', 'PROVIDER_RUNTIME_UNAVAILABLE'))
        self.assertTrue(other.status()['summary']['active'])

    def test_running_process_alone_is_never_reported_as_collecting(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        supply.start()
        self.wait_until(lambda: kraken.requests)
        status = supply.status()
        self.assertTrue(status['worker_alive'])
        self.assertEqual((status['state'], status['summary']['collecting']), ('SUBSCRIBED_NO_DATA', 0))
        self.assertEqual(status['targets'][0]['state'], 'ACTIVE_NO_DATA')
        self.assertEqual(status['health_basis'], 'COMMITTED_CHECKPOINTS_NOT_PROCESS_LIVENESS')
        # Active with nothing committed for longer than the stale window, in a session that expects data.
        self.now[0] += headless_supply.STALE_SECONDS + 1
        self.assertEqual((supply.status()['state'], supply.status()['targets'][0]['state']), ('STALE', 'STALE'))

    def test_closed_market_is_not_reported_as_stale(self):
        moomoo = StubProvider()
        supply = self.supply(self.TARGETS[:1], {'moomoo': moomoo})
        self.now[0] = epoch('2026-10-17T15:00:00')  # Saturday
        supply.step()
        self.now[0] += headless_supply.STALE_SECONDS + 1
        status = supply.status()
        self.assertEqual({row['state'] for row in status['targets']}, {'SESSION_CLOSED'})
        self.assertEqual((status['state'], status['providers']['moomoo']['session']['label']), ('SUBSCRIBED_NO_DATA', 'CLOSED'))

    def test_another_process_owning_the_writer_puts_supply_on_standby_without_tearing_anything_down(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        supply.step()
        self.assertEqual(len(kraken.requests), 1)
        other = MarketStreamWriter(self.path, sources=('kraken',), symbols=(BTC,))  # a live owner elsewhere
        try:
            supply.step()
            self.assertEqual(kraken.releases, [(BTC, 'CRYPTO_TRADES')])
            self.assertEqual(self.states(supply)[('kraken', BTC, 'CRYPTO_TRADES')],
                             ('STANDBY', 'MARKET_WRITER_OWNED_BY_ANOTHER_PROCESS'))
            supply.step()
            self.assertEqual((len(kraken.requests), len(kraken.releases), supply.status()['state']), (1, 1, 'STANDBY'))
            # The owner was never touched: its run is still open and its lease intact.
            self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_runs WHERE closed_ns IS NULL')[0][0], 1)
            self.assertEqual(other.status()['ownership'], 'HELD')
        finally:
            other.stop()
        supply.step()
        self.assertEqual((len(kraken.requests), supply.status()['state']), (2, 'SUBSCRIBED_NO_DATA'))

    def test_run_left_open_by_a_dead_owner_does_not_put_supply_on_standby(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        dead = MarketStreamWriter(self.path, sources=('kraken',), symbols=(BTC,))
        dead._owner_lock.release()  # what the operating system does when the owning process dies
        dead.connection.close()
        dead._closed = True
        (lease,), = self.rows('SELECT lease_until_ns FROM market_stream_runs WHERE closed_ns IS NULL')
        self.assertGreater(lease, time.time_ns())  # its lease is still running
        supply.step()
        self.assertEqual((len(kraken.requests), kraken.releases, supply.status()['state']), (1, [], 'SUBSCRIBED_NO_DATA'))

    def test_own_writer_run_is_not_mistaken_for_another_owner(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        self.writer.gap('TEST_GAP')
        self.writer.flush()
        self.assertEqual(self.writer.status()['ownership'], 'HELD')
        supply.step()
        self.assertEqual((kraken.releases, supply.status()['state']), ([], 'SUBSCRIBED_NO_DATA'))

    def test_stop_releases_demand_closes_sessions_and_is_idempotent(self):
        moomoo, kraken = StubProvider(), StubProvider()
        supply = self.supply(self.TARGETS, {'moomoo': moomoo, 'kraken': kraken})
        supply.start()
        self.wait_until(lambda: kraken.requests and len(moomoo.requests) >= 2)
        supply.stop()
        supply.stop()
        self.assertEqual(sorted(moomoo.releases), [('AAPL', 'US_EQUITY_L1'), ('AAPL', 'US_EQUITY_TICKS')])
        self.assertEqual((kraken.releases, moomoo.closed, kraken.closed), ([(BTC, 'CRYPTO_TRADES')], 1, 1))
        self.assertEqual((supply.status()['state'], supply.status()['worker_alive']), ('STOPPED', False))
        requests = len(kraken.requests)
        supply.step()
        self.assertEqual(len(kraken.requests), requests)
        with self.assertRaisesRegex(ValueError, 'MARKET_SUPPLY_STOPPED'):
            supply.start()

    def test_status_evidence_reaches_the_existing_health_reader_and_expires(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        supply.step()
        env = {'IMP_STATE_DIR': self.temp.name}
        saved = supply_status(env, clock=lambda: self.now[0])
        self.assertEqual((saved['enabled'], saved['state'], saved['reported_by']), (True, 'SUBSCRIBED_NO_DATA', 'HEADLESS_CHILD_EVIDENCE'))
        self.assertEqual(saved['execution_authority'], 'NONE')
        # A child that stopped reporting must not look subscribed for ever.
        expired = supply_status(env, clock=lambda: self.now[0] + headless_supply.STATUS_LEASE_SECONDS + 1)
        self.assertEqual((expired['state'], expired['reason']), ('STALE', 'SUPPLY_STATUS_EXPIRED'))
        self.assertEqual((expired['summary']['active'], expired['summary']['collecting']), (0, 0))
        self.assertEqual({(row['state'], row['subscription_active']) for row in expired['targets']}, {('UNKNOWN', False)})
        supply.stop()
        stopped = supply_status(env, clock=lambda: self.now[0])
        self.assertEqual((stopped['enabled'], stopped['state']), (False, 'STOPPED'))
        self.assertEqual(self.rows('SELECT lease_owner FROM news_collection_jobs WHERE job_id=?', SUPPLY_JOB), [(None,)])

    def test_status_evidence_never_writes_into_a_replacement_store(self):
        supply = self.supply(self.TARGETS[1:], {'kraken': StubProvider()})
        supply.step()
        self.writer.stop()  # release handles before replacing this disposable database on Windows
        self.path.rename(self.path.with_name('original.sqlite3'))
        LocalStateConnection(self.path).close()
        supply._save(final=True)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM news_collection_jobs WHERE job_id=?', SUPPLY_JOB), [(0,)])

    def test_owned_provider_drains_before_selected_demand_is_released(self):
        class DrainingProvider(StubProvider):
            def prepare_stop(provider):
                provider.demand_at_drain = set(supply._held)
        provider = DrainingProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': provider})
        supply.step()
        supply.stop()
        self.assertEqual(getattr(provider, 'demand_at_drain', set()), {('kraken', BTC, 'CRYPTO_TRADES')})
        self.assertEqual(provider.releases, [(BTC, 'CRYPTO_TRADES')])

    def test_failed_provider_drain_records_incomplete_shutdown_and_still_releases_all_demand(self):
        class FailedDrain(StubProvider):
            def prepare_stop(provider):
                raise TimeoutError('synthetic drain timeout')
        moomoo, kraken = FailedDrain(), StubProvider()
        supply = self.supply(self.TARGETS, {'moomoo': moomoo, 'kraken': kraken})
        supply.step()
        supply.stop()
        status = supply.status()
        self.assertEqual(status['state'], 'BLOCKED')
        self.assertTrue(status['shutdown_incomplete'])
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')
        self.assertEqual((len(moomoo.releases), len(kraken.releases), moomoo.closed, kraken.closed), (2, 1, 1, 1))
        evidence = supply_status({'IMP_STATE_DIR': str(self.path.parent)})
        self.assertEqual((evidence['state'], evidence['shutdown_error'], evidence['enabled']),
                         ('BLOCKED', 'SUPPLY_SHUTDOWN_INCOMPLETE', False))

    def test_failed_provider_close_records_incomplete_shutdown(self):
        class FailedClose(StubProvider):
            def close(provider):
                raise OSError('synthetic close failure')
        supply = self.supply(self.TARGETS[1:], {'kraken': FailedClose()})
        supply.step()
        supply.stop()
        self.assertEqual(supply.status()['state'], 'BLOCKED')
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')

    def test_failed_demand_release_records_incomplete_shutdown(self):
        class FailedRelease(StubProvider):
            def release(provider, symbol, capability):
                raise OSError('synthetic release failure')
        supply = self.supply(self.TARGETS[1:], {'kraken': FailedRelease()})
        supply.step()
        supply.stop()
        self.assertEqual(supply.status()['state'], 'BLOCKED')
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')

    def test_historical_provider_error_does_not_mark_successful_shutdown_incomplete(self):
        provider = StubProvider()
        provider.fail = True
        supply = self.supply(self.TARGETS[1:], {'kraken': provider})
        supply.step()
        provider.fail = False
        supply.stop()
        status = supply.status()
        self.assertGreater(status['reconcile_errors'], 0)
        self.assertEqual(status['state'], 'STOPPED')
        self.assertFalse(status['shutdown_incomplete'])
        self.assertIsNone(supply.shutdown_error)

    def test_unreadable_status_store_never_stops_supply(self):
        kraken = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': kraken})
        with patch.object(headless_supply.sqlite3, 'connect', side_effect=sqlite3.OperationalError('database is locked')):
            supply.step()
            status = supply.status()
        self.assertEqual((len(kraken.requests), status['checkpoints_readable']), (1, False))
        self.assertNotEqual(status['targets'][0]['state'], 'STALE')

    def test_concurrent_stop_waits_for_inflight_request_and_preserves_final_evidence(self):
        entered, release = threading.Event(), threading.Event()
        class WaitingProvider(StubProvider):
            def request(provider, symbol, capability):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('synthetic blocked request timeout')
                return super().request(symbol, capability)
        provider = WaitingProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': provider})
        self.addCleanup(release.set)
        supply.start()
        self.assertTrue(entered.wait(2))
        stopping = threading.Thread(target=supply.stop)
        stopping.start()
        self.assertTrue(supply._stop.wait(2))
        release.set()
        stopping.join(3)
        self.assertFalse(stopping.is_alive())
        evidence = supply_status({'IMP_STATE_DIR': str(self.path.parent)})
        self.assertEqual((evidence['state'], evidence['enabled'], evidence['summary']['active']), ('STOPPED', False, 0))
        supply.step()
        self.assertEqual(supply_status({'IMP_STATE_DIR': str(self.path.parent)})['state'], 'STOPPED')
        self.assertEqual(provider.releases, [(BTC, 'CRYPTO_TRADES')])

    def test_status_exception_does_not_kill_reconciliation_worker(self):
        provider = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': provider})
        supply.interval = 0.01
        with patch.object(self.writer, 'status', side_effect=RuntimeError('synthetic status failure')):
            supply.start()
            # A step requests first and publishes status after releasing the lock, so the third request
            # is visible before its failure is counted. Wait for the failures, not for the requests.
            self.wait_until(lambda: supply._errors >= 3)
            self.assertTrue(supply.alive())
        self.assertGreaterEqual(len(provider.requests), 3)
        status = supply.status()
        self.assertGreaterEqual(status['reconcile_errors'], 3)
        self.assertEqual(status['summary']['active'], 1)

    def test_status_failure_is_counted_after_the_request_of_the_same_step(self):
        # The ordering the test above depends on: a request is on record while its step's status
        # publication is still running, and that publication's failure is counted only when it returns.
        provider = StubProvider()
        supply = self.supply(self.TARGETS[1:], {'kraken': provider})
        publishing, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def failing_status():
            publishing.set()
            release.wait(5)
            raise RuntimeError('synthetic status failure')
        with patch.object(self.writer, 'status', side_effect=failing_status):
            stepping = threading.Thread(target=supply.step)
            stepping.start()
            self.assertTrue(publishing.wait(5))
            self.assertEqual((len(provider.requests), supply._errors), (1, 0))
            release.set()
            stepping.join(5)
        self.assertFalse(stepping.is_alive())
        self.assertEqual((len(provider.requests), supply._errors), (1, 1))

    def test_start_supply_is_single_and_requires_the_writer(self):
        with self.assertRaisesRegex(ValueError, 'MARKET_SUPPLY_REQUIRES_PERSISTENCE'):
            start_supply(None, BASE, providers={})
        providers = {'moomoo': StubProvider(), 'kraken': StubProvider()}
        supply = start_supply(self.writer, BASE, providers=providers)
        self.addCleanup(headless_supply.stop_supply)
        self.assertIs(headless_supply.active_supply(), supply)
        self.assertEqual(supply.entitled_sources, frozenset())  # no confirmation in BASE: nothing may be requested
        with self.assertRaisesRegex(ValueError, 'MARKET_SUPPLY_ALREADY_STARTED'):
            start_supply(self.writer, BASE, providers=providers)
        headless_supply.stop_supply()
        self.assertIsNone(headless_supply.active_supply())
        self.assertEqual(providers['kraken'].requests, [])


class KrakenStreamSupplyTests(SupplyCase):
    """Real KrakenStreamRuntime over a synthetic socket, real writer."""

    def setUp(self):
        super().setUp()
        self.venue = SyntheticKraken()
        self.waits = []
        self.runtime = KrakenStreamRuntime(resolve=KRAKEN_PAIRS.get, connect=self.venue.connect, start_worker=False,
                                           jitter=lambda: 0.5, wait=self.waits.append)
        self.target = SupplyTarget('kraken', BTC, ('CRYPTO_TRADES',))
        self.key = ('kraken', BTC, 'CRYPTO_TRADES')

    def make(self, targets=None, **kwargs):
        return self.supply(targets or (self.target,), {'kraken': _KrakenSupply(runtime=lambda: self.runtime)}, **kwargs)

    def pump(self, supply, steps=6):
        supply.step()
        for _ in range(steps):
            self.runtime.step()
        supply.step()

    def test_owned_kraken_broken_transport_reports_incomplete_stop_and_detaches_runtime(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None  # own this real runtime, while using only synthetic venue transport
        connection = self.venue.connection
        self.venue.drop()
        supply.stop()
        self.assertEqual(supply.status()['state'], 'BLOCKED')
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')
        self.assertTrue(supply.status()['shutdown_incomplete'])
        self.assertEqual(supply.status()['providers']['kraken']['shutdown'],
                         {'state': 'UNVERIFIED', 'reason': 'TRANSPORT_OR_DRAIN_FAILURE', 'tail_observations': 'UNKNOWN'})
        self.assertTrue(connection.closed)
        self.assertIsNone(provider.runtime)
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps WHERE reason=?',
                                   'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'), [(1,)])

    def test_owned_kraken_missing_unsubscribe_ack_reports_incomplete_stop(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None
        connection = self.venue.connection
        send_text = connection.send_text
        def send_without_unsubscribe_ack(text):
            send_text(text)
            with connection.lock:
                connection.inbox[:] = [message for message in connection.inbox
                    if json.loads(message).get('method') != 'unsubscribe']
        with patch.object(connection, 'send_text', send_without_unsubscribe_ack):
            supply.stop()
        self.assertEqual(supply.status()['state'], 'BLOCKED')
        self.assertEqual(supply.shutdown_error, 'SUPPLY_SHUTDOWN_INCOMPLETE')
        self.assertTrue(connection.closed)
        self.assertIsNone(provider.runtime)
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps WHERE reason=?',
                                   'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'), [(1,)])

    def test_owned_kraken_acknowledged_drain_stops_cleanly_and_commits_the_received_tail(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None
        for _ in range(3):
            self.assertTrue(self.venue.push_trade('BTC/USD'))
        supply.stop()
        status = supply.status()
        self.assertEqual((status['state'], status['shutdown_incomplete'], supply.shutdown_error), ('STOPPED', False, None))
        self.assertEqual(status['providers']['kraken']['shutdown']['state'], 'ACKNOWLEDGED')
        self.writer.flush()
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_records'), [(3,)])
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps WHERE reason=?',
                                   'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'), [(0,)])

    def test_unverified_kraken_tail_is_saved_as_blocked_evidence_and_keeps_committed_records_distinct(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None
        for _ in range(2):
            self.assertTrue(self.venue.push_trade('BTC/USD'))
        self.pump(supply)  # these two were received; anything after the break is unknown
        self.venue.drop()
        supply.stop()
        self.writer.flush()
        evidence = supply_status({'IMP_STATE_DIR': str(self.path.parent)})
        self.assertEqual((evidence['state'], evidence['shutdown_incomplete'], evidence['shutdown_error']),
                         ('BLOCKED', True, 'SUPPLY_SHUTDOWN_INCOMPLETE'))
        self.assertEqual(evidence['providers']['kraken']['shutdown']['tail_observations'], 'UNKNOWN')
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_records'), [(2,)])
        # One uncertainty interval for the tail; the two committed trades are not folded into it.
        self.assertEqual(self.rows('SELECT COUNT(*),SUM(observations) FROM market_stream_gaps WHERE reason=?',
                                   'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'), [(1, 1)])

    def test_socket_lost_by_the_receiver_before_stop_is_not_a_clean_stop(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None
        self.venue.drop()
        self.runtime.step()  # the receiver, not shutdown, discovers the loss and drops the connection
        self.assertIsNone(self.runtime._connection)
        supply.stop()
        status = supply.status()
        self.assertEqual((status['state'], status['shutdown_incomplete']), ('BLOCKED', True))
        self.assertEqual(status['providers']['kraken']['shutdown'],
                         {'state': 'UNVERIFIED', 'reason': 'DISCONNECTED_BEFORE_SHUTDOWN', 'tail_observations': 'UNKNOWN'})
        self.writer.flush()
        # The loss is the disconnect gap the receiver already recorded; shutdown adds no second interval.
        self.assertEqual(self.rows('SELECT reason,COUNT(*) FROM market_stream_gaps WHERE reason LIKE ? GROUP BY 1', 'KRAKEN_%'),
                         [('KRAKEN_DISCONNECT_NO_REPLAY', 1)])
        # New demand on the same stream starts a new lifecycle and does not inherit that verdict.
        self.runtime.subscribe(instrument_id=BTC, capabilities=['CRYPTO_TRADES'], consumer_id='later')
        self.assertEqual(self.runtime.shutdown()['state'], 'NOT_REQUESTED')

    def test_stream_that_never_connected_stops_cleanly(self):
        self.venue.fail_connects = 99
        supply = self.make()
        self.pump(supply)
        supply.providers['kraken']._factory = None
        supply.stop()
        self.assertEqual((supply.status()['state'], supply.shutdown_error), ('STOPPED', None))

    def test_direct_close_of_an_owned_stream_also_refuses_an_unverified_tail(self):
        supply = self.make()
        self.pump(supply)
        provider = supply.providers['kraken']
        provider._factory = None
        self.venue.drop()
        with self.assertRaisesRegex(RuntimeError, 'KRAKEN_SHUTDOWN_TAIL_UNVERIFIED'):
            provider.close()
        self.assertIsNone(provider.runtime)

    def test_owned_kraken_without_open_connection_stops_cleanly(self):
        supply = self.make()
        supply.providers['kraken'].runtime = self.runtime
        supply.providers['kraken']._factory = None
        supply.stop()
        self.assertEqual(supply.status()['state'], 'STOPPED')
        self.assertIsNone(supply.shutdown_error)
        self.assertEqual(self.venue.connections, [])

    def test_subscription_trades_commit_and_checkpoint(self):
        supply = self.make()
        supply.step()
        self.assertEqual(self.states(supply)[self.key], ('REQUESTED', None))
        self.pump(supply)
        self.assertEqual(self.venue.subscribed(), {('trade', 'BTC/USD')})
        self.assertEqual(self.states(supply)[self.key][0], 'ACTIVE_NO_DATA')
        for _ in range(5):
            self.assertTrue(self.venue.push_trade('BTC/USD'))
        self.pump(supply)
        self.assertEqual(self.writer.flush(), 5)
        status = supply.status()
        self.assertEqual((status['state'], status['targets'][0]['state'], status['writer']['committed']), ('COLLECTING', 'COLLECTING', 5))
        self.assertTrue(status['targets'][0]['subscription_active'])
        stored = self.rows('SELECT provider,symbol,capability FROM market_stream_records')
        self.assertEqual(set(stored), {('KRAKEN', BTC, 'CRYPTO_TRADES')})
        checkpoint = self.rows('SELECT stream_id,last_record_id FROM market_stream_checkpoints')
        self.assertEqual(checkpoint[0][0], f'KRAKEN:{BTC}:CRYPTO_TRADES')

    def test_repeated_requests_send_one_subscription_and_replayed_trades_are_deduplicated(self):
        supply = self.make()
        for _ in range(4):
            self.pump(supply)
        subscribes = [m for m in self.venue.connection.sent if m['method'] == 'subscribe']
        self.assertEqual(len(subscribes), 1)
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id=BTC, capability='CRYPTO_TRADES'), 1)
        self.venue.push_trade('BTC/USD')
        replay = json.loads(self.venue.connection.inbox[-1])
        self.pump(supply)
        self.venue.connection.deliver(replay)  # the venue repeats the same trade
        self.pump(supply)
        self.writer.flush()
        status = self.writer.status()
        self.assertEqual((status['committed'], status['duplicates']), (1, 1))

    def test_unselected_pair_traffic_is_neither_subscribed_nor_stored(self):
        supply = self.make()
        self.pump(supply)
        self.assertFalse(self.venue.push_trade('ETH/USD'))
        self.assertEqual({symbol for _, symbol in self.venue.subscribed()}, {'BTC/USD'})

    def test_disconnect_records_a_gap_reconnects_with_bounded_backoff_and_restores_the_subscription(self):
        supply = self.make()
        self.pump(supply)
        self.venue.push_trade('BTC/USD')
        self.pump(supply)
        self.writer.flush()
        self.venue.drop()
        self.pump(supply, steps=1)
        self.assertEqual(supply.status()['providers']['kraken']['connection'], 'RECONNECTING')
        self.assertEqual(supply.status()['state'], 'RECOVERY_PENDING')
        self.assertEqual(self.states(supply)[self.key][0], 'REQUESTED')
        self.pump(supply)
        self.assertEqual(len(self.venue.connections), 2)
        self.assertEqual(self.venue.subscribed(), {('trade', 'BTC/USD')})
        self.assertTrue(self.venue.push_trade('BTC/USD'))
        self.pump(supply)
        self.writer.flush()
        self.assertEqual(self.writer.status()['committed'], 2)
        self.assertIn(('*', 'KRAKEN_DISCONNECT_NO_REPLAY'), self.rows('SELECT stream_id,reason FROM market_stream_gaps'))
        self.assertTrue(self.waits and max(self.waits) <= 36)

    def test_venue_that_will_not_accept_connections_is_retried_at_a_capped_rate(self):
        self.venue.fail_connects = 9
        supply = self.make()
        for _ in range(9):
            self.pump(supply, steps=1)
        self.assertEqual((len(self.venue.connections), self.venue.connect_attempts), (0, 9))
        self.assertEqual(self.waits[:6], [1.0, 2.0, 4.0, 8.0, 16.0, 30.0])
        self.assertEqual(set(self.waits[6:]), {30.0})
        self.assertEqual(supply.status()['state'], 'RECOVERY_PENDING')
        self.pump(supply)
        self.assertEqual(self.states(supply)[self.key][0], 'ACTIVE_NO_DATA')

    def test_refused_subscription_is_reported_and_recorded_once(self):
        self.venue.refuse = {('trade', 'BTC/USD')}
        supply = self.make()
        for _ in range(3):
            self.pump(supply)
        self.assertEqual(self.states(supply)[self.key], ('REFUSED', 'PROVIDER_REFUSED_SUBSCRIPTION'))
        self.assertEqual(supply.status()['state'], 'DEGRADED')
        self.writer.flush()
        self.assertEqual(self.rows('SELECT stream_id,observations FROM market_stream_gaps WHERE reason=?', 'SUPPLY_SUBSCRIPTION_REFUSED'),
                         [(f'kraken:{BTC}:CRYPTO_TRADES', 1)])

    def test_unknown_pair_is_blocked_by_the_existing_resolver(self):
        unknown = 'XA01:00000000000000FF'
        supply = self.make((SupplyTarget('kraken', unknown, ('CRYPTO_TRADES',)),))
        self.pump(supply)
        self.assertEqual(self.states(supply)[('kraken', unknown, 'CRYPTO_TRADES')], ('BLOCKED', 'UNKNOWN_INSTRUMENT'))
        self.assertEqual(self.venue.connect_attempts, 0)

    def test_maintenance_is_its_own_provider_state(self):
        supply = self.make()
        self.pump(supply)
        self.venue.status('maintenance')
        self.pump(supply)
        provider = supply.status()['providers']['kraken']
        self.assertEqual((provider['connection'], provider['maintenance'], provider['available']), ('MAINTENANCE', True, False))

    def test_serving_demand_on_the_same_stream_survives_the_collector_and_the_reverse(self):
        screener = 'screener:order-flow'
        self.runtime.subscribe(instrument_id=BTC, capabilities=['CRYPTO_TRADES'], consumer_id=screener)
        supply = self.make()
        self.pump(supply)
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id=BTC, capability='CRYPTO_TRADES'), 2)
        self.assertEqual(len([m for m in self.venue.connection.sent if m['method'] == 'subscribe']), 1)
        supply.stop()
        self.pump(supply)
        self.assertEqual(self.runtime.subscriptions.ref_count(instrument_id=BTC, capability='CRYPTO_TRADES'), 1)
        self.assertEqual(self.venue.subscribed(), {('trade', 'BTC/USD')})
        self.assertFalse(self.venue.connection.closed)
        self.assertEqual([m for m in self.venue.connection.sent if m['method'] == 'unsubscribe'], [])
        # The other direction: the screener leaving does not drop a collector's stream.
        again = self.make()
        self.pump(again)
        self.runtime.unsubscribe(instrument_id=BTC, capabilities=['CRYPTO_TRADES'], consumer_id=screener)
        self.pump(again)
        self.assertEqual(self.venue.subscribed(), {('trade', 'BTC/USD')})

    def test_stop_removes_the_last_subscription_from_the_venue(self):
        supply = self.make()
        self.pump(supply)
        supply.stop()
        self.runtime.step()
        self.assertEqual(self.venue.subscribed(), set())
        self.assertEqual([m['method'] for m in self.venue.connection.sent], ['subscribe', 'unsubscribe'])


class MoomooFeedSupplyTests(SupplyCase):
    """Real LiveObservationalRuntime, subscription manager, push feed and admission over a synthetic OpenD."""

    ENV = {'IMP_LIVE_OBSERVATIONAL': '1', 'IMP_MOOMOO_LIVE': '1', 'IMP_LIVE_RECONNECT_BACKOFF_SEC': '0.05',
           'IMP_MOOMOO_OPEND_CHECK_SEC': '0',  # notice a dropped OpenD on the next pass, not 15 s later
           'IMP_OBSERVATIONAL_PROVIDER': 'moomoo', 'IMP_IBKR_LIVE': '0', 'IMP_SHADOW_RECORDING': '0'}

    def runtime(self, opend, *, env=None, **probe):
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime

        report = synthetic_probe(Path(self.temp.name) / 'probe.json', **probe)
        item = patch.dict(os.environ, {**self.ENV, 'IMP_MOOMOO_PROBE_REPORT': str(report), **(env or {})})
        item.start()
        self.addCleanup(item.stop)
        for started in opend.install():
            self.addCleanup(started.stop)
        runtime = LiveObservationalRuntime()
        runtime.configure()
        self.addCleanup(runtime.stop)
        return runtime

    def make(self, runtime, capabilities=('US_EQUITY_L1', 'US_EQUITY_TICKS'), symbols=('AAPL',)):
        targets = tuple(SupplyTarget('moomoo', symbol, capabilities) for symbol in symbols)
        return self.supply(targets, {'moomoo': _MoomooSupply(runtime=lambda: runtime)})

    def active(self, supply, count):
        def ready():
            supply.step()
            return supply.status()['summary']['active'] == count
        self.wait_until(ready)

    def test_verified_targets_are_subscribed_once_and_their_data_is_committed(self):
        opend = SyntheticOpenD()
        runtime = self.runtime(opend)
        supply = self.make(runtime)
        self.active(supply, 2)
        self.assertEqual(opend.subscribed(), {('US.AAPL', 'QUOTE'), ('US.AAPL', 'TICKER')})
        for _ in range(3):
            supply.step()
        self.assertEqual(sorted(opend.context.subscribe_calls), [('US.AAPL', 'QUOTE'), ('US.AAPL', 'TICKER')])
        self.assertEqual(runtime.subscriptions.active_subscriptions()[0]['consumers'], [SUPPLY_CONSUMER])
        for _ in range(4):
            self.assertTrue(opend.push_tick('US.AAPL'))
        self.assertFalse(opend.push_tick('US.MSFT'))  # never requested, so never delivered
        self.wait_until(lambda: self.writer.flush() >= 0 and self.writer.status()['committed'] >= 5)
        stored = dict(self.rows('SELECT capability,COUNT(*) FROM market_stream_records GROUP BY capability'))
        self.assertEqual(stored['US_EQUITY_TICKS'], 4)
        self.assertGreaterEqual(stored['US_EQUITY_L1'], 1)
        self.assertEqual(self.rows('SELECT DISTINCT symbol FROM market_stream_records'), [('AAPL',)])
        status = supply.status()
        self.assertEqual((status['state'], status['summary']['collecting']), ('COLLECTING', 2))
        self.assertEqual(runtime.feed.trade_api_counters, {'broker_cancels': 0, 'broker_modifications': 0,
                         'broker_orders_submitted': 0, 'trade_contexts_created': 0, 'trade_unlock_calls': 0})
        self.assertEqual(runtime.lifecycle.execution_use, 'DISPLAY_ONLY')

    def test_stale_missing_or_partial_probe_keeps_the_gate_closed(self):
        opend = SyntheticOpenD()
        runtime = self.runtime(opend, verified_at='2026-01-01T00:00:00+00:00')
        supply = self.make(runtime)
        supply.step()
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_PROBE_STALE')})
        time.sleep(1.2)  # two feed sync rounds
        self.assertEqual((opend.subscribed(), runtime.subscriptions.active_subscriptions()), (set(), []))
        (Path(self.temp.name) / 'probe.json').unlink()
        supply.providers['moomoo']._probe = None
        supply.step()
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_PROBE_MISSING')})

    def test_opend_is_not_contacted_until_the_probe_verifies_a_target(self):
        opend = SyntheticOpenD()
        report = synthetic_probe(Path(self.temp.name) / 'probe.json', verified_at='2026-01-01T00:00:00+00:00')
        item = patch.dict(os.environ, {**self.ENV, 'IMP_MOOMOO_PROBE_REPORT': str(report)})
        item.start()
        self.addCleanup(item.stop)
        for started in opend.install():
            self.addCleanup(started.stop)
        created = []
        def factory():
            from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime

            runtime = LiveObservationalRuntime()
            runtime.configure()
            self.addCleanup(runtime.stop)
            created.append(runtime)
            return runtime
        provider = _MoomooSupply(runtime=factory)
        supply = self.supply((SupplyTarget('moomoo', 'AAPL', ('US_EQUITY_L1',)),), {'moomoo': provider})
        for _ in range(3):
            supply.step()
        time.sleep(0.3)
        # Operator confirmation alone: no runtime, no feed thread, no OpenD session.
        self.assertEqual((created, opend.contexts), ([], []))
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_PROBE_STALE')})
        # A probe refreshed while the child runs is picked up without a restart.
        synthetic_probe(report)
        provider._probe = None
        self.active(supply, 1)
        self.assertEqual((len(created), opend.subscribed()), (1, {('US.AAPL', 'QUOTE')}))
        # And one that ages past the limit while running releases what it allowed.
        synthetic_probe(report, verified_at='2026-01-01T00:00:00+00:00')
        provider._probe = None
        supply.step()
        self.assertEqual(set(self.states(supply).values()), {('BLOCKED', 'ENTITLEMENT_PROBE_STALE')})
        self.assertEqual(created[0].subscriptions.active_subscriptions(), [])

    def test_entitlement_file_cache_reloads_without_manual_invalidation(self):
        report = synthetic_probe(Path(self.temp.name) / 'reload-probe.json')
        provider = _MoomooSupply(runtime=lambda: None)
        moment = [10.0]
        with patch.dict(os.environ, {'IMP_MOOMOO_PROBE_REPORT': str(report)}), \
             patch.object(headless_supply.time, 'monotonic', side_effect=lambda: moment[0]):
            self.assertIsNone(provider.entitlement('US_EQUITY_L1'))
            synthetic_probe(report, verified_at='2026-01-01T00:00:00+00:00')
            moment[0] = 10.5
            self.assertIsNone(provider.entitlement('US_EQUITY_L1'))  # bounded cache window
            moment[0] = 11.1
            self.assertEqual(provider.entitlement('US_EQUITY_L1'), 'ENTITLEMENT_PROBE_STALE')
            synthetic_probe(report)
            moment[0] = 12.2
            self.assertIsNone(provider.entitlement('US_EQUITY_L1'))
        self.assertIsNone(provider.runtime)  # reload itself never opens a provider

    def test_unreachable_opend_does_not_keep_an_idle_writer_owning_the_store(self):
        opend = SyntheticOpenD()
        opend.drop()
        runtime = self.runtime(opend)
        supply = self.make(runtime, capabilities=('US_EQUITY_TICKS',))
        supply.step()
        time.sleep(0.6)  # a dozen failed connection attempts at the test backoff
        self.writer.flush()
        # Nothing was lost, so nothing is recorded and the writer still owns nothing another process could want.
        self.assertIsNone(self.writer.run_id)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_gaps'), [(0,)])
        self.assertEqual(self.rows('SELECT COUNT(*) FROM market_stream_runs'), [(0,)])

    def test_only_capabilities_the_probe_verified_are_requested(self):
        opend = SyntheticOpenD()
        runtime = self.runtime(opend, entitled=('US_EQUITY_L1',))
        supply = self.make(runtime, capabilities=('US_EQUITY_L1', 'US_EQUITY_DEPTH'))
        self.active(supply, 1)
        self.assertEqual(self.states(supply)[('moomoo', 'AAPL', 'US_EQUITY_DEPTH')][0], 'BLOCKED')
        time.sleep(0.7)
        self.assertEqual(opend.subscribed(), {('US.AAPL', 'QUOTE')})

    def test_provider_refusal_and_quota_are_reported_not_retried_in_a_loop(self):
        opend = SyntheticOpenD(refuse=(('US.AAPL', 'TICKER'),))
        runtime = self.runtime(opend, env={'IMP_MOOMOO_SUBSCRIPTION_QUOTA': '2'})
        supply = self.make(runtime, symbols=('AAPL', 'MSFT'))
        def refused():
            supply.step()
            return self.states(supply)[('moomoo', 'AAPL', 'US_EQUITY_TICKS')][0] == 'REFUSED'
        self.wait_until(refused)
        states = self.states(supply)
        self.assertEqual(states[('moomoo', 'AAPL', 'US_EQUITY_TICKS')], ('REFUSED', 'PROVIDER_REFUSED_SUBSCRIPTION'))
        # The existing quota of two is spent on AAPL; MSFT is rejected by the manager, never sent to OpenD.
        self.assertEqual({states[('moomoo', 'MSFT', name)] for name in ('US_EQUITY_L1', 'US_EQUITY_TICKS')},
                         {('BLOCKED', 'QUOTA_EXHAUSTED')})
        time.sleep(1.2)
        self.assertEqual(opend.context.subscribe_calls.count(('US.AAPL', 'TICKER')), 1)  # 15 s retry spacing, not every sync
        self.assertFalse(any(code == 'US.MSFT' for code, _ in opend.context.subscribe_calls))
        self.assertEqual(supply.status()['state'], 'DEGRADED')

    def test_opend_loss_records_a_gap_and_the_subscription_is_restored_on_reconnect(self):
        opend = SyntheticOpenD(snapshots=False)
        runtime = self.runtime(opend)
        supply = self.make(runtime, capabilities=('US_EQUITY_TICKS',))
        self.active(supply, 1)
        opend.push_tick('US.AAPL')
        opend.drop()
        self.wait_until(lambda: opend.context is None)
        def pending():
            supply.step()
            return supply.status()['providers']['moomoo']['recovery_pending']
        self.wait_until(pending)
        self.assertEqual(supply.status()['state'], 'RECOVERY_PENDING')
        # Disconnected is not an active subscription, whatever the feed still remembers.
        self.assertEqual(self.states(supply)[('moomoo', 'AAPL', 'US_EQUITY_TICKS')], ('REQUESTED', None))
        self.assertFalse(opend.push_tick('US.AAPL'))
        time.sleep(0.6)  # many failed retries
        opend.restore()
        self.wait_until(lambda: len(opend.contexts) == 2 and opend.subscribed() == {('US.AAPL', 'TICKER')})
        opend.push_tick('US.AAPL')
        self.wait_until(lambda: self.writer.flush() >= 0 and self.writer.status()['committed'] == 2)
        # One gap for the one lost session, not one per failed retry.
        self.assertEqual(self.rows('SELECT stream_id,observations FROM market_stream_gaps WHERE reason=?', 'MOOMOO_DISCONNECT_NO_REPLAY'),
                         [('*', 1)])
        self.active(supply, 1)

    def test_owned_opend_stops_while_selected_demand_is_still_present(self):
        from market_platform_foundation.market_data import live_runtime
        opend = SyntheticOpenD()
        runtime = self.runtime(opend)
        supply = self.make(runtime)
        self.active(supply, 2)
        supply.providers['moomoo']._factory = None  # model the headless process-owned runtime
        active_at_stop = []
        original_stop = runtime.stop
        def stop_runtime():
            active_at_stop.append(len(runtime.subscriptions.active_keys))
            original_stop()
        with patch.object(runtime, 'stop', stop_runtime), patch.object(live_runtime, '_RUNTIME', runtime):
            supply.stop()
        self.assertEqual(active_at_stop[0], 2)
        self.assertEqual(runtime.subscriptions.active_keys, set())
        self.wait_until(lambda: all(context.closed for context in opend.contexts))

    def test_serving_consumers_keep_their_subscriptions_when_the_collector_stops(self):
        opend = SyntheticOpenD()
        runtime = self.runtime(opend)
        runtime.subscribe(instrument_id='AAPL', capabilities=['US_EQUITY_L1'], consumer_id='workspace:1')
        supply = self.make(runtime)
        self.active(supply, 2)
        self.assertEqual(runtime.subscriptions.ref_count(instrument_id='AAPL', capability='US_EQUITY_L1'), 2)
        supply.stop()
        self.assertEqual(runtime.subscriptions.ref_count(instrument_id='AAPL', capability='US_EQUITY_L1'), 1)
        self.assertEqual(runtime.subscriptions.ref_count(instrument_id='AAPL', capability='US_EQUITY_TICKS'), 0)
        self.wait_until(lambda: opend.subscribed() == {('US.AAPL', 'QUOTE')})
        self.assertFalse(opend.context.closed)  # an injected runtime is its owner's to close
        self.assertEqual(opend.context.unsubscribe_calls, [('US.AAPL', 'TICKER')])


class KrakenCatalogSupplyTests(SupplyCase):
    def test_real_pair_resolver_uses_bounded_public_catalog_request(self):
        from market_platform_foundation.ui_api import screener_crypto
        payload = {'error': [], 'result': {'BTC/USD': {'base': 'BTC', 'quote': 'USD', 'status': 'online',
            'aclass_base': 'currency', 'aclass_quote': 'currency', 'pair_decimals': 1, 'lot_decimals': 8}}}
        requests = []
        class Response:
            status = 200
            def __enter__(response): return response
            def __exit__(response, *args): return False
            def read(response, bound):
                self.assertEqual(bound, 10_000_001)
                return json.dumps(payload).encode()
        def offline_urlopen(request, timeout):
            requests.append((request.full_url, timeout))
            return Response()
        service = screener_crypto.CryptoScreener(env={'IMP_CRYPTO_LIVE': '1'})
        with patch.object(screener_crypto.urllib.request, 'urlopen', offline_urlopen), \
             patch.object(screener_crypto, 'crypto_screener_service', return_value=service):
            rows, _, error = service._catalog()
            self.assertIsNone(error)
            instrument = rows[0]['instrument']['instrument_id']
            self.assertEqual(screener_crypto._stream_pair(instrument), ('BTC/USD', 1, 8))
            self.assertIsNone(screener_crypto._stream_pair('XA01:0000000000000000'))
        self.assertEqual(requests, [('https://api.kraken.com/0/public/AssetPairs?assetVersion=1', 10)])

    def test_pair_catalog_failure_refuses_unknown_stream_without_network(self):
        from market_platform_foundation.ui_api import screener_crypto
        service = screener_crypto.CryptoScreener(env={'IMP_CRYPTO_LIVE': '1'})
        with patch.object(screener_crypto.urllib.request, 'urlopen', side_effect=OSError('synthetic unavailable')), \
             patch.object(screener_crypto, 'crypto_screener_service', return_value=service):
            self.assertIsNone(screener_crypto._stream_pair('XA01:0000000000000000'))


if __name__ == '__main__':
    unittest.main()
