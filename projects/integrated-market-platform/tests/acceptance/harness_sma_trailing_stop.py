"""OCT1-08 SOFTWARE_CONTROLLED browser harness. Loopback; every order submit route refused.

Production stop policy, stop service, SQLite persistence, action decisions,
traces and the OCT1-07 reevaluation cycle are used. Only the completed-bar feed,
the last-trade quote, the held-position projection, the model proposal, auth
and the (stepped) clock are fixtures. Run with an isolated IMP_STATE_DIR and
IMP_OCT1_08_HARNESS=1.
"""
import hashlib
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository
from market_platform_foundation.local_state.startup import open_local_state
from market_platform_foundation.research.sma_stop_evaluation import CORPUS_REL
from market_platform_foundation.risk.sma_trailing_stop import price_to_minor
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore
from tests.acceptance.harness_reevaluation import INSTRUMENT, Handler as ReevaluationHandler, base_monday
from tests.intelligence.test_reevaluation import Clock, FixtureAi, FixtureProvider, iso

CORPUS_FILE = ROOT / CORPUS_REL / 'normalized' / 'AAPL_normalized.json'


class Handler(ReevaluationHandler):
    bars, bar_state, quote_ok, preview_attempts, live_attempts = [], 'CURRENT', True, 0, 0

    @classmethod
    def read_bars(cls, instrument, policy, scale):
        return dict(state=cls.bar_state, reason=None if cls.bar_state == 'CURRENT' else 'STALE_BAR_SOURCE', source='CONTROLLED_FIXTURE', bars=list(cls.bars))

    @classmethod
    def read_quote(cls, instrument, scale):
        now = int(cls.clock() * 1e9)
        if not cls.quote_ok:
            return dict(admissible=False, reason='AGE_EXCEEDS_POLICY', source='CONTROLLED_FIXTURE')
        return dict(admissible=True, price_minor=price_to_minor(cls.ai.rows[INSTRUMENT]['price'], scale), as_of_ns=now,
                    source='CONTROLLED_FIXTURE', evidence_ref='q', reason=None)

    @classmethod
    def new_services(cls, owner):
        super().new_services(owner)
        # A fresh repository object over the same SQLite file: what a restarted process would read.
        cls.stops = SmaStopService(cls.store, repository=SmaStopRepository(open_local_state().connection), clock=cls.clock,
                                   bars=cls.read_bars, quotes=cls.read_quote, actions=cls.actions, ai=cls.ai)
        cls.actions.risk_control = cls.stops
        cls.store._sma_stop_service = cls.stops

    def stop_metrics(self):
        account = self.store.paper_ledger.paper_account_id
        return dict(self.metrics(), preview_attempts=Handler.preview_attempts, live_attempts=Handler.live_attempts,
                    submit_attempts=ReevaluationHandler.submit_attempts, bars=len(Handler.bars), bar_state=Handler.bar_state,
                    stop_events=self.stops.repository.event_count(account, INSTRUMENT), durability=self.stops.repository.durability,
                    corpus_sha256=hashlib.sha256(CORPUS_FILE.read_bytes()).hexdigest(),
                    paper_env=os.environ.get('IMP_PAPER_EXECUTION'), live_env=os.environ.get('IMP_LIVE_EXECUTION'))

    def do_GET(self):
        url = urlparse(self.path)
        path, query = url.path, {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        ledger = self.store.paper_ledger
        if path == '/acceptance/stop/metrics':
            self._send_json(self.stop_metrics())
        elif path == '/acceptance/stop/bar':
            # One more completed bar per close: it starts now and becomes available one minute later.
            for close in query['close'].split(','):
                start = int(self.clock() * 1e9)
                value = price_to_minor(close)
                Handler.bars.append(dict(bar_id=f'CONTROLLED:{INSTRUMENT}:1m:{start}', event_time=start, available_time=start + 60_000_000_000,
                                         open=value, high=value, low=value, close=value))
                self.clock.value += 60.0
            if 'price' in query:
                self.ai.rows[INSTRUMENT]['price'] = float(query['price'])
            self._send_json(self.stop_metrics())
        elif path == '/acceptance/stop/set':
            if 'price' in query: self.ai.rows[INSTRUMENT]['price'] = float(query['price'])
            if 'change' in query: self.ai.rows[INSTRUMENT]['change'] = float(query['change'])
            if 'bars' in query: Handler.bar_state = query['bars']
            if 'quote' in query: Handler.quote_ok = query['quote'] == 'ok'
            if 'position' in query:
                quantity = int(query['position'])
                row = dict(instrument_id=INSTRUMENT, symbol='NVDA', quantity=abs(quantity), side='SHORT' if quantity < 0 else 'LONG', mark_minor=15000)
                ledger.project_positions = (lambda: [dict(row)]) if quantity else (lambda: [])
            self._send_json(self.stop_metrics())
        elif path == '/acceptance/stop/reload':
            Handler.new_services('reloaded-' + str(len(Handler.bars)))
            self._send_json(self.stop_metrics())
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith('/paper/risk-control/'):
            UiApiHandler.do_POST(self)  # the stop monitor itself: no order capability on these routes
        elif path == '/paper/orders/preview':
            Handler.preview_attempts += 1  # the ticket revalidates a handed-off draft with a preview; a preview is never a submit
            UiApiHandler.do_POST(self)
        elif path.startswith('/live/'):
            Handler.live_attempts += 1
            self._send_error_json('HARNESS_LIVE_DISABLED', 'This harness never reaches Live.', status=403)
        else:
            super().do_POST()  # every other /paper/* and submit route is refused and counted


if __name__ == '__main__':
    if os.environ.get('IMP_OCT1_08_HARNESS') != '1' or not os.environ.get('IMP_STATE_DIR'):
        raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION'):
        os.environ.pop(key, None)
    os.environ['IMP_PAPER_EXECUTION'] = '1'
    store = ReplayStore(collection_root=ROOT.parent); store.load(); store.mode = 'PAPER'
    store.execution_deferred = False
    # Internal-simulation Paper authority only, exactly as the OCT1-06 harness grants it.
    store.execution_authority = store.paper_ledger.execution_authority = 'AUTHORIZED'
    store.execution_mode = store.paper_ledger.execution_mode = 'INTERNAL_SIMULATION'
    store.paper_ledger.project_positions = lambda: []
    clock, provider = Clock(base_monday()), FixtureProvider()
    ai = FixtureAi(clock, provider)
    ai.rows = {INSTRUMENT: dict(price=150.0, change=2.0)}
    ai.selected = [INSTRUMENT]
    # Shared with the OCT1-07 handler: its control routes and stepped schedule read these from the base class.
    for target in (ReevaluationHandler, Handler):
        target.store, target.clock, target.provider, target.ai = store, clock, provider, ai
        target.original_orders = store.paper_ledger.project_orders
    Handler.new_services('harness-' + str(os.getpid()))
    port = int(os.environ.get('IMP_E2E_API_PORT', '18808'))
    if port in (8766, 5173, 11111):
        raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready', iso(clock()), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
