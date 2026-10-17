"""AUTO-01 — autonomous Paper operations: controller, schedule, AI gating, adapter, exits, recovery.

SOFTWARE_CONTROLLED. The production controller, reevaluation cycle, Action Decision
gate, Paper preview/risk/submit route, simulator, ledger, SQLite local state and the
experiment service are used. The clock, session answer, provider health, Screener
evidence, model, full-universe run tracker, completed-bar feed and the governed
Opportunity are controlled fixtures (``tests.support.paper_automation_harness``).
These tests prove software behaviour only; they are not live-session acceptance.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from market_platform_foundation.intelligence.inference.paper_automation import ARM_ACKNOWLEDGEMENT, required_fields
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.platform.security.route_policy import policy_for_route as policy_for
from market_platform_foundation.ui_api import paper_automation as controller_module
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from market_platform_foundation.xa01.compatibility import register_equity
from tests.intelligence.test_reevaluation import Clock
from tests.intelligence.test_sma_trailing_stop import series
from tests.support.paper_automation_harness import (
    Automation, ClockedFeed, FixtureRuns, PaidProvider, experiment, policy_body,
)
from tests.trading_correctness.test_paper_experiment_api import _Base, _OpenHandler

SRC = Path(__file__).resolve().parents[2] / 'src' / 'market_platform_foundation'


class TickingClock(Clock):
    """Every read is a millisecond later, as on a real machine."""

    def __call__(self):
        self.value += 0.001
        return self.value


class AutoBase(_Base):
    clock_type = Clock

    def setUp(self):
        super().setUp()
        register_equity(symbol='MSFT')
        self.clock = self.clock_type(time.time())
        self.feed.__class__ = ClockedFeed  # the patched Paper feed now stamps bars and marks from the controlled clock
        self.feed.clock = self.clock
        self.experiment = experiment(self.store)
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed)

    def restart(self, owner='process-b'):
        """A new process over the same state directory: nothing is carried in memory except the fixtures."""
        old = self.auto
        self.store = self.boot()
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, ai=old.ai, provider=old.provider, runs=old.runs, owner=owner)
        self.auto.store.strategy_repository = old.store.strategy_repository
        return self.auto

    def enter(self, instrument='AAPL', price=150, auto=None):
        """Drive the armed controller to one filled automatic entry."""
        a = auto or self.auto
        a.quote(instrument, price, 2)
        a.opportunity(instrument)
        if a.service.status()['status'] in ('NOT_CONFIGURED', 'DISARMED'):
            a.go()
        a.cycle()
        a.select(instrument)
        a.cycle()  # adopts the selection, decides ENTER, previews; the risk engine reduces the size
        a.cycle()  # previews once at the approved size and submits
        self.assertIsNotNone(a.position(instrument))
        return a.position(instrument)

    def automation_orders(self, auto=None):
        return [o for o in (auto or self.auto).orders() if str(o.get('client_order_id') or '').startswith('PAI-')]


class EndToEndTests(AutoBase):
    def test_unattended_selection_entry_hold_exit_and_accounting(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        started = a.go()
        self.assertEqual((started['status'], started['armed'], started['boundary']['execution']),
                         ('RUNNING', True, 'INTERNAL_PAPER_SIMULATION_ONLY'))
        first = a.cycle()
        # Nothing is evaluated from the first-50 intake: with no adopted full-universe selection there are no candidates.
        self.assertEqual((first['universe']['state'], first['reevaluation']['candidate_count'], first['actions']), ('STARTED', 0, []))
        self.assertEqual((a.ai.reductions, a.provider.calls, len(a.runs.started)), (0, 0, 1))
        self.assertEqual(a.runs.started[0]['origin'], 'AUTOMATION')
        a.select('AAPL')
        second = a.cycle()
        self.assertEqual(second['universe']['last_result']['adopted'], True)
        self.assertEqual(second['reevaluation']['candidate_source'], 'FULL_UNIVERSE_SELECTION')
        deferred = second['actions'][0]
        # The owner's bounds allow 33; the existing pre-trade risk engine allows 6. The smaller one stands.
        self.assertEqual((deferred['outcome'], deferred['sizing']['quantity'], deferred['quantity'], deferred['sizing']['binding']),
                         ('DEFERRED', 33, 6, 'PRETRADE_RISK_ENGINE'))
        self.assertEqual(self.automation_orders(), [])
        third = a.cycle()
        entry = third['actions'][0]
        self.assertEqual((entry['outcome'], entry['action'], entry['side'], entry['quantity'], entry['filled_quantity']),
                         ('SUBMITTED', 'ENTER', 'BUY', 6, 6))
        position = a.position('AAPL')
        self.assertEqual((position['quantity'], position['side']), (6, 'LONG'))
        order = self.automation_orders()[0]
        self.assertEqual(order['client_order_id'], entry['intent_id'])
        reasons = {r['code']: r['label'] for r in order['decision_source_snapshot']['reasons']}
        status = a.service.status()
        self.assertEqual(reasons['PAPER_AUTOMATION_POLICY'], status['policy']['policy_id'])
        self.assertEqual(reasons['PAPER_AUTOMATION_ARMING'], status['arming']['arming_id'])
        self.assertEqual(reasons['ACTION_DECISION'], entry['decision_id'])
        self.assertTrue(order['correlation_id'].startswith('opportunity:'))

        a.quote('AAPL', 151, 2)
        held = a.cycle(400)
        self.assertEqual((held['actions'], held['reevaluation']['position_count']), ([], 1))
        self.assertEqual(a.actions.history('AAPL')[0]['action_state'], 'HOLD')

        a.quote('AAPL', 153, -2)  # the model's thesis reverses; the gate turns that into EXIT
        closing = a.cycle(400)
        exit_ = closing['actions'][0]
        self.assertEqual((exit_['outcome'], exit_['action'], exit_['side'], exit_['quantity'], exit_['filled_quantity']),
                         ('SUBMITTED', 'EXIT', 'SELL', 6, 6))
        self.assertIsNone(a.position('AAPL'))

        again = a.cycle(400)
        self.assertEqual(again['actions'], [])
        self.assertEqual(len(self.automation_orders()), 2)  # one entry, one exit, never a second of either

        report = a.service.report()
        self.assertEqual((report['fills']['count'], report['fills']['opening'], report['fills']['closing']), (2, 1, 1))
        self.assertEqual(report['outcomes']['realized_pnl_minor'], 6 * 300 - report['fills']['costs_minor'])
        self.assertEqual(report['evidence_class'], 'SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH')
        self.assertIn('not evidence of a profitable', report['statement'])
        self.assertEqual(report['decisions']['by_origin'], dict(MODEL_PROPOSAL_GATED=2, DETERMINISTIC_RISK_CONTROL=0))
        self.assertEqual((report['ai']['universe_runs'], report['ai']['complete_runs']), (1, 1))
        kinds = [e['kind'] for e in a.events()]
        for kind in ('POLICY_CONFIGURED', 'ARMED', 'STARTED', 'SESSION_ACTIVATED', 'UNIVERSE_RUN_STARTED', 'UNIVERSE_RUN_FINISHED',
                     'PAPER_INTENT_DEFERRED', 'PAPER_INTENT_SUBMITTED'):
            self.assertIn(kind, kinds)
        self.assertEqual(a.service.status()['status'], 'RUNNING')

    def test_report_never_changes_policy_limits_or_method(self):
        self.enter()
        a = self.auto
        before = a.service.status()
        a.quote('AAPL', 190, -2)  # a large simulated gain
        a.cycle(400)
        a.service.report()
        after = a.service.status()
        self.assertEqual(after['policy'], before['policy'])
        self.assertEqual(after['arming'], before['arming'])
        self.assertEqual(a.reevaluation.repository.latest_loop(after['account_id'])['policy'],
                         a.reevaluation.repository.latest_loop(after['account_id'])['policy'])
        self.assertEqual(self.store.paper_ledger.policy['max_order_shares'], 100)


class ImmediateRepreviewTests(AutoBase):
    clock_type = TickingClock

    def test_risk_reduced_entry_is_previewed_again_and_submitted_in_the_same_cycle(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        outcome = a.cycle()['actions'][0]
        self.assertEqual((outcome['outcome'], outcome['quantity'], outcome['sizing']['pretrade_reduced_from']), ('SUBMITTED', 6, 33))
        self.assertEqual(a.position('AAPL')['quantity'], 6)


class PolicyAndArmingTests(AutoBase):
    def test_nothing_is_defaulted_and_the_owner_is_asked_once(self):
        a = self.auto
        status = a.service.status()
        self.assertEqual((status['status'], status['required_configuration']), ('NOT_CONFIGURED', required_fields()))
        with self.assertRaises(ValueError) as raised:
            a.service.configure(dict(scope=dict(universe='US_EQUITIES')))
        message = str(raised.exception)
        self.assertTrue(message.startswith('AUTOMATION_POLICY_INCOMPLETE:'))
        for field in required_fields()[1:]:
            self.assertIn(field, message)
        with self.assertRaises(ValueError):
            a.service.configure({})
        self.assertEqual(a.service.status()['status'], 'NOT_CONFIGURED')
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_NOT_CONFIGURED'):
            a.service.start(threaded=False)

    def test_configured_is_not_armed_and_arming_is_exact(self):
        a = self.auto
        configured = a.configure()
        self.assertEqual((configured['status'], configured['armed']), ('DISARMED', False))
        policy_id = configured['policy']['policy_id']
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_NOT_ARMED'):
            a.service.start(threaded=False)
        for bad in (dict(policy_id=policy_id), dict(policy_id=policy_id, acknowledgement='yes'),
                    dict(policy_id=policy_id, acknowledgement=ARM_ACKNOWLEDGEMENT, extra=1), None):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_ARM_ACKNOWLEDGEMENT_REQUIRED'):
                a.service.arm(bad)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_NOT_CURRENT'):
            a.service.arm(dict(policy_id='PAP-other', acknowledgement=ARM_ACKNOWLEDGEMENT))
        armed = a.arm()
        self.assertEqual((armed['status'], armed['arming']['scope'], armed['arming']['operator']),
                         ('STOPPED', 'INTERNAL_PAPER_SIMULATION_ONLY', 'test-owner'))
        self.assertEqual(self.automation_orders(), [])  # arming submits nothing and starts nothing
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_ALREADY_ARMED'):
            a.arm()
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_ARMED_DISARM_FIRST'):
            a.configure(risk=dict(max_open_positions=5))  # limits cannot move under a live authorization
        a.service.disarm()
        changed = a.configure(risk=dict(max_open_positions=5))
        self.assertNotEqual(changed['policy']['policy_id'], policy_id)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_NOT_CURRENT'):
            a.service.arm(dict(policy_id=policy_id, acknowledgement=ARM_ACKNOWLEDGEMENT))  # the old approval does not carry

    def test_policy_bounds_are_enforced_against_the_paper_account(self):
        a = self.auto
        for sections, code in (
                (dict(risk=dict(allow_short=True)), 'AUTOMATION_SHORT_NOT_PERMITTED_BY_PAPER_ACCOUNT'),
                (dict(risk=dict(max_aggregate_exposure_minor=20_000_000)), 'AUTOMATION_EXPOSURE_EXCEEDS_PAPER_CAPITAL'),
                (dict(risk=dict(max_position_notional_minor=2_000_000)), 'AUTOMATION_POSITION_EXCEEDS_AGGREGATE_EXPOSURE'),
                (dict(risk=dict(order_types=['LIMIT'])), 'AUTOMATION_ORDER_TYPE_UNSUPPORTED'),
                (dict(risk=dict(allowed_universes=['US_OPTIONS'])), 'AUTOMATION_INSTRUMENT_SCOPE_UNSUPPORTED'),
                (dict(schedule=dict(sessions=['PRE_MARKET'])), 'AUTOMATION_SESSION_UNSUPPORTED'),
                (dict(schedule=dict(cadence_seconds=5)), 'AUTOMATION_POLICY_FIELD_OUT_OF_RANGE'),
                (dict(ai=dict(allow_paid_inference=True)), 'AUTOMATION_PAID_SPENDING_LIMIT_REQUIRED'),
                (dict(ai=dict(max_paid_requests_per_day=5)), 'AUTOMATION_PAID_SPENDING_NOT_AUTHORIZED'),
                (dict(scope=dict(universe='US_EQUITIES', method='STAGED_LOCAL_FIRST_EXPERIMENTAL')), 'EXPERIMENTAL_METHOD_UNAPPROVED'),
        ):
            with self.assertRaisesRegex(ValueError, code):
                a.configure(**sections)
        self.assertEqual(a.service.status()['status'], 'NOT_CONFIGURED')

    def test_no_active_experiment_means_no_automation(self):
        from market_platform_foundation.ui_api import paper_experiment
        self.auto.configure()
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        with self.assertRaisesRegex(ValueError, 'ACTIVE_PAPER_EXPERIMENT_REQUIRED'):
            self.auto.arm()


class SessionAndProviderTests(AutoBase):
    def test_closed_market_waits_then_activates_at_the_open(self):
        a = self.auto
        a.session_label = 'CLOSED'
        a.quote('AAPL', 150, 2)
        self.assertEqual(a.go()['status'], 'WAITING_FOR_MARKET')
        waiting = a.cycle()
        self.assertEqual((waiting['status'], waiting['reevaluation'], waiting['universe']), ('WAITING_FOR_MARKET', None, None))
        self.assertEqual((a.ai.packets, a.provider.calls, a.runs.started), (0, 0, []))
        a.session_label = 'REGULAR'
        opened = a.cycle()
        self.assertEqual((opened['status'], opened['universe']['state']), ('RUNNING', 'STARTED'))
        activated = a.events('SESSION_ACTIVATED')
        self.assertEqual((len(activated), activated[0]['start_equity_minor']), (1, 10_000_000))
        a.session_label = 'AFTER_HOURS'
        closed = a.cycle()
        self.assertEqual((closed['status'], closed['reevaluation']), ('WAITING_FOR_MARKET', None))
        self.assertEqual(a.service.status()['status'], 'WAITING_FOR_MARKET')

    def test_positions_are_never_flattened_at_the_close(self):
        self.enter()
        a = self.auto
        a.session_label = 'CLOSED'
        a.cycle()
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertEqual(len(self.automation_orders()), 1)

    def test_provider_disconnect_blocks_and_orders_nothing(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        a.health = dict(state='UNHEALTHY', data_mode='LIVE_OBSERVATIONAL', reasons=['LIVE_FEED_UNHEALTHY'])
        calls = a.provider.calls
        down = a.cycle()
        self.assertEqual((down['status'], down['execution'], down['actions']), ('BLOCKED_BY_DATA', 'WITHHELD_PROVIDER_UNHEALTHY', []))
        self.assertIn(dict(category='DATA', code='LIVE_FEED_UNHEALTHY'), down['blockers'])
        self.assertEqual((a.provider.calls, self.automation_orders()), (calls, []))
        self.assertEqual(a.service.status()['status'], 'BLOCKED_BY_DATA')
        a.health = dict(state='CONNECTED', data_mode='LIVE_OBSERVATIONAL', reasons=[])
        self.assertEqual(a.cycle()['status'], 'RUNNING')

    def test_no_run_is_started_while_the_provider_is_down(self):
        a = self.auto
        a.health = dict(state='UNAVAILABLE', data_mode='LIVE_OBSERVATIONAL', reasons=['LIVE_RUNTIME_UNAVAILABLE'])
        a.go()
        cycle = a.cycle()
        self.assertEqual((cycle['status'], a.runs.started), ('BLOCKED_BY_DATA', []))
        self.assertEqual(cycle['universe']['withheld']['reason'], 'LIVE_RUNTIME_UNAVAILABLE')

    def test_missing_quote_is_never_an_entry(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.ai.no_quote.add('AAPL')  # entitlement refused or quote stale: the evidence reader blocks it
        a.go()
        a.cycle()
        a.select('AAPL')
        for _ in range(3):
            cycle = a.cycle()
            self.assertEqual(cycle['actions'], [])
        self.assertEqual(self.automation_orders(), [])
        self.assertNotEqual((a.actions.history('AAPL') or [dict(action_state=None)])[0]['action_state'], 'ENTER')

    def test_no_completed_bar_means_no_fabricated_fill(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        del self.feed.prices['AAPL']  # the Screener still shows a quote; the simulator has no bar to fill against
        for _ in range(3):
            a.cycle()
        self.assertIsNone(a.position('AAPL'))
        self.assertEqual(self.store.paper_ledger.project_fills(), [])
        self.assertEqual([o for o in a.orders() if o['state'] in ('WORKING', 'PARTIALLY_FILLED', 'ACTIVATED')], [])

    def test_evidence_read_failure_is_blocked_by_data(self):
        a = self.auto
        a.go()
        a.ai.fail = 'SCREENER_PROVIDER_UNAVAILABLE'
        cycle = a.cycle()
        self.assertEqual(cycle['status'], 'BLOCKED_BY_DATA')
        self.assertIn(dict(category='DATA', code='EVIDENCE_READ_FAILED'), cycle['blockers'])


class UniverseAndBudgetTests(AutoBase):
    def start_run(self, **sections):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go(**sections)
        a.cycle()
        return a

    def test_incomplete_coverage_is_reported_and_never_adopted(self):
        a = self.start_run()
        a.select('AAPL', status='PARTIAL_COVERAGE', coverage_complete=False, selection_complete=False, evaluated=50,
                 reason='AI_COVERAGE_STOPPED')
        cycle = a.cycle()
        result = cycle['universe']['last_result']
        self.assertEqual((result['adopted'], result['coverage_complete'], result['ai_evaluated_count'], result['universe_count']),
                         (False, False, 50, 7000))
        self.assertEqual((cycle['reevaluation']['candidate_count'], cycle['actions'], self.automation_orders()), (0, [], []))
        self.assertEqual(a.provider.calls, 0)  # the 50 evaluated rows are not treated as a selection
        finished = a.events('UNIVERSE_RUN_FINISHED')[0]
        self.assertEqual((finished['status'], finished['ai_coverage_pct'], finished['adopted']), ('PARTIAL_COVERAGE', 0.71, False))
        self.assertEqual(a.service.report()['ai']['incomplete_runs'], 1)

    def test_coverage_that_does_not_fit_the_budget_blocks_by_budget(self):
        a = self.start_run()
        a.select(status='AI_COVERAGE_BUDGET_INSUFFICIENT', coverage_complete=False, selection_complete=False, evaluated=0,
                 reason='AUTONOMOUS_SPENDING_LIMIT')
        cycle = a.cycle()
        self.assertEqual(cycle['status'], 'BLOCKED_BY_BUDGET')
        self.assertEqual(a.service.status()['status'], 'BLOCKED_BY_BUDGET')
        self.assertEqual(len(a.runs.started), 1)  # not retried every cycle

    def test_a_closed_session_does_not_hide_a_simultaneous_budget_blocker(self):
        # The primary status is one state, but an independent blocker must stay visible in the same payload.
        a = self.start_run()
        a.select(status='AI_COVERAGE_BUDGET_INSUFFICIENT', coverage_complete=False, selection_complete=False, evaluated=0,
                 reason='AUTONOMOUS_SPENDING_LIMIT')
        blocked = a.cycle()
        self.assertEqual(blocked['status'], 'BLOCKED_BY_BUDGET')
        a.session_label = 'CLOSED'
        waiting = a.cycle()
        self.assertEqual(waiting['status'], 'WAITING_FOR_MARKET')
        status = a.service.status()
        self.assertEqual(status['status'], 'WAITING_FOR_MARKET')          # the single primary state
        self.assertFalse(status['session_eligible'])
        self.assertIn(dict(category='BUDGET', code='AI_COVERAGE_BUDGET_INSUFFICIENT'), status['blockers'])
        self.assertIn(dict(category='BUDGET', code='AI_COVERAGE_BUDGET_INSUFFICIENT'), waiting['blockers'])
        # Carried, not invented: the entries come from the last evaluating cycle and say so.
        self.assertEqual(waiting['blockers_from_cycle_id'], blocked['cycle_id'])
        self.assertIsNotNone(waiting['blockers_observed_at'])
        for _ in range(2):
            self.assertIn(dict(category='BUDGET', code='AI_COVERAGE_BUDGET_INSUFFICIENT'), a.cycle()['blockers'])
        self.assertEqual(a.events('CYCLE')[-1].get('error'), None)  # no cycle in the closed session ran or failed

    def test_failed_and_lost_runs_are_recorded_not_adopted(self):
        a = self.start_run()
        a.runs.fail(a.service.status()['universe']['active_run_id'], 'MODEL_UNAVAILABLE')
        result = a.cycle()['universe']['last_result']
        self.assertEqual((result['status'], result['reason'], result['adopted']), ('FAILED', 'MODEL_UNAVAILABLE', False))
        self.assertEqual(self.automation_orders(), [])

    def test_a_complete_empty_selection_clears_candidates(self):
        self.enter()
        a = self.auto
        a.quote('AAPL', 151, 2)
        a.cycle(1800)  # the next full-universe evaluation is due
        self.assertEqual(len(a.runs.started), 2)
        a.select()  # complete coverage, nothing selected
        cycle = a.cycle()
        self.assertEqual(cycle['universe']['last_result']['adopted'], True)
        self.assertEqual((cycle['reevaluation']['candidate_count'], cycle['reevaluation']['position_count']), (0, 1))
        self.assertEqual(a.position('AAPL')['quantity'], 6)  # the held position stays monitored, off the selection

    def test_universe_runs_follow_the_owner_interval(self):
        a = self.start_run()
        a.select('AAPL')
        for _ in range(5):
            a.cycle()
        self.assertEqual(len(a.runs.started), 1)
        a.cycle(1800)
        self.assertEqual(len(a.runs.started), 2)

    def test_paid_inference_needs_the_owners_spending_authorization(self):
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, provider=PaidProvider())
        a = self.start_run()  # the fixture policy authorizes local inference only
        cycle = a.cycle()
        self.assertEqual(cycle['status'], 'BLOCKED_BY_BUDGET')
        self.assertIn(dict(category='BUDGET', code='AUTONOMOUS_SPENDING_NOT_AUTHORIZED'), cycle['blockers'])
        self.assertEqual((a.provider.calls, a.runs.started), (0, []))
        self.assertEqual(cycle['universe']['withheld']['reason'], 'AUTONOMOUS_SPENDING_NOT_AUTHORIZED')
        self.assertEqual(a.service.status()['spending'], dict(allowed=False, reason='AUTONOMOUS_SPENDING_NOT_AUTHORIZED'))

    def test_authorized_paid_run_is_capped_by_the_tighter_of_owner_and_shared_budget(self):
        provider = PaidProvider(requests=4, tokens=20_000)
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, provider=provider)
        a = self.start_run(ai=dict(allow_paid_inference=True, max_paid_requests_per_day=10, max_paid_tokens_per_day=500_000))
        self.assertEqual(a.runs.started[0]['spend_limit'], dict(requests=6, tokens=180_000))
        provider.budget.update(requests=10)  # the owner's request cap is reached before the shared one
        a.select('AAPL')
        cycle = a.cycle()
        self.assertIn(dict(category='BUDGET', code='AUTONOMOUS_SPENDING_LIMIT_REACHED'), cycle['blockers'])
        self.assertEqual((cycle['status'], provider.calls), ('BLOCKED_BY_BUDGET', 0))
        self.assertEqual(self.automation_orders(), [])

    def test_local_inference_also_needs_authorization(self):
        a = self.start_run(ai=dict(allow_local_inference=False))
        self.assertEqual(a.runs.started, [])
        self.assertIn(dict(category='BUDGET', code='AUTONOMOUS_LOCAL_INFERENCE_NOT_AUTHORIZED'), a.cycle()['blockers'])

    def test_model_failure_orders_nothing_and_repeated_failure_latches_the_emergency_stop(self):
        a = self.start_run()
        a.select('AAPL')

        def broken():
            raise RuntimeError('model process died')
        a.provider.hook = broken
        failed = a.cycle()
        self.assertEqual((failed['reevaluation']['cycle_status'], failed['actions'], failed['status']), ('FAILED', [], 'BLOCKED_BY_DATA'))
        self.assertEqual(self.automation_orders(), [])
        a.provider.hook = None
        a.reevaluation.driven_cycle = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('cycle crashed'))
        statuses = [a.cycle()['status'] for _ in range(3)]
        self.assertEqual(statuses, ['ERROR', 'ERROR', 'EMERGENCY_STOPPED'])
        status = a.service.status()
        self.assertEqual((status['status'], status['emergency']['source'], status['emergency']['reason']),
                         ('EMERGENCY_STOPPED', 'CONTROLLER', 'CONSECUTIVE_CYCLE_FAILURES'))
        self.assertEqual(a.cycle().get('skipped'), 'NOT_RUNNING')


class RiskTests(AutoBase):
    def two_candidates(self, **sections):
        a = self.auto
        for instrument, price in (('AAPL', 150), ('NVDA', 120)):
            a.quote(instrument, price, 2)
            a.opportunity(instrument)
        a.go(**sections)
        a.cycle()
        a.select('AAPL', 'NVDA')
        outcomes = []
        for seconds in (60, 60, 60, 400, 60, 60):
            for instrument in ('AAPL', 'NVDA'):
                if a.position(instrument):
                    a.quote(instrument, self.feed.prices[instrument], 2)
            outcomes.extend(a.cycle(seconds)['actions'])
        return a, outcomes

    def test_max_open_positions_stops_the_second_entry(self):
        a, outcomes = self.two_candidates(risk=dict(max_open_positions=1))
        self.assertEqual(sum(1 for p in (a.position('AAPL'), a.position('NVDA')) if p), 1)
        blocked = [o for o in outcomes if o['outcome'] == 'BLOCKED']
        self.assertTrue(blocked)
        self.assertIn('MAX_OPEN_POSITIONS_REACHED', blocked[0]['reason_codes'])

    def test_second_entry_is_decided_again_after_the_first_changed_the_account(self):
        a, outcomes = self.two_candidates()
        self.assertEqual((a.position('AAPL')['quantity'], a.position('NVDA')['quantity']), (6, 8))
        nvda = [(o['outcome'], o['reason_codes'][0]) for o in outcomes if o['instrument_id'] == 'NVDA']
        # Not ordered against an unmarked book, not ordered from a decision made before AAPL was bought.
        self.assertIn(('BLOCKED', 'PORTFOLIO_VALUATION_NOT_CURRENT'), nvda)
        self.assertIn(('DEFERRED', 'ACTION_INPUT_CHANGED'), nvda)
        self.assertEqual(len([d for d in a.actions.history('NVDA') if d['action_state'] == 'ENTER']), 2)
        self.assertEqual(len(self.automation_orders()), 2)
        risk = a.service.status()['risk']
        self.assertEqual((risk['open_positions'], risk['exposure_minor']), (2, 6 * 15000 + 8 * 12000))

    def test_an_unmarked_holding_blocks_new_entries(self):
        a = self.auto
        self.enter()
        a.quote('NVDA', 120, 2)
        a.opportunity('NVDA')
        self.store.paper_ledger.clear_mark('AAPL')
        a.cycle(1800)
        a.select('AAPL', 'NVDA')
        outcomes = [o for _ in range(3) for o in a.cycle()['actions']]
        self.assertIsNone(a.position('NVDA'))
        self.assertTrue(any('PORTFOLIO_VALUATION_NOT_CURRENT' in o['reason_codes'] for o in outcomes))

    def test_daily_loss_limit_halts_entries_and_shows_blocked_by_risk(self):
        a = self.auto
        self.enter()
        a.quote('NVDA', 120, 2)
        a.opportunity('NVDA')
        a.quote('AAPL', 150, 2)
        a.cycle(1800)
        a.select('AAPL', 'NVDA')
        self.feed.mark(self.store, 'AAPL', '149.00')  # a $6.00 mark-to-market loss against a $5.00 fixture limit
        policy = a.service.status()['policy']
        self.assertEqual(policy['risk']['max_daily_loss_minor'], 100_000)
        a.service.disarm()
        a.configure(risk=dict(max_daily_loss_minor=500))
        a.arm()
        a.service.start(threaded=False)
        outcomes, statuses = [], []
        for _ in range(3):
            self.feed.mark(self.store, 'AAPL', '149.00')
            cycle = a.cycle()
            outcomes.extend(cycle['actions'])
            statuses.append(cycle['status'])
        self.assertIsNone(a.position('NVDA'))
        self.assertIn('BLOCKED_BY_RISK', statuses)
        self.assertEqual(a.position('AAPL')['quantity'], 6)  # a loss limit halts entries; it is not a liquidation order

    def test_entry_window_and_entry_switch(self):
        a = self.auto
        a.minutes_to_close = 10
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        outcomes = [o for _ in range(2) for o in a.cycle()['actions']]
        self.assertEqual(outcomes[0]['outcome'], 'BLOCKED')
        self.assertIn('ENTRY_WINDOW_CLOSED', outcomes[0]['reason_codes'])
        self.assertEqual(len(outcomes), 1)  # the same refusal is recorded once, not every cycle
        self.assertEqual(self.automation_orders(), [])

    def test_entries_disabled_still_allows_exits(self):
        self.enter()
        a = self.auto
        a.service.disarm()
        a.configure(risk=dict(allow_entries=False))
        a.arm()
        a.service.start(threaded=False)
        a.quote('AAPL', 152, -2)
        outcomes = [o for _ in range(2) for o in a.cycle(400)['actions']]
        self.assertEqual([(o['action'], o['outcome']) for o in outcomes], [('EXIT', 'SUBMITTED')])
        self.assertIsNone(a.position('AAPL'))

    def test_thesis_exit_can_be_withheld_by_the_owner(self):
        self.enter()
        a = self.auto
        a.service.disarm()
        a.configure(exits=dict(on_thesis_exit=False))
        a.arm()
        a.service.start(threaded=False)
        a.quote('AAPL', 152, -2)
        outcomes = [o for _ in range(2) for o in a.cycle(400)['actions']]
        self.assertEqual([(o['action'], o['outcome'], o['reason_codes']) for o in outcomes],
                         [('EXIT', 'BLOCKED', ['AUTOMATION_THESIS_EXIT_DISABLED'])])
        self.assertEqual(a.position('AAPL')['quantity'], 6)

    def test_no_governed_opportunity_means_no_entry(self):
        a = self.auto
        a.quote('AAPL', 150, 2)  # the model will propose ENTER, but nothing governed admits it
        a.go()
        a.cycle()
        a.select('AAPL')
        outcomes = [o for _ in range(3) for o in a.cycle()['actions']]
        self.assertEqual(self.automation_orders(), [])
        decision = a.actions.history('AAPL')[0]
        self.assertIn('NO_GOVERNED_OPPORTUNITY', decision['blocker_codes'])
        self.assertTrue(all(o['outcome'] == 'BLOCKED' for o in outcomes))


class ExitTests(AutoBase):
    def with_stop(self):
        """A LONG 6 @150 with an active 140.00 SMA trailing stop from controlled completed bars."""
        self.enter()
        a = self.auto
        self.closes = [14000, 14000]
        a.stops = SmaStopService(
            self.store, repository=SmaStopRepository(), clock=self.clock, actions=a.actions, ai=a.ai,
            bars=lambda instrument, policy, scale: dict(state='CURRENT', reason=None, source='CONTROLLED_FIXTURE', bars=series(self.closes)),
            quotes=lambda instrument, scale: dict(admissible=True, price_minor=int(round(a.ai.rows[instrument]['price'] * 100)),
                                                  as_of_ns=int(self.clock() * 1e9), source='CONTROLLED_FIXTURE', evidence_ref='q', reason=None))
        a.actions.risk_control = a.stops
        a.stops.configure(dict(enabled=True, sma_window_bars=2))
        a.quote('AAPL', 150, 2)
        a.cycle(400)
        self.assertEqual(a.stops.decision_facts('AAPL')['status'], 'ACTIVE')
        return a

    def test_stop_breach_is_closed_automatically_without_a_model_call(self):
        a = self.with_stop()
        calls = a.provider.calls
        a.quote('AAPL', 139, 2)  # through the 140.00 stop while the model would still say HOLD
        cycle = a.cycle()
        exit_ = cycle['actions'][0]
        self.assertEqual((exit_['action'], exit_['outcome'], exit_['side'], exit_['quantity'], exit_['filled_quantity']),
                         ('EXIT', 'SUBMITTED', 'SELL', 6, 6))
        self.assertEqual(a.provider.calls, calls)
        self.assertIsNone(a.position('AAPL'))
        decision = a.actions.history('AAPL')[0]
        self.assertEqual(decision['server_exit']['reason'], 'DETERMINISTIC_SMA_TRAILING_STOP_RISK_CONDITION')
        # The fill is the simulator's, at the bar it observed. The stop level is not a guaranteed price.
        self.assertEqual(exit_['fill_price_minor'], 13900)
        self.assertEqual(a.service.report()['decisions']['by_origin']['DETERMINISTIC_RISK_CONTROL'], 1)
        self.assertEqual(a.cycle()['actions'], [])
        self.assertEqual(len(self.automation_orders()), 2)

    def test_stop_exit_can_be_withheld_and_is_then_recorded_not_executed(self):
        a = self.with_stop()
        a.service.disarm()
        a.configure(exits=dict(on_stop_breach=False))
        a.arm()
        a.service.start(threaded=False)
        a.quote('AAPL', 139, 2)
        outcomes = [o for _ in range(2) for o in a.cycle()['actions']]
        self.assertEqual([(o['outcome'], o['reason_codes']) for o in outcomes], [('BLOCKED', ['AUTOMATION_STOP_EXIT_DISABLED'])])
        self.assertEqual(a.position('AAPL')['quantity'], 6)

    def test_breach_without_a_bar_defers_instead_of_inventing_a_price(self):
        a = self.with_stop()
        a.quote('AAPL', 139, 2)
        del self.feed.prices['AAPL']
        first = a.cycle()['actions'][0]
        # The order reached the simulator, which had no bar after the signal and filled nothing.
        self.assertEqual((first['action'], first['order_state'], first['filled_quantity'], first['fill_price_minor']),
                         ('EXIT', 'REJECTED', 0, None))
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertEqual(len(self.store.paper_ledger.project_fills()), 1)  # only the entry fill exists
        self.feed.prices['AAPL'] = '138.50'
        a.ai.rows['AAPL']['price'] = 138.5
        seen = []
        for _ in range(4):
            seen.extend(a.cycle()['actions'])
            if a.position('AAPL') is None:
                break
        self.assertIsNone(a.position('AAPL'))
        self.assertEqual(self.store.paper_ledger.project_fills()[-1]['fill_price_minor'], 13850)
        # The first decision was never ordered twice: a new EXIT decision was made and got its own single order.
        self.assertEqual([(o['action'], o['outcome'], o['filled_quantity']) for o in seen], [('EXIT', 'SUBMITTED', 6)])
        self.assertNotEqual(seen[0]['decision_id'], first['decision_id'])
        self.assertEqual(len({o['client_order_id'] for o in self.automation_orders()}), 3)

    def test_repeated_unfilled_exits_back_off(self):
        a = self.with_stop()
        a.quote('AAPL', 139, 2)
        del self.feed.prices['AAPL']
        orders = []
        for _ in range(8):
            a.cycle()
            orders.append(len(self.automation_orders()))
        # One entry, then exit orders at +0s, +60s, +180s and +420s instead of one rejected order every cycle.
        self.assertEqual(orders, [2, 3, 3, 4, 4, 4, 4, 5])
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertIn('EXIT_ORDER_BACKOFF', [code for i in a.service.status()['recent_intents'] for code in i['reason_codes']]
                      + [e['reason_codes'][0] for e in a.events('PAPER_INTENT_DEFERRED')])

    def test_partial_fill_cancels_the_remainder_and_the_exit_closes_what_is_held(self):
        a = self.auto
        self.feed.volume = 400  # a thin bar: the 1% participation cap fills four of six
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        outcomes = [o for _ in range(2) for o in a.cycle()['actions']]
        submitted = [o for o in outcomes if o['outcome'] == 'SUBMITTED'][0]
        position = a.position('AAPL')
        self.assertEqual((position['quantity'], submitted['filled_quantity'], submitted['order_state']), (4, 4, 'PARTIALLY_FILLED'))
        self.assertEqual([o for o in a.orders() if o['state'] in ('WORKING', 'PARTIALLY_FILLED')], [])
        self.assertEqual(len(a.events('PAPER_ORDER_REMAINDER_CANCELLED')), 1)
        self.assertEqual(len(self.automation_orders()), 1)  # the unfilled two are not chased with a second entry order
        self.feed.volume = 1_000_000
        a.quote('AAPL', 152, -2)
        closing = [o for _ in range(2) for o in a.cycle(400)['actions']]
        self.assertEqual((closing[0]['action'], closing[0]['quantity'], closing[0]['filled_quantity']), ('EXIT', 4, 4))
        self.assertIsNone(a.position('AAPL'))


class ControlTests(AutoBase):
    def test_pause_resume_and_stop(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        self.assertEqual(a.service.pause()['status'], 'PAUSED')
        paused = a.cycle()
        self.assertEqual((paused.get('skipped'), a.provider.calls, self.automation_orders()), ('NOT_RUNNING', 0, []))
        self.assertEqual(a.service.resume()['status'], 'RUNNING')
        a.cycle()
        a.cycle()
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        stopped = a.service.stop()
        self.assertEqual((stopped['status'], stopped['armed'], stopped['liveness']['owner']), ('STOPPED', True, None))
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_LEASE_LOST'):
            a.cycle()
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertEqual(a.reevaluation.status()['driver'], None)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_NOT_RUNNING_START_FIRST'):
            a.service.resume()
        self.assertEqual(a.service.start(threaded=False)['status'], 'RUNNING')

    def test_pause_between_decision_and_order_stops_the_order(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        original = a.reevaluation.driven_cycle

        def decide_then_pause(*args, **kwargs):
            receipt = original(*args, **kwargs)
            a.service.pause()  # the operator presses Pause while the cycle is still running
            return receipt
        a.reevaluation.driven_cycle = decide_then_pause
        cycle = a.cycle()
        self.assertEqual([(o['outcome'], o['reason_codes']) for o in cycle['actions']], [('NOT_ATTEMPTED', ['AUTOMATION_HALTED_BY_OPERATOR'])])
        self.assertEqual((self.automation_orders(), a.service.status()['status']), ([], 'PAUSED'))

    def test_a_cycle_in_flight_never_orders_under_a_later_arming(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        a.cycle()
        a.select('AAPL')
        original = a.reevaluation.driven_cycle
        first_run = a.service.status()['run']['run_id']

        def decide_then_rearm(*args, **kwargs):
            receipt = original(*args, **kwargs)
            a.reevaluation.driven_cycle = original
            a.service.disarm()  # while this cycle is still running the owner disarms,
            a.configure(risk=dict(max_open_positions=1))  # stores a different policy,
            a.arm()  # arms it,
            a.service.start(threaded=False)  # and starts a new run
            return receipt
        a.reevaluation.driven_cycle = decide_then_rearm
        cycle = a.cycle()
        # Disarm released the loop and its selection, so the old cycle finds nothing to execute; had it found
        # something, the run and arming comparison made before every order would have refused it.
        self.assertEqual((cycle['actions'], cycle['run_id'], cycle.get('superseded')), ([], first_run, True))
        self.assertFalse(a.service._still_permitted(dict(run=dict(run_id=first_run), arming=dict(arming_id='PAA-old'))))
        self.assertEqual(self.automation_orders(), [])
        status = a.service.status()
        self.assertNotEqual(status['run']['run_id'], first_run)
        self.assertNotEqual((status['last_cycle'] or {}).get('cycle_id'), cycle['cycle_id'])  # not written over the new run
        self.assertEqual(status['policy']['risk']['max_open_positions'], 1)

    def test_an_operator_stop_during_a_cycle_is_not_overwritten_by_that_cycle(self):
        a = self.auto
        a.go()
        original = a.reevaluation.driven_cycle

        def stop_mid_cycle(*args, **kwargs):
            receipt = original(*args, **kwargs)
            a.service.stop()
            return receipt
        a.reevaluation.driven_cycle = stop_mid_cycle
        a.cycle()
        status = a.service.status()
        self.assertEqual((status['status'], status['desired_state'], status['liveness']['owner']), ('STOPPED', 'STOPPED', None))

    def test_a_stopped_cycle_never_writes_its_own_state_back(self):
        # Regression: a cycle that an operator stopped while it ran must not keep recording cycle-owned state
        # afterwards (in particular candidate quote subscriptions it may already have released, and its
        # last_cycle / cycle_count), because it no longer holds the lease or the running state.
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        first = a.cycle()
        account = self.store.paper_ledger.paper_account_id
        before = a.service.repository.get_controller(account)
        self.assertEqual(before['last_cycle']['cycle_id'], first['cycle_id'])
        original = a.reevaluation.driven_cycle

        def stop_mid_cycle(*args, **kwargs):
            receipt = original(*args, **kwargs)
            a.service.stop()
            return receipt
        a.reevaluation.driven_cycle = stop_mid_cycle
        stopped = a.cycle(400)
        after = a.service.repository.get_controller(account)
        self.assertEqual(after['desired_state'], 'STOPPED')
        self.assertEqual(after['subscriptions'], [])
        self.assertEqual(after['cycle_count'], before['cycle_count'])
        self.assertEqual(after['last_cycle']['cycle_id'], first['cycle_id'])  # the stopped cycle did not overwrite it
        self.assertNotEqual(after['last_cycle']['cycle_id'], stopped['cycle_id'])
        self.assertTrue(stopped.get('superseded'))

    def test_the_control_re_read_runs_inside_the_submit_lock(self):
        # Regression: Stop-versus-submit. The guard that reads Pause/Stop/Emergency/Disarm/arming/run/lease must
        # be evaluated while the submission lock is held, so a control change cannot land between the guard and
        # the order. The pre-order guard in the adapter also runs outside the lock; only the last one (the one
        # immediately before submit) is required to be inside it.
        a = self.auto

        def held():
            """Whether this thread holds the submission lock (RLock reports ownership; a plain Lock reports held)."""
            lock = a.service.submit_lock()
            owner_check = getattr(lock, '_is_owned', None)
            return bool(owner_check()) if owner_check is not None else lock.locked()

        original = a.service._still_permitted
        locked = []

        def guard(work):
            value = original(work)
            locked.append(held())
            return value
        a.service._still_permitted = guard
        self.enter()  # a full automatic entry: adopt the selection, decide ENTER, preview, submit
        self.assertTrue(locked, 'the control re-read must run before the order')
        self.assertTrue(locked[-1], 'the guard immediately before submit must run inside the submit lock')

    def test_emergency_stop_latches_cancels_and_never_liquidates(self):
        self.enter()
        a = self.auto
        ledger_events = len(self.store.paper_ledger.events)
        stopped = a.service.emergency_stop(dict(reason='operator saw something wrong'))
        self.assertEqual((stopped['status'], stopped['emergency']['source'], stopped['cancelled_orders']), ('EMERGENCY_STOPPED', 'OPERATOR', 0))
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertEqual(len(self.store.paper_ledger.events), ledger_events)  # nothing was sold, nothing was rewritten
        for action in (lambda: a.service.start(threaded=False), a.arm, a.service.resume):
            with self.assertRaises(ValueError):
                action()
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_LEASE_LOST'):
            a.cycle()
        self.clock.value += 600
        self.assertEqual(self.restart().service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_RUNNING_BEFORE_RESTART'))
        self.assertEqual(self.auto.service.status()['status'], 'EMERGENCY_STOPPED')  # the latch survives a restart
        cleared = self.auto.service.disarm()
        self.assertEqual((cleared['status'], cleared['armed'], cleared['emergency']), ('DISARMED', False, None))

    def test_emergency_stop_cancels_a_working_automation_order_but_not_the_operators(self):
        a = self.auto
        a.go()
        self.feed.volume = 100  # one share per bar: a three-share order stays working after its partial fill
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order, submit_paper_order
        for key, instrument in (('PAI-' + 'a' * 40, 'AAPL'), ('operator-order-1', 'NVDA')):
            self.feed.prices[instrument] = '100.00'
            order = dict(instrument_id=instrument, side='BUY', quantity=3, order_type='MARKET', client_order_id=key, idempotency_key=key)
            preview = preview_paper_order(self.store, order)['preview']
            submit_paper_order(self.store, dict(order, preview_id=preview['preview_id']))
        working = {o['client_order_id'] for o in a.orders() if o['state'] in controller_module._WORKING}
        self.assertEqual(working, {'PAI-' + 'a' * 40, 'operator-order-1'})
        stopped = a.service.emergency_stop()
        self.assertEqual(stopped['cancelled_orders'], 1)
        states = {o['client_order_id']: o['state'] for o in a.orders()}
        self.assertEqual(states['PAI-' + 'a' * 40], 'CANCELLED')
        self.assertIn(states['operator-order-1'], controller_module._WORKING)
        self.assertEqual(a.position('AAPL')['quantity'], 1)  # the filled share stays; nothing is liquidated

    def test_disarm_stops_everything_and_keeps_the_records(self):
        self.enter()
        a = self.auto
        events = len(a.events())
        ledger_events = len(self.store.paper_ledger.events)
        disarmed = a.service.disarm()
        self.assertEqual((disarmed['status'], disarmed['armed']), ('DISARMED', False))
        self.assertEqual(len(self.store.paper_ledger.events), ledger_events)
        self.assertGreater(len(a.events()), events)
        self.assertEqual(a.position('AAPL')['quantity'], 6)
        self.assertEqual(len(a.service.status()['recent_intents']), 1)


class OwnershipAndRecoveryTests(AutoBase):
    def test_a_failing_generation_cannot_latch_or_report_over_the_generation_that_replaced_it(self):
        # DISARM -> CONFIGURE -> RE-ARM -> START while a failing cycle is still finishing must not let the old
        # generation stop, arm, disarm, renew or report over the new one -- and its own abandoned latch must be
        # recorded rather than silently dropped.
        a = self.auto
        a.go()
        a.reevaluation.driven_cycle = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('cycle crashed'))
        a.cycle()  # failure 1 of the old generation
        a.cycle()  # failure 2 of the old generation
        old_run = a.service.status()['run']['run_id']

        def crash_then_rearm(*args, **kwargs):
            a.service.disarm()
            a.configure(risk=dict(max_open_positions=1))  # a different policy, a different authorization
            a.arm()
            a.service.start(threaded=False)
            raise RuntimeError('cycle crashed')  # failure 3: the old generation's own latch would trip here
        a.reevaluation.driven_cycle = crash_then_rearm
        cycle = a.cycle()
        self.assertTrue(cycle.get('superseded'))
        status = a.service.status()
        # The new generation is untouched: running, unlatched, its own failure count zero, its own policy in force.
        self.assertEqual((status['status'], status['emergency'], status['desired_state']), ('RUNNING', None, 'RUNNING'))
        self.assertNotEqual(status['run']['run_id'], old_run)
        self.assertEqual(status['liveness']['consecutive_failures'], 0)
        self.assertEqual(status['policy']['risk']['max_open_positions'], 1)
        self.assertIsNone(status['liveness']['last_error'])
        # The abandoned latch is recorded, with its cause and the generation that superseded it.
        latch = a.events('EMERGENCY_LATCH_SUPERSEDED')[0]
        self.assertEqual((latch['reason'], latch['consecutive_failures'], latch['superseded_by_generation']['run_id']),
                         ('CONSECUTIVE_CYCLE_FAILURES', 3, status['run']['run_id']))
        self.assertEqual((latch['run_id'], cycle['run_id']), (old_run, old_run))
        self.assertEqual(self.automation_orders(), [])
        self.assertEqual(a.service.status()['status'], 'RUNNING')

    def test_a_failing_generation_still_latches_its_own_generation(self):
        # The same failures without a replacement must still latch: generation ownership must not weaken the
        # controller's own consecutive-failure stop.
        a = self.auto
        a.go()
        a.reevaluation.driven_cycle = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('cycle crashed'))
        statuses = [a.cycle()['status'] for _ in range(3)]
        self.assertEqual(statuses, ['ERROR', 'ERROR', 'EMERGENCY_STOPPED'])
        status = a.service.status()
        self.assertEqual((status['status'], status['emergency']['source']), ('EMERGENCY_STOPPED', 'CONTROLLER'))
        self.assertEqual(a.events('EMERGENCY_LATCH_SUPERSEDED'), [])

    def test_a_second_instance_cannot_run_the_same_account(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        other = Automation(self.store, clock=self.clock, feed=self.feed, ai=a.ai, provider=a.provider, runs=a.runs, owner='process-b')
        self.store._action_decision_service = a.actions
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_ALREADY_OWNED'):
            other.service.start(threaded=False)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_LEASE_LOST'):
            other.service.run_cycle()
        elsewhere = other.service.status()
        self.assertEqual((elsewhere['status'], elsewhere['liveness']['owner']), ('ERROR', 'OTHER_PROCESS'))
        self.assertIn(dict(category='AUTHORITY', code='RUNNING_ELSEWHERE'), elsewhere['blockers'])
        self.assertEqual(a.cycle()['status'], 'RUNNING')

    def test_a_cycle_never_overlaps_itself(self):
        a = self.auto
        a.go()
        seen = []
        original = a.reevaluation.driven_cycle

        def reentrant(*args, **kwargs):
            try:
                a.service.run_cycle()
            except ValueError as exc:
                seen.append(str(exc))
            return original(*args, **kwargs)
        a.reevaluation.driven_cycle = reentrant
        a.cycle()
        self.assertEqual(seen, ['AUTOMATION_CYCLE_IN_PROGRESS'])

    def test_restart_resumes_only_what_was_armed_and_running_and_backfills_nothing(self):
        self.enter()
        before = dict(orders=len(self.auto.orders()), fills=len(self.store.paper_ledger.project_fills()),
                      decisions=len(self.auto.actions.history('AAPL')), calls=self.auto.provider.calls)
        authorization = self.auto.service.status()['arming']
        self.clock.value += 1500  # the process is down for 25 minutes; its lease expires
        b = self.restart()
        crashed = b.service.status()
        self.assertEqual((crashed['status'], crashed['desired_state']), ('ERROR', 'RUNNING'))  # wanted running, nothing is: not RUNNING
        self.assertIn(dict(category='AUTHORITY', code='CONTROLLER_NOT_ALIVE'), crashed['blockers'])
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=True, reason=None))
        gap = b.events('NOT_OBSERVED')[0]
        self.assertEqual((gap['reason'], gap['missed_scheduled_cycles'], gap['evaluations_backfilled'], gap['orders_backfilled']),
                         ('PROCESS_DOWNTIME', 25, 0, 0))
        after = dict(orders=len(b.orders()), fills=len(self.store.paper_ledger.project_fills()),
                     decisions=len(b.actions.history('AAPL')), calls=b.provider.calls)
        self.assertEqual(after, before)
        status = b.service.status()
        self.assertEqual((status['status'], status['arming'], status['liveness']['owner']), ('RUNNING', authorization, 'THIS_PROCESS'))
        self.assertEqual(b.position('AAPL')['quantity'], 6)
        self.assertEqual(status['day']['start_equity_minor'], 10_000_000)  # the day's reference survives the restart
        b.quote('AAPL', 151, 2)
        self.assertEqual(b.cycle()['status'], 'RUNNING')
        self.assertEqual(len(self.automation_orders(b)), 1)

    def test_a_restart_inside_the_predecessor_lease_waits_it_out_and_resumes(self):
        self.enter()
        self.clock.value += 30  # an operator restart: the old process is gone, its lease still has ~150 s
        b = self.restart()
        waited = []

        def sleep(seconds):
            waited.append(seconds)
            self.clock.value += seconds
        b.service.sleep = sleep
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=True, reason=None))
        self.assertEqual(len(waited), 1)
        self.assertLessEqual(waited[0], 180 + 5)
        self.assertEqual(b.events('STARTUP_RESUME_WAITING_FOR_LEASE')[0]['wait_seconds'], round(waited[0], 3))
        self.assertTrue(b.events('STARTUP_RESUMED')[0]['after_lease_wait'])
        self.assertEqual((b.service.status()['status'], b.service.status()['liveness']['owner']), ('RUNNING', 'THIS_PROCESS'))

    def test_a_predecessor_that_keeps_renewing_still_wins_after_the_wait(self):
        self.enter()
        b = self.restart()
        account = b.service._account()

        def sleep(seconds):
            self.clock.value += seconds
            # The old process is alive and renews its lease while the new one waits.
            b.service.repository.heartbeat(account, 'process-a', now=self.clock.value, lease_seconds=180)
        b.service.sleep = sleep
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=False, reason='AUTOMATION_ALREADY_OWNED'))
        self.assertEqual(b.events('STARTUP_RESUME_REFUSED')[0]['reason'], 'AUTOMATION_ALREADY_OWNED')

    def test_a_controller_stopped_during_the_wait_is_not_resumed(self):
        self.enter()
        b = self.restart()

        def sleep(seconds):
            b.service.stop()  # the operator stops automation while the new process waits
            self.clock.value += seconds
        b.service.sleep = sleep
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_RUNNING_BEFORE_RESTART'))
        self.assertNotEqual(b.service.status()['status'], 'RUNNING')

    def test_restart_does_not_resume_a_stopped_paused_or_disarmed_controller(self):
        a = self.auto
        a.go()
        a.service.pause()
        self.clock.value += 600
        self.assertEqual(self.restart('p2').service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_RUNNING_BEFORE_RESTART'))
        self.auto.service.stop()
        self.assertEqual(self.restart('p3').service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_RUNNING_BEFORE_RESTART'))
        self.auto.service.disarm()
        self.assertEqual(self.restart('p4').service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_ARMED'))
        self.assertEqual(self.auto.runs.started, [])

    def test_restart_refuses_when_a_safety_condition_changed(self):
        self.enter()
        self.clock.value += 600
        for key, code in (('IMP_BROKER_PAPER_EXECUTION', 'BROKER_PAPER_ENVIRONMENT_ENABLED'), ('IMP_LIVE_EXECUTION', 'LIVE_EXECUTION_ENVIRONMENT_ENABLED')):
            os.environ[key] = '1'
            try:
                b = self.restart('after-' + key)
                result = b.service.resume_on_startup(threaded=False)
            finally:
                os.environ.pop(key, None)
            self.assertEqual(result, dict(resumed=False, reason=code))
            self.assertEqual(b.events('STARTUP_RESUME_REFUSED')[0]['reason'], code)
            self.assertNotEqual(b.service.status()['status'], 'RUNNING')
            self.assertEqual(len(self.automation_orders(b)), 1)

    def test_restart_refuses_when_the_paper_risk_policy_changed(self):
        self.enter()
        self.clock.value += 600
        b = self.restart()
        self.store.paper_ledger.policy['risk_policy_identity_hash'] = 'changed-since-arming'
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=False, reason='PAPER_RISK_POLICY_CHANGED'))
        self.assertNotEqual(b.service.status()['status'], 'RUNNING')

    def test_an_order_is_never_repeated_for_the_same_decision(self):
        self.enter()
        a = self.auto
        decision = next(d for d in a.actions.history('AAPL') if d['action_state'] == 'ENTER')
        status = a.service.status()
        work = dict(a.service._controller())
        self.assertIsNone(a.service.execute_decision(decision, status['policy'], work, a.session(self.clock())))
        self.assertEqual(len(self.automation_orders()), 1)

    def test_crash_between_ledger_write_and_intent_record_adopts_the_order(self):
        self.enter()
        a = self.auto
        decision = next(d for d in a.actions.history('AAPL') if d['action_state'] == 'ENTER')
        intent_id = a.service.status()['recent_intents'][0]['intent_id']
        connection = a.service.repository.connection
        with connection.transaction():  # the process died before the intent was marked submitted
            connection.execute('DELETE FROM paper_automation_intents WHERE intent_id=?', (intent_id,))
        self.clock.value += 600
        b = self.restart()
        work = dict(b.service._controller())
        policy = b.service.repository.get_policy(work['policy_id'])
        outcome = b.service.execute_decision(decision, policy, work, b.session(self.clock()))
        self.assertEqual((outcome['outcome'], outcome['reason_codes'], outcome['filled_quantity']), ('SUBMITTED', ['RECOVERED_EXISTING_ORDER'], 6))
        self.assertEqual(len(self.automation_orders(b)), 1)
        self.assertEqual(b.position('AAPL')['quantity'], 6)
        self.assertIsNone(b.service.execute_decision(decision, policy, work, b.session(self.clock())))

    def test_ledger_and_audit_history_survive_restart(self):
        self.enter()
        events = [(e['sequence'], e['kind']) for e in self.auto.events()]
        fills = self.store.paper_ledger.project_fills()
        self.clock.value += 600
        b = self.restart()
        self.assertEqual([(e['sequence'], e['kind']) for e in b.events()], events)
        self.assertEqual(self.store.paper_ledger.project_fills(), fills)
        self.assertEqual(b.service.status()['durability'], 'SQLITE_LOCAL_STATE')


class WorkerScheduleTests(AutoBase):
    def test_slots_stay_on_the_grid_and_an_overrun_is_skipped_not_caught_up(self):
        a = self.auto
        a.go()
        worker = a.service.worker
        anchor = worker.anchor

        def wait(seconds):
            self.clock.value += seconds
        worker.wait = wait
        worker.run(max_cycles=3)
        controller = a.service._controller()
        self.assertEqual((controller['cycle_count'], controller['last_scheduled_epoch']), (3, anchor + 120))
        original = a.ai._packet

        def slow(*args, **kwargs):
            self.clock.value += 150  # this cycle takes two and a half cadences
            a.ai._packet = original
            return original(*args, **kwargs)
        a.ai._packet = slow
        worker.run(max_cycles=2)
        controller = a.service._controller()
        self.assertEqual(controller['cycle_count'], 5)
        self.assertEqual(controller['last_scheduled_epoch'], anchor + 360)  # 180 ran long; 240 and 300 were skipped
        self.assertEqual(controller['last_cycle']['missed_cycles_before'], 2)
        self.assertTrue(worker.alive())

    def _fault_log(self):
        import tempfile
        from pathlib import Path
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.auto.service._trace_log_path = lambda: Path(folder.name) / 'paper-automation-scope-errors.log'
        return Path(folder.name) / 'paper-automation-worker-errors.log'

    def test_a_busy_store_during_lease_renewal_is_retried_with_its_traceback_retained(self):
        import sqlite3
        a = self.auto
        a.go()
        log = self._fault_log()
        worker = a.service.worker
        worker.wait = lambda seconds: setattr(self.clock, 'value', self.clock.value + seconds)
        real, failures = a.service.heartbeat, [2]

        def heartbeat():
            if failures[0]:
                failures[0] -= 1
                raise sqlite3.OperationalError('database is locked')
            return real()
        a.service.heartbeat = heartbeat
        before = a.service._controller()['cycle_count']
        worker.run(max_cycles=3)
        # The worker's renewal fails once; the cycle's own renewal fails once, so that slot is unobserved, not run.
        self.assertEqual(a.service._controller()['cycle_count'], before + 2)
        self.assertTrue(worker.alive())
        self.assertEqual(worker.transient_failures, 0)
        text = log.read_text(encoding='utf-8')
        self.assertEqual((text.count('"phase": "HEARTBEAT"'), text.count('"phase": "CYCLE"')), (1, 1))
        self.assertIn('sqlite3.OperationalError: database is locked', text)
        self.assertIn('"owner_id": "%s"' % a.service.owner_id, text)

    def test_persistent_store_errors_end_the_worker_and_say_why(self):
        import sqlite3
        from market_platform_foundation.ui_api.paper_automation import TRANSIENT_STORE_RETRIES
        a = self.auto
        a.go()
        log = self._fault_log()
        worker = a.service.worker
        worker.wait = lambda seconds: setattr(self.clock, 'value', self.clock.value + seconds)

        def heartbeat():
            raise sqlite3.OperationalError('database is locked')
        a.service.heartbeat = heartbeat
        worker.run(max_cycles=3)
        self.assertFalse(worker.alive())
        self.assertEqual(a.service._controller()['last_error']['code'], 'WORKER_OperationalError')
        text = log.read_text(encoding='utf-8')
        self.assertEqual(text.count('"transient": true'), TRANSIENT_STORE_RETRIES)
        self.assertIn('"phase": "WORKER_EXIT"', text)
        self.assertIn('Traceback (most recent call last)', text)

    def test_a_worker_that_loses_its_lease_stops_scheduling(self):
        a = self.auto
        a.go()
        worker = a.service.worker
        a.service.repository.release_lease(a.service._account(), a.service.owner_id)
        worker.run(max_cycles=1)
        self.assertEqual((worker.exit_reason, worker.alive()), ('AUTOMATION_LEASE_LOST', False))
        self.assertEqual(a.service.status()['status'], 'ERROR')

    def test_threaded_start_runs_a_cycle_and_stop_ends_the_thread(self):
        a = self.auto
        a.configure()
        a.arm()
        a.service.start(threaded=True)
        deadline = time.time() + 10
        while time.time() < deadline and not a.service._controller()['cycle_count']:
            time.sleep(0.02)
        self.assertGreaterEqual(a.service._controller()['cycle_count'], 1)
        thread = a.service.worker.thread
        a.service.stop()
        thread.join(5)
        self.assertFalse(thread.is_alive())


class IsolationTests(AutoBase):
    def test_broker_or_live_environment_blocks_arming_cycles_and_orders(self):
        a = self.auto
        a.configure()
        os.environ['IMP_BROKER_PAPER_EXECUTION'] = '1'
        try:
            with self.assertRaisesRegex(ValueError, 'BROKER_PAPER_ENVIRONMENT_ENABLED'):
                a.arm()
        finally:
            os.environ.pop('IMP_BROKER_PAPER_EXECUTION', None)
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.arm()
        a.service.start(threaded=False)
        a.cycle()
        a.select('AAPL')
        os.environ['IMP_LIVE_EXECUTION'] = '1'
        try:
            cycle = a.cycle()
            self.assertEqual((cycle['status'], cycle['reevaluation'], cycle['actions']), ('BLOCKED_BY_AUTHORITY', None, []))
            self.assertIn(dict(category='AUTHORITY', code='LIVE_EXECUTION_ENVIRONMENT_ENABLED'), cycle['blockers'])
            self.assertEqual(a.service.status()['status'], 'BLOCKED_BY_AUTHORITY')
        finally:
            os.environ.pop('IMP_LIVE_EXECUTION', None)
        self.assertEqual((a.provider.calls, self.automation_orders()), (0, []))

    def test_a_non_internal_ledger_is_refused_before_any_order(self):
        self.enter()
        a = self.auto
        a.quote('AAPL', 152, -2)
        ledger = self.store.paper_ledger
        ledger.execution_provider = 'MOOMOO'
        try:
            cycle = a.cycle(400)
        finally:
            ledger.execution_provider = 'INTERNAL'
        self.assertEqual((cycle['status'], cycle['actions']), ('BLOCKED_BY_AUTHORITY', []))
        self.assertEqual(len(self.automation_orders()), 1)

    def test_authority_loss_blocks_without_an_order(self):
        self.enter()
        a = self.auto
        a.quote('AAPL', 152, -2)
        os.environ.pop('IMP_PAPER_EXECUTION')
        try:
            cycle = a.cycle(400)
        finally:
            os.environ['IMP_PAPER_EXECUTION'] = '1'
        self.assertEqual(cycle['status'], 'BLOCKED_BY_AUTHORITY')
        self.assertEqual(len(self.automation_orders()), 1)

    def test_the_controller_imports_no_broker_or_live_order_route(self):
        for relative in ('ui_api/paper_automation.py', 'intelligence/inference/paper_automation.py', 'local_state/paper_automation.py'):
            source = (SRC / relative).read_text(encoding='utf-8')
            imports = [line for line in source.splitlines() if line.strip().startswith(('import ', 'from '))]
            for line in imports:
                for forbidden in ('broker', 'moomoo', 'ibkr', 'live_order', 'live_execution', 'trading_gateway'):
                    self.assertNotIn(forbidden, line.replace('broker_paper_execution_env_enabled', '').replace('live_execution_env_enabled', ''),
                                     f'{relative}: {line}')
        source = (SRC / 'ui_api/paper_automation.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('submit_paper_order('), 1)  # one submit call: the canonical Paper route
        self.assertNotIn('ledger.submit', source)
        self.assertNotIn('record_fill', source)

    def test_route_policies(self):
        for path in ('/paper/automation/status', '/paper/automation/history', '/paper/automation/report'):
            self.assertEqual(policy_for('GET', path).capability, 'audit.read', path)
        for path in ('/paper/automation/arm', '/paper/automation/start', '/paper/automation/resume'):
            self.assertEqual(policy_for('POST', path).capability, 'paper.order.submit', path)
        for path in ('/paper/automation/configure', '/paper/automation/disarm', '/paper/automation/pause', '/paper/automation/stop',
                     '/paper/automation/emergency-stop'):
            self.assertEqual(policy_for('POST', path).capability, 'state.write', path)


class HttpRouteTests(AutoBase):
    def setUp(self):
        super().setUp()
        self.store._paper_automation_service = self.auto.service
        _OpenHandler.store = self.store
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _OpenHandler)
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b'{}')

    def test_operator_controls_over_http(self):
        status, payload = self.call('/paper/automation/status')
        self.assertEqual((status, payload['status']), (200, 'NOT_CONFIGURED'))
        status, refused = self.call('/paper/automation/configure', dict(scope=dict(universe='US_EQUITIES')))
        self.assertEqual(status, 400)
        self.assertIn('AUTOMATION_POLICY_INCOMPLETE', json.dumps(refused))
        status, configured = self.call('/paper/automation/configure', policy_body())
        self.assertEqual((status, configured['status']), (200, 'DISARMED'))
        status, refused = self.call('/paper/automation/start', {})
        self.assertEqual(status, 400)
        self.assertIn('AUTOMATION_NOT_ARMED', json.dumps(refused))
        status, armed = self.call('/paper/automation/arm', dict(policy_id=configured['policy']['policy_id'], acknowledgement=ARM_ACKNOWLEDGEMENT))
        self.assertEqual((status, armed['armed']), (200, True))
        status, refused = self.call('/paper/automation/pause', dict(unexpected=True))
        self.assertEqual(status, 400)
        status, _ = self.call('/paper/automation/liquidate', {})
        self.assertEqual(status, 404)
        status, stopped = self.call('/paper/automation/emergency-stop', dict(reason='test'))
        self.assertEqual((status, stopped['status']), (200, 'EMERGENCY_STOPPED'))
        status, history = self.call('/paper/automation/history?limit=5')
        self.assertEqual((status, history['events'][0]['kind']), (200, 'EMERGENCY_STOP'))
        status, report = self.call('/paper/automation/report')
        self.assertEqual((status, report['fills']['count']), (200, 0))
        status, disarmed = self.call('/paper/automation/disarm', {})
        self.assertEqual((status, disarmed['status']), (200, 'DISARMED'))


if __name__ == '__main__':
    import unittest
    unittest.main()
