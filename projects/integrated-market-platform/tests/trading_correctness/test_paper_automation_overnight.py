"""Step 7: controlled Paper-only overnight and close-out regressions."""
import copy
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from tests.trading_correctness.test_paper_automation import AutoBase
from tests.support.paper_automation_harness import policy_body
from market_platform_foundation.ui_api import paper_automation as controller
from market_platform_foundation.intelligence.inference.paper_automation import (
    build_policy, sessions_held, select_overnight_carry,
)


class OwnershipTests(unittest.TestCase):
    def book(self, trades):
        events, orders = [], {}
        for n, (side, qty, automatic) in enumerate(trades):
            oid = str(n)
            orders[oid] = dict(instrument_id='AAPL', side=side, client_order_id=('PAI-' if automatic else 'manual-') + oid)
            events.append(dict(event_type='FillRecorded', payload=dict(order_id=oid,
                fill=dict(fill_quantity=qty, fill_time_ns=n + 1))))
        return SimpleNamespace(events=events, lookup_order=lambda oid: orders[oid])

    def test_reductions_use_own_bucket_first_and_reversal_resets_ownership(self):
        for trades, expected in [([('BUY', 5, False)], 0),
            ([('BUY', 5, False), ('BUY', 6, True)], 6),
            ([('BUY', 5, False), ('BUY', 6, True), ('SELL', 7, False)], 4),
            ([('BUY', 5, False), ('BUY', 6, True), ('SELL', 8, True)], 0),
            ([('BUY', 5, False), ('SELL', 8, True)], -3),
            ([('SELL', 5, True), ('BUY', 8, False)], 0)]:
            with self.subTest(trades=trades):
                self.assertEqual(controller._automation_quantities(self.book(trades)).get('AAPL', 0), expected)

    def test_multiscope_missing_carry_initializes_account_state(self):
        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        work = dict(carry=None)
        service._owned_positions = lambda: []
        service._event = lambda *args, **kwargs: None
        service._carry_rollover(work, dict(session_date='2026-10-05', trading_day=True), 1791208800.0)
        self.assertEqual(work['carry']['pending'], {})

    def test_continuous_scope_cannot_roll_equity_carry_on_weekend(self):
        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        service.session = lambda now: dict(session_date='2026-10-10', trading_day=False, label='CLOSED')
        position = dict(instrument_id='AAPL', quantity=4, first_entry_time_ns=1791208800000000000)
        service._owned_positions = lambda: [position]
        service._event = lambda *args, **kwargs: None
        approval = dict(session_date='2026-10-09', quantity=4, entry_ns=position['first_entry_time_ns'])
        work = dict(carry=dict(session_date='2026-10-09', approved={'AAPL': approval}, reviewed={}, pending={}, closing=[], blocked=[]))
        service._carry_rollover(work, dict(session_date='2026-10-10', trading_day=True, label='CONTINUOUS'), 1791648000)
        self.assertEqual(work['carry']['session_date'], '2026-10-09')
        self.assertIn('AAPL', work['carry']['approved'])

    def test_weekend_restart_detects_unapproved_equity_carry_for_all_scopes(self):
        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        weekend = dict(session_date='2026-10-10', trading_day=False, label='CLOSED')
        service.session = lambda now: weekend
        service._owned_positions = lambda: [dict(instrument_id='AAPL', quantity=4, first_entry_time_ns=1791208800000000000)]
        service._event = lambda *args, **kwargs: None
        for session in (weekend, dict(weekend, trading_day=True, label='CONTINUOUS')):
            work = dict(carry=dict(session_date='2026-10-09', approved={}, reviewed={}, pending={}, closing=[], blocked=[]))
            service._carry_rollover(work, session, 1791648000)
            self.assertIn('AAPL', work['carry']['pending'])

    def test_first_cycle_without_saved_day_detects_old_automation_position(self):
        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        service._owned_positions = lambda: [dict(instrument_id='AAPL', quantity=4, first_entry_time_ns=1791208800000000000)]
        service._event = lambda *args, **kwargs: None
        work = {}
        service._carry_rollover(work, dict(session_date='2026-10-07', trading_day=True, label='REGULAR'), 1791381600)
        self.assertIn('AAPL', work['carry']['pending'])

    def test_missed_trading_session_requires_open_close(self):
        service = controller.PaperAutomationService.__new__(controller.PaperAutomationService)
        position = dict(instrument_id='AAPL', quantity=4, first_entry_time_ns=1791208800000000000)
        service._owned_positions = lambda: [position]
        service._event = lambda *args, **kwargs: None
        approval = dict(session_date='2026-10-05', quantity=4, entry_ns=position['first_entry_time_ns'])
        work = dict(carry=dict(session_date='2026-10-05', approved={'AAPL': approval}, reviewed={}, pending={}, closing=[], blocked=[]))
        service._carry_rollover(work, dict(session_date='2026-10-07', trading_day=True, label='REGULAR'), 1791381600)
        self.assertIn('AAPL', work['carry']['pending'])

    def test_holiday_and_weekend_do_not_age_a_hold(self):
        from market_platform_foundation.intelligence.forward_qualification.evidence01.continuity import is_trading_day
        self.assertEqual(sessions_held('2026-11-25', '2026-11-30', is_trading_day), 3)

    def test_selection_skips_over_budget_and_continues_in_stable_order(self):
        candidates = [dict(instrument_id=i, return_bps=p, exposure_minor=e) for i,p,e in
            [('A', 30, 200), ('B', 20, 200), ('D', 10, 50), ('C', 10, 50)]]
        kept, refused = select_overnight_carry(candidates, dict(max_positions=2, max_exposure_minor=250))
        self.assertEqual([p['instrument_id'] for p in kept], ['A', 'C'])
        self.assertEqual(len(refused), 2)


class CloseOutTests(AutoBase):
    def setUp(self):
        super().setUp()
        self.clock.value = 1791208800.0  # match the controlled 2026-10-05 session

    def test_close_out_runs_with_unhealthy_provider_and_recovers(self):
        self.enter()
        a = self.auto
        a.minutes_to_close = 8
        a.health = dict(state='STALE', reasons=['CONTROLLED_FEED_DOWN'])
        with patch.object(a.service, '_close_position', wraps=a.service._close_position) as close:
            result = a.cycle()
            self.assertTrue(close.called)
            self.assertEqual(result['execution'], 'WITHHELD_PROVIDER_UNHEALTHY')

    def test_unfilled_close_is_retried_with_new_key_and_bounded(self):
        self.enter()
        a = self.auto
        a.minutes_to_close = 8
        del self.feed.prices['AAPL']
        for _ in range(8):
            a.cycle()
        orders = [o for o in a.orders() if o['client_order_id'].startswith('PAI-EOD-')]
        self.assertEqual(len(orders), 6)
        self.assertEqual(len({o['client_order_id'] for o in orders}), 6)
        self.assertIsNotNone(a.position('AAPL'))

    def test_close_retry_cannot_repeat_in_same_tick_or_after_restart(self):
        self.enter()
        a = self.auto
        a.minutes_to_close = 8
        del self.feed.prices['AAPL']
        a.cycle()
        a.cycle(0)
        orders = lambda: [o for o in a.orders() if o['client_order_id'].startswith('PAI-EOD-')]
        self.assertEqual(len(orders()), 1)
        # Even if controller retry metadata is lost, the ledger's attempt time fences a restart.
        work = a.service._controller()
        work['carry'].pop('retry_after', None)
        summary = dict(actions=[], blockers=[])
        policy = a.service.repository.get_policy(work['policy_id'])
        a.service._close_retry(work, policy, summary, a.session(self.clock()), self.clock(), a.service._owned_positions()[0])
        self.assertEqual(len(orders()), 1)

    def test_next_open_closes_unplanned_carry_before_entries(self):
        self.enter()
        a = self.auto
        a.session_label = 'POST_MARKET'
        a.cycle()
        self.assertIn('AAPL', a.service.status()['carry']['pending'])
        a.session_label, a.session_date, a.minutes_to_close = 'REGULAR', '2026-10-06', 390
        a.quote('AAPL', 151, 2)
        outcomes = a.cycle()['actions']
        self.assertEqual(outcomes[0]['action'], 'OPEN_CLOSE')
        self.assertIsNone(a.position('AAPL'))

    def test_real_mixed_fills_close_only_automation_shares(self):
        self.enter()
        a = self.auto
        self.order('AAPL', 'BUY', 3, '150.00')
        self.assertEqual(a.position('AAPL')['quantity'], 9)
        self.assertEqual(controller._automation_quantities(self.store.paper_ledger)['AAPL'], 6)
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        closed = a.cycle()['actions'][0]
        self.assertEqual(closed['filled_quantity'], 6)
        self.assertEqual(a.position('AAPL')['quantity'], 3)
        self.assertEqual(controller._automation_quantities(self.store.paper_ledger).get('AAPL', 0), 0)

    def test_real_mixed_fills_ai_exit_leaves_manual_shares(self):
        self.enter()
        a = self.auto
        self.order('AAPL', 'BUY', 3, '150.00')
        a.quote('AAPL', 148, -2)
        a.cycle()
        self.assertEqual(a.position('AAPL')['quantity'], 3)

    def test_real_manual_only_fill_is_never_closed(self):
        a = self.auto
        self.order('AAPL', 'BUY', 3, '150.00')
        a.go(risk=dict(allow_entries=False))
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2); a.cycle()
        self.assertEqual(a.position('AAPL')['quantity'], 3)

    def test_one_unadmitted_symbol_cannot_abort_other_close_outs(self):
        self.enter()
        a = self.auto
        ledger = self.store.paper_ledger
        positions = ledger.project_positions()
        bad = dict(positions[0], instrument_id='UNADMITTED')
        from market_platform_foundation.ui_api import paper_projections
        original = paper_projections._admit_focus_instrument
        def admit(store, iid):
            if iid == 'UNADMITTED': raise ValueError('INSTRUMENT_NOT_FOUND')
            return original(store, iid)
        with patch.object(ledger, 'project_positions', return_value=[bad, *positions]), \
             patch.object(controller, '_automation_quantities', return_value={'UNADMITTED': 2, 'AAPL': 6}), \
             patch.object(paper_projections, '_admit_focus_instrument', side_effect=admit):
            rows = a.service._owned_positions()
            self.assertEqual({p['instrument_id'] for p in rows}, {'UNADMITTED', 'AAPL'})
            work = a.service._controller()
            summary = dict(actions=[], blockers=[])
            policy = a.service.repository.get_policy(work['policy_id'])
            a.minutes_to_close = 8
            with patch.object(a.service, '_close_position', return_value={'outcome': 'BLOCKED', 'reason_codes': ['INSTRUMENT_NOT_FOUND']}) as close:
                a.service._eod_flatten(work, policy, summary, a.session(self.clock()), self.clock())
                self.assertEqual(close.call_count, 2)

    def test_manual_only_position_is_not_closed(self):
        a = self.auto
        self.enter()
        with patch.object(controller, '_automation_quantities', return_value={}):
            a.minutes_to_close = 8
            a.quote('AAPL', 151, 2)
            a.cycle()
            self.assertEqual(a.position('AAPL')['quantity'], 6)

    def test_mixed_position_only_automation_quantity_is_closed(self):
        self.enter()
        a = self.auto
        with patch.object(controller, '_automation_quantities', return_value={'AAPL': 2}):
            a.minutes_to_close = 8
            a.quote('AAPL', 151, 2)
            actions = a.cycle()['actions']
            self.assertEqual(next(o for o in actions if o['action'] == 'EOD_FLATTEN')['quantity'], 2)
            self.assertEqual(a.position('AAPL')['quantity'], 4)


class CarryTests(AutoBase):
    def setUp(self):
        super().setUp()
        self.clock.value = 1791208800.0
    def enable_holds(self):
        import json
        from dataclasses import replace
        a = self.auto
        original = a.provider.infer
        def infer(packet, **kwargs):
            response = original(packet, **kwargs)
            answer = json.loads(response.raw_text)
            answer.update(schema_version='action-proposal-wire/3.0.0',
                rationale=dict(basis_refs=['q', 't'], assessment='EVIDENCE_SUFFICIENT'), uncertainties=[])
            if packet.scope.get('overnight_review') and answer['proposal_state'] == 'HOLD':
                answer['hold_conditions'].append('OVERNIGHT_THESIS_SUPPORTED')
            return replace(response, raw_text=json.dumps(answer))
        a.provider.infer = infer
        a.go(risk=dict(max_open_positions=15, max_aggregate_exposure_minor=7500000,
            max_daily_loss_minor=200000, max_overnight_positions=5,
            max_overnight_exposure_minor=2500000, max_hold_sessions=5))
        self.enter()
        a.minutes_to_close = 40
        a.quote('AAPL', 151, 2)
        a.cycle()
        return a

    def test_evidence_backed_hold_and_fresh_next_day_review(self):
        a = self.enable_holds()
        d = a.actions.history('AAPL')[0]
        self.assertTrue(d['overnight_carry']['qualified'], d)
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        a.cycle()
        self.assertIsNotNone(a.position('AAPL'))
        self.assertIn('AAPL', a.service.status()['carry']['approved'])
        a.session_date = '2026-10-06'
        self.clock.value += 86400
        a.minutes_to_close = 300
        a.quote('AAPL', 149, 2)
        a.cycle()
        status = a.service.status()
        self.assertEqual(status['carry']['approved'], {})
        self.assertEqual(status['carry']['pending'], {})
        a.minutes_to_close = 8
        a.quote('AAPL', 149, 2)
        a.cycle()
        self.assertIsNone(a.position('AAPL'))  # yesterday's reason cannot carry today

    def test_carry_gate_refuses_invalid_review_matrix(self):
        a = self.enable_holds()
        work = a.service._controller()
        policy = a.service.repository.get_policy(work['policy_id'])
        position = a.service._owned_positions()[0]
        now, session = self.clock(), a.session(self.clock())
        decision = a.actions.history('AAPL')[0]
        self.assertIsNotNone(a.service._carry_candidate(position, work, policy, session, now))
        for case in ('plain_hold', 'weak_assessment', 'no_nonquote_support', 'expired', 'quantity_changed',
                     'server_stop', 'old_review', 'no_review', 'daily_loss', 'conflict', 'weak_ref', 'stale_support', 'stale_quote'):
            d, w = copy.deepcopy(decision), copy.deepcopy(work)
            if case == 'conflict': d['conflicting_refs'] = ['q']
            if case == 'weak_ref': d['weak_refs'] = ['q']
            if case in ('stale_support', 'stale_quote'):
                index = 1 if case == 'stale_support' else 0
                d['evidence_snapshot']['evidence']['current_market_evidence'][index]['valid_until'] = '2026-10-05T13:00:00Z'
            if case == 'plain_hold': d['overnight_carry']['qualified'] = False
            if case == 'weak_assessment': d['model_reasoning_wire']['rationale']['assessment'] = 'EVIDENCE_MIXED'
            if case == 'no_nonquote_support': d['supporting_refs'] = ['q']
            if case == 'expired': d['valid_until'] = '2026-10-05T13:00:00Z'
            if case == 'quantity_changed': d['position']['quantity'] = 5
            if case == 'server_stop': d['server_exit'] = True
            if case == 'old_review': w['carry']['reviewed']['AAPL']['session_date'] = '2026-10-02'
            if case == 'no_review': w['carry']['reviewed'] = {}
            if case == 'daily_loss': w['day']['start_equity_minor'] += 300000
            with self.subTest(case=case), patch.object(a.actions, 'history', return_value=[d]):
                self.assertIsNone(a.service._carry_candidate(position, w, policy, session, now))
        for label, target, value in [
            ('feed_down', a.service, dict(state='STALE', reasons=['DOWN'])),
        ]:
            with patch.object(target, 'provider_health', return_value=value):
                self.assertIsNone(a.service._carry_candidate(position, work, policy, session, now))
        with patch.object(a.actions, '_risk_facts', return_value=dict(status='BREACHED')):
            self.assertIsNone(a.service._carry_candidate(position, work, policy, session, now))
        with patch.object(self.store.paper_ledger, 'short_margin_status', return_value=dict(maintenance_breached=True)):
            self.assertIsNone(a.service._carry_candidate(position, work, policy, session, now))
        stale_mark = dict(position, mark_as_of_ns=int((now - 3600) * 1e9))
        self.assertIsNone(a.service._carry_candidate(stale_mark, work, policy, session, now))
        with patch.object(a.service, '_hold_sessions', return_value=5):
            self.assertIsNone(a.service._carry_candidate(position, work, policy, session, now))

    def test_new_stop_breach_is_refreshed_before_carry_approval(self):
        a = self.enable_holds()
        work = a.service._controller()
        policy = a.service.repository.get_policy(work['policy_id'])
        position = a.service._owned_positions()[0]
        state = {'status': 'ACTIVE'}
        stop = SimpleNamespace(evaluate=lambda iid: state.update(status='BREACHED'))
        with patch.object(a.actions, 'risk_control', stop), patch.object(a.actions, '_risk_facts', side_effect=lambda iid: dict(state)):
            self.assertIsNone(a.service._carry_candidate(position, work, policy, a.session(self.clock()), self.clock()))

    def test_gap_uses_saved_equity_and_missing_baseline_stays_blocked(self):
        a = self.enable_holds()
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        a.cycle()
        saved = a.service._controller()['day']['last_equity_minor']
        a.session_date, a.minutes_to_close = '2026-10-06', 300
        self.clock.value += 86400
        a.quote('AAPL', 140, 2)
        a.cycle()
        self.assertEqual(a.service._controller()['day']['start_equity_minor'], saved)
        self.assertLess(a.service.status()['risk']['day_pnl_minor'], 0)

    def test_policy_optional_fields_are_all_or_none_and_limits_are_bounded(self):
        a = self.auto
        old = a.configure()['policy']['policy_id']
        self.assertEqual(a.configure()['policy']['policy_id'], old)
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_INCOMPLETE'):
            a.configure(risk=dict(max_overnight_positions=1))
        for count, amount in [(6, 2500000), (5, 2500001)]:
            with self.subTest(count=count, amount=amount), self.assertRaises(ValueError):
                a.configure(risk=dict(max_open_positions=15, max_aggregate_exposure_minor=7500000,
                    max_overnight_positions=count, max_overnight_exposure_minor=amount, max_hold_sessions=5))


    def test_review_limit_is_ten_positions_and_not_requeued(self):
        a = self.enable_holds()
        work = a.service._controller()
        policy = a.service.repository.get_policy(work['policy_id'])
        work['carry']['reviewed'] = {}
        rows = [dict(a.service._owned_positions()[0], instrument_id=f'T{i:02}') for i in range(12)]
        with patch.object(a.service, '_owned_positions', return_value=rows), \
             patch.object(a.service, '_hold_sessions', return_value=1), \
             patch.object(a.actions, '_risk_facts', return_value=None), \
             patch.object(a.reevaluation, 'request_redecision') as request:
            a.service._prepare_overnight_reviews(work, policy, a.session(self.clock()), self.clock(), a.health)
            a.service._prepare_overnight_reviews(work, policy, a.session(self.clock()), self.clock(), a.health)
            self.assertEqual(request.call_count, 10)
            self.assertEqual(len(work['carry']['reviewed']), 10)

    def test_approved_carry_survives_midnight_and_weekend(self):
        a = self.enable_holds()
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        a.cycle()
        # Tuesday before the premarket: a planned hold must not become unplanned.
        a.session_date, a.session_label = '2026-10-06', 'CLOSED'
        self.clock.value = 1791262800.0  # Tuesday 01:00 ET
        a.cycle()
        self.assertEqual(a.service.status()['carry']['pending'], {})

    def test_carry_state_survives_process_restart(self):
        a = self.enable_holds()
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        a.cycle()
        old = a.service.status()['carry']
        restarted = self.restart()
        self.assertEqual(restarted.service.status()['carry'], old)

    def test_missing_previous_equity_does_not_reset_loss_basis_at_open(self):
        a = self.enable_holds()
        a.minutes_to_close = 8
        a.quote('AAPL', 151, 2)
        a.cycle()
        work = a.service._controller()
        work['day'].pop('last_equity_minor', None)
        a.service._save(work, fenced=True)
        a.session_date, a.minutes_to_close = '2026-10-06', 300
        self.clock.value += 86400
        a.quote('AAPL', 140, 2)
        a.cycle(); a.cycle()
        self.assertIsNone(a.service._controller()['day']['start_equity_minor'])

    def test_feed_down_close_refusal_is_reported_once_and_recovery_fills(self):
        self.enter()
        a = self.auto
        a.minutes_to_close = 8
        from market_platform_foundation.ui_api import paper_projections
        with patch.object(paper_projections, 'preview_paper_order', side_effect=ValueError('LIVE_FEED_UNHEALTHY')):
            a.cycle(); a.cycle()
        events = [e for e in a.events() if e['kind'] == 'PAPER_EOD_FLATTEN_BLOCKED']
        self.assertEqual(len(events), 1)
        a.quote('AAPL', 151, 2)
        a.cycle()
        self.assertIsNone(a.position('AAPL'))


class ShortCarryTests(AutoBase):
    def test_short_carries_under_shared_caps_and_pays_one_rollover_fee(self):
        import json
        from dataclasses import replace
        from market_platform_foundation.ui_api import paper_experiment
        from tests.support.paper_automation_harness import Automation
        from tests.trading_correctness.test_paper_automation_shorts import ShortProvider
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = paper_experiment.create_experiment(self.store, {'allow_short': True})['experiment']
        self.clock.value = 1791208800.0
        provider = ShortProvider()
        original = provider.infer
        def infer(packet, **kwargs):
            response = original(packet, **kwargs)
            answer = json.loads(response.raw_text)
            answer.update(schema_version='action-proposal-wire/3.0.0',
                rationale=dict(basis_refs=['q', 't'], assessment='EVIDENCE_SUFFICIENT'), uncertainties=[])
            if packet.scope['position']['state'] == 'SHORT': answer['direction'] = 'SHORT'
            if packet.scope.get('overnight_review') and answer['proposal_state'] == 'HOLD':
                answer['hold_conditions'].append('OVERNIGHT_THESIS_SUPPORTED')
            return replace(response, raw_text=json.dumps(answer))
        provider.infer = infer
        a = self.auto = Automation(self.store, clock=self.clock, feed=self.feed, provider=provider)
        a.quote('AAPL', 150, -2)
        a.opportunity('AAPL', side='SHORT')
        a.go(risk=dict(allow_short=True, max_open_positions=15, max_aggregate_exposure_minor=7500000,
            max_overnight_positions=5, max_overnight_exposure_minor=2500000, max_hold_sessions=5))
        a.cycle(); a.select('AAPL'); a.cycle(); a.cycle()
        self.assertEqual(a.position('AAPL')['side'], 'SHORT')
        a.minutes_to_close = 40
        a.quote('AAPL', 149, -2); a.cycle()
        a.minutes_to_close = 8
        a.quote('AAPL', 149, -2); a.cycle()
        self.assertIn('AAPL', a.service.status()['carry']['approved'])
        a.session_date, a.minutes_to_close = '2026-10-06', 300
        self.clock.value += 86400
        a.quote('AAPL', 148, -2); a.cycle(); a.cycle()
        fees = [e for e in a.events() if e['kind'] == 'SHORT_BORROW_FEE_ACCRUED']
        self.assertEqual(len(fees), 1)
        self.assertGreater(fees[0]['fee_minor'], 0)


class ReservedOrderTests(unittest.TestCase):
    def test_manual_http_routes_reject_reserved_ids_after_normalization(self):
        import json
        import threading
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        from tests.trading_correctness.test_paper_experiment_api import _OpenHandler
        class Handler(_OpenHandler):
            store = None  # rejection must occur before touching the Paper store
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path in ('/paper/orders/preview', '/paper/orders'):
                for field in ('client_order_id', 'idempotency_key'):
                    for value in ('PAI-fake', '  PAI-fake  '):
                        body = json.dumps({field: value}).encode()
                        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,
                            data=body, headers={'Content-Type': 'application/json'})
                        with self.subTest(path=path, field=field, value=value), self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(req, timeout=10)
                        self.assertEqual(caught.exception.code, 400)
                        self.assertIn('CLIENT_ORDER_ID_RESERVED', caught.exception.read().decode())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
