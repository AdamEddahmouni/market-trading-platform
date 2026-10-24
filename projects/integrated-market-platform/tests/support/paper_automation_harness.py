"""AUTO-01 controlled harness for autonomous Paper operations tests.

SOFTWARE_CONTROLLED. The production controller, reevaluation cycle, Action Decision
gate, Paper preview/risk/submit route, simulator, ledger and SQLite local state are
used. Only the clock, the session calendar answer, the provider-health answer, the
Screener evidence reader, the model, the full-universe run tracker, the completed-bar
feed and the governed Opportunity are fixtures. Nothing here is market truth.
"""
from __future__ import annotations

import threading
import time

from market_platform_foundation.intelligence.contracts.common import ContractReference, IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.persistence.memory import InMemoryIntelligenceRepository
from market_platform_foundation.ui_api import paper_experiment
from market_platform_foundation.ui_api.paper_automation import PaperAutomationService
from market_platform_foundation.ui_api.screener_action import ScreenerActionService
from market_platform_foundation.ui_api.screener_reevaluation import ReevaluationService
from tests.intelligence.test_reevaluation import Clock, FixtureAi, FixtureProvider
from tests.support.paper_experiment_feed import ControlledFeed

SCOPE = dict(universe='US_EQUITIES')
CAPITAL = 10_000_000  # the experiment's fixed $100,000.00 in minor units


def policy_body(**sections):
    """A complete owner policy for tests. These are fixture numbers, not recommended settings."""
    body = dict(
        scope=dict(SCOPE),
        schedule=dict(sessions=['REGULAR'], cadence_seconds=60, universe_evaluation_interval_seconds=1800,
                      no_new_entries_minutes_before_close=15),
        risk=dict(max_position_notional_minor=500_000, max_aggregate_exposure_minor=1_000_000, max_open_positions=2,
                  max_daily_loss_minor=100_000, max_per_trade_risk_minor=10_000, assumed_adverse_move_bps=200,
                  allowed_universes=['US_EQUITIES'], order_types=['MARKET'], allow_long=True, allow_short=False,
                  allow_entries=True, allow_exits=True),
        exits=dict(on_stop_breach=True, on_thesis_exit=True),
        ai=dict(allow_local_inference=True, allow_paid_inference=False, max_paid_requests_per_day=0, max_paid_tokens_per_day=0),
        emergency_stop=dict(max_consecutive_failures=3),
    )
    for section, values in sections.items():
        body[section] = dict(body[section], **values)
    return body


class ClockedFeed(ControlledFeed):
    """Bars and marks stamped from the controlled clock, so evidence and fills share one time base."""

    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def now_ns(self):
        self._last_ns = max(int(self.clock() * 1e9), self._last_ns + 1_000)
        return self._last_ns


class EquityAi(FixtureAi):
    """Screener evidence reader over canonical equity identities (AAPL, NVDA)."""

    def __init__(self, clock, provider):
        super().__init__(clock, provider)
        self.rows = {'AAPL': dict(price=150.0, change=2.0)}
        self.selected = []
        self.fail = None

    @staticmethod
    def _query(body):
        if not isinstance(body, dict) or body.get('universe') != 'US_EQUITIES':
            raise ValueError('INVALID_AI_SCREENER_SCOPE')
        return dict(dict(universe='US_EQUITIES', search='', sort='symbol', descending=False, filters=[], result_set=None,
                         view='Overview', screen=''), **body)

    def candidate(self, iid, now):
        # The base fixture keys rows and quote refusals by a prefixed identity and derives the symbol from it.
        alias = 'US:' + iid
        self.rows[alias] = self.rows[iid]
        if iid in self.no_quote:
            self.no_quote.add(alias)
        try:
            value = super().candidate(alias, now)
        finally:
            del self.rows[alias]
            self.no_quote.discard(alias)
        value['instrument'] = dict(instrument_id=iid, symbol=iid, universe='US_EQUITIES')
        return value

    def _packet(self, body, *, refresh_news=False, include_flow=None):
        if self.fail:
            raise ValueError(self.fail)
        return super()._packet(body, refresh_news=refresh_news, include_flow=include_flow)


class PaidProvider(FixtureProvider):
    """A paid engine with a readable shared daily budget."""
    runtime = 'PAID_API'

    def __init__(self, *, requests=0, tokens=0, max_requests=30, max_tokens=200_000):
        super().__init__()
        self.budget = dict(requests=requests, tokens=tokens, max_requests=max_requests, max_tokens=max_tokens,
                           held_requests=0, held_tokens=0)

    def budget_status(self):
        return dict(self.budget)


class FixtureRuns:
    """Stands in for the full-universe AI run tracker. Records every start; a run finishes only when told to."""

    def __init__(self, clock):
        self.clock = clock
        self.started, self.stopped, self.snapshots, self.rows = [], [], {}, {}

    def start(self, account_id, body, *, spend_limit=None, origin='OPERATOR', slice_plan=None):
        run_id = f'AIR-{len(self.started) + 1}'
        self.started.append(dict(run_id=run_id, account_id=account_id, scope=dict(body), spend_limit=spend_limit, origin=origin,
                                 slice_plan=slice_plan))
        self.snapshots[run_id] = dict(run_id=run_id, state='RUNNING', stage='EVALUATING', progress=dict(evaluated=0), origin=origin)
        return dict(run_id=run_id, state='RUNNING', engine=dict(runtime='LOCAL_MODEL'))

    def read(self, account_id, run_id):
        return self.snapshots.get(run_id)

    def row_outcomes(self, run_id):
        return {key: value if isinstance(value, str) else value[0] for key, value in (self.rows.get(run_id) or {}).items()}

    def row_records(self, run_id):
        # A row is 'CLASS' or ('CLASS', [reasons]), as the ledger's FINAL rows record it.
        return {key: (value, []) if isinstance(value, str) else (value[0], list(value[1]))
                for key, value in (self.rows.get(run_id) or {}).items()}

    def stop(self, account_id, run_id):
        self.stopped.append(run_id)
        return self.snapshots.get(run_id)

    def finish(self, run_id, chosen, *, status='GLOBAL_SELECTION_COMPLETE', coverage_complete=True, selection_complete=True,
               universe=7000, evaluated=None, reason=None, slice_complete=False, rows=None):
        evaluated = universe if evaluated is None else evaluated
        if rows is not None:
            self.rows[run_id] = dict(rows)
        coverage = dict(status=status, reason=reason, coverage_complete=coverage_complete, selection_complete=selection_complete,
                        slice_complete=slice_complete,
                        universe_count=universe, eligible_count=universe, ai_evaluated_count=evaluated,
                        ai_coverage_pct=round(100 * evaluated / universe, 2), model_calls=3,
                        budget=dict(tokens_input=1200, tokens_output=300))
        result = dict(run_id='CU-' + run_id, state='CURRENT' if chosen else 'NO_GROUNDED_CANDIDATES',
                      candidates=[dict(instrument_id=iid, rank=rank) for rank, iid in enumerate(chosen, 1)],
                      evidence=[dict(instrument=dict(instrument_id=iid, symbol=iid, universe='US_EQUITIES')) for iid in chosen],
                      provisional=[], universe_coverage=coverage, provider_id='fixture', model_id='controlled', runtime='LOCAL_MODEL')
        self.snapshots[run_id] = dict(run_id=run_id, state='COMPLETE', finished_at='2026-10-05T14:05:00Z', result=result, error=None)

    def fail(self, run_id, code):
        self.snapshots[run_id] = dict(run_id=run_id, state='FAILED', finished_at='2026-10-05T14:05:00Z', result=None, error=dict(code=code))


class Automation:
    """One process view: a controller with its own owner id over a store and the shared local state."""

    def __init__(self, store, *, clock, feed, ai=None, provider=None, runs=None, owner='process-a'):
        self.store, self.clock, self.feed = store, clock, feed
        self.provider = provider or FixtureProvider()
        self.ai = ai or EquityAi(clock, self.provider)
        self.ai.provider = self.provider
        self.runs = runs or FixtureRuns(clock)
        self.session_label, self.minutes_to_close, self.session_date = 'REGULAR', 300, '2026-10-05'
        self.health = dict(state='CONNECTED', data_mode='CONTROLLED_FIXTURE', reasons=[])
        self.actions = ScreenerActionService(store, ai=self.ai, clock=clock)
        store._action_decision_service = self.actions  # the Paper route revalidates Action provenance through this
        if not hasattr(store, 'strategy_repository') or store.strategy_repository is None:
            store.strategy_repository = InMemoryIntelligenceRepository()
        self.reevaluation = ReevaluationService(store, actions=self.actions, ai=self.ai, clock=clock, owner_id=owner)
        self.service = PaperAutomationService(store, reevaluation=self.reevaluation, runs=self.runs, clock=clock, owner_id=owner,
                                              session=self.session, provider_health=lambda: dict(self.health),
                                              submit_lock=threading.RLock())

    def session(self, epoch):
        return dict(label=self.session_label, trading_day=self.session_label != 'CLOSED', session_date=self.session_date,
                    minutes_to_close=self.minutes_to_close if self.session_label == 'REGULAR' else None,
                    early_close_metadata='UNAVAILABLE')

    # --- owner actions ---------------------------------------------------------------
    def configure(self, **sections):
        return self.service.configure(policy_body(**sections))

    def arm(self):
        from market_platform_foundation.intelligence.inference.paper_automation import ARM_ACKNOWLEDGEMENT
        policy_id = self.service.status()['policy']['policy_id']
        return self.service.arm(dict(policy_id=policy_id, acknowledgement=ARM_ACKNOWLEDGEMENT, operator='test-owner'))

    def go(self, **sections):
        self.configure(**sections)
        self.arm()
        return self.service.start(threaded=False)

    # --- time and evidence -------------------------------------------------------------
    def cycle(self, seconds=60):
        self.clock.value += seconds
        return self.service.run_cycle(scheduled=self.clock.value)

    def quote(self, instrument, price, change):
        """One coherent observation: Screener evidence, the next completed bar, and the mark of a held position."""
        self.ai.rows[instrument] = dict(price=float(price), change=float(change))
        self.feed.prices[instrument] = f'{float(price):.2f}'
        if any(p['instrument_id'] == instrument and p.get('quantity') for p in self.store.paper_ledger.project_positions()):
            self.feed.mark(self.store, instrument, f'{float(price):.2f}')

    def opportunity(self, instrument, *, side='LONG', lifetime=3600):
        """A governed Opportunity that shares the candidate's quote evidence lineage. A fixture, minted by no model."""
        now = self.clock()
        record = OpportunityV1(f'auto-opportunity-{instrument}-{time.time_ns()}', '1', IntelligenceScope((instrument,)),
                               int((now - 1) * 1e9), QualitySummary('GOOD'), side=side, valid_until_ns=int((now + lifetime) * 1e9),
                               lineage_refs=(ContractReference('EvidenceV1', 'q'),))
        self.store.strategy_repository.put_opportunity(record)
        return record.opportunity_id

    def select(self, *instruments, **coverage):
        """Finish the active full-universe run with this selection."""
        run_id = self.service.status()['universe']['active_run_id']
        self.runs.finish(run_id, list(instruments), **coverage)
        return run_id

    # --- reads -----------------------------------------------------------------------------
    def position(self, instrument):
        return next((p for p in self.store.paper_ledger.project_positions() if p['instrument_id'] == instrument and p.get('quantity')), None)

    def orders(self):
        return self.store.paper_ledger.project_orders()

    def events(self, kind=None):
        return self.service.history(limit=200, kind=kind)['events']


def experiment(store):
    return paper_experiment.create_experiment(store, {})['experiment']
