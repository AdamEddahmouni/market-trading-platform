"""Operator evidence review: read-only projections over existing authorities.

Stored news is read as it was known at a cutoff, the inference dry-run planner is given the
facts this process actually holds, decisions come from the existing Action Decision receipts,
and the replay is the existing fixture harness. Nothing here starts a collector, reserves
budget, calls a provider or model, writes state, or grants execution authority.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo('America/New_York')
AUTHORITY = dict(provider_calls=0, inference_calls=0, budget_reserved=False, state_written=False,
                 trading_mutation=False, execution_authority=False)
# Display rows for the windows inference_session classifies; the function remains the authority.
SCHEDULE = (dict(window='INFERENCE_PAUSE', start='20:00', end='03:30', inference_allowed=False),
            dict(window='CATCH_UP', start='03:30', end='04:00', inference_allowed=True),
            dict(window='PREMARKET', start='04:00', end='09:30', inference_allowed=True),
            dict(window='REGULAR', start='09:30', end='16:00', inference_allowed=True),
            dict(window='AFTER_HOURS', start='16:00', end='20:00', inference_allowed=True))
MAX_KNOWLEDGE_ROWS = 200
MAX_JOURNAL_EVIDENCE_IDS = 50


def _iso(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace('+00:00', 'Z')


def _instant(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if parsed.tzinfo is None:
        raise ValueError(code)
    return parsed.astimezone(UTC)


def _bound(value, code: str, *, minimum: int = 0, maximum: int = 10_000_000) -> int | None:
    if value is None or value == '':
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if not minimum <= number <= maximum:
        raise ValueError(code)
    return number


def _trading_day(day: date) -> bool | None:
    """The existing holiday table's answer, or None for a year the table does not cover."""
    from ..intelligence.forward_qualification.evidence01.continuity import _DEFAULT_HOLIDAYS, is_trading_day

    if not any(holiday.startswith(f'{day.year}-') for holiday in _DEFAULT_HOLIDAYS):
        return None
    return is_trading_day(day)


class EvidenceReviewService:
    def __init__(self, store, *, connection=None, actions=None, evaluation=None, settings=None, budget=None,
                 clock=time.time):
        self.store = store
        self._connection = connection
        self._actions = actions
        self._evaluation = evaluation
        self._settings = settings
        self._budget = budget
        self.clock = clock

    # ------------------------------------------------------------------ sources
    def now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), UTC)

    def connection(self):
        """The application's own open local state; this reader never opens another store."""
        if self._connection is not None:
            return self._connection
        from ..local_state.paths import persistence_enabled
        from ..local_state.startup import open_local_state

        local = open_local_state() if persistence_enabled() else None
        return local.connection if local else None

    def actions(self):
        if self._actions is None:
            from ..local_state.action_decisions import action_repository
            return action_repository()
        return self._actions

    def evaluation(self):
        if self._evaluation is None:
            from .prospective_evaluation import evaluation_service
            return evaluation_service(self.store)
        return self._evaluation

    def settings(self):
        if self._settings is None:
            from .screener_news import _default_synthesis_settings
            self._settings = _default_synthesis_settings()
        return self._settings

    def budget_status(self) -> dict:
        """The shared paid-inference budget as recorded; a missing file means nothing was spent today."""
        if self._budget is not None:
            return self._budget()
        from ..intelligence.inference.anthropic_synthesis import (
            BUDGET_RELATIVE, DAILY_REQUESTS_ENV, DAILY_TOKENS_ENV, DEFAULT_DAILY_REQUESTS, DEFAULT_DAILY_TOKENS,
            DailyBudget, _int_setting,
        )
        from ..local_state.external_cache import imp_cache_dir
        from ..news.config import configured_value

        limits = dict(max_requests=_int_setting(configured_value, DAILY_REQUESTS_ENV, DEFAULT_DAILY_REQUESTS),
                      max_tokens=_int_setting(configured_value, DAILY_TOKENS_ENV, DEFAULT_DAILY_TOKENS))
        path = imp_cache_dir() / BUDGET_RELATIVE
        if not path.exists():  # constructing a budget would create its lock file; a read must not
            return dict(day=self.now().date().isoformat(), requests=0, tokens=0, usage_overrun=False,
                        held_requests=0, held_tokens=0, source='NO_USAGE_RECORDED', **limits)
        try:
            return dict(DailyBudget(path, **limits).status(), source='RECORDED_BUDGET_STATE')
        except ValueError as exc:
            return dict(source='BUDGET_STATE_UNREADABLE', reason=str(exc))

    def cutoff(self, value: str | None) -> tuple[str, datetime]:
        """A cutoff is an instant already reached; the present is the default."""
        now = self.now()
        if not value:
            return _iso(now), now
        instant = _instant(value, 'INVALID_EVIDENCE_CUTOFF')
        if instant > now:
            raise ValueError('INVALID_EVIDENCE_CUTOFF')
        return value, instant

    # ------------------------------------------------------------------ status
    def collection(self) -> dict:
        from ..market_data.headless_supply import supply_status
        from ..market_data.persistence import persistence_status
        from ..news.collection import collection_status
        from ..news.supervision import supervision_status

        return dict(raw_collection=collection_status(), market_persistence=persistence_status(),
                    market_supply=supply_status(), collection_supervision=supervision_status())

    def knowledge_store(self) -> dict:
        connection = self.connection()
        if connection is None:
            return dict(state='UNAVAILABLE', reason='DURABLE_STATE_DISABLED', records=None, latest_ingested_time=None)
        try:
            row = connection.fetchone('SELECT COUNT(*) AS n, MAX(ingested_time) AS latest FROM news_collection_records')
        except sqlite3.Error:
            return dict(state='UNAVAILABLE', reason='NEWS_COLLECTION_STORE_MISSING', records=None,
                        latest_ingested_time=None)
        latest = row['latest']
        return dict(state='AVAILABLE' if row['n'] else 'EMPTY', reason=None if row['n'] else 'NO_RECORD_COLLECTED',
                    records=row['n'],
                    latest_ingested_time=_iso(datetime.fromtimestamp(latest, UTC)) if latest is not None else None)

    def model(self) -> dict:
        """The operator's saved engine and model. Configuration only; availability is never probed here."""
        from ..intelligence.inference.synthesis_engines import AUTO

        settings = self.settings()
        choice = settings.current()
        options = {option['id']: option for option in settings.options()}
        engine = choice['engine']
        if engine == AUTO:
            engine = 'anthropic' if options['anthropic']['state'] == 'AVAILABLE' else 'local'
        option = options[engine]
        return dict(engine=engine, model=choice['model'] or option['default_model'], selection_source=choice['source'],
                    runtime=option['runtime'], configured=option['state'] == 'AVAILABLE',
                    configuration_reason=option['reason'], availability='NOT_PROBED')

    def session(self, instant: datetime) -> dict:
        from ..intelligence.scheduling.local_plan import inference_session

        local_day = instant.astimezone(NEW_YORK).date()
        trading_day = _trading_day(local_day)
        return dict(inference_session(instant, trading_day),
                    trading_day_basis='EXISTING_HOLIDAY_TABLE' if trading_day is not None else 'CALENDAR_YEAR_NOT_COVERED')

    def status(self) -> dict:
        now = self.now()
        return dict(schema_version='evidence-review-status/1', server_time=_iso(now), session=self.session(now),
                    schedule=list(SCHEDULE), schedule_timezone='America/New_York',
                    # The pause is an inference policy. Collection has its own gates and is reported as it is.
                    collection_independent_of_inference_pause=True, collection=self.collection(),
                    knowledge=self.knowledge_store(), model=self.model(), authority=AUTHORITY)

    # ------------------------------------------------------------------ stored knowledge
    def _retrieve(self, **filters) -> tuple[dict, list[dict]]:
        from ..news.knowledge import StoredNewsRepository

        state = self.knowledge_store()
        if state['state'] == 'UNAVAILABLE':
            return state, []
        try:
            return state, StoredNewsRepository(self.connection()).retrieve(**filters)
        except sqlite3.Error:
            return dict(state, state='UNAVAILABLE', reason='NEWS_COLLECTION_STORE_UNREADABLE'), []

    def knowledge(self, *, as_of=None, symbol=None, source_id=None, provider_id=None, limit=None,
                  include_revisions=False) -> dict:
        as_of, _ = self.cutoff(as_of)
        limit = _bound(limit, 'INVALID_EVIDENCE_LIMIT', minimum=1, maximum=MAX_KNOWLEDGE_ROWS) or 50
        state, rows = self._retrieve(as_of=as_of, symbol=symbol or None, source_id=source_id or None,
                                     provider_id=provider_id or None, include_revisions=bool(include_revisions),
                                     limit=limit)
        records = []
        for row in rows:
            article, provenance = row['article'], row['provenance']
            records.append(dict(
                record_id=row['record_id'], article_id=row['article_id'],
                supersedes_record_id=row['supersedes_record_id'],
                headline=article.get('headline'), summary=article.get('summary'), url=article.get('url'),
                provider_id=article.get('provider_id'), source_id=article.get('source_id'),
                instruments=sorted({str(link.get('instrument_id') or link.get('provider_symbol') or '')
                                    for link in article.get('instrument_linkages', [])} - {''}),
                published_time=article.get('published_time') or None,
                retrieved_time=article.get('retrieved_time'), first_observed_time=row['first_observed_time'],
                available_time=_iso(datetime.fromtimestamp(row['available_at_ns'] / 1_000_000_000, UTC)),
                evidence_class=provenance.get('evidence_class'), source_reference=provenance.get('source_reference'),
                license=provenance.get('license')))
        return dict(schema_version='evidence-review-knowledge/1', as_of=as_of, store=state, records=records,
                    count=len(records), limit=limit, include_revisions=bool(include_revisions),
                    # Publication time is a label on the article. Visibility follows the availability clock.
                    availability_basis='LATEST_OF_OBSERVATION_INGESTION_AND_SAVED_AVAILABILITY',
                    authority=AUTHORITY)

    # ------------------------------------------------------------------ catch-up dry run
    def plan(self, *, at=None, max_requests=None, max_tokens=None, max_backlog=None,
             request_allowance=None, assume_available=False) -> dict:
        """What a catch-up at ``at`` would plan from evidence stored now. Nothing is dispatched or reserved."""
        from ..intelligence.inference.paper_automation import plan_local_inference_dry_run

        now = self.now()
        instant = _instant(at, 'INVALID_PLAN_CLOCK') if at else now
        if instant < now:
            # Stored evidence is read as of the present; an earlier clock would plan with later knowledge.
            raise ValueError('INVALID_PLAN_CLOCK')
        budget = self.budget_status()
        model = self.model()
        backlog = _bound(max_backlog, 'INVALID_PLAN_BOUND', maximum=MAX_KNOWLEDGE_ROWS) or 100
        allowance = _bound(request_allowance, 'INVALID_PLAN_BOUND', minimum=1)
        # Operator bounds can only tighten the recorded budget; none supplied means the budget's own limits.
        schedule = dict(
            max_requests=_bound(max_requests, 'INVALID_PLAN_BOUND') if max_requests not in (None, '') else int(budget.get('max_requests') or 0),
            max_tokens=_bound(max_tokens, 'INVALID_PLAN_BOUND') if max_tokens not in (None, '') else int(budget.get('max_tokens') or 0),
            max_backlog=backlog)
        state, rows = self._retrieve(as_of=_iso(now), limit=backlog)
        rows = sorted(rows, key=lambda row: (row['available_at_ns'], row['record_id']))  # oldest evidence first
        if allowance is not None:
            # Stored bytes bound the content tokens; the allowance is the operator's bound for the
            # prompt, schema and answer of one request. Without it the planner refuses every record.
            rows = [dict(row, estimated_tokens=row['estimated_tokens'] + allowance,
                         token_estimate_scope='REQUEST_AND_OUTPUT_BOUND') for row in rows]
        available = True if assume_available and model['configured'] else None
        plan = plan_local_inference_dry_run(
            rows, now=instant, schedule=schedule, session_is_trading_day=_trading_day(instant.astimezone(NEW_YORK).date()),
            engine=model['engine'], model=model['model'] or '', provider_configured=model['configured'],
            provider_available=available, resource_allowed=True, budget_status=budget,
            provider_gate=dict(allowed=True, reason=None))

        by_record = {row['record_id']: row for row in rows}

        def reference(row, **extra):
            source = by_record.get(row.get('record_id'))
            article = (source or {}).get('article', {})
            return dict(record_id=row.get('record_id'), headline=article.get('headline'),
                        source_id=article.get('source_id'),
                        available_time=_iso(datetime.fromtimestamp(source['available_at_ns'] / 1_000_000_000, UTC)) if source else None,
                        worst_case_tokens=source['estimated_tokens'] if source else 0, **extra)

        reasons: dict[str, int] = {}
        for item in plan['deferred']:
            reasons[item['reason']] = reasons.get(item['reason'], 0) + 1
        return dict(
            schema_version='evidence-review-plan/1', dry_run=True, planned_for=_iso(instant),
            clock_source='OPERATOR_PREVIEW_CLOCK' if at else 'SERVER_CLOCK', evidence_as_of=_iso(now),
            session=dict(plan['session'], trading_day_basis=self.session(instant)['trading_day_basis']),
            store=state, candidates=len(rows), planned_requests=plan['planned_requests'],
            planned_tokens=plan['planned_tokens'], planned=[reference(row) for row in plan['planned']],
            deferred=[reference(row, reason=row['reason']) for row in plan['deferred']],
            deferred_reasons=reasons, unscanned_count=plan['unscanned_count'], unscanned_reason=plan['unscanned_reason'],
            bounds=schedule, budget=budget, model=model, model_route=plan['model_route'],
            availability_basis='OPERATOR_ASSUMPTION_FOR_PREVIEW' if available else 'NOT_VERIFIED',
            estimate_basis='STORED_BYTES_PLUS_OPERATOR_ALLOWANCE' if allowance is not None else 'STORED_CONTENT_BYTES_ONLY',
            request_allowance=allowance,
            # No catch-up worker exists, so no completed analysis has been acknowledged against a revision.
            processed_state='NO_COMPLETED_ANALYSIS_RECORDED', collection_independent=plan['collection_independent'],
            inference_calls=plan['inference_calls'], budget_reserved=plan['budget_reserved'], authority=AUTHORITY)

    # ------------------------------------------------------------------ decision journal
    def journal(self, *, day=None, as_of=None, decision_id=None) -> dict:
        from ..intelligence.news_strategy_evaluation.journal import build_daily_journal, capture_decision_snapshot

        as_of, instant = self.cutoff(as_of)
        try:
            selected = date.fromisoformat(day) if day else instant.astimezone(NEW_YORK).date()
        except (TypeError, ValueError) as exc:
            raise ValueError('INVALID_JOURNAL_DAY') from exc
        mode = 'DEMO' if getattr(self.store, 'mode', None) == 'DEMO' else 'PAPER'
        account = self.store.paper_ledger.paper_account_id
        snapshots, unjournaled = [], []
        for decision in self.actions().evaluation_decisions(account, as_of):
            try:
                if _instant(decision['decision_time'], 'JOURNAL_CLOCK_INVALID').astimezone(NEW_YORK).date() != selected:
                    continue
                snapshots.append(capture_decision_snapshot(decision=decision, mode=mode))
            except (ValueError, KeyError, TypeError) as exc:
                # A receipt the journal contract refuses is listed, never repaired or dropped silently.
                unjournaled.append(dict(decision_id=decision.get('decision_id'), instrument_id=decision.get('instrument_id'),
                                        decision_time=decision.get('decision_time'), reason=str(exc) or type(exc).__name__))
        journal = build_daily_journal(snapshots, day=selected.isoformat(), observation_as_of=as_of)
        later, later_reason = {}, None
        try:
            for record in self.evaluation().project(cutoff=as_of)['inputs']['records']:
                if record.get('action_decision_id'):
                    later[record['action_decision_id']] = record
        except (ValueError, KeyError, TypeError) as exc:
            later_reason = str(exc) or type(exc).__name__

        def later_evidence(identifier):
            record = later.get(identifier)
            if record is None:
                return dict(status='UNAVAILABLE', reason=later_reason or 'NO_EVALUATION_RECORD_AT_CUTOFF')
            return dict(status='AVAILABLE', evaluation_id=record['evaluation_id'], evidence_class=record.get('evidence_class'),
                        trade_episode_id=record.get('trade_episode_id'),
                        # Paper execution appears only where the ledger holds the episode.
                        execution_outcome=record.get('execution_outcome'), signal_outcomes=record.get('signal_outcomes', []),
                        limitations=record.get('limitations', []))

        if decision_id:
            entry = next((item for item in journal['items'] if item['decision_id'] == decision_id), None)
            if entry is None:
                raise ValueError('JOURNAL_DECISION_NOT_FOUND')
            return dict(schema_version='evidence-review-journal-entry/1', day=journal['day'], observation_as_of=as_of,
                        entry=entry, later_evidence=later_evidence(decision_id), authority=AUTHORITY)
        items = []
        for entry in journal['items']:
            refs = entry['source_refs']
            evidence_ids = refs.get('evidence_ids', refs.get('news_event_ids', []))
            items.append(dict(
                decision_id=entry['decision_id'], decision_time=entry['decision_time'], instrument_id=entry['instrument_id'],
                mode=entry['mode'], opportunity_id=entry['opportunity_id'], action=entry['action'],
                decision_snapshot_hash=entry['decision_snapshot_hash'],
                evidence_snapshot_id=refs.get('evidence_snapshot_id'), candidate_run_id=refs.get('candidate_run_id'),
                decision_trace_id=refs.get('decision_trace_id'), evidence_count=len(evidence_ids),
                evidence_ids=evidence_ids[:MAX_JOURNAL_EVIDENCE_IDS], missing_information=entry['missing_information'],
                outcome_status=entry['outcome_status'], reviews=entry['reviews'],
                realized_pnl=entry['realized_pnl'], realized_pnl_status=entry['realized_pnl_status'],
                later_evidence=later_evidence(entry['decision_id'])))
        return dict(schema_version='evidence-review-journal/1', day=journal['day'], day_basis=journal['day_basis'],
                    observation_as_of=as_of, account_id=account, mode=mode, items=items, unjournaled=unjournaled,
                    source='ACTION_DECISION_RECEIPTS', later_evidence_source='PROSPECTIVE_EVALUATION_PROJECTION',
                    authority=AUTHORITY)

    # ------------------------------------------------------------------ as-of replay
    def replay(self, *, replay_date=None, as_of=None) -> dict:
        from ..intelligence.news_strategy_evaluation.fixture_loader import load_fixture_pack
        from ..intelligence.news_strategy_evaluation.replay import EvaluationReplayHarness

        try:
            pack = load_fixture_pack()
        except (OSError, ValueError) as exc:
            raise ValueError('REPLAY_FIXTURE_UNAVAILABLE') from exc
        clocks: dict[str, list[str]] = {}
        for sample in pack.samples:
            try:
                local_day = _instant(sample.as_of, 'x').astimezone(NEW_YORK).date().isoformat()
            except ValueError:
                continue
            clocks.setdefault(local_day, []).append(sample.as_of)
        available = [dict(replay_date=key, clocks=sorted(set(values), key=lambda value: _instant(value, 'x')))
                     for key, values in sorted(clocks.items())]
        if not available:
            raise ValueError('REPLAY_FIXTURE_UNAVAILABLE')
        replay_date = replay_date or available[-1]['replay_date']
        chosen = next((item for item in available if item['replay_date'] == replay_date), None)
        as_of = as_of or (chosen['clocks'][-1] if chosen else None)
        if not as_of:
            raise ValueError('REPLAY_DAY_NOT_IN_FIXTURE')
        harness = EvaluationReplayHarness()
        view = harness.snapshot_at(replay_date=replay_date, as_of=as_of, pack=pack)
        again = harness.snapshot_at(replay_date=replay_date, as_of=as_of, pack=pack)
        decisions, verdicts = [], set()
        for sample in view['decisions']:
            policies = [dict(policy_id=item['policy_id'], policy_version=item['policy_version'],
                             classification=item['policy_classification'], decision=item['decision'],
                             directional_units=item['normalized_directional_units'], decision_id=item['decision_id'],
                             inference_record_ids=item['inference_record_ids']) for item in sample['policy_decisions']]
            verdicts.add(tuple(item['decision'] for item in policies))
            first = sample['policy_decisions'][0]
            decisions.append(dict(sample_id=sample['sample_id'], as_of=sample['as_of'], instrument_id=first['instrument_id'],
                                  news_event_ids=first['news_event_ids'], market_snapshot_ref=first['market_snapshot_ref'],
                                  feature_snapshot_id=first['feature_snapshot_id'], policies=policies,
                                  policies_differ=len({item['decision'] for item in policies}) > 1))
        return dict(schema_version='evidence-review-replay/1', evidence_class='SOFTWARE_FIXTURE_ONLY',
                    replay_date=view['replay_date'], as_of=view['as_of'], timezone=view['timezone'],
                    market_data_ref=view['market_data_ref'], config_hash=view['config_hash'], coverage=view['coverage'],
                    decisions=decisions, gaps=view['gaps'], limitations=view['limitations'],
                    snapshot_hash=view['snapshot_hash'], deterministic=view == again, available=available,
                    # Verdicts on a fixture describe policy behaviour on identical inputs. They are not returns.
                    comparison=dict(basis='SAME_AS_OF_SNAPSHOT_FOR_EVERY_POLICY',
                                    any_policy_difference=any(item['policies_differ'] for item in decisions),
                                    performance_ranking=None, ranking_status='NOT_A_PERFORMANCE_RANKING'),
                    simulation_only=view['simulation_only'], authority=AUTHORITY)


_SERVICE = None
_STORE = None


def evidence_review_service(store) -> EvidenceReviewService:
    global _SERVICE, _STORE
    if _SERVICE is None or _STORE is not store:
        _STORE = store
        _SERVICE = EvidenceReviewService(store)
    return _SERVICE


def read_evidence(store, path: str, query: dict[str, list[str]]) -> dict:
    """GET /evaluation/evidence/<view>. Every view is a read."""
    service = evidence_review_service(store)
    first = lambda key: (query.get(key) or [None])[0]
    flag = lambda key: first(key) in ('1', 'true')
    view = path.removeprefix('/evaluation/evidence/')
    if view == 'status':
        return service.status()
    if view == 'knowledge':
        return service.knowledge(as_of=first('as_of'), symbol=first('symbol'), source_id=first('source'),
                                 provider_id=first('provider'), limit=first('limit'),
                                 include_revisions=flag('revisions'))
    if view == 'plan':
        return service.plan(at=first('at'), max_requests=first('max_requests'), max_tokens=first('max_tokens'),
                            max_backlog=first('max_backlog'), request_allowance=first('request_allowance'),
                            assume_available=flag('assume_available'))
    if view == 'journal':
        return service.journal(day=first('day'), as_of=first('as_of'), decision_id=first('decision_id'))
    if view == 'replay':
        return service.replay(replay_date=first('date'), as_of=first('as_of'))
    raise ValueError('EVIDENCE_ROUTE_NOT_FOUND')


__all__ = ['AUTHORITY', 'EvidenceReviewService', 'evidence_review_service', 'read_evidence']
