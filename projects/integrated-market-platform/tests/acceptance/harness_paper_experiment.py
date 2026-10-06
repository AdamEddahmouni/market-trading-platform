"""OCT1-09 SOFTWARE_CONTROLLED browser harness. Loopback; Live is never reachable.

The production experiment service, Paper preview/submit route, pre-trade risk,
bar-conservative simulator, ledger, SQLite local state, action decisions and
traces are used. Only the completed-bar feed, the marks, the candidate receipt,
the model proposal, the governed Opportunity and auth are fixtures. A restart
is a real process restart over the same IMP_STATE_DIR: nothing is carried in
memory. Run with an isolated IMP_STATE_DIR and IMP_OCT1_09_HARNESS=1.
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
from market_platform_foundation.local_state.paper_experiments import paper_experiment_repository
from market_platform_foundation.local_state.startup import persist_ledger
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.xa01.compatibility import register_equity
from tests.acceptance.harness_action_decision import FixtureModel, Handler as ActionHandler, iso
from tests.intelligence.test_action_decision import candidate
from tests.support.paper_experiment_feed import ControlledFeed

INSTRUMENT = 'AAPL'
SECOND = 'NVDA'


class Handler(ActionHandler):
    feed = ControlledFeed()
    submit_attempts = preview_attempts = live_attempts = 0

    @classmethod
    def configure(cls, state, authority=True):
        """A governed candidate receipt for AAPL. Positions, orders and authority are the real ledger's."""
        cls.cutoff = time.time()
        cls.model.state = state
        cls.service.clock = lambda: cls.cutoff
        price = float(cls.feed.prices.get(INSTRUMENT, '150.00'))
        c = candidate()
        c['sufficient'] = True
        c['instrument'] = dict(instrument_id=INSTRUMENT, symbol=INSTRUMENT, universe='US_EQUITIES')
        for e in c['current_market_evidence']:
            e.update(as_of=iso(cls.cutoff), valid_until=iso(cls.cutoff + 600), instrument_id=INSTRUMENT, source='CONTROLLED_FIXTURE',
                     delivery_mode='FIXTURE', freshness_status='CURRENT')
        c['current_market_evidence'][0]['facts']['price'] = price
        if state == 'EXIT':
            c['current_market_evidence'][1]['facts']['change_pct'] = -2
        # The OCT1-06 fixture proposal always discloses one conflicting reference; it must exist in the receipt.
        c['reference_evidence'] = [dict(c['current_market_evidence'][1], evidence_id='news-conflict', capability='SENTIMENT',
                                        role='REFERENCE_CONTEXT', facts=dict(label='NEGATIVE'))]
        c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['news-conflict'], news_refs=[], kind='NEWS_SENTIMENT_VS_PRICE',
                                method='CONTROLLED_FIXTURE', observed_direction='POSITIVE', comparator_ref='t', cutoff=iso(cls.cutoff),
                                alignment_id='controlled-conflict', limitations=['Fixture conflict'])]
        selected = dict(instrument_id=INSTRUMENT, rank=1, rationale='Observed evidence warrants review.', supporting_refs=['q', 't'],
                        conflicting_refs=['news-conflict'], weak_refs=[], missing_capabilities=[], uncertainties=[])
        identity = 'controlled-' + str(time.time_ns())
        cls.run = dict(schema_version='screener-ai-screener/1.0.0', run_id=identity, state='CURRENT', valid_until=iso(cls.cutoff + 600),
                       input_hash=identity, evidence=[c], candidates=[selected], decision_cutoff=iso(cls.cutoff), generated_at=iso(cls.cutoff),
                       matched_count=1, intake_count=1, max_intake=20, provider_id=cls.model.provider_id, model_id=cls.model.model_id,
                       runtime='LOCAL_MODEL', prompt_id='screener.candidate_reduction.v1', prompt_version='1', prompt_hash='fixture',
                       packet_bytes=1000, cache='MISS', simulated=True, limitations=['SOFTWARE_CONTROLLED_EVIDENCE'], coverage={})
        cls.repo.put('candidate_run', identity, cls.run)
        cls.store.strategy_repository = InMemoryIntelligenceRepository()
        cls.store.strategy_repository.put_opportunity(OpportunityV1(
            'controlled-opportunity-' + str(time.time_ns()), '1', IntelligenceScope((INSTRUMENT,)), int((cls.cutoff - 1) * 1e9),
            QualitySummary('GOOD'), side='LONG', valid_until_ns=int((cls.cutoff + 600) * 1e9)))

    def metrics(self):
        ledger = self.store.paper_ledger
        return dict(model_calls=self.model.calls, ledger_events=len(ledger.events), experiment_id=ledger.experiment_id,
                    experiments=paper_experiment_repository().count(), fills=len(ledger.project_fills()),
                    submit_attempts=Handler.submit_attempts, preview_attempts=Handler.preview_attempts, live_attempts=Handler.live_attempts,
                    pid=os.getpid(), data_mode=self.store.data_mode, execution_mode=ledger.execution_mode,
                    execution_authority=ledger.execution_authority, execution_deferred=bool(self.store.execution_deferred),
                    paper_env=os.environ.get('IMP_PAPER_EXECUTION'), live_env=os.environ.get('IMP_LIVE_EXECUTION'),
                    broker_paper_env=os.environ.get('IMP_BROKER_PAPER_EXECUTION'), live_observational_env=os.environ.get('IMP_LIVE_OBSERVATIONAL'))

    def do_GET(self):
        url = urlparse(self.path)
        path, query = url.path, {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        if path == '/acceptance/experiment/metrics':
            self._send_json(self.metrics())
        elif path == '/acceptance/experiment/scenario':
            self.configure(query.get('state', 'ENTER'))
            self._send_json(dict(self.metrics(), run_id=self.run['run_id']))
        elif path == '/acceptance/experiment/price':
            # The next completed bar for this instrument: the simulator fills against it.
            Handler.feed.prices[query['instrument']] = query['price']
            self._send_json(self.metrics())
        elif path == '/acceptance/experiment/mark':
            Handler.feed.mark(self.store, query['instrument'], query['price'], quality=query.get('quality', 'PASS'))
            self._send_json(self.metrics())
        elif path == '/acceptance/experiment/clear-mark':
            self.store.paper_ledger.clear_mark(query['instrument'])
            persist_ledger(self.store.paper_ledger)
            self._send_json(self.metrics())
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith('/live/'):
            Handler.live_attempts += 1
            self._send_error_json('HARNESS_LIVE_DISABLED', 'This harness never reaches Live.', status=403)
        elif path == '/paper/orders':
            Handler.submit_attempts += 1  # the real production submit route, internal simulation only
            UiApiHandler.do_POST(self)
        elif path == '/paper/orders/preview':
            Handler.preview_attempts += 1
            UiApiHandler.do_POST(self)
        elif path.startswith('/paper/experiments') or path == '/paper/orders/cancel':
            UiApiHandler.do_POST(self)
        else:
            super().do_POST()


if __name__ == '__main__':
    if os.environ.get('IMP_OCT1_09_HARNESS') != '1' or not os.environ.get('IMP_STATE_DIR'):
        raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION', 'IMP_BROKER_LIVE_EXECUTION',
                'IMP_MOOMOO_LIVE', 'IMP_FINVIZ_LIVE', 'IMP_LIVE_INTERNAL_SIMULATION'):
        os.environ.pop(key, None)
    os.environ['IMP_PAPER_EXECUTION'] = '1'
    # Canonical (G1) registration of the second instrument, as the operator fixtures are registered.
    register_equity(symbol=SECOND)
    Handler.feed.install()
    # Loading restores a persisted ACTIVE experiment from its own events; nothing is created or re-seeded here.
    store = ReplayStore(collection_root=ROOT.parent)
    store.load()
    store.mode = 'PAPER'
    Handler.store = ActionHandler.store = store
    Handler.repo = ActionHandler.repo = action_repository()
    Handler.model = ActionHandler.model = FixtureModel()
    ai = SimpleNamespace(_news_service=lambda: SimpleNamespace(synthesis_provider=lambda: Handler.model))
    Handler.service = ActionHandler.service = ScreenerActionService(store, repository=Handler.repo, ai=ai)
    store._action_decision_service = Handler.service
    Handler.configure('NO_ACTION')
    port = int(os.environ.get('IMP_E2E_API_PORT', '18809'))
    if port in (8766, 5173, 11111, 18909):
        raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready', os.getpid(), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
