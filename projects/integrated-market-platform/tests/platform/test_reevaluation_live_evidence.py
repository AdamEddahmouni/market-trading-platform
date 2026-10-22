"""OCT1-12: the reevaluation cycle on the real Screener row/cache evidence path: SOFTWARE_CONTROLLED."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
from market_platform_foundation.local_state.reevaluation import ReevaluationRepository
from market_platform_foundation.market_data.observational_state import QuoteSnapshot
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.rt01.execution_decision_trace.repository import InMemoryExecutionDecisionTraceRepository
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.screener_projections import ScreenerService
from market_platform_foundation.ui_api.screener_reevaluation import ReevaluationService
from tests.intelligence.test_action_decision import proposal
from tests.platform.test_screener_s18 import CandidateProvider, News

T0 = datetime(2026, 10, 6, 18, 5, 24, tzinfo=UTC).timestamp()  # Tuesday 14:05 ET, regular session
SYMBOLS = ('AAPL', 'NVDA', 'AMD')


def iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z')


class Source:
    def fetch_export(self, **kwargs):
        return dict(success=True, received_at=iso(T0), rows=[
            FinvizScreenerRow(ticker=s, company=s, price=240.0, volume=1000 + i, market_cap=500.0, short_float_pct=2.0)
            for i, s in enumerate(SYMBOLS)])


class LiveProvider(CandidateProvider):
    """One engine for both prompts, as in the runtime: candidate reduction and action decision."""

    def __init__(self):
        super().__init__()
        self.reductions = self.actions = 0

    def infer(self, packet, *, rendered_prompt, config):
        position = (packet.scope or {}).get('position') if isinstance(packet.scope, dict) else None
        if position is None:
            self.reductions += 1
            return super().infer(packet, rendered_prompt=rendered_prompt, config=config)
        self.actions += 1
        self.calls += 1
        value = proposal('ENTER') if position['state'] == 'FLAT' else proposal('HOLD')
        candidate = packet.candidates[0]
        value.update(supporting_refs=[e['evidence_id'] for e in candidate['current_market_evidence']],
                     missing_capabilities=[m['capability'] for m in candidate['missing']])
        return ProviderInferenceResponse(json.dumps(value), self.provider_id, self.model_id, simulated=True,
                                         tokens_input=250, tokens_output=120, latency_ms=1)


class LiveEvidenceReevaluationTests(unittest.TestCase):
    def setUp(self):
        self.now = T0
        self.quotes = {}
        self.runtime = SimpleNamespace(state=SimpleNamespace(quote_for=self.quotes.get),
                                       lifecycle=SimpleNamespace(connection_state='CONNECTED'),
                                       feed=SimpleNamespace(subscription_errors={}))
        self.screener = ScreenerService(source_factory=Source, runtime_getter=lambda **_: self.runtime, now=lambda: iso(self.now))
        base = 'market_platform_foundation.ui_api.'
        for target, kwargs in [(base + 'screener_projections.time.time_ns', dict(side_effect=lambda: int(self.now * 1e9))),
                               (base + 'screener_projections.us_equity_screener_session', dict(return_value='REGULAR')),
                               (base + 'screener_ai.flow_observation', dict(return_value=[]))]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.provider = LiveProvider()
        self.ai = ScreenerAiService(reader=self.screener, news=News(self.provider), clock=lambda: self.now)
        self.ledger = PaperExecutionLedger(paper_account_id='controlled-live-evidence', session_id='controlled')
        store = SimpleNamespace(paper_ledger=self.ledger, execution_deferred=False)
        self.action_repo = ActionDecisionRepository()
        patcher = patch('market_platform_foundation.local_state.action_decisions.action_repository', return_value=self.action_repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.actions = ScreenerActionService(store, repository=self.action_repo, ai=self.ai, clock=lambda: self.now,
                                             trace_repository=InMemoryExecutionDecisionTraceRepository())
        self.service = ReevaluationService(store, repository=ReevaluationRepository(), actions=self.actions, ai=self.ai,
                                           clock=lambda: self.now, owner_id='controlled')
        self.prices = dict.fromkeys(SYMBOLS, 240.0)

    def tick_quotes(self, *, age=1.0, quality='PASS', symbols=SYMBOLS):
        ns = int(self.now * 1e9)
        for symbol in symbols:
            price = self.prices[symbol]
            self.quotes[symbol] = QuoteSnapshot(symbol, round(price - .01, 2), round(price + .01, 2), 10, 10, price, volume=2000,
                                                event_time_ns=ns - int(age * 1e9), available_time_ns=ns - int(age * 5e8),
                                                received_ns=ns - int(age * 5e8), quality=quality, provider='MOOMOO_OPEND')

    def configure(self, **policy):
        self.tick_quotes()
        return self.service.configure(dict(scope=dict(universe='US_EQUITIES'), requested_cadence_seconds=60, policy=policy))

    def cycle(self, seconds=60, **quote):
        self.now += seconds
        if quote.pop('tick', True):
            self.tick_quotes(**quote)
        return self.service.run_once()

    def hold(self, symbol='NVDA'):
        self.ledger.project_positions = Mock(return_value=[dict(instrument_id=symbol, symbol=symbol, quantity=10)])

    def test_first_cycle_reaches_a_decision_from_live_cached_quotes(self):
        self.configure()
        receipt = self.service.run_once()
        self.assertEqual(receipt['cycle_status'], 'MATERIAL_CHANGE')
        self.assertEqual(receipt['readiness']['readiness'], 'REEVALUATION_READY')
        quote = next(s for s in receipt['provider_states'] if s['capability'] == 'QUOTE')
        self.assertEqual((quote['provider'], quote['cadence_semantics'], quote['within_requested_cadence']), ('MOOMOO_OPEND', 'CURRENT', True))
        self.assertEqual(self.provider.reductions, 1)
        self.assertGreaterEqual(self.provider.actions, 1)

    def test_ticking_quotes_below_the_price_gate_cost_no_model_calls(self):
        self.hold()
        self.configure()
        self.service.run_once()
        self.cycle()  # whatever was deferred by the per-cycle cap
        calls = self.provider.calls
        for step in range(1, 11):  # every tick has a new price and new clocks; the largest drift is 20 bps
            for symbol in SYMBOLS:
                self.prices[symbol] = round(240.0 * (1 + 0.0002 * step), 2)
            receipt = self.cycle()
            self.assertEqual((receipt['cycle_status'], receipt['model_call_count']), ('NO_MATERIAL_CHANGE', 0), receipt['transitions'])
        self.assertEqual(self.provider.calls, calls)

    def test_a_real_price_move_is_material_once(self):
        self.hold()
        self.configure(min_state_dwell_seconds=0)
        self.service.run_once()
        self.cycle()
        calls = self.provider.calls
        self.prices['NVDA'] = 243.0  # 125 bps
        moved = self.cycle()
        self.assertIn('PRICE_MOVED', [code for t in moved['transitions'] if t['instrument_id'] == 'NVDA' for code in t['reason_codes']])
        self.assertEqual(self.provider.calls, calls + 1)
        self.assertEqual(self.cycle()['model_call_count'], 0)

    def test_quote_flapping_across_the_event_ttl_buys_no_model_call_inside_the_dwell(self):
        self.hold()
        self.configure()
        self.service.run_once()
        self.cycle()
        calls, decisions = self.provider.calls, len(self.action_repo.history('NVDA'))
        lost = self.cycle(age=61.0)  # no provider quote update within the 60 s event TTL
        self.assertIn('QUOTE_LOST', [code for t in lost['transitions'] if t['instrument_id'] == 'NVDA' for code in t['reason_codes']])
        for age in (1.0, 61.0, 1.0):
            receipt = self.cycle(age=age)
            self.assertEqual(receipt['model_call_count'], 0, receipt['transitions'])
            self.assertFalse(any(t['new_decision_id'] for t in receipt['transitions']), receipt['transitions'])
        self.assertEqual((self.provider.calls, len(self.action_repo.history('NVDA'))), (calls, decisions + 1))
        settled = self.cycle(seconds=120)  # one evaluation per instrument once the dwell since the loss has passed
        self.assertEqual([t['model_call'] for t in settled['transitions'] if t['instrument_id'] == 'NVDA'], [True])

    def test_a_silent_feed_is_stale_even_when_the_last_event_is_recent(self):
        self.hold()
        self.configure()
        self.service.run_once()
        self.cycle()
        calls = self.provider.calls
        receipt = self.cycle(age=20.0)  # received 10 s ago: the feed stopped delivering
        self.assertEqual((receipt['readiness']['readiness'], receipt['model_call_count'], self.provider.calls), ('REEVALUATION_BLOCKED', 0, calls))

    def test_stale_delayed_and_disconnected_quotes_fail_closed_without_a_model(self):
        for label, quote, connection in [('stale', dict(age=75.0), 'CONNECTED'), ('delayed', dict(quality='DELAYED'), 'CONNECTED'),
                                         ('no-tick', dict(tick=False), 'CONNECTED'), ('disconnected', {}, 'DISCONNECTED')]:
            with self.subTest(label=label):
                self.setUp()
                self.hold()
                self.configure()
                self.service.run_once()
                self.cycle()
                calls = self.provider.calls
                self.runtime.lifecycle.connection_state = connection
                receipt = self.cycle(seconds=120, **quote)
                self.assertEqual((receipt['model_call_count'], self.provider.calls), (0, calls))
                self.assertNotEqual(receipt['readiness']['readiness'], 'REEVALUATION_READY')
                latest = self.action_repo.history('NVDA')[0]
                self.assertEqual((latest['action_state'], latest['execution_readiness']), ('REVALIDATION_REQUIRED', 'BLOCKED'))
                self.assertEqual(self.ledger.events, [])


if __name__ == '__main__':
    unittest.main()
