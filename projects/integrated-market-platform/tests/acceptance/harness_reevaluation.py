"""OCT1-07 SOFTWARE_CONTROLLED browser harness. Loopback; every submit route refused.

Production next-session/reevaluation/action services, SQLite persistence, lease and
receipts are used. Only the Screener evidence reader, the model proposal, held
position/pending-order projections, auth and the (accelerated) clock are fixtures.
Run with an isolated IMP_STATE_DIR and IMP_OCT1_07_HARNESS=1.
"""
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from market_platform_foundation.local_state.action_decisions import action_repository
from market_platform_foundation.local_state.reevaluation import reevaluation_repository
from market_platform_foundation.rt01.execution_decision_trace.runtime import execution_decision_trace_repository
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_next_session import NextSessionService
from market_platform_foundation.ui_api.screener_reevaluation import ReevaluationService
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore
from tests.intelligence.test_reevaluation import Clock, FixtureAi, FixtureProvider, iso

ET = ZoneInfo('America/New_York')
INSTRUMENT = 'US:NVDA'


def base_monday():
    """10:30 ET on the first Monday after today, so browser expiry clocks stay ahead of real time."""
    override = os.environ.get('IMP_OCT1_07_BASE_DATE')
    day = date.fromisoformat(override) if override else date.today() + timedelta(days=1)
    while not override and day.weekday() != 0:
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, 10, 30, tzinfo=ET).timestamp()


class ControlledReevaluation(ReevaluationService):
    """Same core; the schedule is stepped by the harness instead of a wall-clock thread."""
    policy_override = {}

    def configure(self, body):
        return super().configure(dict(body, policy=dict(self.policy_override)) if self.policy_override else body)

    def start(self, **_):
        return super().start(wait=Handler.advance, threaded=False)


class Handler(UiApiHandler):
    submit_attempts = 0

    def _authorize_request(self, *args, **kwargs):
        return True  # test-only, not auth acceptance

    @classmethod
    def advance(cls, seconds):
        cls.clock.value += float(seconds)

    @classmethod
    def new_services(cls, owner):
        cls.actions = ScreenerActionService(cls.store, repository=action_repository(), clock=cls.clock, ai=cls.ai,
                                            trace_repository=execution_decision_trace_repository())
        cls.reevaluation = ControlledReevaluation(cls.store, repository=reevaluation_repository(), actions=cls.actions, ai=cls.ai,
                                                  clock=cls.clock, owner_id=owner)
        quote = lambda instrument, now: dict(price=cls.ai.rows[INSTRUMENT]['price'], as_of=now, source='CONTROLLED_FIXTURE', delivery_mode='REALTIME')
        cls.next_session = NextSessionService(cls.store, repository=reevaluation_repository(), actions=cls.actions, clock=cls.clock, quote_reader=quote)
        cls.store._action_decision_service, cls.store._reevaluation_service, cls.store._next_session_service = cls.actions, cls.reevaluation, cls.next_session

    def metrics(self):
        loop = self.reevaluation.repository.latest_loop(self.store.paper_ledger.paper_account_id)
        return dict(clock=iso(self.clock()), model_calls=self.provider.calls, reductions=self.ai.reductions, packets=self.ai.packets,
                    news_refreshes=sum(bool(x) for x in self.ai.refreshes), ledger_events=len(self.store.paper_ledger.events),
                    submit_attempts=Handler.submit_attempts, decisions=len(self.actions.history(INSTRUMENT)),
                    cycles=len(self.reevaluation.repository.cycles(loop['loop_id'], limit=100)) if loop else 0,
                    owner=self.reevaluation.owner_id)

    def do_GET(self):
        url = urlparse(self.path)
        path, query = url.path, {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        ledger = self.store.paper_ledger
        if path == '/screener':
            now = iso(self.clock())
            self._send_json(dict(schema_version='screener/1.0.0', universe='US_EQUITIES', generated_at=now, market_session='regular', universe_as_of=now,
                                 screener_as_of=now, result_count=0, unfiltered_count=0, provider_health=[], source_error=None, rows=[]))
        elif path == '/screener/ai-screener/preview':
            self._send_json(dict(schema_version='screener-ai-screener-preview/1.0.0', ai=dict(state='AVAILABLE', reason=None, provider_id=self.provider.provider_id,
                                 model_id=self.provider.model_id, runtime='LOCAL_MODEL'), scope=dict(universe='US_EQUITIES', search='', sort='symbol', descending=False, filters=[]),
                                 matched_count=1, intake_count=1, max_intake=20, estimate=None, evidence_summary=dict(sufficient=1, blocked=0, missing=0, weak=0), decision_cutoff=iso(self.clock())))
        elif path == '/acceptance/reevaluation/metrics':
            self._send_json(self.metrics())
        elif path == '/acceptance/reevaluation/advance':
            self.advance(query['seconds']); self._send_json(self.metrics())
        elif path == '/acceptance/reevaluation/tick':
            # One governed scheduled cycle through the production worker, on the accelerated clock.
            self.reevaluation.worker.run(max_cycles=1); self._send_json(self.metrics())
        elif path == '/acceptance/reevaluation/set':
            row = self.ai.rows[INSTRUMENT]
            if 'price' in query: row['price'] = float(query['price'])
            if 'change' in query: row['change'] = float(query['change'])
            if 'force' in query: self.provider.force = query['force'] or None
            if 'policy' in query: ControlledReevaluation.policy_override = json.loads(query['policy'])
            if 'position' in query:
                quantity = int(query['position'])
                ledger.project_positions = (lambda: [dict(instrument_id=INSTRUMENT, symbol='NVDA', quantity=quantity, side='LONG', mark_minor=15000)]) if quantity else (lambda: [])
            if 'pending' in query:
                ledger.project_orders = (lambda: [dict(instrument_id=INSTRUMENT, state='SUBMITTED', order_id='controlled-pending')]) if query['pending'] == '1' else self.original_orders
            self._send_json(self.metrics())
        elif path == '/acceptance/reevaluation/crash':
            # Process death: no stop(), no lease release. A new owner must wait out the lease.
            Handler.new_services('restarted-' + str(time.time_ns())); self._send_json(self.metrics())
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/screener/ai-screener':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
            now = self.clock()
            candidate = self.ai.candidate(INSTRUMENT, now)
            # The operator-facing run carries only fields the AI Screener card renders; the story card needs real S11 fields.
            candidate['reference_evidence'] = [e for e in candidate['reference_evidence'] if e['capability'] != 'NEWS']
            for e in (*candidate['current_market_evidence'], *candidate['reference_evidence']): e['instrument_id'] = INSTRUMENT
            identity = 'controlled-' + str(time.time_ns())
            selected = dict(instrument_id=INSTRUMENT, rank=1, rationale='Observed evidence warrants review.', supporting_refs=['q', 't'],
                            conflicting_refs=[], weak_refs=[], missing_capabilities=[], uncertainties=[])
            run = dict(schema_version='screener-ai-screener/1.0.0', run_id=identity, state='CURRENT', valid_until=iso(now + 600), input_hash=identity,
                       evidence=[candidate], candidates=[selected], decision_cutoff=iso(now), generated_at=iso(now), matched_count=1, intake_count=1, max_intake=20,
                       provider_id=self.provider.provider_id, model_id=self.provider.model_id, runtime='LOCAL_MODEL', prompt_id='screener.candidate_reduction.v1',
                       prompt_version='1', prompt_hash='fixture', packet_bytes=1000, cache='MISS', simulated=True, limitations=['SOFTWARE_CONTROLLED_EVIDENCE'], coverage={})
            action_repository().put('candidate_run', identity, run)
            self._send_json(dict(run, scope=body))
        elif path.startswith('/paper/') or 'submit' in path or path.startswith('/live/'):
            Handler.submit_attempts += 1
            self._send_error_json('HARNESS_SUBMIT_DISABLED', 'This harness never submits.', status=403)
        else:
            super().do_POST()


if __name__ == '__main__':
    if os.environ.get('IMP_OCT1_07_HARNESS') != '1' or not os.environ.get('IMP_STATE_DIR'):
        raise SystemExit('Isolated harness environment required')
    for key in ('IMP_LIVE_EXECUTION', 'IMP_LIVE_OBSERVATIONAL', 'IMP_BROKER_PAPER_EXECUTION'):
        os.environ.pop(key, None)
    os.environ['IMP_PAPER_EXECUTION'] = '1'
    Handler.store = ReplayStore(collection_root=ROOT.parent); Handler.store.load(); Handler.store.mode = 'PAPER'
    Handler.store.execution_deferred = False
    Handler.original_orders = Handler.store.paper_ledger.project_orders
    Handler.store.paper_ledger.project_positions = lambda: []
    Handler.clock = Clock(base_monday())
    Handler.provider = FixtureProvider()
    Handler.ai = FixtureAi(Handler.clock, Handler.provider)
    Handler.ai.rows = {INSTRUMENT: dict(price=150.0, change=2.0)}
    Handler.ai.selected = [INSTRUMENT]
    Handler.ai.reference = [
        dict(evidence_id='news', capability='NEWS', role='REFERENCE_CONTEXT', source='RSS', delivery_mode='SNAPSHOT', freshness_status='CURRENT',
             decision_admissibility='ADMISSIBLE', as_of=iso(Handler.clock() - 1860), valid_until=iso(Handler.clock() + 86400 * 3), policy='news-reference/4h-window',
             basis='PUBLICATION', weak_reasons=[], facts=dict(headline='Controlled reference story')),
        dict(evidence_id='rates', capability='RATES', role='REFERENCE_CONTEXT', source='TREASURY', delivery_mode='PUBLICATION_BASED', freshness_status='CURRENT',
             decision_admissibility='ADMISSIBLE', as_of=iso(Handler.clock() - 20 * 3600), valid_until=None, policy='treasury-publication', basis='PUBLICATION',
             weak_reasons=[], facts=dict(reference_rate=4.1))]
    Handler.new_services('harness-' + str(os.getpid()))
    port = int(os.environ.get('IMP_E2E_API_PORT', '18807'))
    if port in (8766, 5173, 11111):
        raise SystemExit('Campaign port forbidden')
    print('SOFTWARE_CONTROLLED_EVIDENCE ready', iso(Handler.clock()), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
