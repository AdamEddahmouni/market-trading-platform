"""SOFTWARE_CONTROLLED production UI harness. No external data or trading."""
import json
import mimetypes
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests.trading_correctness.test_prospective_evaluation_api import ProspectiveServiceTests
from market_platform_foundation.ui_api.server import UiApiHandler
import market_platform_foundation.ui_api.prospective_evaluation as evaluation
case=ProspectiveServiceTests();case.setUp()
for price in ('152.00','148.00','150.00'):
    case.quote=150.;case.enter();case.tick(60)
    d=case.exit(price=price);case.governed(d,price=price);case.tick(60)
case.tick(1);case.order('AAPL','BUY',1,'150.00');case.tick(1)
case.decide(case.new_run('NVDA'),'NO_ACTION','NVDA');case.enter(instrument='NVDA');case.tick(60)
service=case.evaluation();evaluation._SERVICE,evaluation._STORE=service,case.store
DIST=ROOT/'ui'/'dist'
mutation_requests=[]
class Handler(UiApiHandler):
    store=case.store
    def _authorize_request(self,*args,**kwargs): return True
    def log_message(self,*args): pass
    def do_POST(self):
        mutation_requests.append(self.path.split('?')[0])
        super().do_POST()
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/harness-baseline':
            self._send_json(dict(fills=len(case.store.paper_ledger.project_trades()),model_calls=case.model.calls,live_submissions=sum('/live/' in p for p in mutation_requests),paper_submission_requests=sum('/paper/' in p for p in mutation_requests),evidence_class='SOFTWARE_CONTROLLED'));return
        if path.startswith('/assets/') or path in ('/','/portfolio/evaluation','/favicon.svg'):
            file=DIST/path.lstrip('/') if path.startswith('/assets/') or path=='/favicon.svg' else DIST/'index.html'
            if not file.is_file(): self.send_error(404);return
            content=file.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',8891),Handler)
print(json.dumps(dict(url='http://127.0.0.1:8891/portfolio/evaluation',classification='SOFTWARE_CONTROLLED')),flush=True)
try: server.serve_forever()
finally: server.server_close();case.doCleanups()
