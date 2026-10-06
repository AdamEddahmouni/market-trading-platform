"""OCT1-10 SOFTWARE_CONTROLLED browser harness. Loopback; Live is never reachable.

The production lifecycle projection, action-decision service, SMA stop service,
Paper preview/submit route, pre-trade risk, simulator, experiment ledger and
SQLite local state are used. Only the clock, the completed-bar feed, the
last-trade quote, the marks, the candidate receipts, the model proposal, the
governed Opportunity and auth are fixtures. Run with an isolated IMP_STATE_DIR
and IMP_OCT1_10_HARNESS=1. Nothing here is market evidence.
"""
import os
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from market_platform_foundation.intelligence.contracts.common import IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.persistence.memory import InMemoryIntelligenceRepository
from market_platform_foundation.local_state.action_decisions import action_repository
from market_platform_foundation.local_state.sma_trailing_stop import sma_stop_repository
from market_platform_foundation.ui_api.paper_risk_control import SmaStopService
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_lifecycle import TradeLifecycleService
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.xa01.compatibility import register_equity
from tests.acceptance.harness_action_decision import FixtureModel, Handler as ActionHandler, iso
from tests.acceptance.harness_paper_experiment import Handler as ExperimentHandler, SECOND
from tests.intelligence.test_action_decision import candidate

MINUTE = 60_000_000_000


class Handler(ExperimentHandler):
    offset, cutoff, anchor, closes, quote, runs = 0.0, 0.0, None, [], 150.0, 0

    # --- one controlled clock for decisions, stops, fills and marks ------------------
    @classmethod
    def advance(cls, seconds=0.0):
        cls.offset += seconds
        cls.cutoff = max(cls.cutoff + seconds, time.time() + cls.offset)

    @classmethod
    def packet(cls, instrument, state):
        price = float(cls.feed.prices.get(instrument, '150.00'))
        c = candidate()
        c['sufficient'] = True
        c['instrument'] = dict(instrument_id=instrument, symbol=instrument, universe='US_EQUITIES')
        for e in c['current_market_evidence']:
            e.update(as_of=iso(cls.cutoff), valid_until=iso(cls.cutoff + 600), instrument_id=instrument, source='CONTROLLED_FIXTURE',
                     delivery_mode='FIXTURE', freshness_status='CURRENT')
        c['current_market_evidence'][0]['facts']['price'] = price
        if state == 'EXIT':
            c['current_market_evidence'][1]['facts']['change_pct'] = -2
        c['reference_evidence'] = [dict(c['current_market_evidence'][1], evidence_id='news-conflict', capability='SENTIMENT',
                                        role='REFERENCE_CONTEXT', facts=dict(label='NEGATIVE'), delivery_mode='PUBLICATION_BASED',
                                        freshness_status='PUBLICATION_CURRENT')]
        c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['news-conflict'], news_refs=[], kind='NEWS_SENTIMENT_VS_PRICE',
                                method='CONTROLLED_FIXTURE', observed_direction='POSITIVE', comparator_ref='t', cutoff=iso(cls.cutoff),
                                alignment_id='controlled-conflict', limitations=['Fixture conflict'])]
        # What the candidate does not have stays visible: one excluded stale input.
        c['blocked'] = [dict(capability='LEVEL2', role='CURRENT_MARKET', source='CONTROLLED_FIXTURE', as_of=iso(cls.cutoff - 900),
                             reason_codes=['AGE_EXCEEDS_POLICY'], freshness_status='STALE', decision_admissibility='BLOCKED')]
        return c

    @classmethod
    def configure(cls, state, authority=True, instruments=('AAPL',)):
        """A stored AI Screener run that selected these instruments. Positions, orders and authority are the real ledger's."""
        cls.advance()
        cls.model.state = state
        cls.runs += 1
        identity = f'controlled-{int(cls.cutoff * 1e6)}-{cls.runs}'
        cls.run = dict(
            schema_version='screener-ai-screener/1.0.0', run_id=identity, state='CURRENT', valid_until=iso(cls.cutoff + 600), input_hash=identity,
            evidence=[cls.packet(i, state) for i in instruments],
            candidates=[dict(instrument_id=i, rank=rank, rationale='Observed evidence warrants review.', supporting_refs=['q', 't'],
                             conflicting_refs=['news-conflict'], weak_refs=[], missing_capabilities=[], uncertainties=[])
                        for rank, i in enumerate(instruments, 1)],
            decision_cutoff=iso(cls.cutoff), generated_at=iso(cls.cutoff), matched_count=len(instruments), intake_count=len(instruments), max_intake=20,
            provider_id=cls.model.provider_id, model_id=cls.model.model_id, runtime='LOCAL_MODEL', prompt_id='screener.candidate_reduction.v1',
            prompt_version='1', prompt_hash='fixture', packet_bytes=1000, cache='MISS', simulated=True, limitations=['SOFTWARE_CONTROLLED_EVIDENCE'], coverage={})
        cls.repo.put('candidate_run', identity, cls.run)
        repository = getattr(cls.store, 'strategy_repository', None)
        if not isinstance(repository, InMemoryIntelligenceRepository):
            repository = cls.store.strategy_repository = InMemoryIntelligenceRepository()
        repository.put_opportunity(OpportunityV1(
            f'controlled-opportunity-{cls.runs}', '1', IntelligenceScope(tuple(instruments)), int((cls.cutoff - 1) * 1e9),
            QualitySummary('GOOD'), side='LONG', valid_until_ns=int((cls.cutoff + 600) * 1e9)))

    # --- controlled stop inputs ---------------------------------------------------------
    @classmethod
    def read_bars(cls, instrument, policy, scale):
        bars = [dict(bar_id=f'B{i}', event_time=cls.anchor + i * MINUTE, available_time=cls.anchor + (i + 1) * MINUTE, open=c, high=c, low=c, close=c)
                for i, c in enumerate(cls.closes)] if cls.anchor is not None else []
        return dict(state='CURRENT', reason=None, source='CONTROLLED_FIXTURE', bars=bars)

    @classmethod
    def read_quote(cls, instrument, scale):
        return dict(admissible=True, price_minor=int(round(cls.quote * 100)), as_of_ns=int(cls.cutoff * 1e9), source='CONTROLLED_FIXTURE',
                    evidence_ref='q', reason=None)

    def stop(self, query):
        operation, instrument = query.get('op'), query.get('instrument', 'AAPL')
        if operation == 'configure':
            Handler.advance()
            Handler.anchor, Handler.closes = int(Handler.cutoff * 1e9), []
            self.stops.configure(dict(enabled=True, sma_window_bars=int(query.get('window', 2))))
        elif operation == 'bar':
            # One more completed bar: the clock moves past it, as it does for a monitored position.
            Handler.closes.append(int(round(float(query['close']) * 100)))
            Handler.advance(60)
            self.stops.evaluate(instrument)
        elif operation == 'quote':
            Handler.quote = float(query['price'])
            Handler.feed.prices[instrument] = query['price']
            Handler.advance(1)
            # The production "Evaluate Stop Now" path: on a breach it appends the deterministic EXIT, never an order.
            self.stops.evaluate_now(dict(instrument_id=instrument))
        else:
            raise ValueError('UNKNOWN_STOP_OPERATION')
        return self.stops.status(instrument)

    def lifecycle_metrics(self):
        account = self.store.paper_ledger.paper_account_id
        return dict(self.metrics(), run_id=self.run['run_id'], offset_seconds=Handler.offset, bars=len(Handler.closes),
                    stop_events=self.stops.repository.event_count(account, 'AAPL'), decisions=len(self.repo.history('AAPL')),
                    trades=len(self.store.paper_ledger.project_trades()) if self.store.paper_ledger.is_portfolio_scoped() else 0)

    def do_GET(self):
        url = urlparse(self.path)
        path, query = url.path, {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        if path == '/acceptance/lifecycle/metrics':
            self._send_json(self.lifecycle_metrics())
        elif path == '/acceptance/lifecycle/scenario':
            self.configure(query.get('state', 'ENTER'), instruments=tuple(query.get('instruments', 'AAPL').split(',')))
            self._send_json(self.lifecycle_metrics())
        elif path == '/acceptance/lifecycle/stop':
            self._send_json(self.stop(query))
        else:
            super().do_GET()


if __name__ == '__main__':
    if os.environ.get('IMP_OCT1_10_HARNESS') != '1' or not os.environ.get('IMP_STATE_DIR'):
        raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_BROKER_LIVE_EXECUTION',
                'IMP_MOOMOO_LIVE', 'IMP_FINVIZ_LIVE', 'IMP_LIVE_INTERNAL_SIMULATION'):
        os.environ.pop(key, None)
    os.environ['IMP_PAPER_EXECUTION'] = '1'
    register_equity(symbol=SECOND)
    Handler.cutoff = time.time()
    feed, last = Handler.feed, [0]

    def now_ns():
        last[0] = max(int(Handler.cutoff * 1e9), last[0] + 1_000)
        return last[0]
    feed.now_ns = now_ns  # fills and marks share the decisions' controlled clock
    feed.install()
    store = ReplayStore(collection_root=ROOT.parent)
    store.load()
    store.mode = 'PAPER'
    Handler.store = ExperimentHandler.store = ActionHandler.store = store
    Handler.repo = ExperimentHandler.repo = ActionHandler.repo = action_repository()
    Handler.model = ExperimentHandler.model = ActionHandler.model = FixtureModel()
    ai = SimpleNamespace(_news_service=lambda: SimpleNamespace(synthesis_provider=lambda: Handler.model), _query=lambda body: body,
                         _packet=lambda scope, **_: (scope, [Handler.packet('AAPL', 'EXIT')], iso(Handler.cutoff), {}))
    clock = lambda: Handler.cutoff
    Handler.service = ExperimentHandler.service = ActionHandler.service = ScreenerActionService(store, repository=Handler.repo, ai=ai, clock=clock)
    store._action_decision_service = Handler.service
    Handler.stops = SmaStopService(store, repository=sma_stop_repository(), clock=clock, bars=Handler.read_bars, quotes=Handler.read_quote,
                                   actions=Handler.service, ai=ai)
    Handler.service.risk_control = Handler.stops
    store._sma_stop_service = Handler.stops
    # The projection reads a moving clock, so decision validity and mark age are judged honestly.
    store._trade_lifecycle_service = TradeLifecycleService(store, clock=lambda: time.time() + Handler.offset)
    Handler.configure('NO_ACTION')
    port = int(os.environ.get('IMP_E2E_API_PORT', '18810'))
    if port in (8766, 5173, 11111, 18909):
        raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready', os.getpid(), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
