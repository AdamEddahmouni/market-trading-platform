"""OCT1-06 position, temporal, proposal and history boundaries."""
import copy
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from market_platform_foundation.intelligence.inference.action_decision import (
    build_conditions, gate_proposal, parse_proposal, snapshot_evidence,
)
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
from market_platform_foundation.local_state.connection import LocalStateConnection

NOW = '2026-10-05T14:00:00Z'
END = '2026-10-05T14:01:00Z'


def candidate():
    return dict(instrument=dict(instrument_id='US:NVDA', symbol='NVDA', universe='US_EQUITIES'),
        current_market_evidence=[dict(evidence_id='q', capability='QUOTE', as_of=NOW, valid_until=END,
            role='CURRENT_MARKET', decision_admissibility='ADMISSIBLE', weak_reasons=[], facts=dict(price=150)),
            dict(evidence_id='t', capability='TECHNICALS', as_of=NOW, valid_until=END,
            role='CURRENT_MARKET', decision_admissibility='ADMISSIBLE', weak_reasons=[], facts=dict(change_pct=2))],
        reference_evidence=[], blocked=[], weak=[], missing=[], alignments=[])


def proposal(state='ENTER', direction='LONG'):
    return dict(schema_version='action-proposal/1.0.0', proposal_state=state, direction=direction,
        rationale='Observed positive price change supports this assessment.', supporting_refs=['q', 't'],
        conflicting_refs=[], weak_refs=[], missing_capabilities=[], uncertainties=[],
        entry_conditions=['CURRENT_QUOTE', 'DIRECTION_SUPPORTED'], hold_conditions=['THESIS_CONTINUES'],
        exit_conditions=['THESIS_REVERSED', 'DECISION_EXPIRED'])


class ActionDecisionTests(unittest.TestCase):
    def context(self, quantity=0):
        return dict(position=dict(state='LONG' if quantity > 0 else 'SHORT' if quantity < 0 else 'FLAT',
            quantity=quantity, snapshot_at=NOW, pending=False), candidate_valid_until=END,
            opportunity=None, authority=False, allow_short=False)

    def gate(self, p, context=None, c=None, now=NOW):
        c = c or candidate()
        return gate_proposal(p, c, context or self.context(), now=now)

    def test_bounded_states_and_unknown_execution_keys(self):
        for p in [dict(proposal(), proposal_state='STRONG_BUY'), dict(proposal(), quantity=1000),
                  dict(proposal(), exit_conditions=['stop_at_184']), dict(proposal(), rationale='Guaranteed profit'),
                  dict(proposal(), rationale='Entry price should be fifty dollars.')]:
            self.assertIsNotNone(parse_proposal(json.dumps(p), candidate(), build_conditions(candidate(), self.context(), NOW))[1])

    def test_flat_no_action_and_consider(self):
        for state in ['NO_ACTION', 'CONSIDER_ENTRY']:
            self.assertEqual(self.gate(proposal(state))['action_state'], state)

    def test_enter_is_decision_without_execution_authority(self):
        result = self.gate(proposal())
        self.assertEqual(result['action_state'], 'ENTER')
        self.assertEqual(result['execution_readiness'], 'BLOCKED')
        self.assertIn('NO_GOVERNED_OPPORTUNITY', result['blocker_codes'])

    def test_position_legal_states(self):
        for state in ['HOLD', 'EXIT']:
            self.assertEqual(self.gate(proposal(state))['action_state'], 'REVALIDATION_REQUIRED')
        self.assertEqual(self.gate(proposal(), self.context(10))['action_state'], 'REVALIDATION_REQUIRED')
        self.assertEqual(self.gate(proposal('HOLD'), self.context(10))['action_state'], 'HOLD')
        c = candidate(); c['current_market_evidence'][1]['facts']['change_pct'] = -2
        self.assertEqual(self.gate(proposal('EXIT'), self.context(10), c)['action_state'], 'EXIT')

    def test_exit_requires_met_condition_and_entry_exit_plan(self):
        self.assertEqual(self.gate(proposal('EXIT'), self.context(10))['action_state'], 'REVALIDATION_REQUIRED')
        p = proposal(); p['exit_conditions'] = []
        self.assertEqual(self.gate(p)['action_state'], 'CONSIDER_ENTRY')

    def test_stale_candidate_quote_position_and_pending(self):
        self.assertEqual(self.gate(proposal(), now=END)['action_state'], 'REVALIDATION_REQUIRED')
        for context in [dict(self.context(10), position=dict(self.context(10)['position'], snapshot_at='2026-10-04T14:00:00Z')),
                        dict(self.context(), position=dict(self.context()['position'], pending=True))]:
            self.assertEqual(self.gate(proposal('HOLD'), context)['action_state'], 'REVALIDATION_REQUIRED')

    def test_short_policy(self):
        c = candidate(); c['current_market_evidence'][1]['facts']['change_pct'] = -2
        result = self.gate(proposal(direction='SHORT'), c=c)
        self.assertEqual(result['execution_readiness'], 'BLOCKED')
        self.assertIn('SHORT_NOT_ALLOWED', result['blocker_codes'])

    def test_future_evidence_excluded_and_snapshot_detached(self):
        c = candidate(); future = copy.deepcopy(c['current_market_evidence'][1])
        future.update(evidence_id='future', as_of=END); c['current_market_evidence'].append(future)
        frozen = snapshot_evidence(c, NOW)
        self.assertNotIn('future', [e['evidence_id'] for e in frozen['current_market_evidence']])
        c['current_market_evidence'][0]['facts']['price'] = 200
        self.assertEqual(frozen['current_market_evidence'][0]['facts']['price'], 150)

    def test_conflicts_cannot_be_erased_unknown_duplicate_refs(self):
        c = candidate(); conflict = dict(c['current_market_evidence'][1], evidence_id='n', capability='SENTIMENT')
        c['reference_evidence'] = [conflict]; c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['n'])]
        for p in [proposal(), dict(proposal(), supporting_refs=['q','q']), dict(proposal(), supporting_refs=['q','unknown'])]:
            self.assertIsNotNone(parse_proposal(json.dumps(p), c, build_conditions(c, self.context(), NOW))[1])

    def test_durable_immutable_readback_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'state.sqlite'
            connection = LocalStateConnection(path)
            repo = ActionDecisionRepository(connection)
            a = dict(decision_id='a', instrument_id='US:NVDA', decision_time=NOW, input_hash='a', evidence_snapshot=candidate())
            repo.put('decision', 'a', a); repo.put('decision', 'a', a)
            with self.assertRaises(ValueError): repo.put('decision', 'a', dict(a, input_hash='changed'))
            connection.close()

            connection = LocalStateConnection(path)
            reopened = ActionDecisionRepository(connection)
            self.assertEqual(reopened.history('US:NVDA'), [a])
            read = reopened.get('decision', 'a'); read['evidence_snapshot']['instrument']['symbol'] = 'BAD'
            self.assertEqual(reopened.get('decision', 'a'), a)
            connection.close()


class ActionServiceTests(unittest.TestCase):
    def setUp(self):
        from market_platform_foundation.paper.ledger import PaperExecutionLedger
        from market_platform_foundation.ui_api.screener_action import ScreenerActionService
        from market_platform_foundation.rt01.execution_decision_trace.repository import InMemoryExecutionDecisionTraceRepository
        self.repo = ActionDecisionRepository()
        self.clock = lambda: 1791208800.0  # 2026-10-05T14:00Z
        self.ledger = PaperExecutionLedger(paper_account_id='controlled',session_id='session')
        self.store = SimpleNamespace(paper_ledger=self.ledger,execution_deferred=False)
        self.provider = Mock(provider_id='fixture',model_id='controlled',runtime='LOCAL_MODEL')
        self.ai = Mock(); self.ai._news_service.return_value.synthesis_provider.return_value=self.provider
        self.traces=InMemoryExecutionDecisionTraceRepository()
        self.service = ScreenerActionService(self.store,repository=self.repo,clock=self.clock,ai=self.ai,trace_repository=self.traces)
        self.repo.put('candidate_run','run', dict(run_id='run',state='CURRENT',valid_until=END,input_hash='candidate-input',
            evidence=[candidate()],candidates=[dict(proposal(),instrument_id='US:NVDA',rank=1)]))
        self.body=dict(run_id='run',instrument_id='US:NVDA')
        from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
        self.response=ProviderInferenceResponse(raw_text=json.dumps(proposal()),provider_id='fixture',model_id='controlled',simulated=True)
        self.provider.infer.return_value=self.response

    def test_preview_zero_inference_and_run_zero_ledger_mutations(self):
        before=copy.deepcopy(self.ledger.events)
        self.service.preview(self.body); self.provider.infer.assert_not_called()
        d=self.service.run(self.body)
        self.assertEqual(d['action_state'],'ENTER'); self.assertEqual(self.ledger.events,before)
        trace=self.traces.get_execution_decision_trace(d['decision_trace_id'])
        self.assertEqual(trace.decision_kind.value,'ACTION_ASSESSED')
        self.assertEqual(trace.rule_evaluations[0].evidence_refs[0].id,d['decision_id'])
        self.assertEqual(d['evidence_snapshot']['context']['position']['quantity'],0)

    def test_idempotency_and_position_change_new_transition(self):
        first=self.service.run(self.body); second=self.service.run(self.body)
        self.assertEqual(first['decision_id'],second['decision_id']); self.assertEqual(second['cache'],'HIT')
        self.assertEqual(self.provider.infer.call_count,1)
        self.ledger.project_positions=Mock(return_value=[dict(instrument_id='US:NVDA',quantity=10)])
        from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
        self.provider.infer.return_value=ProviderInferenceResponse(json.dumps(proposal('HOLD')),'fixture','controlled',simulated=True)
        held=self.service.run(self.body)
        self.assertEqual(held['action_state'],'HOLD'); self.assertEqual(held['previous_decision_id'],first['decision_id'])
        self.assertEqual(len(self.repo.history('US:NVDA')),2)
        self.assertEqual(self.repo.get('decision',first['decision_id'])['position']['quantity'],0)

    def test_browser_cannot_supply_evidence_or_quantities(self):
        with self.assertRaises(ValueError): self.service.run(dict(self.body,quantity=1000))
        with self.assertRaises(ValueError): self.service.run(dict(self.body,evidence=[]))
        self.provider.infer.assert_not_called()

    def test_returning_to_prior_inputs_caches_the_latest_transition(self):
        first=self.service.run(self.body)
        original=self.ledger.policy['max_order_shares']
        self.ledger.policy['max_order_shares']=original+1
        self.service.run(self.body)
        self.ledger.policy['max_order_shares']=original
        returned=self.service.run(self.body)
        cached=self.service.run(self.body)
        self.assertNotEqual(first['decision_id'],returned['decision_id'])
        self.assertEqual(cached['decision_id'],returned['decision_id'])
        self.assertEqual(cached['cache'],'HIT')
        self.assertEqual(self.provider.infer.call_count,3)
        self.assertEqual(len(self.repo.history('US:NVDA')),3)

    def test_no_candidate_lineage_fabrication_and_expiry(self):
        d=self.service.run(self.body); self.assertIsNone(d['opportunity_id'])
        with self.assertRaises(ValueError): self.service.handoff(dict(decision_id=d['decision_id']))
        self.service.clock=lambda:1791208861.0
        expired=self.service.run(self.body)
        self.assertEqual(expired['action_state'],'REVALIDATION_REQUIRED')
        self.assertEqual(self.provider.infer.call_count,1)

    def test_authority_loss_and_changed_policy_fail_handoff(self):
        self.ledger.execution_authority='PAPER_ONLY'; self.ledger.execution_mode='INTERNAL_SIMULATION'
        self.service._opportunity=Mock(return_value=dict(opportunity_id='governed',side='LONG'))
        with patch('market_platform_foundation.operating_modes.paper_execution_env_enabled',return_value=True):
            d=self.service.run(self.body)
            self.assertEqual(d['execution_readiness'],'PREVIEW_ALLOWED')
            draft=self.service.handoff(dict(decision_id=d['decision_id']))
            self.assertEqual(draft['quantity'],1)
            self.ledger.execution_authority='BLOCKED'
            with self.assertRaises(ValueError): self.service.handoff(dict(decision_id=d['decision_id']))

    def test_exit_close_quantity_from_current_ledger_and_no_submit(self):
        self.ledger.execution_authority='PAPER_ONLY'; self.ledger.execution_mode='INTERNAL_SIMULATION'
        self.ledger.project_positions=Mock(return_value=[dict(instrument_id='US:NVDA',quantity=7)])
        c=candidate(); c['current_market_evidence'][1]['facts']['change_pct']=-2
        self.repo.put('candidate_run','exit-run',dict(run_id='exit-run',state='CURRENT',valid_until=END,input_hash='exit-input',evidence=[c],candidates=[dict(proposal(),instrument_id='US:NVDA',rank=1)]))
        from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
        self.provider.infer.return_value=ProviderInferenceResponse(json.dumps(proposal('EXIT')),'fixture','controlled',simulated=True)
        with patch('market_platform_foundation.operating_modes.paper_execution_env_enabled',return_value=True):
            d=self.service.run(dict(run_id='exit-run',instrument_id='US:NVDA'))
            self.assertEqual(d['action_state'],'EXIT')
            draft=self.service.handoff(dict(decision_id=d['decision_id']))
            self.assertEqual((draft['side'],draft['quantity']),('SELL',7))
            self.assertEqual(self.ledger.events,[])

    def test_inflight_position_change_requires_revalidation(self):
        def mutate(*args,**kwargs):
            self.ledger.project_positions=Mock(return_value=[dict(instrument_id='US:NVDA',quantity=10)])
            return self.response
        self.provider.infer.side_effect=mutate
        d=self.service.run(self.body)
        self.assertEqual(d['action_state'],'REVALIDATION_REQUIRED')
        self.assertIn('ACTION_INPUT_CHANGED_DURING_INFERENCE',d['blocker_codes'])

    def test_inflight_policy_snapshot_is_frozen(self):
        self.ledger.policy['max_order_shares']=100
        def mutate(*args,**kwargs):
            self.ledger.policy['max_order_shares']=101
            return self.response
        self.provider.infer.side_effect=mutate
        d=self.service.run(self.body)
        self.assertEqual(d['evidence_snapshot']['context']['risk_policy']['max_order_shares'],100)
        self.assertIn('ACTION_INPUT_CHANGED_DURING_INFERENCE',d['blocker_codes'])

    def test_real_opportunity_identity_and_expired_action_order_boundary(self):
        from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
        from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
        opportunity=OpportunityV1('governed','1',IntelligenceScope(('US:NVDA',)),1791208799000000000,
            QualitySummary('GOOD'),side='LONG',valid_until_ns=1791208860000000000)
        self.store.strategy_repository=SimpleNamespace(list_opportunities=lambda:[opportunity],get_opportunity=lambda identity:opportunity if identity=='governed' else None)
        self.ledger.execution_authority='PAPER_ONLY'; self.ledger.execution_mode='INTERNAL_SIMULATION'
        body=dict(self.body,opportunity_id='governed')
        with patch('market_platform_foundation.operating_modes.paper_execution_env_enabled',return_value=True):
            d=self.service.run(body)
            self.assertEqual(d['execution_readiness'],'PREVIEW_ALLOWED')
            draft=self.service.handoff(dict(decision_id=d['decision_id']))
            parsed=dict(side='BUY',quantity=5,decision_source_snapshot=draft['sourceContext'])
            self.service.validate_order_source(parsed,'US:NVDA')
            with self.assertRaises(ValueError): self.service.validate_order_source(parsed,'US:AAPL')
            self.service.clock=lambda:1791208861.0
            with self.assertRaisesRegex(ValueError,'ACTION_DECISION_EXPIRED'):
                self.service.validate_order_source(parsed,'US:NVDA')

    def test_action_reference_is_bound_into_existing_preview_claims(self):
        from market_platform_foundation.ui_api.paper_projections import _preview_binding_context
        parsed=dict(side='BUY',quantity=1,order_type='MARKET',limit_price_minor=None,decision_source_snapshot=None)
        with patch('market_platform_foundation.ui_api.paper_projections._paper_observation_time',return_value=1791208800000000000):
            manual=_preview_binding_context(self.store,focus='US:NVDA',parsed=parsed)
            parsed['decision_source_snapshot']=dict(reasons=[dict(code='ACTION_DECISION',label='ad')])
            action=_preview_binding_context(self.store,focus='US:NVDA',parsed=parsed)
            self.assertNotEqual(manual['risk_policy_revision'],action['risk_policy_revision'])

    def test_existing_pretrade_risk_owns_entry_quantity(self):
        from market_platform_foundation.intelligence.persistence.memory import InMemoryIntelligenceRepository
        from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
        from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
        self.store.strategy_repository=InMemoryIntelligenceRepository()
        self.store.strategy_repository.put_opportunity(OpportunityV1('governed','1',IntelligenceScope(('US:NVDA',)),1791208799000000000,
            QualitySummary('GOOD'),side='LONG',valid_until_ns=1791208860000000000))
        self.ledger.execution_authority='AUTHORIZED'; self.ledger.execution_mode='INTERNAL_SIMULATION'
        with patch('market_platform_foundation.operating_modes.paper_execution_env_enabled',return_value=True):
            d=self.service.run(dict(self.body,opportunity_id='governed'))
            approved=self.service.assess_entry_risk(d,dict(quantity=1))
            self.assertEqual(approved['decision'],'APPROVE')
            reduced=self.service.assess_entry_risk(d,dict(quantity=100000))
            self.assertLess(reduced['approved_quantity'],100000)
            self.assertEqual(self.ledger.events,[])
            self.assertIsNotNone(self.store.strategy_repository.get_risk_decision(approved['risk_decision_id']))
            self.ledger.project_orders=Mock(return_value=[dict(state='FILLED',decision_source_snapshot=dict(source_type='watched_opportunity',source_id='governed'))])
            self.service.clock=lambda:1791208801.0
            duplicate=self.service.assess_entry_risk(d,dict(quantity=1))
            self.assertEqual(duplicate['decision'],'REJECT')
            self.assertIn('DUPLICATE_OPPORTUNITY',duplicate['reason_codes'])

    def test_shared_paid_budget_blocks_action_before_provider(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider, DailyBudget
        budget=DailyBudget(None,max_requests=1,max_tokens=100000,clock=self.clock)
        self.provider.reasoning_headroom=0
        self.ai._news_service.return_value.synthesis_provider.return_value=BudgetedProvider(self.provider,budget)
        self.service.run(self.body)
        self.service.run(self.body)  # equivalent inputs do not charge again
        self.assertEqual(self.provider.infer.call_count,1)
        self.ledger.policy['max_order_shares']+=1
        result=self.service.run(self.body)
        self.assertEqual(result['action_state'],'REVALIDATION_REQUIRED')
        self.assertIn('PROVIDER_RATE_LIMIT',result['blocker_codes'])
        self.assertEqual(self.provider.infer.call_count,1)

    def test_atomic_trace_companion_and_restart_readback(self):
        from market_platform_foundation.rt01.execution_decision_trace.sqlite_repository import SqliteExecutionDecisionTraceRepository
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.sqlite'; connection=LocalStateConnection(path)
            self.service.repository=ActionDecisionRepository(connection)
            self.service.repository.put('candidate_run','run',self.repo.get('candidate_run','run'))
            self.service.trace_repository=SqliteExecutionDecisionTraceRepository(connection)
            with patch.object(self.service.trace_repository,'put_execution_decision_trace',side_effect=RuntimeError('controlled storage failure')):
                with self.assertRaises(RuntimeError): self.service.run(self.body)
            self.assertEqual(self.service.repository.history('US:NVDA'),[])
            d=self.service.run(self.body)
            connection.close(); connection=LocalStateConnection(path)
            restored=ActionDecisionRepository(connection)
            self.assertEqual(restored.history('US:NVDA')[0],{k:v for k,v in d.items() if k!='cache'})
            self.assertIsNotNone(SqliteExecutionDecisionTraceRepository(connection).get_execution_decision_trace(d['decision_trace_id']))
            connection.close()

    def test_short_position_projection_uses_ledger_side(self):
        self.ledger.project_positions=Mock(return_value=[dict(instrument_id='US:NVDA',quantity=7,side='SHORT')])
        position=self.service.preview(self.body)['position']
        self.assertEqual((position['state'],position['quantity']),('SHORT',-7))

    def test_submit_retry_returns_prior_ack_without_revalidating_consumed_action(self):
        from market_platform_foundation.ui_api.paper_projections import _submit_paper_order
        body=dict(instrument_id='US:NVDA',side='BUY',quantity=1,idempotency_key='same',client_order_id='same')
        self.ledger.lookup_idempotent_order=Mock(return_value='order')
        self.ledger.lookup_order=Mock(return_value=dict(order_id='order',intent_digest='digest'))
        with patch('market_platform_foundation.ui_api.live_projections.apply_live_marks_to_ledger'), patch('market_platform_foundation.ui_api.paper_projections.maybe_release_execution_gate'), patch('market_platform_foundation.ui_api.paper_projections._assert_live_execution_allowed'), patch('market_platform_foundation.ui_api.paper_projections._admit_focus_instrument',return_value={}), patch('market_platform_foundation.ui_api.paper_projections._preview_binding_context',return_value=dict(intent_digest='digest')), patch('market_platform_foundation.ui_api.paper_projections._paper_envelope',side_effect=lambda store,payload:payload), patch('market_platform_foundation.ui_api.screener_action.action_service',return_value=self.service), patch.object(self.service,'validate_order_source',side_effect=ValueError('ACTION_INPUT_CHANGED')) as validation:
            result=_submit_paper_order(self.store,body)
            self.assertTrue(result['submission']['duplicate'])
            validation.assert_not_called()

    def test_submit_rechecks_action_after_wait_before_mutation(self):
        from market_platform_foundation.ui_api.paper_projections import _submit_paper_order
        body=dict(instrument_id='US:NVDA',side='SELL',quantity=7,idempotency_key='new',client_order_id='new')
        self.ledger.lookup_idempotent_order=Mock(return_value=None)
        def expire(*args,**kwargs):
            self.service.clock=lambda:1791208861.0
            return []
        def validate(*args,**kwargs):
            if self.service.clock()>1791208860: raise ValueError('ACTION_DECISION_EXPIRED')
            return dict(action_state='EXIT')
        with patch('market_platform_foundation.ui_api.live_projections.apply_live_marks_to_ledger'), patch('market_platform_foundation.ui_api.paper_projections.maybe_release_execution_gate'), patch('market_platform_foundation.ui_api.paper_projections._assert_live_execution_allowed'), patch('market_platform_foundation.ui_api.paper_projections._admit_focus_instrument',return_value={}), patch('market_platform_foundation.ui_api.paper_projections._paper_observation_time',return_value=1791208800000000000), patch('market_platform_foundation.ui_api.paper_projections._resolve_order_margin_facts',return_value=None), patch('market_platform_foundation.ui_api.paper_projections._require_valid_preview'), patch('market_platform_foundation.ui_api.paper_projections._bars_for_paper_execution',return_value=[]), patch('market_platform_foundation.ui_api.paper_projections._wait_for_post_intent_bars',side_effect=expire), patch('market_platform_foundation.ui_api.paper_projections.submit_interactive_order') as submit, patch('market_platform_foundation.ui_api.screener_action.action_service',return_value=self.service), patch.object(self.service,'validate_order_source',side_effect=validate):
            with self.assertRaisesRegex(ValueError,'ACTION_DECISION_EXPIRED'):
                _submit_paper_order(self.store,body)
            submit.assert_not_called()
