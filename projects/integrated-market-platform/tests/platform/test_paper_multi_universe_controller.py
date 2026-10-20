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
        if not hasattr(h.store, 'data_mode'):
            h.store.data_mode = 'LIVE_OBSERVATIONAL'
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

    def closed_equity_cycle(self, equity_run):
        """One cycle with the real closed-session equity scope and a recording CRYPTO scope."""
        h, service = self.service()
        service._runs = Mock()
        service._runs.read.return_value = equity_run
        real, crypto_saw = service._cycle_scope, []
        def cycle(work, policy, summary, now, scheduled, missed):
            if policy['scope']['universe'] == 'US_EQUITIES':
                return real(work, policy, summary, now, scheduled, missed)
            summary['session'] = service._scope_session(policy['scope'], now)
            crypto_saw.append(work['_global_universe_active'])
        service._cycle_scope = cycle
        work = dict(account_id='controlled', universes=dict(US_EQUITIES=dict(universe=dict(active_run_id='equity-run'))))
        summary = dict(actions=[], blockers=[], error=None)
        service._cycle(work, self.policy(), summary, h.clock(), h.clock(), 0)
        return work, summary, crypto_saw

    def test_finished_equity_run_after_the_close_no_longer_holds_the_shared_run_slot(self):
        stopped = dict(run_id='equity-run', state='COMPLETED', error=None, finished_at='2026-10-11T17:09:57Z',
                       result=dict(universe_coverage=dict(status='STOPPED', reason='STOPPED_BY_OPERATOR')))
        work, summary, crypto_saw = self.closed_equity_cycle(stopped)
        equity = work['universes']['US_EQUITIES']['universe']
        self.assertIsNone(equity['active_run_id'])
        self.assertEqual(equity['last_result']['status'], 'STOPPED')
        self.assertFalse(equity['last_result']['adopted'])
        self.assertEqual(crypto_saw, [False])
        self.assertEqual(summary['actions'], [])

    def test_running_equity_run_after_the_close_still_holds_the_shared_run_slot(self):
        work, summary, crypto_saw = self.closed_equity_cycle(dict(run_id='equity-run', state='RUNNING', stage='BATCH_INFERENCE', progress={}))
        self.assertEqual(work['universes']['US_EQUITIES']['universe']['active_run_id'], 'equity-run')
        self.assertEqual(crypto_saw, [True])
        self.assertEqual(summary['universes']['US_EQUITIES']['universe']['state'], 'RUNNING')

    def test_each_scope_is_separated_from_its_own_last_start_not_the_accounts(self):
        # Rolling slices alternate: an equity run started a minute ago does not make crypto wait a full separation.
        from unittest.mock import patch
        h, service = self.service()
        seen = []
        service._universe_facts = lambda policy, universe, **_: (dict(last_started_epoch=universe.get('last_started_epoch'),
                                                                      active_run_id=None), 'fingerprint')
        service._event = lambda *args, **kwargs: None
        decided = dict(decision='DEFER', reason_codes=['UNIVERSE_MIN_SEPARATION'], next_eligible_epoch=h.clock(), detail={})
        with patch('market_platform_foundation.ui_api.paper_automation.should_run_universe',
                   side_effect=lambda facts: seen.append(dict(facts)) or decided):
            work = dict(account_id='controlled', last_universe_started_epoch=h.clock() - 60, universe=dict(last_started_epoch=None))
            service._universe(work, dict(scope=dict(universe='CRYPTO')), dict(blockers=[]), h.clock(), dict(label='CONTINUOUS'),
                              dict(allowed=True))
        self.assertIsNone(seen[0]['last_started_epoch'])

    def waiting_states(self, now, *, decided_ago=60, equity_started_ago=3600, crypto_started_ago=1900):
        from market_platform_foundation.ui_api.paper_automation import _iso
        waiting = dict(decision='DEFER', reason_codes=['UNIVERSE_RUN_ACTIVE'], detail=dict(run_id='SHARED_ACCOUNT_RUN_ACTIVE'),
                       at_iso=_iso(now - decided_ago))
        return dict(US_EQUITIES=dict(universe=dict(last_decision=waiting, last_started_epoch=now - equity_started_ago)),
                    CRYPTO=dict(universe=dict(last_started_epoch=now - crypto_started_ago)))

    def regular_session_service(self, label='REGULAR'):
        h, service = self.service()
        service.session = lambda _: dict(label=label, session_date='2026-10-20', trading_day=True, minutes_to_close=300)
        return h, service

    def test_a_continuous_scope_yields_the_freed_slot_to_an_in_session_peer_that_waited_longer(self):
        # 2026-10-20: a crypto slice outlasting the 30-minute separation restarted in the cycle it finished, before
        # the equity scope (evaluated first, still seeing the finished run's handle) could take the slot.
        h, service = self.regular_session_service()
        now = h.clock()
        states = self.waiting_states(now)
        self.assertTrue(service._peer_waiting(self.policy(), states, 'CRYPTO', now))
        self.assertFalse(service._peer_waiting(self.policy(), states, 'US_EQUITIES', now))

    def test_a_stale_or_closed_or_more_recent_peer_never_makes_a_scope_wait(self):
        h, service = self.regular_session_service()
        now = h.clock()
        # Older than two cadences (policy cadence 60 s): the peer stopped evaluating, e.g. its session closed.
        self.assertFalse(service._peer_waiting(self.policy(), self.waiting_states(now, decided_ago=121), 'CRYPTO', now))
        # The peer started after this scope did: it already had the more recent turn.
        self.assertFalse(service._peer_waiting(self.policy(), self.waiting_states(now, equity_started_ago=600), 'CRYPTO', now))
        # The peer is outside its own session.
        h, closed = self.regular_session_service('CLOSED')
        self.assertFalse(closed._peer_waiting(self.policy(), self.waiting_states(h.clock()), 'CRYPTO', h.clock()))
        # A peer deferred for its own reason is not waiting on the shared slot.
        states = self.waiting_states(now)
        states['US_EQUITIES']['universe']['last_decision']['detail'] = {}
        self.assertFalse(service._peer_waiting(self.policy(), states, 'CRYPTO', now))

    def test_only_a_run_yields_to_a_waiting_peer(self):
        from unittest.mock import patch
        h, service = self.service()
        service._universe_facts = lambda policy, universe, **_: (dict(active_run_id=None), 'fingerprint')
        service._event = lambda *args, **kwargs: None
        service._runs = Mock()
        verdicts = dict(RUN=dict(decision='RUN', reason_codes=['UNIVERSE_MIN_SEPARATION_ELAPSED'], next_eligible_epoch=None, detail={}),
                        BLOCK=dict(decision='BLOCK', reason_codes=['UNIVERSE_PLAN_INFEASIBLE'], next_eligible_epoch=None, detail={}))
        for name, verdict in verdicts.items():
            work = dict(account_id='controlled', universe={}, _peer_waiting=True)
            summary = dict(blockers=[])
            with patch('market_platform_foundation.ui_api.paper_automation.should_run_universe', return_value=dict(verdict)):
                service._universe(work, dict(scope=dict(universe='CRYPTO'), schedule=dict(universe_evaluation_interval_seconds=1800)),
                                  summary, h.clock(), dict(label='CONTINUOUS'), dict(allowed=True))
            decided = work['universe']['last_decision']
            if name == 'RUN':
                self.assertEqual((decided['decision'], decided['reason_codes']), ('DEFER', ['UNIVERSE_PEER_WAITING']))
                self.assertEqual(decided['detail'], dict(run_id='SHARED_ACCOUNT_PEER_WAITING'))
                self.assertIsNone(work['universe'].get('active_run_id'))
            else:
                self.assertEqual(decided['decision'], 'BLOCK')
                self.assertEqual(summary['blockers'][0]['code'], 'UNIVERSE_PLAN_INFEASIBLE')
        service._runs.start.assert_not_called()


class CryptoEvidenceIntegrationTests(unittest.TestCase):
    """The CRYPTO scope's provider health and candidate quotes against the real serving Kraken contracts.

    Software-controlled: one stub stream runtime stands in for the observed ``_RUNTIME``. No connection,
    no collection writer, no market data. These tests exist because the first integration regressed exactly
    here with an ``ImportError`` recorded as a DATA blocker every cycle.
    """

    def service(self):
        h = Harness()
        if not hasattr(h.store, 'data_mode'):
            h.store.data_mode = 'LIVE_OBSERVATIONAL'
        service = PaperAutomationService(h.store, reevaluation=h.service, clock=h.clock,
                                        session=lambda _: dict(label='CLOSED', session_date='2026-10-11',
                                                               trading_day=False, minutes_to_close=None))
        service.paper_identity = lambda _: []
        return h, service

    def test_provider_health_gate_off_is_unavailable_not_broken(self):
        from unittest.mock import patch
        import market_platform_foundation.crypto_market.kraken_stream as ks
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('IMP_CRYPTO_LIVE', None)
            _h, service = self.service()
            health = service.provider_health(dict(universe='CRYPTO'))
        self.assertEqual(health['state'], 'UNAVAILABLE')
        self.assertEqual(health['reasons'], ['CRYPTO_NOT_CONFIGURED'])
        self.assertEqual(health['provider'], 'KRAKEN')
        self.assertEqual(health['detail']['stream']['instruments'], {})

    def test_provider_health_probes_the_authorized_supply_and_carries_upstream_verdict(self):
        from unittest.mock import patch
        import market_platform_foundation.ui_api.screener_crypto as screener_crypto
        verdict = ('CONNECTED', (), dict(catalog_as_of='c', snapshot_as_of='s', instruments=2, priced=2))
        with patch.dict('os.environ', {'IMP_CRYPTO_LIVE': '1'}), patch.object(screener_crypto, 'crypto_supply_health', return_value=verdict):
            _h, service = self.service()
            health = service.provider_health(dict(universe='CRYPTO'))
        self.assertEqual(health['state'], 'CONNECTED')
        self.assertEqual(health['reasons'], [])
        self.assertEqual(health['detail']['instruments'], 2)
        self.assertEqual(health['detail']['stream']['instruments'], {})

        verdict = ('UNAVAILABLE', ('MARKET_SNAPSHOT_INCOMPLETE',), dict(catalog_as_of='c', instruments=2, priced=0))
        with patch.dict('os.environ', {'IMP_CRYPTO_LIVE': '1'}), patch.object(screener_crypto, 'crypto_supply_health', return_value=verdict):
            _h, service = self.service()
            health = service.provider_health(dict(universe='CRYPTO'))
        self.assertEqual(health['state'], 'UNAVAILABLE')
        self.assertEqual(health['reasons'], ['MARKET_SNAPSHOT_INCOMPLETE'])

    def test_provider_health_observed_stream_runtime_carries_execution_detail(self):
        import threading
        from unittest.mock import patch
        import market_platform_foundation.crypto_market.kraken_stream as ks
        import market_platform_foundation.ui_api.screener_crypto as screener_crypto

        class StubRuntime:
            def __init__(self):
                self._lock = threading.RLock()
                self.lifecycle = SimpleNamespace(connection_state='CONNECTED', last_received_ns=42)
                self._consumers = {('BTC/USD', 'BOOK'): {'paper-automation-candidates'},
                                   ('BTC/USD', 'TRADES'): {'paper-automation-candidates'}}
                self.state = SimpleNamespace(trades_for=lambda iid: [1, 2, 3])

        verdict = ('CONNECTED', (), dict(catalog_as_of='c', snapshot_as_of='s', instruments=2, priced=2))
        original = getattr(ks, '_RUNTIME', None)
        try:
            ks._RUNTIME = StubRuntime()
            with patch.dict('os.environ', {'IMP_CRYPTO_LIVE': '1'}), patch.object(screener_crypto, 'crypto_supply_health', return_value=verdict):
                _h, service = self.service()
                health = service.provider_health(dict(universe='CRYPTO'))
            self.assertEqual(health['state'], 'CONNECTED')
            self.assertEqual(health['detail']['stream'], dict(connection_state='CONNECTED', last_received_ns=42,
                                                             instruments={'BTC/USD': 3}))
        finally:
            if original is None:
                ks._RUNTIME = None
            else:
                ks._RUNTIME = original

    def crypto_service(self, stub_runtime):
        h, service = self.service()
        service._reevaluation = Mock()
        service._reevaluation.bound_scope = dict(universe='CRYPTO')
        service._reevaluation._loop.return_value = dict(selected=['BTC'], pending_selection=None)
        service._crypto_stream_runtime = lambda *, create: stub_runtime(create)
        return h, service

    def test_crypto_candidates_subscribe_their_own_pairs_once(self):
        calls = []

        class StubRuntime:
            def subscribe(self, *, instrument_id, capabilities, consumer_id):
                calls.append(('subscribe', instrument_id, tuple(capabilities), consumer_id))
                return [dict(accepted=True, reason=None)]

            def unsubscribe(self, **kwargs):
                calls.append(('unsubscribe', kwargs.get('instrument_id')))

        service = self.crypto_service(lambda create: StubRuntime())[1]
        work, summary = dict(), dict(actions=[], blockers=[])
        service._candidate_quotes(work, summary)
        self.assertEqual(work['subscriptions'], ['BTC'])
        self.assertNotIn('quote_refusals', summary)
        self.assertEqual(calls, [('subscribe', 'BTC', ('BOOK', 'TRADES'), 'paper-automation-candidates')])
        # A second cycle with the same selection subscribes nothing new.
        service._candidate_quotes(work, summary)
        self.assertEqual(calls, [('subscribe', 'BTC', ('BOOK', 'TRADES'), 'paper-automation-candidates')])

    def test_crypto_candidate_venue_refusal_is_recorded_not_worked_around(self):
        class StubRuntime:
            def subscribe(self, *, instrument_id, capabilities, consumer_id):
                if instrument_id == 'BTC':
                    return [dict(accepted=False, reason='VETOED_AT_EVENT_TIME')]
                return [dict(accepted=True, reason=None)]

        service = self.crypto_service(lambda create: StubRuntime())[1]
        work, summary = dict(), dict(actions=[], blockers=[])
        service._candidate_quotes(work, summary)
        self.assertEqual(work['subscriptions'], [])
        self.assertEqual(summary['quote_refusals'],
                         [dict(universe='CRYPTO', instrument_id='BTC', reason='VETOED_AT_EVENT_TIME')])

    def test_crypto_release_never_creates_demand(self):
        requests = []

        class StubRuntime:
            def unsubscribe(self, *, instrument_id, capabilities, consumer_id):
                requests.append(('unsubscribe', instrument_id))

        runtime = StubRuntime()
        h, service = self.service()
        service._reevaluation = Mock()
        service._reevaluation.bound_scope = dict(universe='CRYPTO')
        service._crypto_stream_runtime = lambda *, create: (requests.append(('get', create)), (None if False else runtime))[1]
        service._release_candidate_quotes(['BTC'])
        self.assertEqual(requests, [('get', False), ('unsubscribe', 'BTC')])

        requests.clear()
        service._crypto_stream_runtime = lambda *, create: (requests.append(('get', create)), None)[1]
        service._release_candidate_quotes(['BTC'])
        self.assertEqual(requests, [('get', False)])  # no runtime, no unsubscribe attempted, no demand created

    def test_crypto_demand_is_not_created_while_the_local_writer_owns_kraken(self):
        import market_platform_foundation.market_data.persistence as persistence
        import market_platform_foundation.crypto_market.kraken_stream as ks

        writer = SimpleNamespace(sources=('kraken', 'moomoo'))
        original_writer, original_runtime = persistence.active_writer, getattr(ks, '_RUNTIME', None)
        probe = []
        try:
            persistence.active_writer = lambda: writer
            ks._RUNTIME = None
            _h, service = self.service()
            probe.append(service._crypto_stream_runtime(create=True))
            self.assertIsNone(probe[-1], msg='a second collector stream must not be created under the owner writer')
        finally:
            persistence.active_writer = original_writer
            if original_runtime is None:
                ks._RUNTIME = None
            else:
                ks._RUNTIME = original_runtime
