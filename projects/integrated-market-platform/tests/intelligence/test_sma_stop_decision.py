"""OCT1-08 stop breach as a deterministic EXIT: safety precedence, model boundary, Paper handoff."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from market_platform_foundation.intelligence.inference.action_decision import (
    build_conditions, gate_proposal, output_schema, parse_proposal,
)
from market_platform_foundation.intelligence.inference.reevaluation import SAFETY_REASONS, material_change, stability_decision
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from tests.intelligence.test_action_decision import NOW, candidate, proposal
from tests.intelligence.test_reevaluation import Harness, T0, only
from tests.intelligence.test_sma_trailing_stop import series

IID = 'US:NVDA'
AUTHORITY = 'market_platform_foundation.operating_modes.paper_execution_env_enabled'


class StopHarness(Harness):
    """OCT1-07 controlled loop plus a controlled completed-bar source for the stop monitor."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.closes, self.bar_state = [], 'CURRENT'
        self.ledger.execution_authority, self.ledger.execution_mode = 'PAPER_ONLY', 'INTERNAL_SIMULATION'
        self.stops = SmaStopService(self.store, repository=SmaStopRepository(), clock=self.clock, actions=self.actions, ai=self.ai,
                                    bars=lambda instrument, policy, scale: dict(state=self.bar_state, reason=None, source='CONTROLLED_FIXTURE', bars=series(self.closes)),
                                    quotes=lambda instrument, scale: dict(admissible=True, price_minor=int(round(self.ai.rows[instrument]['price'] * 100)),
                                                                          as_of_ns=int(self.clock() * 1e9), source='CONTROLLED_FIXTURE', evidence_ref='q', reason=None))
        self.actions.risk_control = self.stops

    def hold(self, quantity=10, iid=IID):
        rows = [dict(instrument_id=iid, symbol=iid.split(':')[1], quantity=abs(quantity), side='SHORT' if quantity < 0 else 'LONG')] if quantity else []
        self.ledger.project_positions = Mock(return_value=rows)

    def bar(self, close, *, price=None):
        """One more completed bar becomes available, then one cycle runs."""
        self.closes.append(close)
        self.clock.value = T0 + 60 * len(self.closes)
        if price is not None:
            self.ai.rows[IID]['price'] = price
        return self.service.run_once()

    def arm(self, window=2):
        """LONG 10 with an active 140.00 stop under a 150.00 market and a current HOLD decision."""
        self.hold(10)
        self.stops.configure(dict(enabled=True, sma_window_bars=window))
        self.closes = [14000] * (window - 1)
        self.clock.value = T0 + 60 * len(self.closes)
        self.configure()
        return self.bar(14000)


class ConditionTests(unittest.TestCase):
    def context(self, **risk):
        base = dict(position=dict(state='LONG', quantity=7, snapshot_at=NOW, pending=False), candidate_valid_until='2026-10-05T14:01:00Z',
                    authority=True, opportunity=None)
        if risk:
            base['risk_control'] = dict(dict(status='BREACHED', side='LONG', policy_id='STP-x', stop_state_id='STS-x', position_epoch_id='PE-x',
                                             active_stop='186.1', previous_stop='185.12', trigger_price='185.95', triggered_at=NOW), **risk)
        return base

    def test_unconfigured_decisions_are_byte_identical_to_oct1_06(self):
        conditions = build_conditions(candidate(), self.context(), NOW)
        self.assertEqual([c['condition_id'] for c in conditions], ['CURRENT_QUOTE', 'DIRECTION_SUPPORTED', 'THESIS_CONTINUES', 'THESIS_REVERSED', 'DECISION_EXPIRED'])
        self.assertTrue(all(c['source'] == 'SERVER_ACTION_POLICY' for c in conditions))

    def test_breach_is_a_server_condition_the_model_cannot_select(self):
        context = self.context(status='BREACHED')
        conditions = build_conditions(candidate(), context, NOW)
        stop = conditions[-1]
        self.assertEqual((stop['condition_id'], stop['status'], stop['source'], stop['source_value'], stop['trigger_price']),
                         ('SMA_TRAILING_STOP_BREACHED', 'MET', 'SERVER_RISK_CONTROL', '186.1', '185.95'))
        schema = output_schema(candidate(), conditions)
        self.assertNotIn('SMA_TRAILING_STOP_BREACHED', schema['properties']['exit_conditions']['items']['enum'])
        chosen = dict(proposal('EXIT'), exit_conditions=['SMA_TRAILING_STOP_BREACHED'])
        self.assertEqual(parse_proposal(json.dumps(chosen), candidate(), conditions), (None, 'UNSUPPORTED_CONDITION'))

    def test_model_text_cannot_author_or_move_a_stop(self):
        conditions = build_conditions(candidate(), self.context(status='ACTIVE'), NOW)
        for text in ('Change SMA stop to 120.', 'Lower the trailing level.', 'Cancel the stop for now.', 'Use a slower SMA window.'):
            self.assertEqual(parse_proposal(json.dumps(dict(proposal('HOLD'), rationale=text)), candidate(), conditions),
                             (None, 'UNSUPPORTED_EXECUTION_OR_LEVEL'), text)
        extra = dict(proposal('HOLD'), stop_level=120)
        self.assertEqual(parse_proposal(json.dumps(extra), candidate(), conditions), (None, 'SCHEMA_INVALID'))

    def test_gate_exits_without_a_proposal_and_a_model_cannot_veto(self):
        context = self.context(status='BREACHED')
        gated = gate_proposal(None, candidate(), context, now=NOW)
        self.assertEqual((gated['action_state'], gated['execution_readiness'], gated['reason_codes']),
                         ('EXIT', 'PREVIEW_ALLOWED', ['SMA_TRAILING_STOP_BREACHED', 'SERVER_RISK_EXIT']))
        vetoed = gate_proposal(proposal('HOLD'), candidate(), context, now=NOW)
        self.assertEqual(vetoed['action_state'], 'EXIT')

    def test_degraded_inputs_block_the_preview_but_never_erase_the_exit(self):
        context = self.context(status='BREACHED')
        context['position']['pending'] = True
        context['authority'] = False
        gated = gate_proposal(None, candidate(), context, now=NOW)
        self.assertEqual((gated['action_state'], gated['execution_readiness']), ('EXIT', 'BLOCKED'))
        self.assertEqual(gated['blocker_codes'], ['PENDING_ORDER_REVALIDATION', 'PAPER_AUTHORITY_UNAVAILABLE'])

    def test_only_a_breach_on_the_held_side_exits(self):
        for risk in (dict(status='ACTIVE'), dict(status='STALE'), dict(status='WARMING_UP'), dict(status='BREACHED', side='SHORT')):
            gated = gate_proposal(None, candidate(), self.context(**risk), now=NOW)
            self.assertEqual(gated['action_state'], 'REVALIDATION_REQUIRED', risk)
        flat = self.context(status='BREACHED')
        flat['position'].update(state='FLAT', quantity=0)
        self.assertNotEqual(gate_proposal(None, candidate(), flat, now=NOW)['action_state'], 'EXIT')

    def test_breach_is_a_safety_reason_and_bookkeeping_is_not(self):
        self.assertIn('SMA_TRAILING_STOP_BREACHED', SAFETY_REASONS)
        policy = dict(min_state_dwell_seconds=300, price_move_bps=50)
        held = stability_decision(['SMA_TRAILING_STOP_BREACHED'], now='2026-10-05T14:01:50Z', last_state_change=NOW, policy=policy)
        self.assertEqual((held['evaluate'], held['safety']), (True, True))  # 190 seconds of dwell remained
        base = dict(position=['LONG', 10], pending=False, quote='MET', authority=True, exit_met=False, direction='LONG', current=[], blocked=[],
                    reference=[], alignments=[], opportunity=None, policy='p', price=150.0)
        step = lambda before, after: material_change(dict(base, stop=before), dict(base, stop=after), policy)
        self.assertEqual(step(['ACTIVE', '100', 'PE-1'], ['ACTIVE', '100', 'PE-1']), [])
        self.assertEqual(step(['WARMING_UP', None, 'PE-1'], ['ACTIVE', '100', 'PE-1']), ['STOP_INITIALIZED'])
        self.assertEqual(step(['ACTIVE', '100', 'PE-1'], ['ACTIVE', '102', 'PE-1']), ['STOP_TIGHTENED'])
        self.assertEqual(step(['ACTIVE', '102', 'PE-1'], ['STALE', '102', 'PE-1']), ['STOP_UPDATE_STALE'])
        self.assertEqual(step(['STALE', '102', 'PE-1'], ['ACTIVE', '102', 'PE-1']), ['STOP_UPDATE_RESUMED'])
        self.assertEqual(step(['ACTIVE', '102', 'PE-1'], ['ACTIVE', '99', 'PE-2']), ['STOP_EPISODE_CHANGED'])
        self.assertEqual(step(['ACTIVE', '102', 'PE-1'], ['BREACHED', '102', 'PE-1']), ['SMA_TRAILING_STOP_BREACHED'])
        self.assertEqual(material_change(base, dict(base, stop=['ACTIVE', '100', 'PE-1']), policy), ['STOP_INITIALIZED'])


class ReevaluationStopTests(unittest.TestCase):
    def setUp(self):
        self.h = StopHarness()
        patcher = patch(AUTHORITY, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_breach_exits_inside_the_dwell_without_a_model_call(self):
        first = self.h.arm()
        self.assertEqual(self.h.history()[0]['action_state'], 'HOLD')
        self.assertEqual((first['cycle_status'], self.h.provider.calls), ('MATERIAL_CHANGE', 1))
        hold = copy.deepcopy(self.h.history()[0])
        cycle = self.h.bar(14000, price=139.5)  # 60 seconds into a 300 second dwell; the model's thesis still says HOLD
        transition = only(cycle, 'STATE_CHANGED')[0]
        self.assertEqual((transition['prior_state'], transition['new_state'], transition['safety'], transition['model_call']), ('HOLD', 'EXIT', True, False))
        self.assertTrue({'SAFETY_PRECEDENCE', 'SMA_TRAILING_STOP_BREACHED'} <= set(transition['reason_codes']))
        self.assertEqual((cycle['model_call_count'], self.h.provider.calls), (0, 1))
        self.assertEqual(only(cycle, 'CHURN_SUPPRESSED'), [])
        decision, prior = self.h.history()[0], self.h.history()[1]
        self.assertEqual(prior, hold)  # the earlier HOLD is not rewritten
        self.assertEqual((decision['action_state'], decision['previous_state'], decision['previous_decision_id'], decision['model_proposal']),
                         ('EXIT', 'HOLD', hold['decision_id'], None))
        exit_ = decision['server_exit']
        self.assertEqual((exit_['active_stop'], exit_['trigger_price'], exit_['policy_id'], exit_['model_call'], exit_['paper_close']),
                         ('140', '139.5', self.h.stops._config()[1]['policy_id'], False, 'NOT_SUBMITTED'))
        self.assertEqual(exit_['trigger_evidence']['evidence_ref'], 'q')
        self.assertEqual((decision['model']['provider_id'], decision['model']['authored_by']), (None, 'SERVER_RISK_CONTROL'))
        self.assertEqual([c['condition_id'] for c in decision['exit_plan']], ['SMA_TRAILING_STOP_BREACHED'])
        self.assertEqual(decision['position']['quantity'], 10)
        trace = self.h.actions.trace_repository.get_execution_decision_trace(decision['decision_trace_id'])
        self.assertIn(exit_['policy_id'], trace.config_version_refs)
        self.assertEqual((trace.rule_evaluations[1].rule_id, trace.rule_evaluations[1].reason_codes, trace.rule_evaluations[1].evidence_refs[0].id),
                         (exit_['policy_id'], ('SMA_TRAILING_STOP_BREACHED',), exit_['stop_state_id']))

    def test_breach_exits_with_no_model_available_at_all(self):
        self.h.arm()
        self.h.ai.provider = None
        self.h.actions.ai = self.h.ai
        with patch.object(self.h.ai, '_news_service', return_value=Mock(synthesis_provider=lambda: None)):
            cycle = self.h.bar(14000, price=139.0)
        transition = [t for t in cycle['transitions'] if t['new_state'] == 'EXIT'][0]
        self.assertEqual((transition['model_call'], transition['safety']), (False, True))
        self.assertEqual(self.h.history()[0]['server_exit']['trigger_price'], '139')

    def test_routine_tightening_is_recorded_without_a_model_call(self):
        self.h.arm()
        cycle = self.h.bar(14040, price=150.1)  # SMA rises 20 cents; price move is under the material threshold
        transition = only(cycle, 'MATERIAL_EVIDENCE_CHANGED')[0]
        self.assertEqual((transition['reason_codes'], transition['model_call'], transition['new_decision_id']),
                         (['STOP_TIGHTENED', 'DETERMINISTIC_STOP_UPDATE'], False, None))
        self.assertEqual((self.h.provider.calls, len(self.h.history())), (1, 1))
        unchanged = self.h.bar(13960)  # SMA back down: the stop holds, nothing material changed
        self.assertEqual((unchanged['cycle_status'], unchanged['transitions'], self.h.provider.calls), ('NO_MATERIAL_CHANGE', [], 1))
        self.assertEqual(self.h.stops.status(IID)['reason_codes'], ['MONOTONIC_CLAMP'])

    def test_stale_bars_are_a_stop_fact_not_a_model_question(self):
        self.h.arm()
        self.h.bar_state = 'STALE'
        cycle = self.h.bar(14000)
        self.assertEqual(only(cycle, 'MATERIAL_EVIDENCE_CHANGED')[0]['reason_codes'], ['STOP_UPDATE_STALE', 'DETERMINISTIC_STOP_UPDATE'])
        self.assertEqual(self.h.provider.calls, 1)

    def test_breach_never_submits_paper_or_live(self):
        with patch('market_platform_foundation.paper.execution.submit_interactive_order') as paper, \
                patch('market_platform_foundation.paper.execution.preview_interactive_order') as preview, \
                patch('market_platform_foundation.ui_api.paper_projections._submit_paper_order') as route, \
                patch('market_platform_foundation.intelligence.live_canary.submission.MockBrokerTransport.submit') as live:
            self.h.arm()
            self.h.bar(14000, price=139.5)
            self.h.bar(14000, price=138.0)
        for spy in (paper, preview, route, live):
            spy.assert_not_called()
        self.assertEqual(self.h.ledger.events, [])
        self.assertEqual(self.h.history()[0]['action_state'], 'EXIT')
        for module in ('risk.sma_trailing_stop', 'local_state.sma_trailing_stop', 'ui_api.paper_risk_control'):
            source = Path(__import__('market_platform_foundation.' + module, fromlist=['x']).__file__).read_text(encoding='utf-8')
            for forbidden in ('paper_projections', 'handoff(', 'submit_interactive_order', 'preview_interactive_order', 'place_order', 'live_canary', 'execute_order_intent'):
                self.assertNotIn(forbidden, source, (module, forbidden))

    def test_handoff_uses_current_ledger_quantity_not_the_stop(self):
        self.h.arm()
        self.h.bar(14000, price=139.5)
        decision = self.h.history()[0]
        self.assertEqual(decision['execution_readiness'], 'PREVIEW_ALLOWED')
        draft = self.h.actions.handoff(dict(decision_id=decision['decision_id']))
        self.assertEqual((draft['side'], draft['quantity'], draft['orderType']), ('SELL', 10, 'MARKET'))
        self.assertNotIn('quantity', decision['server_exit'])
        self.h.hold(4)  # a partial close happened elsewhere: the old draft identity no longer matches the ledger
        with self.assertRaisesRegex(ValueError, 'ACTION_INPUT_CHANGED'):
            self.h.actions.handoff(dict(decision_id=decision['decision_id']))
        renewed = self.h.bar(14000)
        fresh = self.h.history()[0]
        self.assertEqual((fresh['action_state'], fresh['position']['quantity']), ('EXIT', 4))
        self.assertEqual(self.h.actions.handoff(dict(decision_id=fresh['decision_id']))['quantity'], 4)
        self.assertEqual(renewed['model_call_count'], 0)
        self.assertEqual(self.h.ledger.events, [])

    def test_short_breach_buys_to_close(self):
        self.h.hold(-10)
        self.h.stops.configure(dict(enabled=True, sma_window_bars=2))
        self.h.closes = [16000]
        self.h.clock.value = T0 + 60
        self.h.ai.rows[IID]['change'] = -2.0
        self.h.configure()
        self.h.bar(16000)
        self.assertEqual((self.h.history()[0]['action_state'], self.h.stops.status(IID)['stop']['side']), ('HOLD', 'SHORT'))
        self.h.bar(16000, price=160.0)
        decision = self.h.history()[0]
        self.assertEqual((decision['action_state'], decision['server_exit']['side'], decision['server_exit']['active_stop']), ('EXIT', 'SHORT', '160'))
        self.assertEqual(self.h.actions.handoff(dict(decision_id=decision['decision_id']))['side'], 'BUY')

    def test_closed_position_closes_the_stop_inside_the_cycle(self):
        self.h.arm()
        self.h.hold(0)
        self.h.bar(14000)
        self.assertEqual(self.h.stops.status(IID)['status'], 'CLOSED')
        self.assertIsNone(self.h.stops.decision_facts(IID))

    def test_evaluate_now_uses_the_same_core_and_records_the_exit(self):
        self.h.arm()
        self.h.closes.append(14000)
        self.h.clock.value = T0 + 60 * len(self.h.closes)
        self.h.ai.rows[IID]['price'] = 139.5
        with self.assertRaises(ValueError):
            self.h.stops.evaluate_now(dict(instrument_id=IID, quantity=10))
        result = self.h.stops.evaluate_now(dict(instrument_id=IID))
        self.assertEqual((result['status'], result['stop']['exit_decision']['action_state'], result['paper_close']), ('BREACHED', 'EXIT', 'NOT_SUBMITTED'))
        decision = self.h.history()[0]
        self.assertEqual((decision['decision_id'], decision['evidence_snapshot']['candidate_run_id'][:3]), (result['stop']['exit_decision']['decision_id'], 'RK-'))
        self.assertEqual(self.h.provider.calls, 1)
        again = self.h.stops.evaluate_now(dict(instrument_id=IID))
        self.assertEqual((again['stop']['exit_decision']['decision_id'], len(self.h.history())), (decision['decision_id'], 2))
        cycle = self.h.service.run_once()  # the loop sees the same breach and does not fork a second EXIT
        self.assertEqual(len([d for d in self.h.history() if d['action_state'] == 'EXIT']), 1, cycle['transitions'])
        self.assertIn('STOP_EXIT_ALREADY_RECORDED', only(cycle, 'DUPLICATE_SUPPRESSED')[0]['reason_codes'])

    def test_routes_carry_no_submit_capability(self):
        from market_platform_foundation.platform.security.route_policy import AccountScopeKind, policy_for_route
        reads = ['/paper/risk-control/sma-stop', '/paper/risk-control/sma-stop/history', '/paper/risk-control/sma-stop/config',
                 '/paper/risk-control/sma-stop/evaluation']
        writes = ['/paper/risk-control/sma-stop/configure', '/paper/risk-control/sma-stop/evaluate']
        for path in reads:
            policy = policy_for_route('GET', path)
            self.assertEqual((policy.capability, policy.account_scope), ('audit.read', AccountScopeKind.PAPER_LEDGER), path)
        for path in writes:
            policy = policy_for_route('POST', path)
            self.assertEqual((policy.capability, policy.account_scope), ('state.write', AccountScopeKind.PAPER_LEDGER), path)


if __name__ == '__main__':
    unittest.main()
