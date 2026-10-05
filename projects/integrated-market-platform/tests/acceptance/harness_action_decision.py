"""OCT1-06 SOFTWARE_CONTROLLED browser harness. Loopback; no submit route.

Production action service, persistence, traces and Paper preview are used. Only
candidate receipts/model output/held-position projections and auth are fixtures.
Run with an isolated IMP_STATE_DIR and IMP_OCT1_06_HARNESS=1.
"""
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.local_state.action_decisions import action_repository
from market_platform_foundation.intelligence.persistence.memory import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from tests.intelligence.test_action_decision import candidate, proposal

def iso(value): return datetime.fromtimestamp(value,UTC).isoformat().replace('+00:00','Z')

class FixtureModel:
    provider_id='oct1-06.fixture'; model_id='controlled-proposal'; runtime='LOCAL_MODEL'
    calls=0
    state='NO_ACTION'
    def infer(self,*args,**kwargs):
        self.calls+=1
        p=proposal(self.state)
        p['conflicting_refs']=['news-conflict']
        return ProviderInferenceResponse(json.dumps(p),self.provider_id,self.model_id,simulated=True,tokens_input=250,tokens_output=120,latency_ms=1)

class Handler(UiApiHandler):
    def _authorize_request(self,*args,**kwargs): return True  # test-only, not auth acceptance
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/screener':
            self._send_json(dict(schema_version='screener/1.0.0',universe='US_EQUITIES',generated_at=iso(self.cutoff),market_session='regular',universe_as_of=iso(self.cutoff),screener_as_of=iso(self.cutoff),result_count=0,unfiltered_count=0,provider_health=[],source_error=None,rows=[])); return
        if path=='/acceptance/action/scenario':
            q=parse_qs(urlparse(self.path).query); self.configure(q.get('state',['NO_ACTION'])[0],q.get('authority',['1'])[0]=='1')
            self._send_json({'run_id':self.run['run_id'],'calls':self.model.calls,'ledger_events':len(self.store.paper_ledger.events)}); return
        if path=='/acceptance/action/metrics':
            self._send_json({'calls':self.model.calls,'ledger_events':len(self.store.paper_ledger.events),'decisions':len(self.repo.history('AAPL'))}); return
        if path=='/acceptance/action/expire':
            self.service.clock=lambda:self.cutoff+601
            self._send_json({'expired':True}); return
        if path=='/screener/ai-screener/preview':
            scope=dict(universe='US_EQUITIES',search='',sort='symbol',descending=False,filters=[])
            self._send_json(dict(schema_version='screener-ai-screener-preview/1.0.0',ai=dict(state='AVAILABLE',reason=None,provider_id=self.model.provider_id,model_id=self.model.model_id,runtime='LOCAL_MODEL'),scope=scope,matched_count=1,intake_count=1,max_intake=20,estimate=None,evidence_summary=dict(sufficient=1,blocked=0,missing=0,weak=0),decision_cutoff=iso(self.cutoff))); return
        super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        if path=='/screener/ai-screener':
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
            self._send_json(dict(self.run,scope=body)); return
        if path in ('/paper/orders','/paper/order/submit','/paper/orders/submit'):
            self._send_error_json('HARNESS_SUBMIT_DISABLED','This harness only previews.',status=403); return
        super().do_POST()
    @classmethod
    def configure(cls,state,authority=True):
        cls.cutoff=time.time(); cls.model.state=state
        if state=='ENTER_RISK': cls.model.state='ENTER'
        cls.store.execution_deferred=False
        cls.store.execution_authority='AUTHORIZED' if authority else 'BLOCKED'
        cls.store.execution_mode='INTERNAL_SIMULATION'
        cls.service.clock=lambda:cls.cutoff
        ledger=cls.store.paper_ledger
        ledger.execution_authority='AUTHORIZED' if authority else 'BLOCKED'
        ledger.execution_mode='INTERNAL_SIMULATION'
        ledger.project_orders=cls.original_project_orders
        if state=='ENTER_RISK':
            ledger.project_orders=lambda:[dict(state='FILLED',decision_source_snapshot=dict(source_type='watched_opportunity',source_id='controlled-opportunity'))]
        quantity=7 if state in ('HOLD','EXIT') else 0
        ledger.project_positions=lambda:[dict(instrument_id='AAPL',symbol='AAPL',quantity=quantity,side='LONG',mark_minor=15000)] if quantity else []
        c=candidate(); c['sufficient']=True; c['instrument']=dict(instrument_id='AAPL',symbol='AAPL',universe='US_EQUITIES')
        for e in c['current_market_evidence']:
            e.update(as_of=iso(cls.cutoff),valid_until=iso(cls.cutoff+600),instrument_id='AAPL',source='CONTROLLED_FIXTURE',delivery_mode='FIXTURE',freshness_status='CURRENT')
        if state=='EXIT': c['current_market_evidence'][1]['facts']['change_pct']=-2
        if state=='STALE':
            cls.model.state='ENTER'
            for e in c['current_market_evidence']: e['valid_until']=iso(cls.cutoff-1)
        c['reference_evidence']=[dict(c['current_market_evidence'][1],evidence_id='news-conflict',capability='SENTIMENT',role='REFERENCE_CONTEXT',facts=dict(label='NEGATIVE'))]
        c['alignments']=[dict(result='CONFLICTING',sentiment_refs=['news-conflict'],news_refs=[],kind='NEWS_SENTIMENT_VS_PRICE',method='CONTROLLED_FIXTURE',observed_direction='POSITIVE',comparator_ref='t',cutoff=iso(cls.cutoff),alignment_id='controlled-conflict',limitations=['Fixture conflict'])]
        selected=dict(instrument_id='AAPL',rank=1,rationale='Observed evidence warrants review.',supporting_refs=['q','t'],conflicting_refs=['news-conflict'],weak_refs=[],missing_capabilities=[],uncertainties=[])
        identity='controlled-'+str(time.time_ns())
        cls.run=dict(schema_version='screener-ai-screener/1.0.0',run_id=identity,state='CURRENT',valid_until=iso(cls.cutoff+600),input_hash=identity,evidence=[c],candidates=[selected],
            decision_cutoff=iso(cls.cutoff),generated_at=iso(cls.cutoff),matched_count=1,intake_count=1,max_intake=20,
            provider_id=cls.model.provider_id,model_id=cls.model.model_id,runtime='LOCAL_MODEL',prompt_id='screener.candidate_reduction.v1',prompt_version='1',prompt_hash='fixture',packet_bytes=1000,cache='MISS',simulated=True,limitations=['SOFTWARE_CONTROLLED_EVIDENCE'],coverage={})
        cls.repo.put('candidate_run',identity,cls.run)
        cls.store.strategy_repository=InMemoryIntelligenceRepository()
        cls.store.strategy_repository.put_opportunity(OpportunityV1('controlled-opportunity','1',IntelligenceScope(('AAPL',)),int((cls.cutoff-1)*1e9),QualitySummary('GOOD'),side='LONG',valid_until_ns=int((cls.cutoff+600)*1e9)))

if __name__=='__main__':
    if os.environ.get('IMP_OCT1_06_HARNESS')!='1' or not os.environ.get('IMP_STATE_DIR'): raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION','IMP_LIVE_OBSERVATIONAL','IMP_BROKER_PAPER_EXECUTION'): os.environ.pop(key,None)
    os.environ['IMP_PAPER_EXECUTION']='1'
    Handler.store=ReplayStore(collection_root=ROOT.parent); Handler.store.load(); Handler.store.mode='PAPER'
    Handler.repo=action_repository(); Handler.model=FixtureModel()
    Handler.original_project_orders=Handler.store.paper_ledger.project_orders
    ai=SimpleNamespace(_news_service=lambda:SimpleNamespace(synthesis_provider=lambda:Handler.model))
    Handler.service=ScreenerActionService(Handler.store,repository=Handler.repo,ai=ai)
    Handler.store._action_decision_service=Handler.service
    Handler.configure('NO_ACTION')
    port=int(os.environ.get('IMP_E2E_API_PORT','18806'))
    if port in (8766,5173,11111): raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
