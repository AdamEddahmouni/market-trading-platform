"""OCT1-08 SMA trailing stop: policy math, temporal integrity, lifecycle and persistence."""
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.sma_trailing_stop import (
    REFERENCE_TEST_CONFIG, advance, build_policy, check_bar_trigger, check_quote_trigger, initial_state, normalize_bars,
    position_epoch, price_to_minor, sma_candidate, sma_display,
)
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService

T0 = 1791208800.0  # 2026-10-05T14:00:00Z, Monday 10:00 ET (regular session)
T0_NS = int(T0 * 1e9)
MINUTE = 60_000_000_000
IID = 'US:NVDA'


def bar(index, close, *, low=None, high=None, open_=None, **extra):
    open_ = close if open_ is None else open_
    return dict(bar_id=f'B{index}', event_time=T0_NS + index * MINUTE, available_time=T0_NS + (index + 1) * MINUTE,
                open=open_, high=max(high or close, open_, close), low=min(low or close, open_, close), close=close, **extra)


def series(closes):
    return [bar(i, c) for i, c in enumerate(closes)]


def state_for(side, policy):
    return initial_state(account_id='a', session_id='s', instrument_id=IID, position_epoch_id='PE-1', epoch_basis='TEST',
                         side=side, quantity=10, policy=policy, activated_at=T0_NS, activation_reason='POSITION_OPENED')


def stops(side, closes, window=2):
    policy = build_policy(sma_window_bars=window)
    state, path, kinds = state_for(side, policy), [], []
    for count in range(1, len(closes) + 1):
        state, events = advance(state, series(closes[:count]), policy)
        path.append(state['active_stop'])
        kinds.extend(e['kind'] for e in events)
    return state, path, kinds


def quote(price, at_ns, admissible=True):
    return dict(admissible=admissible, price_minor=price, as_of_ns=at_ns, source='FIXTURE', evidence_ref='q',
                reason=None if admissible else 'AGE_EXCEEDS_POLICY')


class PolicyContractTests(unittest.TestCase):
    def test_identity_covers_every_behavioural_parameter(self):
        reference = build_policy(**REFERENCE_TEST_CONFIG)
        self.assertEqual(reference['config_label'], 'REFERENCE_TEST_CONFIG')
        self.assertEqual(reference['policy_id'], build_policy(**REFERENCE_TEST_CONFIG, created_at='2026-10-06T00:00:00Z')['policy_id'])
        others = [build_policy(sma_window_bars=21), build_policy(sma_window_bars=20, bar_interval='5m'),
                  build_policy(sma_window_bars=20, tick_minor=5), build_policy(sma_window_bars=20, session_scope='EXTENDED')]
        self.assertEqual(len({reference['policy_id'], *(p['policy_id'] for p in others)}), 5)
        self.assertEqual(others[0]['config_label'], 'OPERATOR_BOUNDED_CONFIG')
        for field in ('sma_window_bars', 'bar_interval', 'price_basis', 'trigger_basis', 'tick_rounding_policy', 'long_behavior',
                      'short_behavior', 'update_timing', 'warmup_requirement', 'evaluation_fill_model', 'schema_version'):
            self.assertIn(field, reference)

    def test_only_bounded_parameters_are_accepted(self):
        for bad in (dict(sma_window_bars=1), dict(sma_window_bars=201), dict(sma_window_bars='20'), dict(sma_window_bars=True),
                    dict(sma_window_bars=20, bar_interval='1d'), dict(sma_window_bars=20, tick_minor=0)):
            with self.assertRaises(ValueError):
                build_policy(**bad)

    def test_rounding_is_exact_and_toward_protection(self):
        self.assertEqual(sma_candidate([10001, 10002, 10002], 'LONG'), (10002, 30005))   # 10001.67 rounds up for a long
        self.assertEqual(sma_candidate([10001, 10002, 10002], 'SHORT'), (10001, 30005))  # and down for a short
        self.assertEqual(sma_candidate([10000, 10010], 'LONG', 5)[0], 10005)
        self.assertEqual(sma_display(30005, 3), '100.0167')
        self.assertEqual(price_to_minor(185.95), 18595)
        self.assertEqual(price_to_minor('0.1') + price_to_minor('0.2'), 30)  # no float drift
        for bad in (0, -1, float('nan'), None, True):
            with self.assertRaises(ValueError):
                price_to_minor(bad)


class MonotonicTests(unittest.TestCase):
    def test_long_stop_never_moves_down(self):
        # SMA 100, 102, 101, 105 -> stop 100, 102, 102, 105
        state, path, kinds = stops('LONG', [10000, 10000, 10400, 9800, 11200])
        self.assertEqual(path, [None, 10000, 10200, 10200, 10500])
        self.assertEqual(kinds, ['ACTIVATED', 'TIGHTENED', 'CLAMPED', 'TIGHTENED'])
        self.assertEqual((state['tighten_count'], state['clamp_count']), (2, 1))

    def test_short_stop_never_moves_up(self):
        # SMA 100, 98, 99, 95 -> stop 100, 98, 98, 95
        _, path, kinds = stops('SHORT', [10000, 10000, 9600, 10200, 8800])
        self.assertEqual(path, [None, 10000, 9800, 9800, 9500])
        self.assertEqual(kinds, ['ACTIVATED', 'TIGHTENED', 'CLAMPED', 'TIGHTENED'])

    def test_adverse_sma_clamps_and_says_so(self):
        long_state, long_path, _ = stops('LONG', [10000, 10000, 9400])     # SMA falls to 97
        short_state, short_path, _ = stops('SHORT', [10000, 10000, 10600])  # SMA rises to 103
        self.assertEqual((long_path[-1], long_state['candidate_stop'], long_state['reason_codes']), (10000, 9700, ['MONOTONIC_CLAMP']))
        self.assertEqual((short_path[-1], short_state['candidate_stop'], short_state['reason_codes']), (10000, 10300, ['MONOTONIC_CLAMP']))

    def test_random_paths_never_loosen(self):
        rng = random.Random(8)
        for side in ('LONG', 'SHORT'):
            closes = [10000 + rng.randint(-400, 400) for _ in range(120)]
            _, path, _ = stops(side, closes, window=5)
            live = [p for p in path if p is not None]
            self.assertTrue(all((b >= a) if side == 'LONG' else (b <= a) for a, b in zip(live, live[1:])))


class BarAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.policy = build_policy(sma_window_bars=3)

    def test_insufficient_history_is_warming_up_with_no_stop(self):
        state, events = advance(state_for('LONG', self.policy), series([10000, 10100]), self.policy)
        self.assertEqual((state['status'], state['active_stop'], state['sma_value'], state['reason_codes'], events),
                         ('WARMING_UP', None, None, ['INSUFFICIENT_HISTORY'], []))

    def test_partial_and_future_bars_are_excluded(self):
        bars = [*series([10000, 10000, 10000]), bar(3, 20000, complete=False), bar(4, 30000)]
        normalized = normalize_bars(bars, cutoff_ns=T0_NS + 4 * MINUTE, interval='1m')
        self.assertEqual([b['bar_id'] for b in normalized['bars']], ['B0', 'B1', 'B2'])
        self.assertEqual((normalized['excluded']['partial'], normalized['excluded']['future']), (1, 1))
        state, _ = advance(state_for('LONG', self.policy), normalized['bars'], self.policy)
        self.assertEqual(state['active_stop'], 10000)

    def test_shuffled_input_normalizes_to_one_sequence(self):
        bars = series([10000, 10100, 10200, 10300, 10400])
        shuffled = bars[:]
        random.Random(3).shuffle(shuffled)
        cutoff = T0_NS + 10 * MINUTE
        self.assertEqual(normalize_bars(shuffled, cutoff_ns=cutoff, interval='1m')['bars'], normalize_bars(bars, cutoff_ns=cutoff, interval='1m')['bars'])

    def test_duplicate_bar_counts_once_and_conflicts_fail_closed(self):
        bars = series([10000, 10100, 10200])
        normalized = normalize_bars([*bars, dict(bars[2])], cutoff_ns=T0_NS + 10 * MINUTE, interval='1m')
        self.assertEqual((len(normalized['bars']), normalized['excluded']['duplicate']), (3, 1))
        self.assertEqual(advance(state_for('LONG', self.policy), normalized['bars'], self.policy)[0]['sma_value'], '101.0000')
        with self.assertRaisesRegex(ValueError, 'BAR_IDENTITY_CONFLICT'):
            normalize_bars([*bars, dict(bars[2], close=10201, high=10201)], cutoff_ns=T0_NS + 10 * MINUTE, interval='1m')
        with self.assertRaisesRegex(ValueError, 'BAR_IDENTITY_CONFLICT'):
            normalize_bars([*bars, dict(bars[2], bar_id='OTHER')], cutoff_ns=T0_NS + 10 * MINUTE, interval='1m')

    def test_missing_bar_is_never_synthesized(self):
        bars = [b for b in series([10000, 10100, 10200, 10300, 10400]) if b['bar_id'] != 'B2']
        state, _ = advance(state_for('LONG', self.policy), bars, self.policy)
        self.assertEqual((state['status'], state['active_stop'], state['reason_codes']), ('BLOCKED', None, ['BAR_GAP_IN_WINDOW']))
        # A stop that already exists is held, flagged stale, and not loosened by the gap.
        active, _ = advance(state_for('LONG', self.policy), series([10000, 10100, 10200]), self.policy)
        held, events = advance(active, [*series([10000, 10100, 10200]), bar(4, 9000)], self.policy)
        self.assertEqual((held['status'], held['active_stop'], held['reason_codes']), ('STALE', 10100, ['STOP_UPDATE_STALE', 'BAR_GAP_IN_WINDOW']))
        self.assertEqual([e['kind'] for e in events], ['STALE'])

    def test_malformed_bars_are_rejected_not_repaired(self):
        bad = [dict(bar(0, 10000), close=10000.5), dict(bar(1, 10000), low=10100), dict(bar(2, 10000), available_time=T0_NS + 9 * MINUTE),
               dict(bar_id='X')]
        normalized = normalize_bars(bad, cutoff_ns=T0_NS + 20 * MINUTE, interval='1m')
        self.assertEqual((normalized['bars'], normalized['excluded']['invalid']), ([], 4))


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.policy = build_policy(sma_window_bars=2)

    def active(self, side='LONG', closes=(10000, 10000)):
        return advance(state_for(side, self.policy), series(list(closes)), self.policy)[0]

    def test_stop_from_bar_k_is_not_applied_to_bar_k(self):
        closes = [10000, 10000, 10400]
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10400, low=10150)]  # bar 2 traded under the stop it will produce (102.00)
        state = advance(state_for('LONG', self.policy), bars, self.policy)[0]
        self.assertEqual(state['active_stop'], 10200)
        self.assertIsNone(check_bar_trigger(state, bars[2]))  # only the earlier 100.00 stop was in force during bar 2
        hit = check_bar_trigger(state, bar(3, 10300, low=10190))
        self.assertEqual((hit['stop'], hit['gap_through_stop'], hit['intrabar_sequence']), (10200, False, 'UNKNOWN'))
        self.assertEqual(len(closes), 3)

    def test_first_stop_is_not_tested_against_its_own_bar(self):
        bars = [bar(0, 10000), bar(1, 10000, low=9000)]
        state = advance(state_for('LONG', self.policy), bars, self.policy)[0]
        self.assertIsNone(check_bar_trigger(state, bars[1]))

    def test_long_bar_breach_boundaries(self):
        state = self.active()
        self.assertEqual(check_bar_trigger(state, bar(2, 10100, low=9900))['stop'], 10000)
        self.assertIsNone(check_bar_trigger(state, bar(2, 10100, low=10001)))
        self.assertIsNotNone(check_bar_trigger(state, bar(2, 10100, low=10000)))  # touching the stop is a breach

    def test_short_bar_breach(self):
        state = self.active('SHORT', (10500, 10500))
        self.assertEqual(check_bar_trigger(state, bar(2, 10400, high=10600))['stop'], 10500)
        self.assertIsNone(check_bar_trigger(state, bar(2, 10400, high=10499)))

    def test_gap_through_stop_is_recorded_not_filled_at_the_stop(self):
        hit = check_bar_trigger(self.active(), bar(2, 9650, open_=9700, low=9600, high=9750))
        self.assertEqual((hit['stop'], hit['open'], hit['low'], hit['gap_through_stop']), (10000, 9700, 9600, True))
        self.assertNotIn('fill_price', hit)  # the trigger never names a fill

    def test_quote_triggers_long_and_short(self):
        at = T0_NS + 3 * MINUTE
        self.assertEqual(check_quote_trigger(self.active(), quote(10001, at))['status'], 'ACTIVE')
        breached = check_quote_trigger(self.active(), quote(9995, at))
        self.assertEqual((breached['status'], breached['trigger_price'], breached['trigger_evidence']['stop'], breached['reason_codes'][0]),
                         ('BREACHED', 9995, 10000, 'SMA_TRAILING_STOP_BREACHED'))
        short = self.active('SHORT', (10500, 10500))
        self.assertEqual(check_quote_trigger(short, quote(10499, at))['status'], 'ACTIVE')
        self.assertEqual(check_quote_trigger(short, quote(10500, at))['status'], 'BREACHED')

    def test_stale_quote_proves_neither_breach_nor_safety(self):
        state = check_quote_trigger(self.active(), quote(9000, T0_NS + 3 * MINUTE, admissible=False))
        self.assertEqual((state['status'], state['trigger_state'], state['trigger_reason_codes']),
                         ('ACTIVE', 'TRIGGER_UNAVAILABLE', ['REVALIDATION_REQUIRED', 'AGE_EXCEEDS_POLICY']))
        self.assertIsNone(state['triggered_at'])
        recovered = check_quote_trigger(state, quote(10100, T0_NS + 3 * MINUTE))
        self.assertEqual((recovered['trigger_state'], recovered['trigger_reason_codes']), ('ARMED', []))

    def test_quote_older_than_the_stop_cannot_trigger_it(self):
        state = advance(state_for('LONG', self.policy), series([10000, 10000, 10400]), self.policy)[0]  # stop 102 effective after bar 2
        before = quote(10150, T0_NS + 3 * MINUTE - 1)
        self.assertEqual(check_quote_trigger(state, before)['status'], 'ACTIVE')  # judged against the earlier 100.00 stop
        self.assertEqual(check_quote_trigger(state, quote(10150, T0_NS + 3 * MINUTE))['status'], 'BREACHED')
        first = self.active()
        self.assertEqual(check_quote_trigger(first, quote(9000, T0_NS + MINUTE))['trigger_state'], 'NOT_ARMED')

    def test_terminal_states_do_not_update(self):
        breached = check_quote_trigger(self.active(), quote(9995, T0_NS + 3 * MINUTE))
        later, events = advance(breached, series([10000, 10000, 12000, 12000]), self.policy)
        self.assertEqual((later, events), (breached, []))


class EpochTests(unittest.TestCase):
    @staticmethod
    def events(*shares):
        return [dict(event_type='PositionChanged', sequence=i, event_time=T0_NS + i, payload=dict(position_shares=s, fill_id=f'F{i}'))
                for i, s in enumerate(shares)]

    def epoch(self, shares, side='LONG'):
        return position_epoch(self.events(*shares), account_id='a', session_id='s', instrument_id=IID, side=side)

    def test_epoch_follows_ledger_fill_lineage(self):
        opened = self.epoch([10])
        self.assertEqual((opened['epoch_basis'], opened['opening_fill_id']), ('LEDGER_OPENING_FILL', 'F0'))
        self.assertEqual(self.epoch([10, 4])['position_epoch_id'], opened['position_epoch_id'])   # partial reduction: same episode
        self.assertEqual(self.epoch([10, 15])['position_epoch_id'], opened['position_epoch_id'])  # add: same episode
        self.assertNotEqual(self.epoch([10, 0, 10])['position_epoch_id'], opened['position_epoch_id'])  # flat then long: new episode
        reversed_ = self.epoch([10, -5], side='SHORT')
        self.assertNotEqual(reversed_['position_epoch_id'], opened['position_epoch_id'])
        self.assertIsNone(self.epoch([10, 0]))
        self.assertIsNone(self.epoch([10], side='SHORT'))


class Clock:
    def __init__(self, value=T0):
        self.value = value

    def __call__(self):
        return self.value


class Fixture:
    """A controlled completed-bar and last-trade source. No provider, no model."""

    def __init__(self, *, connection=None, clock=None, ledger=None):
        self.clock = clock or Clock()
        self.closes, self.state, self.reason, self.price, self.quote_ok = [], 'CURRENT', None, 20000, True
        self.ledger = ledger or PaperExecutionLedger(paper_account_id='controlled', session_id='session')
        self.store = SimpleNamespace(paper_ledger=self.ledger, execution_deferred=False)
        self.repository = SmaStopRepository(connection)
        self.service = SmaStopService(self.store, repository=self.repository, clock=self.clock, bars=self.bars, quotes=self.quotes,
                                      actions=SimpleNamespace(history=lambda instrument: []))
        self.service._monitoring = lambda state, now_ns, policy: dict(state='NOT_RUNNING', worker_state='STOPPED', last_evaluated_at=None, liveness='OBSERVED')

    def bars(self, instrument, policy, scale):
        return dict(state=self.state, reason=self.reason, source='CONTROLLED_FIXTURE', bars=series(self.closes))

    def quotes(self, instrument, scale):
        now = int(self.clock() * 1e9)
        return quote(self.price, now, self.quote_ok)

    def hold(self, quantity=10, side='LONG'):
        rows = [dict(instrument_id=IID, symbol='NVDA', quantity=quantity, side=side)] if quantity else []
        self.ledger.project_positions = Mock(return_value=rows)

    def step(self, close=None, *, price=None, minutes=1):
        """One more completed bar, then evaluate at its availability time."""
        if close is not None:
            self.closes.append(close)
            self.clock.value = T0 + 60 * len(self.closes)
        else:
            self.clock.value += 60 * minutes
        if price is not None:
            self.price = price
        return self.service.evaluate(IID)

    def kinds(self):
        return [e['kind'] for e in reversed(self.repository.events('controlled', IID, limit=100))]


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.f.hold(10)

    def configure(self, window=2, **extra):
        return self.f.service.configure(dict(enabled=True, sma_window_bars=window, **extra))

    def test_not_configured_is_explicit(self):
        status = self.f.service.evaluate(IID)
        self.assertEqual((status['status'], status['stop'], status['reason_codes']), ('NOT_CONFIGURED', None, ['STOP_NOT_CONFIGURED']))
        self.assertEqual((status['paper_close'], status['order_type'], status['live_execution']), ('NOT_SUBMITTED', 'NONE_STOP_MONITOR_ONLY', 'UNCHANGED'))
        self.assertEqual(self.f.repository.durability, 'INTENTIONAL_EPHEMERAL')

    def test_configuration_is_bounded(self):
        for bad in (dict(enabled=True, sma_window_bars=1), dict(enabled=True, formula='close*0.9'), dict(enabled='yes'),
                    dict(enabled=True, bar_interval='1d'), dict(enabled=True, active_stop=120), dict(enabled=False, sma_window_bars=5), []):
            with self.assertRaises(ValueError):
                self.f.service.configure(bad)
        view = self.f.service.configure(dict(enabled=True))
        self.assertEqual((view['policy']['sma_window_bars'], view['policy']['bar_interval'], view['policy']['config_label']), (20, '1m', 'REFERENCE_TEST_CONFIG'))

    def test_warmup_then_active_tighten_and_clamp(self):
        self.configure(3)
        self.assertEqual(self.f.step(10000)['status'], 'WARMING_UP')
        warming = self.f.step(10000)
        self.assertEqual((warming['status'], warming['stop']['active_stop'], warming['stop']['bars_available']), ('WARMING_UP', None, 2))
        active = self.f.step(10000)
        self.assertEqual((active['status'], active['stop']['active_stop'], active['stop']['sma_value'], active['stop']['side']),
                         ('ACTIVE', '100', '100.0000', 'LONG'))
        tightened = self.f.step(10600)
        self.assertEqual((tightened['stop']['active_stop'], tightened['stop']['previous_stop']), ('102', '100'))
        clamped = self.f.step(9400)
        self.assertEqual((clamped['stop']['active_stop'], clamped['stop']['candidate_stop'], clamped['reason_codes']), ('102', '100', ['MONOTONIC_CLAMP']))
        self.assertEqual((clamped['stop']['distance_to_stop'], clamped['stop']['reference_price']), ('98', '200'))
        self.assertEqual(self.f.kinds(), ['EPISODE_STARTED', 'ACTIVATED', 'TIGHTENED', 'CLAMPED'])

    def test_late_activation_is_not_backdated(self):
        self.configure()
        late = self.f.step(10000)
        self.assertEqual(late['stop']['activation_reason'], 'LATE_ACTIVATION')
        self.assertEqual(late['stop']['activated_at'], '2026-10-05T14:01:00Z')
        watched = Fixture()
        watched.hold(0)
        watched.service.configure(dict(enabled=True, sma_window_bars=2))
        watched.step(10000)
        watched.hold(10)
        self.assertEqual(watched.step(10000)['stop']['activation_reason'], 'POSITION_OPENED')

    def test_stop_already_through_the_price_is_an_immediate_exit_condition(self):
        self.configure()
        self.f.step(10000)
        status = self.f.step(10000, price=9900)
        self.assertEqual((status['status'], status['reason_codes']), ('BREACHED', ['SMA_TRAILING_STOP_BREACHED', 'IMMEDIATE_EXIT_CONDITION']))

    def test_breach_is_terminal_until_the_position_closes(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        breached = self.f.step(10000, price=9995)
        self.assertEqual((breached['status'], breached['stop']['trigger_price'], breached['stop']['active_stop'], breached['paper_close']),
                         ('BREACHED', '99.95', '100', 'NOT_SUBMITTED'))
        self.assertEqual(self.f.step(12000, price=20000)['status'], 'BREACHED')  # recovery does not un-breach or move the stop
        self.assertEqual(self.f.step(12000)['stop']['active_stop'], '100')
        self.f.hold(0)
        self.assertEqual(self.f.step(12000)['status'], 'CLOSED')

    def test_stale_quote_leaves_the_stop_armed_but_unresolved(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        self.f.quote_ok = False
        status = self.f.step(10000, price=9000)
        self.assertEqual((status['status'], status['stop']['trigger_state'], status['stop']['trigger_reason_codes'][0]),
                         ('ACTIVE', 'TRIGGER_UNAVAILABLE', 'REVALIDATION_REQUIRED'))
        self.assertIsNone(status['stop']['distance_to_stop'])

    def test_stale_bars_keep_the_stop_and_say_stale(self):
        self.configure()
        self.f.step(10000); self.f.step(10000); self.f.step(10400)
        self.f.state, self.f.reason = 'STALE', 'STALE_BAR_SOURCE'
        stale = self.f.step(minutes=4)
        self.assertEqual((stale['status'], stale['stop']['active_stop'], stale['reason_codes']), ('STALE', '102', ['STOP_UPDATE_STALE', 'STALE_BAR_SOURCE']))
        self.assertEqual(stale['stop']['trigger_state'], 'ARMED')  # the level is still known and still enforced
        self.f.state, self.f.reason = 'CURRENT', None
        self.f.closes.extend([10400, 10400, 10400])
        resumed = self.f.step(10400)
        self.assertEqual((resumed['status'], resumed['stop']['active_stop']), ('ACTIVE', '104'))
        self.assertEqual(self.f.kinds()[-3:], ['STALE', 'RESUMED', 'TIGHTENED'])

    def test_unavailable_bars_never_create_a_stop(self):
        self.configure()
        self.f.state, self.f.reason = 'UNAVAILABLE', 'OPEND_UNAVAILABLE'
        self.f.closes = [10000, 10000, 10000]
        status = self.f.step(minutes=3)
        self.assertEqual((status['status'], status['stop']['active_stop'], status['reason_codes']), ('BLOCKED', None, ['OPEND_UNAVAILABLE']))

    def test_position_close_resets_and_nothing_leaks_to_the_next_position(self):
        self.configure()
        self.f.step(10000); self.f.step(10000); self.f.step(10800)
        first = self.f.service.status(IID)['stop']
        self.f.hold(0)
        closed = self.f.step(10800)
        self.assertEqual((closed['status'], closed['stop']['closed_reason']), ('CLOSED', 'POSITION_FLAT'))
        self.assertEqual(self.f.service.decision_facts(IID), None)
        self.f.hold(5)
        reopened = self.f.step(9000)  # a lower SMA is a new episode's first stop, not a loosening of the old one
        self.assertNotEqual(reopened['stop']['position_epoch_id'], first['position_epoch_id'])
        self.assertEqual((reopened['stop']['active_stop'], reopened['stop']['previous_stop'], reopened['stop']['quantity']), ('99', None, 5))

    def test_reversal_closes_the_long_stop_and_starts_a_short_episode(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        long_id = self.f.service.status(IID)['stop']['stop_state_id']
        self.f.hold(-10, side='SHORT')
        short = self.f.step(10000, price=9000)
        self.assertEqual((short['stop']['side'], short['stop']['active_stop'], short['status']), ('SHORT', '100', 'ACTIVE'))
        self.assertNotEqual(short['stop']['stop_state_id'], long_id)
        self.assertEqual(self.f.repository.get('state', long_id)['closed_reason'], 'POSITION_REVERSED')

    def test_partial_reduction_keeps_the_episode_and_reads_ledger_quantity(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        before = self.f.service.status(IID)['stop']
        self.f.hold(4)
        after = self.f.step(10400)['stop']
        self.assertEqual((after['stop_state_id'], after['quantity'], after['active_stop']), (before['stop_state_id'], 4, '102'))

    def test_config_change_while_active_is_rejected_and_cannot_loosen(self):
        self.configure(2)
        self.f.step(10000); self.f.step(10000); self.f.step(10800)
        with self.assertRaisesRegex(ValueError, 'STOP_POLICY_CHANGE_REJECTED_WHILE_ACTIVE'):
            self.configure(5)
        self.assertEqual(self.f.kinds()[-1], 'POLICY_CHANGE_REJECTED')
        self.assertEqual(self.f.service.status(IID)['stop']['active_stop'], '104')
        # Explicit disable then re-enable with a slower window: the earlier level is carried, never lowered.
        self.f.service.configure(dict(enabled=False))
        self.assertEqual(self.f.service.status(IID)['status'], 'NOT_CONFIGURED')
        self.configure(3)
        carried = self.f.step(10000)
        self.assertEqual((carried['stop']['active_stop'], carried['stop']['candidate_stop'], carried['reason_codes']), ('104', '102.67', ['MONOTONIC_CLAMP']))
        self.assertIsNotNone(carried['stop']['carried_from'])

    def test_downtime_is_a_monitoring_gap_not_reconstructed_updates(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        self.f.closes.extend([10200] * 30)
        self.f.clock.value = T0 + 60 * len(self.f.closes)
        status = self.f.service.evaluate(IID)
        self.assertEqual(status['stop']['update_count'], 2)  # one resume update, not thirty back-filled ones
        gap = next(e for e in self.f.repository.events('controlled', IID, limit=100) if e['kind'] == 'MONITORING_GAP')
        self.assertEqual((gap['liveness'], gap['updates_backfilled']), ('NOT_OBSERVED', 0))

    def test_history_is_bounded_and_paged(self):
        self.configure()
        for index in range(12):
            self.f.step(10000 + index * 100)
        page = self.f.service.history(IID, limit=5)
        self.assertEqual((len(page['events']), page['total'] > 5, page['events'][0]['kind']), (5, True, 'TIGHTENED'))
        older = self.f.service.history(IID, limit=5, before=page['next_before'])
        self.assertTrue(all(e['sequence'] < page['next_before'] for e in older['events']))
        self.assertEqual(len(self.f.service.history(IID, limit=100000)['events']), page['total'])

    def test_deferred_ledger_infers_nothing(self):
        self.configure()
        self.f.step(10000); self.f.step(10000)
        self.f.store.execution_deferred = True
        status = self.f.step(10000, price=9000)
        self.assertEqual((status['status'], status['reason_codes'], status['stop']['active_stop']), ('BLOCKED', ['POSITION_SNAPSHOT_UNAVAILABLE'], '100'))
        self.assertEqual(self.f.repository.latest_state('controlled', IID)['status'], 'ACTIVE')


class PersistenceTests(unittest.TestCase):
    def test_restart_recovers_the_same_stop_and_never_loosens(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            connection = LocalStateConnection(path)
            first = Fixture(connection=connection)
            first.hold(10)
            first.service.configure(dict(enabled=True, sma_window_bars=2))
            first.step(10000); first.step(10000); first.step(10800)
            before = first.service.status(IID)['stop']
            events = first.kinds()
            connection.close()

            connection = LocalStateConnection(path)
            second = Fixture(connection=connection, clock=Clock(first.clock.value + 30))
            second.hold(10)
            second.closes = list(first.closes)
            self.assertEqual(second.repository.durability, 'SQLITE_LOCAL_STATE')
            recovered = second.service.status(IID)['stop']
            self.assertEqual((recovered['stop_state_id'], recovered['active_stop'], recovered['policy_id']),
                             (before['stop_state_id'], '104', before['policy_id']))
            self.assertEqual(second.kinds(), events)
            after = second.step(9000)  # a lower SMA after restart still cannot lower the stop
            self.assertEqual((after['stop']['active_stop'], after['reason_codes']), ('104', ['MONOTONIC_CLAMP']))
            state = second.repository.latest_state('controlled', IID)
            with self.assertRaisesRegex(ValueError, 'STOP_LOOSENING_REJECTED'):
                second.repository.put('state', state['stop_state_id'], dict(state, active_stop=10300))
            connection.close()

    def test_a_different_position_after_restart_does_not_inherit_the_old_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'imp-state.sqlite3'
            connection = LocalStateConnection(path)
            first = Fixture(connection=connection)
            first.hold(10)
            first.service.configure(dict(enabled=True, sma_window_bars=2))
            first.step(10000); first.step(10800)
            old = first.service.status(IID)['stop']
            connection.close()

            connection = LocalStateConnection(path)
            ledger = PaperExecutionLedger(paper_account_id='controlled', session_id='session')
            ledger.events = EpochTests.events(10, 0, 7)  # the ledger now shows a later position episode
            second = Fixture(connection=connection, clock=Clock(first.clock.value), ledger=ledger)
            second.hold(7)
            second.closes = [9000, 9000]
            new = second.service.evaluate(IID)['stop']
            self.assertNotEqual(new['position_epoch_id'], old['position_epoch_id'])
            self.assertEqual((new['active_stop'], new['epoch_basis'], new['quantity']), ('90', 'LEDGER_OPENING_FILL', 7))
            self.assertEqual(second.repository.get('state', old['stop_state_id'])['closed_reason'], 'POSITION_EPOCH_CHANGED')
            connection.close()

    def test_terminal_states_and_policies_are_immutable(self):
        repository = SmaStopRepository()
        policy = build_policy(sma_window_bars=2)
        repository.put('policy', policy['policy_id'], policy)
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE_STOP_POLICY_COLLISION'):
            repository.put('policy', policy['policy_id'], dict(policy, sma_window_bars=3))
        state = dict(state_for('LONG', policy), status='BREACHED', active_stop=10000)
        repository.put('state', state['stop_state_id'], state)
        with self.assertRaisesRegex(ValueError, 'STOP_STATE_TERMINAL'):
            repository.put('state', state['stop_state_id'], dict(state, status='ACTIVE'))


if __name__ == '__main__':
    unittest.main()
