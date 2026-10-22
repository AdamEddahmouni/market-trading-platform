"""Full-universe AI Screener SOFTWARE_CONTROLLED browser harness. Loopback; Live is never reachable.

The production run tracker, coverage pipeline, candidate reducer, coverage ledger and status/stop/coverage
routes are used. Only the Screener rows, the reduction engine's answers and auth are fixtures: Run now in
the real UI starts a real full-universe run over a controlled universe. Run with an isolated IMP_STATE_DIR
and IMP_FULL_UNIVERSE_HARNESS=1. Nothing here is market evidence.

Query parameters of ``/acceptance/coverage/scenario`` choose the next run's universe and engine:
``rows`` (default 260), ``fail_on`` (a request number that fails), ``delay_ms`` per request (default 400).
"""
import json
import os
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from market_platform_foundation.local_state.action_decisions import action_repository
from market_platform_foundation.ui_api import screener_ai_runs
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.store import ReplayStore
from tests.acceptance.harness_action_decision import FixtureModel, Handler as ActionHandler, iso
from tests.support.coverage_universe import FailingProvider, News, PagingReader, universe


class FreshReader(PagingReader):
    """Every read is observed now, as a live Screener page is, and any pinned result set is this one."""

    def read(self, **kwargs):
        now = iso(time.time())
        for row in self.rows:
            for field in row['fields'].values():
                field['as_of'] = now
        page = super().read(**{**kwargs, 'result_set': None})
        return {**page, 'universe_as_of': now, 'screener_as_of': now}


class PacedEngine(FailingProvider):
    """The controlled reduction engine, slowed so a person can watch the batches go by."""

    def __init__(self, *, fail_on, delay):
        super().__init__(fail_on=fail_on)
        self.delay = delay

    def on_call(self, call, packet):
        time.sleep(self.delay)
        return super().on_call(call, packet)


class Handler(ActionHandler):
    engine = None

    @classmethod
    def scenario(cls, rows=260, fail_on=0, delay_ms=400):
        strong = {rows - 1: 96.0, rows // 2: 91.0, 51: 87.0} if rows > 52 else {rows - 1: 96.0} if rows else {}
        cls.engine = PacedEngine(fail_on=fail_on, delay=delay_ms / 1000)
        service = ScreenerAiService(reader=FreshReader(universe(rows, strong=strong)), news=News(cls.engine), clock=time.time)
        screener_ai_runs._RUNS = screener_ai_runs.AiScreenerRuns(service)
        return dict(rows=rows, strong_positions=sorted(strong), fail_on=fail_on, delay_ms=delay_ms)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/acceptance/coverage/scenario':
            query = {key: int(value[0]) for key, value in parse_qs(url.query).items()}
            self._send_json(self.scenario(**query))
            return
        if url.path == '/acceptance/coverage/metrics':
            self._send_json(dict(model_calls=self.engine.calls, ledger_events=len(self.store.paper_ledger.events)))
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/screener/ai-screener':
            # The production start: a real full-universe run over the controlled universe.
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
            self._send_json(screener_ai_runs.ai_screener_runs().start(self.store.paper_ledger.paper_account_id, body))
            return
        super().do_POST()


if __name__ == '__main__':
    if os.environ.get('IMP_FULL_UNIVERSE_HARNESS') != '1' or not os.environ.get('IMP_STATE_DIR'):
        raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_BROKER_LIVE_EXECUTION',
                'IMP_MOOMOO_LIVE', 'IMP_FINVIZ_LIVE', 'IMP_LIVE_INTERNAL_SIMULATION'):
        os.environ.pop(key, None)
    os.environ['IMP_PAPER_EXECUTION'] = '1'
    Handler.store = ActionHandler.store = ReplayStore(collection_root=ROOT.parent)
    Handler.store.load()
    Handler.store.mode = 'PAPER'
    Handler.repo = ActionHandler.repo = action_repository()
    Handler.model = ActionHandler.model = FixtureModel()
    Handler.original_project_orders = ActionHandler.original_project_orders = Handler.store.paper_ledger.project_orders
    ai = SimpleNamespace(_news_service=lambda: SimpleNamespace(synthesis_provider=lambda: Handler.model))
    Handler.service = ActionHandler.service = ScreenerActionService(Handler.store, repository=Handler.repo, ai=ai)
    Handler.store._action_decision_service = Handler.service
    Handler.configure('NO_ACTION')
    Handler.scenario()
    port = int(os.environ.get('IMP_E2E_API_PORT', '18840'))
    if port in (8766, 5173, 11111, 18909):
        raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready', os.getpid(), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
