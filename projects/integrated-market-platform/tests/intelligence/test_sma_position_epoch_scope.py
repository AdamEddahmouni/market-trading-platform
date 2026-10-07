import unittest
from market_platform_foundation.risk.sma_trailing_stop import position_epoch
from tests.trading_correctness.test_paper_experiment_accounting import _experiment_ledger, _Orders

class PositionEpochIsolationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = _experiment_ledger()
        self.orders = _Orders(self.ledger)

    def epoch(self, instrument):
        return position_epoch(self.ledger.events, account_id=self.ledger.paper_account_id,
                              session_id=self.ledger.session_id, instrument_id=instrument, side='LONG')

    def test_two_open_instruments_use_their_own_opening_fill(self):
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        self.orders.submit('US:NVDA', 'BUY', 10, '250')
        trades = self.ledger.project_trades()
        self.assertEqual(self.epoch('US:AAPL')['opening_fill_id'], trades[0]['fill_id'])
        self.assertEqual(self.epoch('US:NVDA')['opening_fill_id'], trades[1]['fill_id'])

    def test_reopened_aapl_while_nvda_open_gets_a_new_episode(self):
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        self.orders.submit('US:NVDA', 'BUY', 10, '250')
        first = self.epoch('US:AAPL')
        self.orders.submit('US:AAPL', 'SELL', 10, '150')
        self.orders.submit('US:NVDA', 'BUY', 2, '250')
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        self.assertNotEqual(self.epoch('US:AAPL')['position_epoch_id'], first['position_epoch_id'])
        self.assertEqual(self.epoch('US:AAPL')['opening_fill_id'], self.ledger.project_trades()[-1]['fill_id'])

    def test_another_instrument_close_cannot_erase_open_aapl_lineage(self):
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        first = self.epoch('US:AAPL')
        self.orders.submit('US:NVDA', 'BUY', 10, '250')
        self.orders.submit('US:NVDA', 'SELL', 10, '250')
        self.assertEqual(self.epoch('US:AAPL'), first)


from pathlib import Path
import tempfile
from types import SimpleNamespace
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from tests.intelligence.test_sma_trailing_stop import Clock, T0, series, quote

class StopEpisodeServiceTests(unittest.TestCase):
    def setUp(self):
        self.ledger = _experiment_ledger()
        self.orders = _Orders(self.ledger)
        self.clock = Clock(T0 + 180)
        self.closes = {'US:AAPL': [14500, 14500], 'US:NVDA': [23800, 23800]}
        self.prices = {'US:AAPL': 15000, 'US:NVDA': 25000}
        self.store = SimpleNamespace(paper_ledger=self.ledger, execution_deferred=False)
        self.repository = SmaStopRepository()
        self.service = self.make_service(self.repository)
        self.service.configure(dict(enabled=True, sma_window_bars=2))
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        self.orders.submit('US:NVDA', 'BUY', 10, '250')

    def make_service(self, repository):
        service = SmaStopService(self.store, repository=repository, clock=self.clock,
            bars=lambda instrument, policy, scale: dict(state='CURRENT', reason=None, source='SOFTWARE_CONTROLLED', bars=series(self.closes[instrument])),
            quotes=lambda instrument, scale: quote(self.prices[instrument], int(self.clock() * 1e9)),
            actions=SimpleNamespace(history=lambda instrument: []))
        service._monitoring = lambda *args: dict(state='NOT_RUNNING')
        return service

    def test_partial_close_and_scale_in_do_not_roll_stop_after_nvda_close(self):
        first = self.service.evaluate('US:AAPL')['stop']
        self.orders.submit('US:NVDA', 'SELL', 10, '250')
        self.orders.submit('US:AAPL', 'SELL', 4, '150')
        reduced = self.service.evaluate('US:AAPL')['stop']
        self.assertEqual(reduced['stop_state_id'], first['stop_state_id'])
        self.assertEqual(reduced['quantity'], 6)
        self.orders.submit('US:AAPL', 'BUY', 2, '150')
        self.assertEqual(self.service.evaluate('US:AAPL')['stop']['stop_state_id'], first['stop_state_id'])

    def test_reopen_is_hidden_before_evaluation_and_starts_clean(self):
        first = self.service.evaluate('US:AAPL')['stop']
        self.orders.submit('US:AAPL', 'SELL', 10, '150')
        self.orders.submit('US:AAPL', 'BUY', 3, '150')
        self.assertIsNone(self.service.status('US:AAPL')['stop'])
        self.assertIsNone(self.service.decision_facts('US:AAPL'))
        self.closes['US:AAPL'] = [14000, 14000]
        self.clock.value += 1
        new = self.service.evaluate('US:AAPL')['stop']
        self.assertNotEqual(new['position_epoch_id'], first['position_epoch_id'])
        self.assertEqual((new['active_stop'], new['previous_stop'], new['carried_from'], new['update_count']), ('140', None, None, 1))

    def test_restart_restores_separate_instrument_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            connection = LocalStateConnection(path)
            first = self.make_service(SmaStopRepository(connection))
            first.configure(dict(enabled=True, sma_window_bars=2))
            a = first.evaluate('US:AAPL')['stop']
            n = first.evaluate('US:NVDA')['stop']
            connection.close()
            connection = LocalStateConnection(path)
            second = self.make_service(SmaStopRepository(connection))
            self.assertEqual(second.status('US:AAPL')['stop']['active_stop'], '145')
            self.assertEqual(second.status('US:NVDA')['stop']['active_stop'], '238')
            self.assertEqual(second.evaluate('US:AAPL')['stop']['position_epoch_id'], a['position_epoch_id'])
            self.assertEqual(second.evaluate('US:NVDA')['stop']['position_epoch_id'], n['position_epoch_id'])
            connection.close()

from market_platform_foundation.intelligence.inference.trade_lifecycle import episodes_from_trades
from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict

class EpochContractTests(PositionEpochIsolationTests):
    def test_matches_canonical_trade_episode_and_is_stable_under_reordered_reads(self):
        self.orders.submit('US:AAPL', 'BUY', 3, '150')
        self.orders.submit('US:AAPL', 'BUY', 2, '150')
        self.orders.submit('US:NVDA', 'BUY', 10, '250')
        args = dict(account_id=self.ledger.paper_account_id, session_id=self.ledger.session_id,
                    instrument_id='US:AAPL', side='LONG', experiment_id=self.ledger.experiment_id)
        epoch = position_epoch(self.ledger.events, **args)
        episode = episodes_from_trades(self.ledger.project_trades(), account_id=self.ledger.paper_account_id,
                                       experiment_id=self.ledger.experiment_id)[0]
        self.assertEqual(epoch['position_epoch_id'], episode['episode_id'])
        self.assertEqual(position_epoch(list(reversed(self.ledger.events)), **args), epoch)
        for field in ('account_id', 'experiment_id'):
            self.assertNotEqual(position_epoch(self.ledger.events, **dict(args, **{field: 'OTHER'}))['position_epoch_id'], epoch['position_epoch_id'])

    def test_legacy_untagged_position_rows_resolve_only_by_fill_id(self):
        self.orders.submit('US:AAPL', 'BUY', 10, '150')
        expected = self.epoch('US:AAPL')
        rows = []
        for event in self.ledger.events:
            payload = dict(event['payload'])
            if event['event_type'] == 'PositionChanged':
                payload.pop('instrument_id', None)
            rows.append(dict(event, payload=payload))
        args = dict(account_id=self.ledger.paper_account_id, session_id=self.ledger.session_id, instrument_id='US:AAPL', side='LONG')
        self.assertEqual(position_epoch(rows, **args), expected)
        rows = [e for e in rows if e['event_type'] != 'FillRecorded']
        with self.assertRaisesRegex(ValueError, 'POSITION_FILL_LINEAGE_UNAVAILABLE'):
            position_epoch(rows, **args)

class LegacyStopTests(StopEpisodeServiceTests):
    def legacy(self, instrument, *, wrong=False):
        self.service.evaluate(instrument)
        state = self.repository.latest_state(self.ledger.paper_account_id, instrument)
        epoch = self.service._epoch(instrument, 'LONG', dict(generation=0))
        legacy_id = epoch['legacy_position_epoch_id']
        if wrong:
            opening = next(e for e in self.ledger.events if e['event_type'] == 'PositionChanged')
            legacy_id = 'PE-' + input_hash_from_dict(dict(account=self.ledger.paper_account_id, session=self.ledger.session_id,
                instrument=instrument, side='LONG', fill_id=opening['payload']['fill_id'], sequence=opening['sequence']))[:32]
        state.update(schema_version='sma-trailing-stop-state/1.0.0', position_epoch_id=legacy_id)
        for key in ('epoch_schema', 'episode_id', 'experiment_id', 'opening_fill_id'):
            state.pop(key, None)
        # Load the old serialized row into a fresh store; immutable history stays historical.
        repository = SmaStopRepository()
        config, policy = self.service._config()
        repository.put('policy', policy['policy_id'], policy)
        repository.put('config', self.ledger.paper_account_id, config)
        repository.put('state', state['stop_state_id'], state)
        self.repository, self.service = repository, self.make_service(repository)
        return state

    def test_safe_legacy_migration_keeps_stop_and_identifier(self):
        old = self.legacy('US:AAPL')
        read = self.service.status('US:AAPL')['stop']
        self.assertEqual(read['active_stop'], '145')
        self.assertEqual(self.repository.get('state', old['stop_state_id'])['schema_version'], 'sma-trailing-stop-state/1.0.0')
        self.service.evaluate('US:AAPL')
        migrated = self.repository.get('state', old['stop_state_id'])
        self.assertEqual((migrated['schema_version'], migrated['active_stop'], migrated['legacy_position_epoch_id']),
                         ('sma-trailing-stop-state/1.1.0', 14500, old['position_epoch_id']))

    def test_ambiguous_legacy_state_is_blocked_without_guess_or_exit(self):
        old = self.legacy('US:NVDA', wrong=True)
        self.prices['US:NVDA'] = 10000
        for result in (self.service.status('US:NVDA'), self.service.evaluate('US:NVDA')):
            self.assertEqual((result['status'], result['reason_codes'], result['stop']), ('BLOCKED', ['LEGACY_POSITION_EPOCH_AMBIGUOUS'], None))
        self.assertIsNone(self.service.decision_facts('US:NVDA'))
        with self.assertRaisesRegex(ValueError, 'STOP_NOT_BREACHED'):
            self.service.record_exit('US:NVDA')
        self.assertEqual(self.repository.get('state', old['stop_state_id']), old)

    def test_legacy_ambiguity_remains_explicit_after_sqlite_restart(self):
        old = self.legacy('US:NVDA', wrong=True)
        config, policy = self.service._config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.sqlite3'
            connection = LocalStateConnection(path)
            repository = SmaStopRepository(connection)
            repository.put('policy', policy['policy_id'], policy)
            repository.put('config', self.ledger.paper_account_id, config)
            repository.put('state', old['stop_state_id'], old)
            connection.close()
            connection = LocalStateConnection(path)
            repository = SmaStopRepository(connection)
            service = self.make_service(repository)
            self.assertEqual(service.evaluate('US:NVDA')['reason_codes'], ['LEGACY_POSITION_EPOCH_AMBIGUOUS'])
            self.assertEqual(repository.get('state', old['stop_state_id']), old)
            connection.close()

    def test_safe_legacy_breach_retains_terminal_protection(self):
        self.prices['US:AAPL'] = 14100
        old = self.legacy('US:AAPL')
        new = self.service.evaluate('US:AAPL')
        self.assertEqual((new['status'], new['stop']['trigger_price'], new['stop']['stop_state_id']),
                         ('BREACHED', '141', old['stop_state_id']))
        self.assertEqual(self.repository.get('state', old['stop_state_id'])['triggered_at'], old['triggered_at'])
