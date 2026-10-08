"""Full-universe AI Screener run carried through the existing downstream chain.

SOFTWARE_CONTROLLED. The production coverage pipeline, candidate reducer, action-decision service, Paper
preview/submit route, simulator, SMA stop service, lifecycle projection and OCT1-11 evaluation are used
unchanged. Only the Screener rows, the clock, the model answers, the completed-bar feed and the marks are
controlled fixtures. Nothing here is market evidence, and no Live-capital path exists to reach.
"""

from __future__ import annotations

import json

from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger
from market_platform_foundation.local_state.evaluations import EvaluationRepository
from market_platform_foundation.local_state.reevaluation import ReevaluationRepository
from market_platform_foundation.ui_api.prospective_evaluation import ProspectiveEvaluationService
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage
from tests.intelligence.test_action_decision import proposal
from tests.support.coverage_universe import SCOPE, News, PagingReader, RankingProvider, universe
from tests.trading_correctness.test_trade_lifecycle import A, N, _Lifecycle, iso


class ActionModel:
    """The Action Decision proposal for the requested state. It is a different task from candidate reduction."""
    provider_id, model_id, runtime = 'fixture', 'controlled', 'LOCAL_MODEL'

    def __init__(self):
        self.state, self.calls = 'NO_ACTION', 0

    def infer(self, packet, *, rendered_prompt, config):
        self.calls += 1
        candidate = packet.candidates[0]
        value = proposal(self.state, None if self.state == 'NO_ACTION' else 'LONG')
        refs = [e['evidence_id'] for e in candidate['current_market_evidence'] if not e['weak_reasons']]
        value['supporting_refs'] = refs
        value['conflicting_refs'] = []
        value['missing_capabilities'] = [m['capability'] for m in candidate['missing']]
        return ProviderInferenceResponse(json.dumps(value), self.provider_id, self.model_id, simulated=True, tokens_input=1, tokens_output=1, latency_ms=1)


class FullUniverseEndToEndTests(_Lifecycle):
    """Screener universe -> classification -> batches -> global reduction -> Action -> Paper -> stop -> lifecycle -> evaluation."""

    SIZE = 160

    def setUp(self):
        super().setUp()
        self.model = ActionModel()
        self.ai._news_service = lambda: type('NewsStub', (), {'synthesis_provider': staticmethod(lambda: self.model)})()
        self.reducer_engine = RankingProvider()
        self.ledger = CoverageLedger()
        self.scans = 0

    def rows(self, *, price, strengths):
        """A controlled universe observed now. AAPL and NVDA sit at the very end of the sorted result."""
        rows = universe(self.SIZE)
        for row in rows:
            for field in row['fields'].values():
                field['as_of'] = iso(self.t)
        for offset, (symbol, strength) in enumerate(strengths.items()):
            row = rows[self.SIZE - 1 - offset]
            row['instrument'] = dict(instrument_id=symbol, symbol=symbol, universe='US_EQUITIES', asset_class='EQUITY')
            row['symbol'] = symbol
            row['fields']['rsi_14']['value'] = strength
            row['fields']['price']['value'] = price
        return rows

    def scan(self, *, price=150.0, strengths=None, engine=None):
        """One full-universe run, stored where the Action Decision layer reads candidate runs."""
        self.tick()
        self.scans += 1
        strengths = {A: 95.0, N: 90.0} if strengths is None else strengths
        service = ScreenerAiService(reader=PagingReader(self.rows(price=price, strengths=strengths), result_set=f'set-{self.scans}'),
                                    news=News(engine or self.reducer_engine), clock=self.clock)
        result = ScreenerAiCoverage(service, ledger=self.ledger, software_sha='b' * 40, repository=self.repo).run(
            SCOPE, run_id=f'e2e{self.scans:029d}', account_id=self.store.paper_ledger.paper_account_id)
        if result['candidates']:
            self.store.strategy_repository.put_opportunity(OpportunityV1(
                'opp-' + result['run_id'], '1', IntelligenceScope(tuple(p['instrument_id'] for p in result['candidates'])),
                int((self.t - 1) * 1e9), QualitySummary('GOOD'), side='LONG', valid_until_ns=int((self.t + 600) * 1e9)))
        return result

    def test_a_late_universe_selection_travels_the_whole_governed_paper_lifecycle(self):
        calls_before = self.reducer_engine.calls
        scan = self.scan()
        block = scan['universe_coverage']

        # --- Screener universe -> deterministic classification -> batches -> global reduction ---------------
        self.assertEqual((block['status'], block['universe_count'], block['ai_evaluated_count']), ('GLOBAL_SELECTION_COMPLETE', self.SIZE, self.SIZE))
        self.assertEqual((block['batches_planned'], block['batches_completed']), (4, 4))
        self.assertEqual(self.reducer_engine.calls - calls_before, 5)
        self.assertTrue(block['coverage_complete'] and block['selection_complete'] and block['reconciled'])
        # Both selections were the last two rows of the sorted result: unreachable under a first-50 intake.
        self.assertEqual([(p['rank'], p['instrument_id']) for p in scan['candidates']], [(1, A), (2, N)])
        stored = self.repo.get('candidate_run', scan['run_id'])
        self.assertEqual((stored['state'], stored['universe_coverage']['coverage_run_id']), ('CURRENT', 'e2e' + '0' * 28 + '1'))

        # --- Action Decision on the stored final result, then the governed Paper preview and explicit submit ---
        entered = self.decide(scan['run_id'], 'ENTER')
        self.assertEqual((entered['action_state'], entered['execution_readiness']), ('ENTER', 'PREVIEW_ALLOWED'), entered['blocker_codes'])
        self.assertEqual((entered['evidence_snapshot']['candidate_run_id'], entered['evidence_snapshot']['candidate_rank']), (scan['run_id'], 1))
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 0)          # a decision is never an order
        submission = self.governed(entered, quantity=6, price='150.00')
        self.assertTrue(submission)
        row = self.only([r for r in self.listing(scan['run_id'])['selected'] if r['symbol'] == A])
        self.assertEqual((row['position']['state'], row['position']['quantity'], row['entry']['status'], row['candidate']['rank']), ('LONG', 6, 'FILLED', 1))
        self.assertEqual((row['ai_selected'], row['position_origin'], row['origin']['run_id']), (True, 'AI_DECISION_GOVERNED', scan['run_id']))

        # --- Held-position reevaluation on a NEW full-universe run: its own evidence, its own immutable record ---
        rescan = self.scan(price=151.0)
        self.assertNotEqual(rescan['run_id'], scan['run_id'])
        self.assertEqual(self.repo.get('candidate_run', scan['run_id']), stored)       # the earlier run is never rewritten
        held = self.decide(rescan['run_id'], 'HOLD')
        self.assertEqual(held['action_state'], 'HOLD')

        # --- SMA trailing stop: deterministic EXIT on a breach, with no model call; the close is a separate fill ---
        self.stops.configure(dict(enabled=True, sma_window_bars=2))
        self.anchor, self.closes = int(self.t * 1e9), []
        self.bar(14000)
        self.bar(14000)
        self.stops.evaluate(A)
        model_calls, reducer_calls = self.model.calls, self.reducer_engine.calls
        self.quote = 139.0
        self.tick()
        self.stops.evaluate_now(dict(instrument_id=A))
        self.assertEqual((self.model.calls, self.reducer_engine.calls), (model_calls, reducer_calls))
        breached = self.only([r for r in self.listing(rescan['run_id'])['selected'] if r['symbol'] == A])
        self.assertEqual((breached['stage'], breached['risk_control']['status'], breached['decision']['origin']),
                         ('EXIT_NOT_EXECUTED', 'BREACHED', 'DETERMINISTIC_RISK_CONTROL'))
        self.assertEqual(breached['position']['state'], 'LONG')
        self.governed(self.repo.get('decision', breached['decision']['decision_id']), price='139.00')

        # --- Lifecycle: one closed episode whose origin is the first full-universe run ---
        closed = self.only(self.listing()['recent_closed'])
        self.assertEqual((closed['stage'], closed['position']['state'], closed['pnl']['realized_minor']), ('POSITION_CLOSED', 'FLAT', -6600))
        self.assertEqual((closed['origin']['run_id'], closed['ai_selected']), (scan['run_id'], True))
        detail = self.service.detail(closed['lifecycle_id'])
        self.assertEqual((detail['experiment']['execution'], detail['experiment']['live_capital']), ('INTERNAL_SIMULATION', False))

        # --- OCT1-11 evaluation reads the same receipts and reproduces from them ---
        evaluation = ProspectiveEvaluationService(self.store, actions=self.repo, next_sessions=ReevaluationRepository(),
                                                  repository=EvaluationRepository(), clock=self.clock)
        self.tick(2)
        projected = evaluation.project()
        self.assertEqual(projected['metrics']['completed_trades'], 1, projected['admission'])
        frozen = evaluation.create(dict(cutoff=iso(self.t)))
        self.assertEqual(evaluation.reproduce(frozen['run_id'])['status'], 'MATCH')
        self.assertEqual(evaluation.reproduce(frozen['run_id'])['source_reconstruction'], 'MATCH')

    def test_a_run_that_did_not_finish_gives_the_action_layer_nothing_to_act_on(self):
        from tests.support.coverage_universe import FailingProvider

        partial = self.scan(engine=FailingProvider(fail_on=3))
        block = partial['universe_coverage']
        self.assertEqual((block['status'], partial['state']), ('PROVISIONAL_PARTIAL_COVERAGE', 'INCOMPLETE'))
        self.assertFalse(block['selection_complete'])
        self.assertIsNone(self.repo.get('candidate_run', partial['run_id']))
        self.assertIsNone(self.repo.get('candidate_run', 'CU-' + partial['run_id']))
        for finalist in partial['provisional']:
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_RUN_NOT_FOUND'):
                self.actions.run(dict(run_id=partial['run_id'], instrument_id=finalist['instrument_id']))
        # No batch answer is loadable either: only a completed global selection is a candidate run.
        for call in self.ledger.records(partial['universe_coverage']['coverage_run_id'], 'batch'):
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_RUN_NOT_FOUND'):
                self.actions.run(dict(run_id=call['reduction_run_id'], instrument_id=A))
        self.assertEqual(self.model.calls, 0)
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 0)

    def test_a_final_selection_whose_evidence_has_expired_cannot_enter(self):
        scan = self.scan()
        self.assertEqual(scan['state'], 'CURRENT')
        # The result is valid only as long as the quotes it cites: sixty seconds from its own cutoff.
        self.assertEqual(scan['valid_until'], iso(self.t + 60))
        self.tick(120)
        decision = self.decide(scan['run_id'], 'ENTER')
        # The existing server-owned gate answers; selection by a completed run does not outlive its evidence.
        self.assertEqual((decision['action_state'], decision['execution_readiness']), ('REVALIDATION_REQUIRED', 'BLOCKED'))
        self.assertIn('CANDIDATE_EXPIRED', decision['blocker_codes'])
        with self.assertRaisesRegex(ValueError, 'ACTION_NOT_HANDOFF_ELIGIBLE|ACTION_HANDOFF_BLOCKED|ACTION_DECISION_EXPIRED'):
            self.actions.handoff(dict(decision_id=decision['decision_id']))
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 0)
