"""Explicit SOFTWARE_CONTROLLED loopback harness; production bundle and services.

No provider credentials, external retrieval or submit route. Start with
IMP_SCREENER_PRICE_HARNESS=1 and isolated IMP_STATE_DIR.
"""
import json
import mimetypes
import os
import sys
import time
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
if os.environ.get('IMP_SCREENER_PRICE_HARNESS')!='1' or not os.environ.get('IMP_STATE_DIR'):
    raise SystemExit('Explicit isolated harness environment required')
for key in ('IMP_LIVE_EXECUTION','IMP_LIVE_OBSERVATIONAL','IMP_BROKER_PAPER_EXECUTION','IMP_PAPER_EXECUTION'):
    os.environ.pop(key,None)
from tests.platform.test_screener_live_price import Source
from tests.platform.test_screener_s18 import CandidateProvider, News
from market_platform_foundation.market_data.observational_state import QuoteSnapshot
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_projections import ScreenerService
from market_platform_foundation.local_state.action_decisions import action_repository
import market_platform_foundation.ui_api.screener_projections as projections
import market_platform_foundation.ui_api.screener_ai as ai_module
projections.us_equity_screener_session=lambda:'REGULAR'  # controlled session, never prospective
quotes={}; active=set()
runtime=SimpleNamespace(state=SimpleNamespace(quote_for=quotes.get), lifecycle=SimpleNamespace(connection_state='CONNECTED'),feed=SimpleNamespace(subscription_errors={}))
def subscribe(**kwargs): active.add((kwargs['consumer_id'],kwargs['instrument_id'])); return [{'accepted':True}]
def unsubscribe(**kwargs): active.discard((kwargs['consumer_id'],kwargs['instrument_id'])); return [{'released':True}]
runtime.subscribe, runtime.unsubscribe=subscribe,unsubscribe
service=ScreenerService(source_factory=Source,runtime_getter=lambda **_:runtime)
projections._SERVICE=service
class Fixture(CandidateProvider):
    def infer(self,packet,**kwargs):
        if packet.task_type.value=='SCREENER_ACTION_DECISION':
            from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
            candidate=packet.candidates[0]
            # Action prompt uses its own production packet; bounded no-action output.
            refs=[e['evidence_id'] for e in packet.candidates[0]['current_market_evidence']]
            self.action_calls+=1
            payload=dict(schema_version='action-proposal/1.0.0',proposal_state='NO_ACTION',direction=None,rationale='Controlled observation for review.',
                supporting_refs=refs,conflicting_refs=[],weak_refs=[],missing_capabilities=[x['capability'] for x in packet.candidates[0]['missing']],uncertainties=[],entry_conditions=[],hold_conditions=[],exit_conditions=[])
            return ProviderInferenceResponse(json.dumps(payload),self.provider_id,self.model_id,simulated=True)
        packet=SimpleNamespace(**{**packet.__dict__,'candidates':[c for c in packet.candidates if c['sufficient']]})
        return super().infer(packet,**kwargs)
    action_calls=0
class ControlledNews(News):
    def candidate_evidence(self, *, universe, rows, refresh=False):
        return {r['instrument']['instrument_id']:dict(state='UNAVAILABLE',window='4h',snapshot_at=datetime.now(UTC).isoformat(),
            providers=[],stories=[],limitations=['SOFTWARE_CONTROLLED: supporting news unavailable'],
            sentiment=dict(state='NOT_CONFIGURED',reason='CONTROLLED_NO_NEWS',dominant=None,model_id=None,model_revision=None,
                sentiment_version='news/finbert-sentiment/1.0.0',basis='IMP_DERIVED_FINBERT',method='No controlled headlines',counts={},scored=0,unscored=0,window='4h')) for r in rows}
Fixture.runtime='LOCAL_MODEL'  # configured inference contract; response remains simulated=True
model=Fixture(); ai=ScreenerAiService(reader=service,news=ControlledNews(model));ai_module._SERVICE=ai
store=ReplayStore(collection_root=ROOT.parent);store.load();store.mode='PAPER'
store._action_decision_service=ScreenerActionService(store,ai=ai)
state='reference'; requests=[]
def tick():
    if state!='live': return
    ns=time.time_ns()
    for symbol,price in [('AAPL',140.15),('NVDA',240.27),('AMD',120.12)]:
        quotes[symbol]=QuoteSnapshot(symbol,round(price-.01,2),round(price+.01,2),10,10,price,volume=2000,
            event_time_ns=ns-200_000_000,available_time_ns=ns,received_ns=ns,provider='MOOMOO_OPEND')
DIST=ROOT/'ui'/'dist'
class Handler(UiApiHandler):
    store=store
    def _authorize_request(self,*args,**kwargs):return True  # fixture auth only
    def log_message(self,*args):pass
    def do_GET(self):
        global state
        path=urlparse(self.path).path
        if path=='/acceptance/state':
            state=parse_qs(urlparse(self.path).query).get('state',['reference'])[0]
            runtime.lifecycle.connection_state='DISCONNECTED' if state=='stale' else 'CONNECTED'
            if state=='reference':quotes.clear()
            if state=='stale':
                for q in quotes.values():q.event_time_ns-=61_000_000_000;q.received_ns-=61_000_000_000
            tick();self._send_json({'state':state});return
        if path=='/acceptance/metrics':
            self._send_json(dict(classification='SOFTWARE_CONTROLLED',state=state,model_calls=model.calls,action_calls=model.action_calls,
                subscribed=len(active),paper_submits=sum('/paper/' in r for r in requests),live_submits=sum('/live/' in r for r in requests),
                ledger_events=len(store.paper_ledger.events)));return
        if path.startswith('/assets/') or path in ('/','/screener','/favicon.svg') and 'text/html' in self.headers.get('Accept',''):
            file=DIST/path.lstrip('/') if path.startswith('/assets/') else DIST/'index.html'
            if not file.is_file():self.send_error(404);return
            content=file.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        if path in ('/screener','/screener/window','/screener/ai-screener/preview'):tick()
        super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path;requests.append(path)
        if '/paper/' in path or '/live/' in path:
            self._send_error_json('HARNESS_SUBMIT_DISABLED','No submissions in this harness',status=403);return
        tick();super().do_POST()
server=ThreadingHTTPServer(('127.0.0.1',18827),Handler)
print('SOFTWARE_CONTROLLED http://127.0.0.1:18827/screener',flush=True)
try:server.serve_forever()
finally:server.server_close()
