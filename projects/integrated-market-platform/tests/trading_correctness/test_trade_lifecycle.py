"""OCT1-10 — trade lifecycle read model over the canonical authorities.

SOFTWARE_CONTROLLED. The production action-decision service, SMA stop service,
Paper preview/submit route, simulator, experiment ledger and the lifecycle
projection are used. Only the clock, the completed-bar feed, the marks, the
candidate receipts, the model proposal and the reevaluation receipts are
controlled fixtures. Nothing here is market evidence or a profitability claim.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.intelligence.inference.trade_lifecycle import (
    ENTRY_STATES, EXIT_STATES, MAX_EVIDENCE, MAX_SELECTED, STAGES,
)
from market_platform_foundation.intelligence.persistence.memory import InMemoryIntelligenceRepository
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.platform.security.route_policy import policy_for_route
from market_platform_foundation.rt01.execution_decision_trace.repository import InMemoryExecutionDecisionTraceRepository
from market_platform_foundation.ui_api.paper_projections import preview_paper_order, submit_paper_order
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_lifecycle import TradeLifecycleService
from market_platform_foundation.ui_api.server import UiApiHandler
from tests.intelligence.test_action_decision import candidate, proposal
from tests.trading_correctness.test_paper_experiment_api import _Base

MINUTE = 60_000_000_000
A, N = 'AAPL', 'NVDA'


def iso(seconds):
    from datetime import UTC, datetime
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z')


class Model:
    """Bounded proposal for the requested state, disclosing the packet's own conflicts and gaps."""
    provider_id, model_id, runtime = 'fixture', 'controlled', 'LOCAL_MODEL'

    def __init__(self):
        self.state, self.calls = 'NO_ACTION', 0

    def infer(self, packet, *, rendered_prompt, config):
        self.calls += 1
        packet_candidate = packet.candidates[0]
        value = proposal(self.state, None if self.state == 'NO_ACTION' else 'LONG')
        value['conflicting_refs'] = sorted({r for a in packet_candidate['alignments'] if a['result'] == 'CONFLICTING' for r in a['sentiment_refs']})
        value['missing_capabilities'] = [m['capability'] for m in packet_candidate['missing']]
        return ProviderInferenceResponse(json.dumps(value), self.provider_id, self.model_id, simulated=True, tokens_input=1, tokens_output=1, latency_ms=1)


class _Lifecycle(_Base):
    def setUp(self):
        super().setUp()
        self.create()
        self.t = time.time()
        self._ns = 0

        def now_ns():
            self._ns = max(int(self.t * 1e9), self._ns + 1_000)
            return self._ns
        self.feed.now_ns = now_ns  # fills and marks share the decisions' controlled clock
        self.clock = lambda: self.t
        self.anchor = int(self.t * 1e9) - 10 * MINUTE
        self.closes, self.quote = [], 150.0
        self.cycle_rows, self.orders = [], 0
        self.repo = ActionDecisionRepository()
        self.model = Model()
        self.packets = {}
        self.ai = SimpleNamespace(
            _news_service=lambda: SimpleNamespace(synthesis_provider=lambda: self.model), _query=lambda body: body,
            _packet=lambda scope, **_: (scope, [self.packet(i, self.quote, 2) for i in (A, N)], iso(self.t), {}))
        self.actions = ScreenerActionService(self.store, repository=self.repo, clock=self.clock, ai=self.ai,
                                             trace_repository=InMemoryExecutionDecisionTraceRepository())
        self.stops = SmaStopService(
            self.store, repository=SmaStopRepository(), clock=self.clock, actions=self.actions, ai=self.ai,
            bars=lambda instrument, policy, scale: dict(state='CURRENT', reason=None, source='CONTROLLED_FIXTURE', bars=self.bars()),
            quotes=lambda instrument, scale: dict(admissible=True, price_minor=int(round(self.quote * 100)), as_of_ns=int(self.t * 1e9),
                                                  source='CONTROLLED_FIXTURE', evidence_ref='q', reason=None))
        self.actions.risk_control = self.stops
        self.store._action_decision_service, self.store._sma_stop_service = self.actions, self.stops
        self.store.strategy_repository = InMemoryIntelligenceRepository()
        self.reevaluation = SimpleNamespace(
            repository=SimpleNamespace(latest_loop=lambda account: dict(loop_id='RL-1'), cycles=lambda loop_id, limit=20: list(self.cycle_rows)),
            status=lambda: dict(worker_state='RUNNING', worker_label='Running', requested_cadence_seconds=60, effective_cadence_seconds=120,
                                liveness=dict(last_completed=iso(self.t))))
        self.service = TradeLifecycleService(self.store, actions=self.actions, stops=self.stops, reevaluation=self.reevaluation, clock=self.clock)

    # --- controlled inputs ----------------------------------------------------------
    def tick(self, seconds=1.0):
        self.t += seconds

    def bars(self):
        return [dict(bar_id=f'B{i}', event_time=self.anchor + i * MINUTE, available_time=self.anchor + (i + 1) * MINUTE,
                     open=c, high=c, low=c, close=c) for i, c in enumerate(self.closes)]

    def bar(self, close):
        self.closes.append(close)
        self.t = max(self.t, (self.anchor + len(self.closes) * MINUTE) / 1e9 + 0.001)

    def packet(self, instrument, price, change):
        c = candidate()
        c['sufficient'] = True
        c['instrument'] = dict(instrument_id=instrument, symbol=instrument, universe='US_EQUITIES')
        for e in c['current_market_evidence']:
            e.update(as_of=iso(self.t), valid_until=iso(self.t + 600), instrument_id=instrument, source='CONTROLLED_FIXTURE',
                     delivery_mode='FIXTURE', freshness_status='CURRENT')
        c['current_market_evidence'][0]['facts']['price'] = price
        c['current_market_evidence'][1]['facts']['change_pct'] = change
        c['reference_evidence'] = [dict(c['current_market_evidence'][1], evidence_id='news-conflict', capability='SENTIMENT',
                                        role='REFERENCE_CONTEXT', facts=dict(label='NEGATIVE'), delivery_mode='PUBLICATION_BASED',
                                        freshness_status='PUBLICATION_CURRENT')]
        c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['news-conflict'], news_refs=[], kind='NEWS_SENTIMENT_VS_PRICE',
                                method='CONTROLLED_FIXTURE', observed_direction='POSITIVE', comparator_ref='t', cutoff=iso(self.t),
                                alignment_id='AL-1', limitations=['Fixture conflict'])]
        c['missing'] = [dict(capability='OPTIONS', reason='NO_INTERNAL_EVIDENCE')]
        c['blocked'] = [dict(capability='LEVEL2', role='CURRENT_MARKET', source='CONTROLLED_FIXTURE', as_of=iso(self.t - 900),
                             reason_codes=['AGE_EXCEEDS_POLICY'], freshness_status='STALE', decision_admissibility='BLOCKED')]
        return c

    def new_run(self, *instruments, change=2, price=150.0):
        """A stored AI Screener run that selected these instruments, in rank order."""
        self.tick()
        self.runs = getattr(self, 'runs', 0) + 1
        identity = f'run-{self.runs}'
        self.store.strategy_repository.put_opportunity(OpportunityV1(
            'opp-' + identity, '1', IntelligenceScope(tuple(instruments)), int((self.t - 1) * 1e9), QualitySummary('GOOD'), side='LONG',
            valid_until_ns=int((self.t + 600) * 1e9)))
        self.repo.put('candidate_run', identity, dict(
            schema_version='ai-screener-output/1.0.0', run_id=identity, state='CURRENT', valid_until=iso(self.t + 600), input_hash=identity,
            decision_cutoff=iso(self.t), generated_at=iso(self.t), provider_id='fixture', model_id='controlled', prompt_id='screener.ai_candidate_reduction.v2',
            prompt_version='2', simulated=True, limitations=[], evidence=[self.packet(i, price, change) for i in instruments],
            candidates=[dict(instrument_id=i, rank=rank, rationale=f'{i} shows observed strength.', supporting_refs=['q', 't'],
                             conflicting_refs=['news-conflict'], weak_refs=[], missing_capabilities=['OPTIONS'], uncertainties=[])
                        for rank, i in enumerate(instruments, 1)]))
        return identity

    def decide(self, run_id, state, instrument=A, *, opportunity=True):
        self.model.state = state
        body = dict(run_id=run_id, instrument_id=instrument)
        if opportunity and state in ('ENTER', 'CONSIDER_ENTRY'):
            body['opportunity_id'] = 'opp-' + run_id
        return self.actions.run(body)

    def governed(self, decision, *, quantity=None, price='150.00'):
        """The existing governed handoff, then the production preview and submit route."""
        draft = self.actions.handoff(dict(decision_id=decision['decision_id']))
        kind, _, source_id = draft['sourceAttentionId'].partition(':')
        self.orders += 1
        key = f'oct110-{self.orders}'
        self.feed.prices[draft['instrumentId']] = price
        body = dict(client_order_id=key, idempotency_key=key, instrument_id=draft['instrumentId'], order_type='MARKET',
                    quantity=quantity or draft['quantity'], side=draft['side'], correlation_id=draft['sourceAttentionId'],
                    decision_source_snapshot=dict(source_type='watched_opportunity' if kind == 'opportunity' else 'workspace_lane',
                                                  source_id=source_id, **draft['sourceContext']))
        preview = preview_paper_order(self.store, body)['preview']
        return submit_paper_order(self.store, {**body, 'preview_id': preview['preview_id']})['submission']

    def enter(self, *, instrument=A, quantity=6, price='150.00', run=None):
        run = run or self.new_run(instrument, price=float(price))
        decision = self.decide(run, 'ENTER', instrument)
        self.assertEqual((decision['action_state'], decision['execution_readiness']), ('ENTER', 'PREVIEW_ALLOWED'), decision['blocker_codes'])
        self.governed(decision, quantity=quantity, price=price)
        return run, decision

    def exit(self, *, instrument=A, price='152.00'):
        self.quote = float(price)
        decision = self.decide(self.new_run(instrument, change=-2, price=float(price)), 'EXIT', instrument)
        self.assertEqual((decision['action_state'], decision['execution_readiness']), ('EXIT', 'PREVIEW_ALLOWED'), decision['blocker_codes'])
        return decision

    def listing(self, run=None, **kwargs):
        return self.service.list(run_id=run, **kwargs)

    def only(self, rows):
        self.assertEqual(len(rows), 1, [r['symbol'] for r in rows])
        return rows[0]


class SemanticTruthTests(_Lifecycle):
    def test_selected_candidate_shows_rank_and_every_evidence_group(self):
        run = self.new_run(A, N)
        rows = self.listing(run)['selected']
        self.assertEqual([(r['candidate']['rank'], r['symbol'], r['stage']) for r in rows],
                         [(1, A, 'SELECTED_NOT_ASSESSED'), (2, N, 'SELECTED_NOT_ASSESSED')])
        self.assertEqual(rows[0]['candidate']['evidence'], dict(counts=dict(supporting=2, conflicting=2, weak=0, missing=1, blocked=1)))
        detail = self.service.detail(rows[0]['lifecycle_id'], run_id=run)
        evidence = detail['candidate']['evidence']
        self.assertEqual([e['capability'] for e in evidence['supporting']['items']], ['QUOTE', 'TECHNICALS'])
        # Conflicts, gaps and blocked inputs stay as visible as support.
        self.assertEqual(evidence['conflicting']['items'][0]['evidence_id'], 'news-conflict')
        self.assertEqual(evidence['conflicting_alignments'][0]['result'], 'CONFLICTING')
        self.assertEqual(evidence['missing'], ['OPTIONS'])
        self.assertEqual((evidence['blocked'][0]['capability'], evidence['blocked'][0]['freshness_status']), ('LEVEL2', 'STALE'))
        quote = evidence['supporting']['items'][0]
        self.assertEqual((quote['source'], quote['freshness_status'], quote['fact']), ('CONTROLLED_FIXTURE', 'CURRENT', 'price: 150.0'))
        self.assertEqual(evidence['conflicting']['items'][0]['freshness_status'], 'PUBLICATION_CURRENT')
        self.assertEqual((detail['position']['state'], detail['entry']['status'], detail['exit']['status']), ('FLAT', 'NOT_PROPOSED', 'NO_EXIT'))

    def test_no_action_is_a_complete_flat_lifecycle(self):
        run = self.new_run(A)
        self.decide(run, 'NO_ACTION')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['decision']['action_state'], row['entry']['status'], row['position']['state']),
                         ('NO_ACTION', 'NO_ACTION', 'NOT_PROPOSED', 'FLAT'))
        self.assertIsNone(row['entry']['fill'])
        self.assertEqual((row['pnl']['realized_minor'], row['pnl']['unrealized_minor'], row['pnl']['quality']), (None, None, 'NOT_APPLICABLE'))
        self.assertEqual(self.store.paper_ledger.project_fills(), [])

    def test_consider_entry_has_no_paper_fill(self):
        run = self.new_run(A)
        self.decide(run, 'CONSIDER_ENTRY')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['entry']['status'], row['entry']['paper'], row['position']['state']),
                         ('CONSIDERING_ENTRY', 'CONSIDERED', 'NO_FILL', 'FLAT'))

    def test_enter_without_fill_is_decided_not_executed_and_never_a_position(self):
        run = self.new_run(A)
        decision = self.decide(run, 'ENTER')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['entry']['status'], row['entry']['paper']), ('ENTER_NOT_EXECUTED', 'DECIDED_ENTER', 'NO_FILL'))
        self.assertEqual((row['position']['state'], row['position']['quantity'], row['kind']), ('FLAT', 0, 'CANDIDATE'))
        # The decision reference is a quote, not an entry price.
        self.assertEqual(row['entry']['decision_reference']['price'], '150.0')
        self.assertEqual(row['entry']['decision_reference']['decision_time'], decision['decision_time'])
        self.assertIsNone(row['entry']['fill'])
        self.assertIsNone(row['entry']['average_price_minor'])

    def test_expired_decision_requires_revalidation_and_is_not_execution_ready(self):
        run = self.new_run(A)
        self.decide(run, 'ENTER')
        self.tick(700)
        late = self.decide(run, 'ENTER', opportunity=False)
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((late['action_state'], row['stage'], row['decision']['action_state']),
                         ('REVALIDATION_REQUIRED', 'REVALIDATION_REQUIRED', 'REVALIDATION_REQUIRED'))
        self.assertIn('CANDIDATE_EXPIRED', row['decision']['blocker_codes'])
        self.assertEqual((row['decision']['execution_readiness'], row['decision']['origin'], row['entry']['status']),
                         ('BLOCKED', 'SERVER_FAILSAFE', 'BLOCKED'))
        self.assertIs(row['freshness']['decision_current'], False)

    def test_open_position_uses_fill_time_and_price_not_the_decision(self):
        run, decision = self.enter(price='150.00')
        self.feed.mark(self.store, A, '151.00')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['kind'], row['entry']['status'], row['entry']['paper']),
                         ('POSITION_OPEN', 'POSITION_EPISODE', 'FILLED', 'SIMULATED_FILL'))
        self.assertEqual((row['position']['state'], row['position']['quantity'], row['position']['average_entry_minor']), ('LONG', 6, 15000))
        fill = row['entry']['fill']
        self.assertEqual((fill['price_minor'], fill['kind'], fill['is_market_truth'], fill['decision_id']),
                         (15000, 'SIMULATED_PAPER_FILL', False, decision['decision_id']))
        self.assertNotEqual(fill['time'], decision['decision_time'])
        self.assertEqual(row['entry']['decision_reference']['price'], '150.0')
        mark = row['position']['mark']
        self.assertEqual((mark['price_minor'], mark['quality'], mark['source']), (15100, 'CURRENT', 'CONTROLLED_FIXTURE'))
        # Current mark moves; the historical fill does not.
        self.assertEqual((row['pnl']['unrealized_minor'], row['pnl']['quality']), (600, 'CURRENT'))
        self.feed.mark(self.store, A, '149.00')
        again = self.only(self.listing(run)['selected'])
        self.assertEqual((again['entry']['fill']['price_minor'], again['pnl']['unrealized_minor']), (15000, -600))

    def test_stale_mark_never_reads_as_current_pnl(self):
        run, _ = self.enter()
        self.feed.mark(self.store, A, '151.00', quality='STALE')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['position']['mark']['quality'], row['pnl']['quality'], row['freshness']['mark_quality']), ('STALE', 'STALE', 'STALE'))
        self.store.paper_ledger.clear_mark(A)
        row = self.only(self.listing(run)['selected'])
        # No mark: unavailable, never a zero.
        self.assertEqual((row['position']['mark']['price_minor'], row['pnl']['unrealized_minor'], row['pnl']['quality']), (None, None, 'UNAVAILABLE'))

    def test_exit_decision_without_close_fill_keeps_the_position_open(self):
        run, _ = self.enter()
        decision = self.exit()
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['decision']['action_state'], row['exit']['status'], row['exit']['paper_close']),
                         ('EXIT_NOT_EXECUTED', 'EXIT', 'EXIT_DECIDED', 'NOT_SUBMITTED'))
        self.assertEqual((row['position']['state'], row['position']['quantity']), ('LONG', 6))
        self.assertIsNone(row['exit']['fill'])
        self.assertEqual(row['exit']['decision_reference']['decision_id'], decision['decision_id'])

    def test_missing_stop_is_stated_and_never_a_zero_level(self):
        run, _ = self.enter()
        risk = self.only(self.listing(run)['selected'])['risk_control']
        self.assertEqual((risk['status'], risk['stop'], risk['configured'], risk['model']), ('NOT_CONFIGURED', None, False, 'none'))

    def test_complete_closed_trade_has_every_acceptance_field(self):
        run, entered = self.enter(price='150.00')
        self.tick()
        held = self.decide(self.new_run(A, price=151.0), 'HOLD')
        self.assertEqual(held['action_state'], 'HOLD')
        exited = self.exit(price='152.00')
        self.governed(exited, price='152.00')
        listing = self.listing()
        row = self.only(listing['recent_closed'])
        self.assertEqual(listing['active_managed'], [])
        self.assertEqual((row['stage'], row['group'], row['ai_selected'], row['position_origin']),
                         ('POSITION_CLOSED', 'RECENT_CLOSED', True, 'AI_DECISION_GOVERNED'))
        self.assertEqual((row['candidate']['rank'], row['candidate']['run_id'], row['origin']['run_id']), (1, run, run))
        self.assertEqual((row['entry']['status'], row['entry']['fill']['price_minor'], row['exit']['status'], row['exit']['fill']['price_minor']),
                         ('FILLED', 15000, 'CLOSED', 15200))
        self.assertEqual((row['position']['state'], row['position']['quantity'], row['exit']['paper_close']), ('FLAT', 0, 'FILLED'))
        self.assertEqual((row['pnl']['realized_minor'], row['pnl']['unrealized_minor'], row['pnl']['quality']), (1200, None, 'REALIZED'))
        detail = self.service.detail(row['lifecycle_id'])
        events = [(r['kind'], r.get('action_state') or r.get('position_effect')) for r in detail['timeline']]
        self.assertEqual(events, [('CANDIDATE_SELECTED', None), ('DECISION', 'ENTER'), ('PAPER_ORDER', None), ('PAPER_FILL', 'OPEN'),
                                  ('DECISION', 'HOLD'), ('DECISION', 'EXIT'), ('PAPER_ORDER', None), ('PAPER_FILL', 'CLOSE')])
        self.assertEqual([d['decision_id'] for d in detail['decisions']], [entered['decision_id'], held['decision_id'], exited['decision_id']])
        self.assertTrue(all(r['at'] and r['event'] and r['source'] and r['ref']['id'] for r in detail['timeline']))
        self.assertEqual(detail['experiment']['capital_kind'], 'SIMULATED')
        self.assertEqual((detail['experiment']['execution'], detail['experiment']['live_capital']), ('INTERNAL_SIMULATION', False))

    def test_pnl_matches_the_ledger_trade_and_valuation_authorities(self):
        self.enter(quantity=5, price='150.00')
        self.governed(self.exit(price='153.00'), price='153.00')
        ledger = self.store.paper_ledger
        row = self.only(self.listing()['recent_closed'])
        self.assertEqual(row['pnl']['realized_minor'], sum(t['realized_pnl_delta_minor'] for t in ledger.project_trades()))
        self.assertEqual(row['pnl']['realized_minor'], ledger.project_valuation()['realized_pnl_minor'])
        self.assertEqual(row['pnl']['realized_minor'], ledger.project_account()['realized_pnl_minor'])
        self.assertEqual(row['pnl']['costs_minor'], ledger.project_valuation()['total_transaction_costs_minor'])


class EpisodeIdentityTests(_Lifecycle):
    def test_two_episodes_of_one_symbol_never_share_entry_stop_or_pnl(self):
        first_run, first = self.enter(quantity=5, price='150.00')
        self.governed(self.exit(price='151.00'), price='151.00')
        self.tick()
        second_run, second = self.enter(quantity=3, price='160.00')
        listing = self.listing(second_run)
        current = self.only(listing['selected'])
        closed = self.only(listing['recent_closed'])
        self.assertNotEqual(current['lifecycle_id'], closed['lifecycle_id'])
        self.assertEqual((current['entry']['fill']['price_minor'], current['position']['quantity'], current['pnl']['realized_minor']), (16000, 3, 0))
        self.assertEqual((closed['entry']['fill']['price_minor'], closed['exit']['fill']['price_minor'], closed['pnl']['realized_minor']), (15000, 15100, 500))
        self.assertEqual((current['origin']['run_id'], closed['origin']['run_id']), (second_run, first_run))
        detail = self.service.detail(current['lifecycle_id'], run_id=second_run)
        self.assertEqual([d['decision_id'] for d in detail['decisions']], [second['decision_id']])
        self.assertNotIn(first['decision_id'], json.dumps(detail['timeline']))
        self.assertEqual([p['lifecycle_id'] for p in detail['prior_episodes']], [closed['lifecycle_id']])
        old = self.service.detail(closed['lifecycle_id'], run_id=second_run)
        # The newest run selects the symbol again; the closed episode keeps the run it was opened from.
        self.assertEqual((old['candidate']['run_id'], old['group']), (first_run, 'RECENT_CLOSED'))
        self.assertNotIn(second['decision_id'], json.dumps(old))

    def test_new_candidate_after_a_closed_episode_inherits_nothing(self):
        self.enter(quantity=5, price='150.00')
        self.governed(self.exit(price='151.00'), price='151.00')
        fresh = self.new_run(A)
        row = self.only(self.listing(fresh)['selected'])
        self.assertEqual((row['kind'], row['stage'], row['position']['state'], row['entry']['status'], row['exit']['status']),
                         ('CANDIDATE', 'SELECTED_NOT_ASSESSED', 'FLAT', 'NOT_PROPOSED', 'NO_EXIT'))
        self.assertEqual((row['entry']['fill'], row['pnl']['realized_minor'], row['risk_control']['stop'], row['decision']), (None, None, None, None))
        detail = self.service.detail(row['lifecycle_id'], run_id=fresh)
        self.assertEqual(len(detail['prior_episodes']), 1)
        self.assertEqual(detail['prior_episodes'][0]['realized_pnl_minor'], 500)

    def test_active_position_stays_visible_when_the_newest_run_drops_it(self):
        run_a, _ = self.enter()
        run_b = self.new_run(N)
        listing = self.listing(run_b)
        self.assertEqual([r['symbol'] for r in listing['selected']], [N])
        managed = self.only(listing['active_managed'])
        self.assertEqual((managed['symbol'], managed['group'], managed['stage'], managed['position']['quantity']), (A, 'ACTIVE_MANAGED', 'POSITION_OPEN', 6))
        # It is shown with the run that selected it, never as a pick of the newest run.
        self.assertEqual((managed['candidate']['run_id'], managed['candidate']['selected_in_current_run'], managed['origin']['same_as_current_run']),
                         (run_a, False, False))
        self.assertEqual(self.only(self.listing()['active_managed'])['lifecycle_id'], managed['lifecycle_id'])

    def test_position_reselected_by_a_later_run_keeps_its_origin(self):
        run_a, _ = self.enter()
        run_b = self.new_run(A)
        row = self.only(self.listing(run_b)['selected'])
        self.assertEqual((row['candidate']['run_id'], row['candidate']['selected_in_current_run'], row['origin']['run_id'], row['origin']['same_as_current_run']),
                         (run_b, True, run_a, False))
        self.assertEqual(self.listing(run_b)['active_managed'], [])

    def test_scale_in_shows_average_first_entry_and_both_fills(self):
        run, _ = self.enter(quantity=4, price='150.00')
        self.tick()
        self.order(A, 'BUY', 4, '152.00')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['position']['quantity'], row['position']['average_entry_minor'], row['entry']['fill_count'], row['entry']['average_price_minor']),
                         (8, 15100, 2, 15100))
        self.assertEqual(row['entry']['fill']['price_minor'], 15000)
        detail = self.service.detail(row['lifecycle_id'], run_id=run)
        self.assertEqual([f['position_effect'] for f in detail['entry']['fills']], ['OPEN', 'ADD'])
        self.assertEqual(detail['position']['first_entry_time'], detail['entry']['fills'][0]['time'])

    def test_partial_exit_keeps_the_episode_open_with_split_pnl(self):
        run, _ = self.enter(quantity=6, price='150.00')
        self.tick()
        self.order(A, 'SELL', 2, '152.00')
        self.feed.mark(self.store, A, '153.00')
        row = self.only(self.listing(run)['selected'])
        self.assertEqual((row['stage'], row['exit']['status'], row['position']['quantity']), ('POSITION_OPEN', 'PARTIALLY_CLOSED', 4))
        self.assertEqual((row['pnl']['realized_minor'], row['pnl']['unrealized_minor'], row['exit']['closed_quantity']), (400, 1200, 2))
        self.assertIsNone(row['exit']['fill'])
        self.assertEqual(self.listing(run)['recent_closed'], [])

    def test_unlinked_paper_activity_is_shown_and_never_called_ai_selected(self):
        self.order(N, 'BUY', 2, '300.00')
        listing = self.listing()
        row = self.only(listing['unlinked'])
        self.assertEqual(listing['active_managed'], [])
        self.assertEqual((row['group'], row['ai_selected'], row['position_origin'], row['candidate'], row['decision']),
                         ('UNLINKED_PAPER_ACTIVITY', False, 'UNLINKED_PAPER_ACTIVITY', None, None))
        self.assertEqual((row['origin']['lineage'], row['lineage']['candidate'], row['position']['quantity']), ('LINEAGE_UNAVAILABLE', 'LINEAGE_UNAVAILABLE', 2))
        # Selected later by an AI run, the manual position is still not AI-governed.
        picked = self.only(self.listing(self.new_run(N))['selected'])
        self.assertEqual((picked['ai_selected'], picked['position_origin'], picked['origin']['lineage']), (True, 'UNLINKED_PAPER_ACTIVITY', 'LINEAGE_UNAVAILABLE'))

    def test_lists_are_bounded_and_closed_episodes_page(self):
        for index in range(3):
            self.enter(quantity=1, price='150.00')
            self.governed(self.exit(price='151.00'), price='151.00')
            self.tick()
        first = self.listing(closed_limit=2)
        self.assertEqual((len(first['recent_closed']), first['counts']['recent_closed']), (2, 3))
        second = self.listing(closed_limit=2, closed_before=first['next_closed_before'])
        self.assertEqual(len(second['recent_closed']), 1)
        self.assertIsNone(second['next_closed_before'])
        self.assertEqual(len({r['lifecycle_id'] for r in (*first['recent_closed'], *second['recent_closed'])}), 3)
        many = self.new_run(*[A, N])
        self.assertLessEqual(len(self.listing(many)['selected']), MAX_SELECTED)
        self.assertEqual(self.listing(closed_limit=999)['bounds']['recent_closed'], 20)


class RiskAndHistoryTests(_Lifecycle):
    def arm(self):
        """LONG 6 with an active 140.00 stop under a 150.00 market."""
        run, entered = self.enter(quantity=6, price='150.00')
        self.stops.configure(dict(enabled=True, sma_window_bars=2))
        # Bars complete after the entry, as they do for a monitored position.
        self.anchor, self.closes = int(self.t * 1e9), []
        self.bar(14000)
        self.bar(14000)
        self.stops.evaluate(A)
        return run, entered

    def test_active_stop_context_comes_from_the_stop_service(self):
        run, _ = self.arm()
        risk = self.only(self.listing(run)['selected'])['risk_control']
        status = self.stops.status(A)
        self.assertEqual((risk['status'], risk['stop']['active_stop'], risk['stop']['sma_value'], risk['policy']['sma_window_bars']),
                         ('ACTIVE', status['stop']['active_stop'], status['stop']['sma_value'], 2))
        self.assertEqual((risk['stop']['distance_to_stop'], risk['origin'], risk['model']), (status['stop']['distance_to_stop'], 'DETERMINISTIC_RISK_CONTROL', 'none'))

    def test_stop_breach_is_a_deterministic_exit_and_the_position_stays_open(self):
        run, _ = self.arm()
        calls = self.model.calls
        self.quote = 139.0
        self.tick()
        self.stops.evaluate_now(dict(instrument_id=A))
        row = self.only(self.listing(run)['selected'])
        self.assertEqual(self.model.calls, calls)
        self.assertEqual((row['stage'], row['risk_control']['status'], row['decision']['action_state'], row['decision']['origin'], row['decision']['model']),
                         ('EXIT_NOT_EXECUTED', 'BREACHED', 'EXIT', 'DETERMINISTIC_RISK_CONTROL', None))
        self.assertEqual((row['position']['state'], row['exit']['status'], row['exit']['paper_close']), ('LONG', 'EXIT_DECIDED', 'NOT_SUBMITTED'))
        self.assertEqual((row['decision']['risk_exit']['active_stop'], row['decision']['risk_exit']['trigger_price'], row['risk_control']['stop']['trigger_price']),
                         ('140', '139', '139'))
        self.assertEqual(row['risk_control']['exit_decision_id'], row['decision']['decision_id'])
        detail = self.service.detail(row['lifecycle_id'], run_id=run)
        stops = [r['stop_kind'] for r in detail['timeline'] if r['kind'] == 'STOP']
        self.assertIn('BREACHED', stops)
        last = detail['timeline'][-1]
        self.assertEqual((last['event'], last['source']), ('Risk control: EXIT', 'Deterministic risk control'))
        # The close is a separate, explicit Paper fill.
        self.governed(self.repo.get('decision', row['decision']['decision_id']), price='139.00')
        closed = self.only(self.listing()['recent_closed'])
        self.assertEqual((closed['stage'], closed['exit']['fill']['price_minor'], closed['pnl']['realized_minor']), ('POSITION_CLOSED', 13900, -6600))
        self.assertEqual(closed['risk_control']['stop']['trigger_price'], '139')

    def test_timeline_orders_interleaved_decisions_stops_and_fills_by_event_time(self):
        run, _ = self.arm()
        held = self.decide(self.new_run(A, price=151.0), 'HOLD')
        self.cycle_rows = [dict(cycle_id='RC-1', trigger='SCHEDULED_CADENCE', transitions=[dict(new_decision_id=held['decision_id'], classification='STATE_CHANGED')])]
        self.bar(14400)
        self.stops.evaluate(A)
        self.governed(self.exit(price='152.00'), price='152.00')
        detail = self.service.detail(self.only(self.listing()['recent_closed'])['lifecycle_id'])
        rows = detail['timeline']
        times = [r['at'] for r in rows]
        self.assertEqual(times, sorted(times))
        events = [r['event'] for r in rows]
        tightened = len(events) - 1 - events[::-1].index('SMA stop tightened')
        self.assertLess(events.index('Reevaluation: HOLD'), tightened)
        self.assertLess(tightened, events.index('Action decision: EXIT'))
        self.assertEqual(events[-1], 'Paper simulated close fill — position closed')
        reevaluated = next(r for r in rows if r['event'] == 'Reevaluation: HOLD')
        self.assertEqual((reevaluated['clocks']['reevaluation_cycle'], reevaluated['clocks']['reevaluation_classification']), ('RC-1', 'STATE_CHANGED'))
        self.assertEqual(detail['reevaluation'], dict(worker_state='RUNNING', worker_label='Running', requested_cadence_seconds=60,
                                                      effective_cadence_seconds=120, last_completed=detail['reevaluation']['last_completed']))

    def test_reevaluation_receipts_join_by_decision_id_through_the_real_repository(self):
        from market_platform_foundation.local_state.reevaluation import ReevaluationRepository
        repository = ReevaluationRepository()
        account = self.store.paper_ledger.paper_account_id
        repository.save_loop(dict(loop_id='RL-real', account_id=account, updated_epoch=self.t))
        self.reevaluation.repository = repository
        run, _ = self.enter()
        self.tick()
        held = self.decide(self.new_run(A, price=151.0), 'HOLD')
        # A transition for another instrument's decision in the same receipt must not attach here.
        repository.put_cycle(dict(cycle_id='RC-real', loop_id='RL-real', scheduled_epoch=self.t, session_date='2026-10-06', model_call_count=1,
                                  trigger='MANUAL', transitions=[dict(instrument_id=A, new_decision_id=held['decision_id'], classification='STATE_CHANGED'),
                                                                 dict(instrument_id=N, new_decision_id='AD-other', classification='STATE_CHANGED'),
                                                                 dict(instrument_id=A, new_decision_id=None, classification='UNCHANGED')]))
        detail = self.service.detail(self.only(self.listing()['active_managed'])['lifecycle_id'])
        decisions = [r for r in detail['timeline'] if r['kind'] == 'DECISION']
        self.assertEqual([(r['event'], r['clocks']['reevaluation_cycle']) for r in decisions],
                         [('Action decision: ENTER', None), ('Reevaluation: HOLD', 'RC-real')])
        self.assertNotIn('AD-other', json.dumps(detail))

    def test_later_decisions_never_rewrite_earlier_history(self):
        run, entered = self.enter()
        self.tick()
        held = self.decide(self.new_run(A, price=151.0), 'HOLD')
        row = self.only(self.listing()['active_managed'])
        before = [r for r in self.service.detail(row['lifecycle_id'])['timeline'] if r['kind'] == 'DECISION']
        self.exit(price='149.00')
        after = [r for r in self.service.detail(row['lifecycle_id'])['timeline'] if r['kind'] == 'DECISION']
        self.assertEqual(after[:len(before)], before)
        self.assertEqual([r['action_state'] for r in after], ['ENTER', 'HOLD', 'EXIT'])
        self.assertEqual(after[1]['ref']['id'], held['decision_id'])

    def test_historical_decision_shows_its_own_frozen_evidence(self):
        run, entered = self.enter(price='150.00')
        self.tick()
        self.decide(self.new_run(A, price=175.0), 'HOLD')
        row = self.only(self.listing()['active_managed'])
        decisions = self.service.detail(row['lifecycle_id'])['decisions']
        old, new = decisions[0], decisions[-1]
        self.assertEqual((old['action_state'], old['reference_price'], old['evidence']['supporting']['items'][0]['fact']), ('ENTER', '150.0', 'price: 150.0'))
        self.assertEqual((new['action_state'], new['reference_price'], new['evidence']['supporting']['items'][0]['fact']), ('HOLD', '175.0', 'price: 175.0'))
        self.assertEqual(old['evidence_snapshot_id'], entered['evidence_snapshot_id'])
        self.assertEqual(old['evidence']['conflicting']['items'][0]['evidence_id'], 'news-conflict')

    def test_reading_a_lifecycle_calls_no_model_and_writes_nothing(self):
        run, _ = self.arm()
        calls, events, decisions = self.model.calls, len(self.store.paper_ledger.events), len(self.repo.history(A))
        stop_events = self.stops.repository.event_count(self.store.paper_ledger.paper_account_id, A)
        row = self.only(self.listing(run)['selected'])
        self.service.detail(row['lifecycle_id'], run_id=run)
        self.assertEqual((self.model.calls, len(self.store.paper_ledger.events), len(self.repo.history(A))), (calls, events, decisions))
        self.assertEqual(self.stops.repository.event_count(self.store.paper_ledger.paper_account_id, A), stop_events)


class ContractTests(_Lifecycle):
    def test_enums_nullability_and_bounds(self):
        run, _ = self.enter()
        self.new_run(N)
        listing = self.listing(run)
        self.assertEqual(listing['schema_version'], 'trade-lifecycle-list/1.0.0')
        self.assertEqual((listing['execution'], listing['experiment']['capital_kind']), ('SIMULATED_PAPER', 'SIMULATED'))
        row = self.only(listing['selected'])
        self.assertEqual(row['schema_version'], 'trade-lifecycle/1.0.0')
        self.assertIn(row['stage'], STAGES)
        self.assertIn(row['entry']['status'], ENTRY_STATES)
        self.assertIn(row['exit']['status'], EXIT_STATES)
        self.assertNotIn('timeline', row)
        self.assertNotIn('fills', row['entry'])
        self.assertEqual(set(row['candidate']['evidence']), {'counts'})
        self.assertLess(len(json.dumps(listing)), 32_000)
        detail = self.service.detail(row['lifecycle_id'], run_id=run)
        for group in ('supporting', 'conflicting', 'weak'):
            self.assertLessEqual(len(detail['candidate']['evidence'][group]['items']), MAX_EVIDENCE)
        self.assertLess(len(json.dumps(detail)), 128_000)
        self.assertIsNone(detail['exit']['fill'])
        self.assertEqual(detail['exit']['average_price_minor'], None)

    def test_unknown_and_malformed_requests_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'LIFECYCLE_NOT_FOUND'):
            self.service.detail('TE-unknown')
        with self.assertRaisesRegex(ValueError, 'INVALID_LIFECYCLE_REQUEST'):
            self.service.detail('x' * 200)
        with self.assertRaisesRegex(ValueError, 'INVALID_LIFECYCLE_REQUEST'):
            self.listing('')
        missing = self.listing('no-such-run')
        self.assertEqual((missing['run'], missing['selected'], missing['limitations']), (None, [], ['CANDIDATE_RUN_NOT_FOUND']))

    def test_reevaluation_and_risk_runs_are_never_listed_as_ai_selections(self):
        self.repo.put('candidate_run', 'RR-x', dict(run_id='RR-x', origin='REEVALUATION', source_run_id=None, state='CURRENT', candidates=[], evidence=[]))
        self.assertEqual(self.listing('RR-x')['limitations'], ['CANDIDATE_RUN_NOT_FOUND'])


class _OpenHandler(UiApiHandler):
    def _authorize_request(self, *args, **kwargs):  # auth is covered by the route-policy tests
        return True


class HttpRouteTests(_Lifecycle):
    def setUp(self):
        super().setUp()
        self.store._trade_lifecycle_service = self.service
        _OpenHandler.store = self.store
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _OpenHandler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_address[1]}{path}', timeout=30) as response:
            return json.loads(response.read())

    def test_list_and_detail_routes_serve_the_projection(self):
        run, _ = self.enter()
        listing = self.get(f'/screener/trade-lifecycles?run_id={run}')
        row = self.only(listing['selected'])
        self.assertEqual((listing['schema_version'], row['stage']), ('trade-lifecycle-list/1.0.0', 'POSITION_OPEN'))
        detail = self.get(f"/screener/trade-lifecycles/{row['lifecycle_id']}?run_id={run}")
        self.assertEqual((detail['schema_version'], detail['lifecycle_id']), ('trade-lifecycle/1.0.0', row['lifecycle_id']))
        self.assertGreaterEqual(len(detail['timeline']), 4)

    def test_errors_are_explicit(self):
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.get('/screener/trade-lifecycles/TE-unknown')
        self.assertEqual((missing.exception.code, json.loads(missing.exception.read())['reason_code']), (404, 'SCREENER_LIFECYCLE_NOT_FOUND'))
        with self.assertRaises(urllib.error.HTTPError) as invalid:
            self.get('/screener/trade-lifecycles?closed_limit=abc')
        self.assertEqual((invalid.exception.code, json.loads(invalid.exception.read())['reason_code']), (400, 'SCREENER_LIFECYCLE_INVALID'))

    def test_routes_are_read_only_audit_reads_on_the_paper_ledger(self):
        for path in ('/screener/trade-lifecycles', '/screener/trade-lifecycles/TE-1'):
            policy = policy_for_route('GET', path)
            self.assertEqual((policy.capability, str(policy.account_scope).rsplit('.', 1)[-1]), ('audit.read', 'PAPER_LEDGER'))
        self.assertNotEqual(policy_for_route('POST', '/screener/trade-lifecycles').capability, 'audit.read')
