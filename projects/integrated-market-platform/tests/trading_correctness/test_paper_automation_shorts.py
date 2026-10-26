"""Rebuild step 6 — the autonomous Paper controller opens, covers and closes out shorts.

SOFTWARE_CONTROLLED, through the production controller, Action Decision gate, Paper preview/risk/submit route,
simulator and ledger (``tests.support.paper_automation_harness``). The model fixture proposes a SHORT entry on
a falling price; everything after that is the unchanged server path. Not live-session acceptance.
"""
from __future__ import annotations

from market_platform_foundation.intelligence.contracts.common import OpportunitySide
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.ui_api import paper_experiment
from tests.intelligence.test_action_decision import proposal, wire
from tests.intelligence.test_reevaluation import FixtureProvider
from tests.support.paper_automation_harness import Automation
from tests.trading_correctness.test_paper_automation import AutoBase


class ShortProvider(FixtureProvider):
    """The base fixture, plus: flat and falling proposes ENTER SHORT."""

    def infer(self, packet, *, rendered_prompt, config):
        change = next(e['facts']['change_pct'] for e in packet.candidates[0]['current_market_evidence'] if e['capability'] == 'TECHNICALS')
        if packet.scope['position']['state'] == 'FLAT' and change < 0 and not self.force:
            self.calls += 1
            self.prompts.append(rendered_prompt)
            return ProviderInferenceResponse(wire(proposal('ENTER', 'SHORT'), packet.candidates[0]), self.provider_id, self.model_id,
                                             simulated=True, tokens_input=250, tokens_output=120, latency_ms=1)
        return super().infer(packet, rendered_prompt=rendered_prompt, config=config)


SHORTS = dict(risk=dict(allow_short=True))


class ShortAutomationTests(AutoBase):
    def setUp(self):
        super().setUp()
        # The harness opened an account without shorts; the owner's short-enabled account replaces it.
        paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = paper_experiment.create_experiment(self.store, {'allow_short': True})['experiment']
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, provider=ShortProvider())

    def short(self, instrument='AAPL', price=150):
        a = self.auto
        a.quote(instrument, price, -2)
        a.opportunity(instrument, side=OpportunitySide.SHORT)
        a.go(**SHORTS)
        a.cycle()
        a.select(instrument)
        outcomes = [o for _ in range(3) for o in a.cycle()['actions']]
        return outcomes

    def test_the_prompt_states_the_short_rules(self):
        self.short()
        self.assertIn('context.allow_short is true', self.auto.provider.prompts[0])
        self.assertIn('EXIT means buying it back (cover)', self.auto.provider.prompts[0])

    def test_short_entry_then_cover_on_reversal(self):
        a = self.auto
        outcomes = self.short()
        entered = [o for o in outcomes if o['outcome'] == 'SUBMITTED']
        self.assertEqual([(o['action'], o['side']) for o in entered], [('ENTER', 'SELL')])
        position = a.position('AAPL')
        self.assertEqual(position['side'], 'SHORT')
        self.assertLess(position['quantity'], 0)
        held = -position['quantity']
        decision = next(d for d in a.actions.history('AAPL') if d['action_state'] == 'ENTER')
        self.assertTrue(decision['evidence_snapshot']['context']['allow_short'])
        order = self.automation_orders()[0]
        intent = a.store.paper_ledger.lookup_intent_for_order(order['order_id'])
        self.assertEqual(intent['short_sale_facts']['day_change_bps'], -200)
        self.assertTrue(intent['short_sale_facts']['source'].startswith('ACTION_DECISION_TECHNICALS:'))

        a.quote('AAPL', 148, 2)  # the price turns up: the thesis reverses and the gate turns that into EXIT
        closing = [o for o in a.cycle(400)['actions'] if o['outcome'] == 'SUBMITTED']
        self.assertEqual([(o['action'], o['side'], o['quantity']) for o in closing], [('EXIT', 'BUY', held)])
        self.assertIsNone(a.position('AAPL'))
        self.assertGreater(a.store.paper_ledger.project_valuation()['realized_pnl_minor'], 0)

    def test_short_entry_is_refused_by_an_owner_policy_without_shorts(self):
        a = self.auto
        a.quote('AAPL', 150, -2)
        a.opportunity('AAPL', side=OpportunitySide.SHORT)
        a.go()  # risk.allow_short stays False in the owner policy
        a.cycle()
        a.select('AAPL')
        outcomes = [o for _ in range(3) for o in a.cycle()['actions']]
        self.assertIn('AUTOMATION_SHORT_NOT_PERMITTED', [code for o in outcomes for code in o['reason_codes']])
        self.assertIsNone(a.position('AAPL'))

    def test_eod_flatten_buys_shorts_back(self):
        a = self.auto
        self.short()
        held = -a.position('AAPL')['quantity']
        a.minutes_to_close = 8
        a.quote('AAPL', 149, -2)
        flattened = [o for o in a.cycle(400)['actions'] if o['action'] == 'EOD_FLATTEN']
        self.assertEqual([(o['outcome'], o['side'], o['quantity']) for o in flattened], [('SUBMITTED', 'BUY', held)])
        self.assertIsNone(a.position('AAPL'))

    def test_a_short_held_into_the_next_session_pays_one_borrow_fee(self):
        a = self.auto
        self.short()
        a.session_date = '2026-10-06'
        a.quote('AAPL', 149, -2)
        a.cycle(400)
        fees = [e for e in a.events() if e['kind'] == 'SHORT_BORROW_FEE_ACCRUED']
        self.assertEqual(len(fees), 1)
        self.assertEqual((fees[0]['accrual_date'], fees[0]['borrow_basis']), ('2026-10-05', 'SIMULATED_EASY_TO_BORROW'))
        self.assertGreater(fees[0]['fee_minor'], 0)
        self.assertEqual(a.store.paper_ledger.project_valuation()['total_borrow_fees_minor'], fees[0]['fee_minor'])
        a.cycle(60)
        self.assertEqual(len([e for e in a.events() if e['kind'] == 'SHORT_BORROW_FEE_ACCRUED']), 1)

    def test_a_maintenance_breach_buys_back_the_short_and_blocks_entries(self):
        a = self.auto
        self.short()
        held = -a.position('AAPL')['quantity']
        a.quote('AAPL', 25_000, -2)  # a fixture move far past the 30% maintenance line
        self.assertTrue(a.store.paper_ledger.short_margin_status()['maintenance_breached'])
        summary = a.cycle(60)
        covers = [o for o in summary['actions'] if o['action'] == 'MARGIN_COVER']
        self.assertEqual([(o['outcome'], o['side'], o['quantity']) for o in covers], [('SUBMITTED', 'BUY', held)])
        self.assertIn('SHORT_MAINTENANCE_MARGIN_BREACH', [b['code'] for b in summary['blockers']])
        self.assertIsNone(a.position('AAPL'))
