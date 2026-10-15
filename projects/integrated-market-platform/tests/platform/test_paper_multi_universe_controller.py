"""Scoped loop isolation and one shared controller, with controlled collaborators."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from market_platform_foundation.ui_api.paper_automation import PaperAutomationService
from market_platform_foundation.ui_api.screener_reevaluation import ReevaluationService
from tests.intelligence.test_reevaluation import Harness, SCOPE


class MultiUniverseControllerTests(unittest.TestCase):
    def test_bound_loop_cannot_follow_another_scope_latest_pointer(self):
        h = Harness()
        h.ai._query = lambda value: dict(SCOPE, **value)
        one = ReevaluationService(h.store, repository=h.repo, ai=h.ai, actions=h.actions, clock=h.clock,
                                  scope=dict(universe='US_EQUITIES'))
        two = ReevaluationService(h.store, repository=h.repo, ai=h.ai, actions=h.actions, clock=h.clock,
                                  scope=dict(universe='CRYPTO'))
        first = one.attach_driver('PAPER_AUTOMATION', scope=dict(universe='US_EQUITIES'), requested_cadence_seconds=60)
        second = two.attach_driver('PAPER_AUTOMATION', scope=dict(universe='CRYPTO'), requested_cadence_seconds=60)
        self.assertNotEqual(first, second)
        self.assertEqual(one._loop()['loop_id'], first)
        self.assertEqual(two._loop()['loop_id'], second)
        loop = one._loop()
        loop['selected'] = ['held-equity']
        h.repo.save_loop(loop, owner_id=one.owner_id)
        two.detach_driver()
        self.assertEqual(one._loop()['selected'], ['held-equity'])
        self.assertEqual(one._loop()['desired_state'], 'RUNNING')

    def service(self):
        h = Harness()
        service = PaperAutomationService(h.store, reevaluation=h.service, clock=h.clock,
                                        session=lambda _: dict(label='CLOSED', session_date='2026-10-11',
                                                               trading_day=False, minutes_to_close=None))
        service.paper_identity = lambda _: []
        service._scoped_reevaluation = lambda scope: h.service
        service._scope_session = lambda scope, now: (dict(label='CONTINUOUS', trading_day=True,
                           session_date='2026-10-11', minutes_to_close=None) if scope['universe'] == 'CRYPTO'
                           else service.session(now))
        return h, service

    def policy(self):
        return dict(scope=dict(universe='US_EQUITIES'), schedule=dict(sessions=['REGULAR'], cadence_seconds=60),
                    scopes=[dict(scope=dict(universe='US_EQUITIES'), sessions=['REGULAR']),
                            dict(scope=dict(universe='CRYPTO'), sessions=['CONTINUOUS'])])

    def test_weekend_crypto_cycle_runs_while_equity_waits_and_state_stays_separate(self):
        h, service = self.service()
        seen = []
        def cycle(work, policy, summary, now, scheduled, missed):
            seen.append(policy['scope']['universe'])
            summary['session'] = service._scope_session(policy['scope'], now)
            if summary['session']['label'] in policy['schedule']['sessions']:
                work['universe'] = dict(adopted_run_id='crypto-selection')
                summary['actions'].append(dict(action='NO_ACTION'))
        service._cycle_scope = cycle
        work = dict(account_id='controlled', universe=dict(adopted_run_id='equity-selection'))
        summary = dict(actions=[], blockers=[], error=None)
        service._cycle(work, self.policy(), summary, h.clock(), h.clock(), 0)
        self.assertEqual(seen, ['US_EQUITIES', 'CRYPTO'])
        self.assertEqual(work['universes']['US_EQUITIES']['universe']['adopted_run_id'], 'equity-selection')
        self.assertEqual(work['universes']['CRYPTO']['universe']['adopted_run_id'], 'crypto-selection')
        self.assertTrue(summary['session_eligible'])
        self.assertEqual(len(summary['actions']), 1)

    def test_failed_scope_does_not_suppress_healthy_scope(self):
        h, service = self.service()
        def cycle(work, policy, summary, now, scheduled, missed):
            if policy['scope']['universe'] == 'US_EQUITIES':
                raise ValueError('EQUITY_PROVIDER_UNAVAILABLE')
            summary['session'] = dict(label='CONTINUOUS')
            summary['actions'].append(dict(action='NO_ACTION'))
        service._cycle_scope = cycle
        summary = dict(actions=[], blockers=[], error=None)
        work = dict(account_id='controlled')
        service._cycle(work, self.policy(), summary, h.clock(), h.clock(), 0)
        self.assertEqual(len(summary['actions']), 1)
        self.assertEqual(work['universes']['US_EQUITIES']['last_error']['code'], 'EQUITY_PROVIDER_UNAVAILABLE')
        self.assertIsNone(work['universes']['CRYPTO']['last_error'])
