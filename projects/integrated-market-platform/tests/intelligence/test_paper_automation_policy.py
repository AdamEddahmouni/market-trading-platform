"""AUTO-01 pure policy, sizing, status, durable state and the reevaluation driver boundary."""
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.inference.paper_automation import (
    AutomationStatus, build_policy, decision_permitted, derive_status, entry_risk_blockers, exposure_minor,
    intent_identity, required_fields, size_entry, spending_gate,
)
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.paper_automation import PaperAutomationRepository
from tests.intelligence.test_reevaluation import SCOPE, Harness

LEDGER_POLICY = dict(max_order_shares=100, max_position_shares=500, allow_short=False, risk_policy_identity_hash='rp-1')


def body(**sections):
    value = dict(
        scope=dict(universe='US_EQUITIES'),
        schedule=dict(sessions=['REGULAR'], cadence_seconds=60, universe_evaluation_interval_seconds=1800,
                      no_new_entries_minutes_before_close=15),
        risk=dict(max_position_notional_minor=500_000, max_aggregate_exposure_minor=1_000_000, max_open_positions=2,
                  max_daily_loss_minor=100_000, max_per_trade_risk_minor=10_000, assumed_adverse_move_bps=200,
                  allowed_universes=['US_EQUITIES'], order_types=['MARKET'], allow_long=True, allow_short=False,
                  allow_entries=True, allow_exits=True),
        exits=dict(on_stop_breach=True, on_thesis_exit=True),
        ai=dict(allow_local_inference=True, allow_paid_inference=False, max_paid_requests_per_day=0, max_paid_tokens_per_day=0),
        emergency_stop=dict(max_consecutive_failures=3))
    for section, values in sections.items():
        value[section] = dict(value[section], **values)
    return value


def policy(**sections):
    return build_policy(body(**sections), account_id='acct', experiment_id='PPE-1', initial_capital_minor=10_000_000,
                        ledger_policy=LEDGER_POLICY)


class PolicyTests(unittest.TestCase):
    def test_every_field_is_required_and_named_together(self):
        with self.assertRaises(ValueError) as raised:
            build_policy({}, account_id='acct', experiment_id='PPE-1', initial_capital_minor=1, ledger_policy=LEDGER_POLICY)
        self.assertEqual(str(raised.exception), 'AUTOMATION_POLICY_INCOMPLETE:' + ','.join(required_fields()))
        partial = body()
        del partial['risk']['max_daily_loss_minor']
        del partial['ai']
        with self.assertRaises(ValueError) as raised:
            build_policy(partial, account_id='acct', experiment_id='PPE-1', initial_capital_minor=10_000_000, ledger_policy=LEDGER_POLICY)
        self.assertEqual(str(raised.exception).split(':')[1].split(','),
                         ['risk.max_daily_loss_minor', 'ai.allow_local_inference', 'ai.allow_paid_inference',
                          'ai.max_paid_requests_per_day', 'ai.max_paid_tokens_per_day'])

    def test_unknown_fields_wrong_types_and_missing_account_are_refused(self):
        for bad in (dict(body(), leverage=2), dict(body(), risk=dict(body()['risk'], take_profit=1)), None, []):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_INVALID'):
                build_policy(bad, account_id='acct', experiment_id='PPE-1', initial_capital_minor=10_000_000, ledger_policy=LEDGER_POLICY)
        for section, field, value in (('risk', 'max_open_positions', '2'), ('risk', 'allow_long', 1), ('schedule', 'cadence_seconds', 60.0),
                                      ('risk', 'max_open_positions', True), ('schedule', 'sessions', 'REGULAR')):
            with self.assertRaisesRegex(ValueError, f'AUTOMATION_POLICY_FIELD_INVALID:{section}.{field}'):
                policy(**{section: {field: value}})
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_PAPER_EXPERIMENT_REQUIRED'):
            build_policy(body(), account_id='acct', experiment_id=None, initial_capital_minor=1, ledger_policy=LEDGER_POLICY)

    def test_identity_is_bound_to_account_experiment_limits_and_ledger_policy(self):
        base = policy()
        self.assertEqual(base['policy_id'], policy()['policy_id'])
        self.assertEqual(base['execution'], dict(mode='INTERNAL_SIMULATION', provider='INTERNAL', live_capital=False))
        self.assertNotEqual(base['policy_id'], policy(risk=dict(max_open_positions=3))['policy_id'])
        other = build_policy(body(), account_id='acct', experiment_id='PPE-2', initial_capital_minor=10_000_000, ledger_policy=LEDGER_POLICY)
        self.assertNotEqual(base['policy_id'], other['policy_id'])
        moved = build_policy(body(), account_id='acct', experiment_id='PPE-1', initial_capital_minor=10_000_000,
                             ledger_policy=dict(LEDGER_POLICY, risk_policy_identity_hash='rp-2'))
        self.assertNotEqual(base['policy_id'], moved['policy_id'])

    def test_schedule_and_direction_consistency(self):
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_SCHEDULE_INVALID'):
            policy(schedule=dict(cadence_seconds=600, universe_evaluation_interval_seconds=300))
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_ENTRY_DIRECTION_REQUIRED'):
            policy(risk=dict(allow_long=False))
        exits_only = policy(risk=dict(allow_long=False, allow_entries=False))
        self.assertFalse(exits_only['risk']['allow_entries'])
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_SCOPE_OUTSIDE_ALLOWED_INSTRUMENTS'):
            policy(risk=dict(allowed_universes=['US_ETFS']))


class SizingTests(unittest.TestCase):
    def size(self, price=15000, positions=(), buying_power=10_000_000, **risk):
        return size_entry(policy(risk=risk) if risk else policy(), price_minor=price, positions=list(positions),
                          buying_power_minor=buying_power, ledger_policy=LEDGER_POLICY)

    def test_the_smallest_bound_wins_and_is_named(self):
        self.assertEqual((self.size()['quantity'], self.size()['binding']), (33, 'MAX_PER_TRADE_RISK'))
        self.assertEqual(self.size(max_per_trade_risk_minor=1_000)['binding'], 'MAX_PER_TRADE_RISK')
        self.assertEqual(self.size(max_per_trade_risk_minor=1_000)['quantity'], 3)  # 1,000 / 2% = 50,000 of notional
        self.assertEqual(self.size(max_per_trade_risk_minor=10_000_000)['binding'], 'MAX_POSITION_NOTIONAL')
        held = [dict(quantity=60, mark_minor=15000)]  # 900,000 of a 1,000,000 exposure limit already used
        self.assertEqual((self.size(positions=held)['quantity'], self.size(positions=held)['binding']), (6, 'MAX_AGGREGATE_EXPOSURE'))
        self.assertEqual((self.size(buying_power=30_000)['quantity'], self.size(buying_power=30_000)['binding']), (2, 'BUYING_POWER'))
        cheap = self.size(price=100, max_position_notional_minor=1_000_000, max_per_trade_risk_minor=1_000_000)
        self.assertEqual((cheap['quantity'], cheap['binding']), (100, 'PAPER_ACCOUNT_MAX_ORDER_SHARES'))

    def test_unknowns_size_to_zero_never_to_a_guess(self):
        self.assertEqual(self.size(price=None), dict(quantity=0, binding='REFERENCE_PRICE_UNAVAILABLE', bounds={}))
        self.assertEqual(self.size(price=0)['quantity'], 0)
        unmarked = [dict(quantity=10, mark_minor=None)]
        self.assertEqual(self.size(positions=unmarked)['binding'], 'PORTFOLIO_VALUATION_NOT_CURRENT')
        self.assertIsNone(exposure_minor(unmarked))
        self.assertEqual(exposure_minor([dict(quantity=-5, mark_minor=200), dict(quantity=0, mark_minor=None)]), 1000)
        self.assertEqual(self.size(buying_power=-5)['quantity'], 0)

    def test_entry_blockers(self):
        valuation = dict(quality='CURRENT', equity_minor=10_000_000)
        ok = dict(positions=[], valuation=valuation, day_start_equity_minor=10_000_000, pending_orders=[], minutes_to_close=120)
        self.assertEqual(entry_risk_blockers(policy(), **ok), [])
        cases = (
            (dict(positions=[dict(quantity=1, mark_minor=100), dict(quantity=1, mark_minor=100)]), 'MAX_OPEN_POSITIONS_REACHED'),
            (dict(positions=[dict(quantity=100, mark_minor=10_000)]), 'MAX_AGGREGATE_EXPOSURE_REACHED'),
            (dict(positions=[dict(quantity=1, mark_minor=None)]), 'PORTFOLIO_VALUATION_NOT_CURRENT'),
            (dict(valuation=dict(quality='STALE', equity_minor=10_000_000)), 'PORTFOLIO_VALUATION_NOT_CURRENT'),
            (dict(valuation=dict(quality='CURRENT', equity_minor=9_900_000)), 'MAX_DAILY_LOSS_REACHED'),
            (dict(day_start_equity_minor=None), 'DAY_START_EQUITY_UNAVAILABLE'),
            (dict(pending_orders=[dict(order_id='x')]), 'WORKING_ORDERS_PRESENT'),
            (dict(minutes_to_close=15), 'ENTRY_WINDOW_CLOSED'),
            (dict(minutes_to_close=None), 'ENTRY_WINDOW_CLOSED'),
        )
        for change, code in cases:
            self.assertIn(code, entry_risk_blockers(policy(), **dict(ok, **change)), code)
        self.assertEqual(entry_risk_blockers(policy(risk=dict(allow_entries=False, allow_long=False)), **ok), ['AUTOMATION_ENTRIES_DISABLED'])

    def test_decision_permission(self):
        enter = dict(action_state='ENTER', direction='LONG', instrument=dict(universe='US_EQUITIES'))
        self.assertIsNone(decision_permitted(policy(), enter))
        self.assertEqual(decision_permitted(policy(), dict(enter, direction='SHORT')), 'AUTOMATION_SHORT_NOT_PERMITTED')
        self.assertEqual(decision_permitted(policy(), dict(enter, direction=None)), 'AUTOMATION_DIRECTION_UNAVAILABLE')
        self.assertEqual(decision_permitted(policy(), dict(enter, instrument=dict(universe='US_OPTIONS'))), 'AUTOMATION_INSTRUMENT_NOT_ALLOWED')
        self.assertEqual(decision_permitted(policy(risk=dict(allow_exits=False)), dict(action_state='EXIT')), 'AUTOMATION_EXITS_DISABLED')
        self.assertEqual(decision_permitted(policy(exits=dict(on_stop_breach=False)), dict(action_state='EXIT', server_exit=dict(x=1))),
                         'AUTOMATION_STOP_EXIT_DISABLED')
        self.assertIsNone(decision_permitted(policy(exits=dict(on_stop_breach=False)), dict(action_state='EXIT')))
        for state in ('HOLD', 'NO_ACTION', 'CONSIDER_ENTRY', 'REVALIDATION_REQUIRED', None):
            self.assertEqual(decision_permitted(policy(), dict(action_state=state)), 'ACTION_NOT_EXECUTABLE')


class SpendingAndStatusTests(unittest.TestCase):
    def test_spending_gate(self):
        local = dict(state='AVAILABLE', runtime='LOCAL_MODEL', budget=None)
        paid = dict(state='AVAILABLE', runtime='PAID_API', reason=None,
                    budget=dict(requests=2, tokens=1000, max_requests=30, max_tokens=200_000, held_requests=1, held_tokens=500))
        authorized = policy(ai=dict(allow_paid_inference=True, max_paid_requests_per_day=5, max_paid_tokens_per_day=50_000))
        self.assertEqual(spending_gate(policy(), local), dict(allowed=True, reason=None))
        self.assertEqual(spending_gate(policy(ai=dict(allow_local_inference=False)), local)['reason'], 'AUTONOMOUS_LOCAL_INFERENCE_NOT_AUTHORIZED')
        self.assertEqual(spending_gate(policy(), paid)['reason'], 'AUTONOMOUS_SPENDING_NOT_AUTHORIZED')
        self.assertEqual(spending_gate(authorized, paid), dict(allowed=True, reason=None))
        self.assertEqual(spending_gate(authorized, dict(paid, budget=dict(paid['budget'], requests=4)))['reason'], 'AUTONOMOUS_SPENDING_LIMIT_REACHED')
        self.assertEqual(spending_gate(authorized, dict(paid, budget=dict(paid['budget'], tokens=49_500)))['reason'], 'AUTONOMOUS_SPENDING_LIMIT_REACHED')
        self.assertEqual(spending_gate(authorized, dict(paid, budget=None))['reason'], 'AUTONOMOUS_SPENDING_BUDGET_UNREADABLE')
        self.assertEqual(spending_gate(authorized, dict(paid, state='UNAVAILABLE', reason='SYNTHESIS_DAILY_BUDGET_EXHAUSTED'))['reason'],
                         'SYNTHESIS_DAILY_BUDGET_EXHAUSTED')
        self.assertEqual(spending_gate(authorized, dict(state='NOT_CONFIGURED'))['reason'], 'MODEL_UNAVAILABLE')
        # The owner's cap can only tighten the shared allowance, never widen it.
        wide = policy(ai=dict(allow_paid_inference=True, max_paid_requests_per_day=1000, max_paid_tokens_per_day=10 ** 9))
        self.assertEqual(spending_gate(wide, dict(paid, budget=dict(paid['budget'], requests=29)))['reason'], 'AUTONOMOUS_SPENDING_LIMIT_REACHED')

    def test_one_primary_status_and_running_only_when_able(self):
        def status(**overrides):
            return derive_status(**dict(dict(configured=True, armed=True, desired='RUNNING', emergency=False, error=False, blockers=[],
                                             session_eligible=True), **overrides))
        block = lambda category: [dict(category=category, code='X')]  # noqa: E731
        self.assertEqual(status(), AutomationStatus.RUNNING)
        self.assertEqual(status(configured=False), AutomationStatus.NOT_CONFIGURED)
        self.assertEqual(status(armed=False), AutomationStatus.DISARMED)
        self.assertEqual(status(desired='STOPPED'), AutomationStatus.STOPPED)
        self.assertEqual(status(desired='PAUSED'), AutomationStatus.PAUSED)
        self.assertEqual(status(emergency=True, armed=False), AutomationStatus.EMERGENCY_STOPPED)
        self.assertEqual(status(error=True), AutomationStatus.ERROR)
        self.assertEqual(status(session_eligible=False), AutomationStatus.WAITING_FOR_MARKET)
        self.assertEqual(status(session_eligible=False, blockers=block('AUTHORITY')), AutomationStatus.BLOCKED_BY_AUTHORITY)
        self.assertEqual(status(session_eligible=False, blockers=block('DATA')), AutomationStatus.WAITING_FOR_MARKET)
        self.assertEqual(status(blockers=block('DATA') + block('RISK') + block('BUDGET')), AutomationStatus.BLOCKED_BY_DATA)
        self.assertEqual(status(blockers=block('RISK') + block('BUDGET')), AutomationStatus.BLOCKED_BY_RISK)
        self.assertEqual(status(blockers=block('BUDGET')), AutomationStatus.BLOCKED_BY_BUDGET)

    def test_intent_identity_is_one_per_decision_per_account(self):
        self.assertEqual(intent_identity('a', 'AD-1'), intent_identity('a', 'AD-1'))
        self.assertNotEqual(intent_identity('a', 'AD-1'), intent_identity('a', 'AD-2'))
        self.assertNotEqual(intent_identity('a', 'AD-1'), intent_identity('b', 'AD-1'))
        self.assertTrue(intent_identity('a', 'AD-1').startswith('PAI-'))


class RepositoryContract:
    def repository(self):
        raise NotImplementedError

    def controller(self, repo, account='acct'):
        repo.save_controller(dict(account_id=account, updated_epoch=1.0, desired_state='STOPPED', arming=None))
        return repo

    def test_policy_versions_are_immutable(self):
        repo = self.repository()
        repo.put_policy(dict(policy_id='PAP-1', account_id='acct', value=1), now=1)
        repo.put_policy(dict(policy_id='PAP-1', account_id='acct', value=1), now=2)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_IMMUTABLE'):
            repo.put_policy(dict(policy_id='PAP-1', account_id='acct', value=2), now=3)
        self.assertEqual(repo.get_policy('PAP-1')['value'], 1)
        self.assertIsNone(repo.get_policy('PAP-none'))

    def test_one_owner_per_account_and_an_expired_lease_is_recoverable(self):
        repo = self.controller(self.repository())
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_NOT_CONFIGURED'):
            repo.acquire_lease('other', 'a', now=0, lease_seconds=10)
        repo.acquire_lease('acct', 'a', now=100, lease_seconds=60)
        repo.acquire_lease('acct', 'a', now=110, lease_seconds=60)  # the same owner renews
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_ALREADY_OWNED'):
            repo.acquire_lease('acct', 'b', now=169, lease_seconds=60)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_LEASE_LOST'):
            repo.heartbeat('acct', 'b', now=120, lease_seconds=60)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_LEASE_LOST'):
            repo.save_controller(dict(repo.get_controller('acct'), updated_epoch=2.0), owner_id='b')
        repo.heartbeat('acct', 'a', now=120, lease_seconds=60)
        self.assertEqual((repo.get_controller('acct')['lease_until'], repo.get_controller('acct')['heartbeat_at']), (180, 120))
        repo.acquire_lease('acct', 'b', now=181, lease_seconds=60)  # the lease ran out: no manual cleanup needed
        self.assertEqual(repo.get_controller('acct')['owner_id'], 'b')
        repo.release_lease('acct', 'a')  # not the owner: nothing changes
        self.assertEqual(repo.get_controller('acct')['owner_id'], 'b')
        repo.release_lease('acct', 'b')
        self.assertEqual((repo.get_controller('acct')['owner_id'], repo.get_controller('acct')['lease_until']), (None, None))

    def test_a_save_never_moves_the_lease(self):
        repo = self.controller(self.repository())
        repo.acquire_lease('acct', 'a', now=100, lease_seconds=60)
        repo.save_controller(dict(repo.get_controller('acct'), desired_state='RUNNING', updated_epoch=3.0, owner_id='forged', lease_until=9e9))
        row = repo.get_controller('acct')
        self.assertEqual((row['owner_id'], row['lease_until'], row['desired_state']), ('a', 160, 'RUNNING'))

    def test_a_submitted_intent_is_terminal(self):
        repo = self.repository()
        intent = dict(intent_id='PAI-1', account_id='acct', decision_id='AD-1', state='BLOCKED', updated_epoch=1.0)
        repo.put_intent(intent, now=1)
        repo.put_intent(dict(intent, state='SUBMITTED', updated_epoch=2.0), now=2)
        for state in ('BLOCKED', 'DEFERRED', 'PREVIEWED', 'CREATED'):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_INTENT_TERMINAL'):
                repo.put_intent(dict(intent, state=state, updated_epoch=3.0), now=3)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_INTENT_IDENTITY_CONFLICT'):
            repo.put_intent(dict(intent, decision_id='AD-2', state='SUBMITTED'), now=4)
        self.assertEqual(repo.get_intent('PAI-1')['state'], 'SUBMITTED')
        repo.put_intent(dict(intent_id='PAI-2', account_id='acct', decision_id='AD-2', state='DEFERRED', updated_epoch=5.0), now=5)
        self.assertEqual([i['intent_id'] for i in repo.intents('acct')], ['PAI-2', 'PAI-1'])
        self.assertEqual([i['intent_id'] for i in repo.intents('acct', states=['SUBMITTED'])], ['PAI-1'])
        self.assertEqual(repo.intents('other'), [])

    def test_events_are_append_only_bounded_and_paged_newest_first(self):
        repo = self.repository()
        for index in range(5):
            repo.append_event('acct', 'CYCLE' if index % 2 else 'ARMED', dict(index=index), now=float(index))
        repo.append_event('other', 'CYCLE', dict(index=99), now=9.0)
        events = repo.events('acct', limit=2)
        self.assertEqual([e['index'] for e in events], [4, 3])
        self.assertEqual([e['index'] for e in repo.events('acct', limit=10, before=events[-1]['sequence'])], [2, 1, 0])
        self.assertEqual([e['index'] for e in repo.events('acct', kinds=['CYCLE'])], [3, 1])
        self.assertEqual(repo.event_counts('acct'), dict(ARMED=3, CYCLE=2))
        self.assertEqual(repo.event_counts('acct', since=3.0), dict(ARMED=1, CYCLE=1))
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_EVENT_BOUND_EXCEEDED'):
            repo.append_event('acct', 'CYCLE', dict(blob='x' * 40000), now=10.0)
        self.assertFalse(hasattr(repo, 'delete_event') or hasattr(repo, 'update_event'))

    def test_armed_controllers(self):
        repo = self.controller(self.repository())
        self.assertEqual(repo.armed_controllers(), [])
        repo.save_controller(dict(repo.get_controller('acct'), arming=dict(arming_id='PAA-1'), updated_epoch=2.0))
        self.assertEqual([c['account_id'] for c in repo.armed_controllers()], ['acct'])


class EphemeralRepositoryTests(RepositoryContract, unittest.TestCase):
    def repository(self):
        repo = PaperAutomationRepository()
        self.assertEqual(repo.durability, 'INTENTIONAL_EPHEMERAL')
        return repo


class SqliteRepositoryTests(RepositoryContract, unittest.TestCase):
    def repository(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'state.sqlite3'
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(self.connection.close)
        repo = PaperAutomationRepository(self.connection)
        self.assertEqual(repo.durability, 'SQLITE_LOCAL_STATE')
        return repo

    def test_state_survives_a_new_connection(self):
        repo = self.controller(self.repository())
        repo.put_policy(dict(policy_id='PAP-1', account_id='acct'), now=1)
        repo.acquire_lease('acct', 'a', now=100, lease_seconds=60)
        repo.put_intent(dict(intent_id='PAI-1', account_id='acct', decision_id='AD-1', state='SUBMITTED', updated_epoch=1.0), now=1)
        repo.append_event('acct', 'ARMED', dict(policy_id='PAP-1'), now=1.0)
        self.connection.close()
        again = LocalStateConnection(self.path)
        self.addCleanup(again.close)
        restored = PaperAutomationRepository(again)
        self.assertEqual(restored.get_policy('PAP-1')['account_id'], 'acct')
        self.assertEqual((restored.get_controller('acct')['owner_id'], restored.get_controller('acct')['lease_until']), ('a', 160))
        self.assertEqual(restored.get_intent('PAI-1')['state'], 'SUBMITTED')
        self.assertEqual(restored.events('acct')[0]['kind'], 'ARMED')
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_INTENT_TERMINAL'):
            restored.put_intent(dict(intent_id='PAI-1', account_id='acct', decision_id='AD-1', state='BLOCKED', updated_epoch=2.0), now=2)


def complete(run_id, chosen, **coverage):
    block = dict(dict(status='GLOBAL_SELECTION_COMPLETE', coverage_complete=True, selection_complete=True), **coverage)
    return dict(run_id=run_id, state='CURRENT' if chosen else 'NO_GROUNDED_CANDIDATES', universe_coverage=block,
                candidates=[dict(instrument_id=iid, rank=rank) for rank, iid in enumerate(chosen, 1)],
                evidence=[dict(instrument=dict(instrument_id=iid, symbol=iid.split(':')[1])) for iid in chosen])


class ReevaluationDriverTests(unittest.TestCase):
    """The loop the controller drives: same lease and cycle, candidates only from a complete full-universe selection."""

    def setUp(self):
        self.h = Harness()
        self.h.ledger.execution_authority, self.h.ledger.execution_mode = 'PAPER_ONLY', 'INTERNAL_SIMULATION'

    def attach(self):
        return self.h.service.attach_driver('PAPER_AUTOMATION', scope=SCOPE, requested_cadence_seconds=60)

    def cycle(self, **kwargs):
        self.h.clock.value += 60
        return self.h.service.driven_cycle('SCHEDULED_CADENCE', self.h.clock.value, **kwargs)

    def test_driver_only_operations_are_refused_without_a_driver(self):
        self.h.configure()
        for call in (lambda: self.h.service.driven_cycle('SCHEDULED_CADENCE', 0), lambda: self.h.service.adopt_selection(complete('CU-1', [])),
                     lambda: self.h.service.request_redecision('US:NVDA', 'X')):
            with self.assertRaisesRegex(ValueError, 'REEVALUATION_DRIVER_REQUIRED'):
                call()

    def test_a_driven_loop_cannot_also_be_started_or_reconfigured_by_hand(self):
        self.attach()
        status = self.h.service.status()
        self.assertEqual((status['driver'], status['paper_execution'], status['candidate_source'], status['worker_state']),
                         ('PAPER_AUTOMATION', 'AUTOMATION_POLICY', 'FULL_UNIVERSE_SELECTION', 'RUNNING'))
        with self.assertRaisesRegex(ValueError, 'REEVALUATION_DRIVEN_BY_PAPER_AUTOMATION'):
            self.h.service.start(threaded=False)
        for manual in (self.h.configure, self.h.service.stop, self.h.service.run_once):
            with self.assertRaisesRegex(ValueError, 'REEVALUATION_DRIVEN_BY_PAPER_AUTOMATION'):
                manual()
        self.assertEqual(self.h.service.status()['worker_state'], 'RUNNING')

    def test_a_running_manual_loop_is_not_taken_over(self):
        self.h.configure()
        self.h.service.start(threaded=False)
        with self.assertRaisesRegex(ValueError, 'REEVALUATION_RUNNING_STOP_FIRST'):
            self.attach()

    def test_the_intake_head_is_never_reduced_in_place_of_coverage(self):
        self.attach()
        for _ in range(3):
            receipt = self.cycle()
        self.assertEqual((self.h.ai.reductions, self.h.provider.calls), (0, 0))
        self.assertEqual((receipt['candidate_count'], receipt['candidate_source']), (0, 'FULL_UNIVERSE_SELECTION'))

    def test_an_intake_head_selection_is_not_carried_under_the_coverage_label(self):
        self.h.configure()
        self.h.tick()  # the manual method reduces the first-50 intake and selects NVDA
        self.assertEqual(self.h.service.status()['tracked_candidates'], ['US:NVDA'])
        self.attach()
        self.assertEqual(self.h.service.status()['tracked_candidates'], [])

    def test_only_a_complete_selection_is_adopted(self):
        self.attach()
        for coverage in (dict(coverage_complete=False), dict(selection_complete=False), dict(status='PARTIAL_COVERAGE')):
            with self.assertRaisesRegex(ValueError, 'SELECTION_COVERAGE_INCOMPLETE'):
                self.h.service.adopt_selection(complete('CU-bad', ['US:NVDA'], **coverage))
        with self.assertRaisesRegex(ValueError, 'SELECTION_COVERAGE_INCOMPLETE'):
            self.h.service.adopt_selection(dict(complete('CU-stale', ['US:NVDA']), state='STALE'))
        self.assertEqual(self.cycle()['candidate_count'], 0)
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']))
        receipt = self.cycle()
        added = [t for t in receipt['transitions'] if t['classification'] == 'CANDIDATE_ADDED']
        self.assertEqual((added[0]['instrument_id'], added[0]['candidate_run_id'], added[0]['reason_codes']),
                         ('US:NVDA', 'CU-1', ['AI_SCREENER_SELECTED', 'FULL_UNIVERSE_SELECTION']))
        self.assertEqual((receipt['candidate_count'], self.h.ai.reductions), (1, 0))
        self.h.service.adopt_selection(complete('CU-2', []))  # complete coverage that selected nothing
        receipt = self.cycle()
        self.assertEqual([t['classification'] for t in receipt['transitions']], ['CANDIDATE_REMOVED'])
        self.assertEqual(receipt['candidate_count'], 0)

    def test_a_completed_slice_is_adopted_for_what_it_selected_only(self):
        self.attach()
        sliced = dict(status='SLICE_SELECTION_COMPLETE', coverage_complete=False, selection_complete=False, slice_complete=True)
        for refused in (dict(complete('CU-s0', ['US:NVDA'], **dict(sliced, slice_complete=False))),
                        dict(complete('CU-s1', ['US:NVDA'], **sliced), state='EXPIRED'),
                        complete('CU-s2', [], **dict(sliced, status='SLICE_COMPLETE_NO_SELECTION'))):
            with self.assertRaisesRegex(ValueError, 'SELECTION_COVERAGE_INCOMPLETE'):
                self.h.service.adopt_selection(refused)
        self.h.service.adopt_selection(complete('CU-s3', ['US:NVDA'], **sliced), ttl_seconds=3600)
        receipt = self.cycle()
        self.assertEqual(receipt['candidate_count'], 1)
        loop = self.h.service._loop()
        self.assertEqual(loop['selection_provenance']['status'], 'SLICE_SELECTION_COMPLETE')
        self.assertEqual(loop['selection_provenance']['run_id'], 'CU-s3')
        self.assertIsNotNone(loop['selection_valid_until_epoch'])

    def test_an_adopted_selection_is_dropped_when_its_lifetime_ends(self):
        self.attach()
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']), ttl_seconds=600)
        self.assertEqual(self.cycle()['candidate_count'], 1)
        self.h.clock.value += 601
        receipt = self.cycle()
        removed = [t for t in receipt['transitions'] if t['classification'] == 'CANDIDATE_REMOVED']
        self.assertEqual((removed[0]['instrument_id'], removed[0]['reason_codes']),
                         ('US:NVDA', ['SELECTION_HYPOTHESIS_EXPIRED', 'FULL_UNIVERSE_SELECTION']))
        self.assertEqual(receipt['candidate_count'], 0)

    def test_a_selected_candidate_outside_the_intake_gets_a_targeted_read(self):
        self.attach()
        self.h.ai.off_intake.add('US:NVDA')
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']))
        receipt = self.cycle()
        self.assertEqual(self.h.history()[0]['instrument_id'], 'US:NVDA')
        self.assertEqual(receipt['model_call_count'], 1)

    def test_the_model_gate_withholds_calls_and_classifies_spending_as_budget(self):
        self.attach()
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']))
        receipt = self.cycle(model_gate=dict(allowed=False, reason='AUTONOMOUS_SPENDING_NOT_AUTHORIZED'))
        self.assertEqual((self.h.provider.calls, receipt['cycle_status'], receipt['model_call_count']), (0, 'BUDGET_BLOCKED', 0))
        receipt = self.cycle(model_gate=dict(allowed=True, reason=None))
        self.assertEqual((self.h.provider.calls, receipt['model_call_count']), (1, 1))

    def test_a_redecision_request_is_evaluated_once_and_respects_the_dwell_when_flat(self):
        self.attach()
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']))
        self.cycle()
        self.assertEqual(self.cycle()['model_call_count'], 0)
        self.h.service.request_redecision('US:NVDA', 'ACTION_INPUT_CHANGED')
        self.h.service.request_redecision('US:NVDA', 'SECOND_REQUEST_IS_THE_SAME_REQUEST')
        held_back = self.cycle()['transitions'][0]  # flat, and its ENTER is younger than the dwell: not asked again yet
        self.assertEqual((held_back['classification'], held_back['model_call']), ('CHURN_SUPPRESSED', False))
        self.assertIn('DECISION_INPUT_CHANGED', held_back['reason_codes'])
        self.assertEqual(self.h.service._loop()['redecide'], {'US:NVDA': 'ACTION_INPUT_CHANGED'})
        self.h.clock.value += 300
        decided = self.cycle()['transitions'][0]
        self.assertIn('DECISION_INPUT_CHANGED', decided['reason_codes'])
        self.assertIsNotNone(decided['new_decision_id'])
        self.assertEqual(self.h.service._loop()['redecide'], {})
        self.assertEqual(self.cycle()['transitions'], [])

    def test_detach_releases_the_loop_for_the_manual_method(self):
        self.attach()
        self.h.service.adopt_selection(complete('CU-1', ['US:NVDA']))
        self.cycle()
        self.h.service.detach_driver()
        status = self.h.service.status()
        self.assertEqual((status['driver'], status['paper_execution'], status['worker_state'], status['tracked_candidates'], status['candidate_source']),
                         (None, 'MANUAL_ONLY', 'STOPPED', [], 'INTAKE_HEAD'))
        self.h.service.start(threaded=False)  # the documented operator method works again
        self.assertEqual(self.h.service.status()['worker_state'], 'RUNNING')

    def test_another_process_cannot_drive_a_loop_it_does_not_own(self):
        self.attach()
        other = Harness(clock=self.h.clock, owner='process-b', ai=self.h.ai, provider=self.h.provider, ledger=self.h.ledger)
        other.service.repository = self.h.repo
        with self.assertRaisesRegex(ValueError, 'REEVALUATION_LOOP_ALREADY_OWNED|REEVALUATION_RUNNING_STOP_FIRST'):
            other.service.attach_driver('PAPER_AUTOMATION', scope=SCOPE, requested_cadence_seconds=60)


if __name__ == '__main__':
    unittest.main()
