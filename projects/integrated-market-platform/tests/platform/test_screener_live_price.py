"""Backend row/cache to AI/action convergence: SOFTWARE_CONTROLLED."""
from __future__ import annotations
import copy
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.market_data.observational_state import QuoteSnapshot
from market_platform_foundation.ui_api.screener_projections import ScreenerService
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from tests.platform.test_screener_s18 import CandidateProvider, News
NOW = '2026-10-06T18:05:24Z'
SECONDS = datetime.fromisoformat(NOW.replace('Z', '+00:00')).timestamp()
NS = int(SECONDS * 1e9)
class Source:
    calls = 0
    def fetch_export(self, **kwargs):
        self.calls += 1
        return dict(success=True, received_at=NOW, rows=[
            FinvizScreenerRow(ticker=s, company=s, price=240.0, volume=1000+i,
                             market_cap=500.0, short_float_pct=2.0)
            for i, s in enumerate(('AAPL', 'NVDA', 'AMD'))])
class LivePriceTests(unittest.TestCase):
    def setUp(self):
        self.source, self.quotes = Source(), {}
        self.runtime = SimpleNamespace(state=SimpleNamespace(quote_for=self.quotes.get),
            lifecycle=SimpleNamespace(connection_state='CONNECTED'), feed=SimpleNamespace(subscription_errors={}))
        self.service = ScreenerService(source_factory=lambda: self.source,
            runtime_getter=lambda **_: self.runtime, now=lambda: NOW)
        for name, value in [('time.time_ns', NS), ('us_equity_screener_session', 'REGULAR')]:
            p = patch('market_platform_foundation.ui_api.screener_projections.'+name, return_value=value)
            p.start(); self.addCleanup(p.stop)
    def quote(self, symbol='NVDA', price=240.27, event=NS-1_000_000_000, received=NS-500_000_000, quality='PASS'):
        self.quotes[symbol] = QuoteSnapshot(symbol, round(price-.01,2), round(price+.01,2), 10, 10, price,
            volume=2000, event_time_ns=event, available_time_ns=received,
            received_ns=received, quality=quality, provider='MOOMOO_OPEND')
    def row(self, symbol='NVDA', **kwargs):
        return next(r for r in self.service.read(**kwargs)['rows'] if r['symbol']==symbol)
    def packet(self, search=''):
        provider = CandidateProvider()
        ai = ScreenerAiService(reader=self.service, news=News(provider), clock=lambda: SECONDS)
        with patch('market_platform_foundation.ui_api.screener_ai.flow_observation', return_value=[]):
            scope, candidates, now, _ = ai._packet({'universe':'US_EQUITIES', 'search':search})
        return ai, provider, scope, candidates
    def test_live_quote_reaches_row_and_ai_with_same_clock(self):
        self.quote(); row=self.row()
        self.assertEqual(row['fields']['price']['value'],240.27)
        self.assertEqual(row['fields']['price']['source'],'MOOMOO_OPEND')
        self.assertEqual(row['fields']['market_cap']['source'],'FINVIZ_ELITE')
        self.assertEqual(row['fields']['market_cap']['value'],500)
        _,_,_,cs=self.packet(); c=next(c for c in cs if c['instrument']['instrument_id']=='NVDA')
        q=next(e for e in c['current_market_evidence'] if e['capability']=='QUOTE')
        self.assertEqual((q['facts']['price'],q['facts']['bid'],q['facts']['ask']),(240.27,240.26,240.28))
        self.assertAlmostEqual(q['facts']['spread_pct'], .02/240.27*100)
        self.assertEqual(q['as_of'],'2026-10-06T18:05:23Z')
        self.assertEqual(q['received_at'],'2026-10-06T18:05:23.500000Z')
        self.assertEqual(q['freshness_status'],'CURRENT'); self.assertTrue(c['sufficient'])
    def test_absent_live_price_remains_timeless_and_no_model_call(self):
        ai,p,scope,cs=self.packet()
        self.assertTrue(all(not c['sufficient'] for c in cs))
        self.assertTrue(all(any('NO_OBSERVATION_TIME' in b['reason_codes'] for b in c['blocked'] if b['capability']=='QUOTE') for c in cs))
        result=ai._provider_reducer().reduce(scope,cs,NOW)
        self.assertEqual(result['state'],'NO_GROUNDED_CANDIDATES'); self.assertEqual(p.calls,0)
    def test_reference_refresh_cannot_overwrite_live_or_cached_reference(self):
        before=self.row(); self.quote(); live=self.row(force_refresh=True)
        self.assertEqual(live['fields']['price']['value'],240.27)
        self.assertEqual(before['fields']['price']['value'],240)
        self.assertEqual(next(r for r in self.service._rows if r['symbol']=='NVDA')['fields']['price']['value'],240)
        self.assertEqual(self.service.row_for('NVDA')[0]['fields']['price']['value'],240.27)
    def test_symbol_isolation_and_snapshot_order_survive(self):
        for s,p,off in [('AAPL',101,1),('NVDA',202,2),('AMD',303,3)]: self.quote(s,p,NS-off*1_000_000_000)
        rows=self.service.read(sort='price')['rows']
        self.assertEqual([r['symbol'] for r in rows],['AAPL','AMD','NVDA'])
        for r in rows:
            q=self.quotes[r['symbol']]
            self.assertEqual(r['fields']['price']['value'],q.last_price)
            self.assertEqual(r['fields']['price']['event_time_ns'],q.event_time_ns)
        self.assertEqual(self.source.calls,1)
    def test_stale_future_delayed_missing_clock_and_disconnect_fail_closed(self):
        for label,attrs in [('stale',dict(event=NS-61_000_000_000)),('future',dict(event=NS+1_000_000_000)),
                            ('delayed',dict(quality='DELAYED')),('missing',dict(event=0)),('disconnected',{})]:
            with self.subTest(label=label):
                self.quote(**attrs); self.runtime.lifecycle.connection_state='DISCONNECTED' if label=='disconnected' else 'CONNECTED'
                self.assertEqual(self.row()['fields']['price']['value'],240.27)
                _,_,_,cs=self.packet(); c=next(c for c in cs if c['instrument']['instrument_id']=='NVDA')
                self.assertFalse(c['sufficient']); self.assertFalse(any(e['capability']=='QUOTE' for e in c['current_market_evidence']))
                reasons=[r for b in c['blocked'] if b['capability']=='QUOTE' for r in b['reason_codes']]
                if label=='future': self.assertIn('FUTURE_OBSERVATION_TIME',reasons)
                if label=='missing': self.assertIn('NO_OBSERVATION_TIME',reasons)
    def test_tick_after_reconnect_restores_current_without_changing_reference(self):
        self.quote(event=NS-61_000_000_000); self.runtime.lifecycle.connection_state='DISCONNECTED'
        self.assertEqual(self.row()['fields']['price']['state'],'STALE')
        self.runtime.lifecycle.connection_state='CONNECTED'; self.quote(price=241)
        self.assertEqual(self.row()['fields']['price']['state'],'LIVE')
        self.assertEqual(self.row()['fields']['short_float_pct']['value'],2)
    def test_aging_without_tick_and_post_cutoff_facts_discarded(self):
        self.quote(); _,_,_,cs=self.packet('NVDA')
        from market_platform_foundation.intelligence.inference.candidate_reduction import build_candidate
        from market_platform_foundation.ui_api.screener_ai import observations_for_row
        from market_platform_foundation.ui_api.screener_freshness import project_screener_response
        for cutoff in ('2026-10-06T18:06:25Z','2026-10-06T18:05:22Z'):
            r=project_screener_response('/screener',self.service.read(search='NVDA'),now=cutoff)['rows'][0]
            c=build_candidate(r['instrument'],observations_for_row(r,now=cutoff),now=cutoff)
            self.assertFalse(c['sufficient']); self.assertNotIn('240.27',str(c))
        self.assertTrue(cs[0]['sufficient'])
    def test_preview_run_action_lineage_hash_and_history(self):
        from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
        from market_platform_foundation.ui_api.screener_action import ScreenerActionService
        from market_platform_foundation.paper.ledger import PaperExecutionLedger
        self.quote(); ai,p,_,_=self.packet('NVDA'); repo=ActionDecisionRepository()
        with patch('market_platform_foundation.local_state.action_decisions.action_repository',return_value=repo), patch('market_platform_foundation.ui_api.screener_ai.flow_observation',return_value=[]):
            preview=ai.preview({'universe':'US_EQUITIES','search':'NVDA'})
            self.assertEqual(p.calls,0); self.assertEqual(preview['evidence_summary']['sufficient'],1)
            run=ai.run({'universe':'US_EQUITIES','search':'NVDA'})
            self.assertEqual(run['state'],'CURRENT'); self.assertEqual(p.calls,1)
            self.assertEqual(run['intake_count'],1); self.assertEqual(run['decision_cutoff'],NOW)
            frozen=copy.deepcopy(repo.get('candidate_run',run['run_id']))
            ledger=PaperExecutionLedger(paper_account_id='controlled-price',session_id='controlled')
            action=ScreenerActionService(SimpleNamespace(paper_ledger=ledger,execution_deferred=False),repository=repo,ai=ai,clock=lambda:SECONDS)
            assessment=action.preview(dict(run_id=run['run_id'],instrument_id='NVDA'))
            self.assertTrue(assessment['candidate_current']); self.assertEqual(p.calls,1)
            packet=action._build(dict(run_id=run['run_id'],instrument_id='NVDA'))
            self.assertEqual(packet['candidate']['current_market_evidence'][0]['facts']['price'],240.27)
            self.assertEqual(ledger.events,[])
            self.quote(price=241); changed=ai.run({'universe':'US_EQUITIES','search':'NVDA'})
            self.assertNotEqual(run['input_hash'],changed['input_hash'])
            self.assertEqual(repo.get('candidate_run',run['run_id']),frozen)
    def test_carried_bid_ask_never_inherit_a_later_last_price_clock(self):
        self.quote()
        self.quotes['NVDA'].book_received_ns = NS-2_000_000_000
        row = self.row()
        self.assertIsNone(row['fields']['bid']['provider_as_of'])
        self.assertEqual(row['fields']['bid']['received_ns'], NS-2_000_000_000)
        _, _, _, candidates = self.packet('NVDA')
        c = candidates[0]
        quote = next(e for e in c['current_market_evidence'] if e['capability']=='QUOTE')
        self.assertEqual(quote['facts'], {'price':240.27})
        self.assertTrue(c['sufficient'])

    def test_etf_canonical_identity_joins_market_data_symbol(self):
        from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener
        self.quote('SPY',500)
        row={'instrument':{'instrument_id':'XA01-ETF-SPY','asset_class':'ETF_FUND'},'symbol':'SPY','company':'SPY',
             'market_data_id':'SPY','fields':{'price':{'value':490,'source':'MOOMOO_OPEND_SNAPSHOT','state':'SNAPSHOT'}}}
        multi=MultiUniverseScreener()
        with patch.object(multi,'_catalog_state',return_value=([row],NOW,None,NOW)), patch('market_platform_foundation.ui_api.screener_multi.screener_service',return_value=self.service):
            page=multi.read(universe='US_ETFS',sort='symbol')
        self.assertEqual(page['rows'][0]['fields']['price']['value'],500)
        self.assertEqual(page['rows'][0]['instrument']['instrument_id'],'XA01-ETF-SPY')
        self.assertEqual(row['fields']['price']['value'],490)
if __name__=='__main__': unittest.main()
