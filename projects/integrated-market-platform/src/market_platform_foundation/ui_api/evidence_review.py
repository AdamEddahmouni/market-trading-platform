"""Operator evidence review: read-only projections over existing authorities.

Stored news is read as it was known at a cutoff, the inference dry-run planner is given the
facts this process actually holds, decisions come from the existing Action Decision receipts,
and the replay is the existing fixture harness. Nothing here starts a collector, reserves
budget, calls a provider or model, mutates a ledger, or grants execution authority. Like the
neighbouring evaluation routes it uses the application's shared repositories, whose first use
in a process opens local state and creates their own tables.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo('America/New_York')
AUTHORITY = dict(provider_calls=0, inference_calls=0, budget_reserved=False, ledger_mutation=False,
                 trading_mutation=False, execution_authority=False)
# Display rows for the windows inference_session classifies on a trading day; the function remains the authority.
SCHEDULE = (dict(window='INFERENCE_PAUSE', start='20:00', end='03:30', inference_allowed=False),
            dict(window='CATCH_UP', start='03:30', end='04:00', inference_allowed=True),
            dict(window='PREMARKET', start='04:00', end='09:30', inference_allowed=True),
            dict(window='REGULAR', start='09:30', end='16:00', inference_allowed=True),
            dict(window='AFTER_HOURS', start='16:00', end='20:00', inference_allowed=True))
MAX_KNOWLEDGE_ROWS = 200
MAX_PLAN_ROWS = 1000  # the stored-news reader's own output limit
MAX_JOURNAL_EVIDENCE_IDS = 50


def _iso(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace('+00:00', 'Z')


def _instant(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError(code)
        return parsed.astimezone(UTC)
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(code) from exc


def _bound(value, code: str, *, default: int | None = None, minimum: int = 0, maximum: int = 10_000_000) -> int | None:
    if value is None or value == '':
        return default
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
        """The application's own local state; this reader never opens a second store."""
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
        """The shared paid-inference budget as recorded; a missing file means nothing was ever spent."""
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
            # The existing budget authority; it takes the budget's own lock for the read and saves nothing.
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

    def knowledge_store(self, as_of: datetime | None = None) -> dict:
        """What the store held at ``as_of`` (the present by default); a later record is not counted."""
        connection = self.connection()
        empty = dict(records=None, latest_ingested_time=None)
        if connection is None:
            return dict(state='UNAVAILABLE', reason='DURABLE_STATE_DISABLED', **empty)
        try:
            row = connection.fetchone('SELECT COUNT(*) AS n, MAX(ingested_time) AS latest FROM news_collection_records '
                                      'WHERE ingested_time<=?', ((as_of or self.now()).timestamp(),))
        except sqlite3.Error as exc:
            missing = 'no such table' in str(exc)
            return dict(state='UNAVAILABLE', **empty,
                        reason='NEWS_COLLECTION_STORE_MISSING' if missing else 'NEWS_COLLECTION_STORE_UNREADABLE')
        latest = row['latest']
        return dict(state='AVAILABLE' if row['n'] else 'EMPTY', reason=None if row['n'] else 'NO_RECORD_COLLECTED',
                    records=row['n'],
                    latest_ingested_time=_iso(datetime.fromtimestamp(latest, UTC)) if latest is not None else None)

    def model(self) -> dict:
        """The operator's saved engine and model. Configuration only; availability is never probed here."""
        from ..intelligence.inference.synthesis_engines import resolved_engine

        settings = self.settings()
        choice = settings.current()
        options = {option['id']: option for option in settings.options()}
        # Automatic is always the free local model; a saved paid key alone never selects paid AI.
        engine = resolved_engine(choice['engine'])
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
                    schedule=list(SCHEDULE), schedule_timezone='America/New_York', schedule_applies_to='TRADING_DAYS',
                    # The pause is an inference policy. Collection has its own gates and is reported as it is.
                    collection_independent_of_inference_pause=True, collection=self.collection(),
                    knowledge=self.knowledge_store(), model=self.model(), authority=AUTHORITY)

    # ------------------------------------------------------------------ stored knowledge
    def _retrieve(self, instant: datetime, **filters) -> tuple[dict, list[dict]]:
        from ..news.knowledge import StoredNewsRepository

        state = self.knowledge_store(instant)
        if state['state'] == 'UNAVAILABLE':
            return state, []
        try:
            return state, StoredNewsRepository(self.connection()).retrieve(as_of=_iso(instant), **filters)
        except sqlite3.Error:
            return dict(state, state='UNAVAILABLE', reason='NEWS_COLLECTION_STORE_UNREADABLE'), []
        except ValueError as exc:
            if str(exc) != 'NEWS_KNOWLEDGE_SCAN_BOUND':
                raise
            # The reader refuses to return incomplete latest evidence past its scan bound; say so, show nothing.
            return dict(state, state='UNAVAILABLE', reason='NEWS_KNOWLEDGE_SCAN_BOUND'), []

    def knowledge(self, *, as_of=None, symbol=None, source_id=None, provider_id=None, limit=None,
                  include_revisions=False) -> dict:
        as_of, instant = self.cutoff(as_of)
        limit = _bound(limit, 'INVALID_EVIDENCE_LIMIT', default=50, minimum=1, maximum=MAX_KNOWLEDGE_ROWS)
        state, rows = self._retrieve(instant, symbol=symbol or None, source_id=source_id or None,
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
                # Saved provenance, verbatim; the collector may have saved none of these.
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
        recorded = self.budget_status()
        budget, budget_basis = recorded, 'RECORDED_USAGE_OF_THE_PLANNED_DAY'
        if isinstance(recorded.get('day'), str) and recorded['day'] != instant.date().isoformat():
            # The budget is per UTC day. Usage recorded for an earlier day does not carry to the planned one.
            budget = dict(recorded, day=instant.date().isoformat(), requests=0, tokens=0, held_requests=0, held_tokens=0,
                          usage_overrun=False)
            budget_basis = 'LIMITS_ONLY_USAGE_RESETS_BEFORE_THE_PLANNED_DAY'
        model = self.model()
        backlog = _bound(max_backlog, 'INVALID_PLAN_BOUND', default=100, maximum=MAX_PLAN_ROWS)
        allowance = _bound(request_allowance, 'INVALID_PLAN_BOUND', minimum=1)
        # Operator bounds can only tighten the recorded budget; none supplied means the budget's own limits.
        schedule = dict(max_requests=_bound(max_requests, 'INVALID_PLAN_BOUND', default=int(budget.get('max_requests') or 0)),
                        max_tokens=_bound(max_tokens, 'INVALID_PLAN_BOUND', default=int(budget.get('max_tokens') or 0)),
                        max_backlog=backlog)
        state, rows = self._retrieve(now, limit=MAX_PLAN_ROWS)
        rows = sorted(rows, key=lambda row: (row['available_at_ns'], row['record_id']))  # oldest evidence first
        if allowance is not None:
            # Stored bytes bound the content tokens; the allowance is the operator's bound for the
            # prompt, schema and answer of one request. Without it the planner refuses every record.
            rows = [dict(row, estimated_tokens=row['estimated_tokens'] + allowance,
                         token_estimate_scope='REQUEST_AND_OUTPUT_BOUND') for row in rows]
        assumed = bool(assume_available) and model['configured']
        plan = plan_local_inference_dry_run(
            rows, now=instant, schedule=schedule, session_is_trading_day=_trading_day(instant.astimezone(NEW_YORK).date()),
            engine=model['engine'], model=model['model'] or '', provider_configured=model['configured'],
            provider_available=True if assumed else None, resource_allowed=True, budget_status=budget,
            # The daily budget is the only spending policy this process holds; it is passed above.
            provider_gate=dict(allowed=True, reason=None))
        route = dict(plan['model_route'])
        if assumed and route['state'] == 'SUPPORTED':
            # The planner was told access exists. That was the operator's assumption, not a verification.
            route.update(state='ASSUMED_FOR_PREVIEW', availability_verified=False)
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
            store=state, candidates=len(rows), candidates_truncated=len(rows) >= MAX_PLAN_ROWS,
            planned_requests=plan['planned_requests'], planned_tokens=plan['planned_tokens'],
            planned=[reference(row) for row in plan['planned']],
            deferred=[reference(row, reason=row['reason']) for row in plan['deferred']],
            # A list, not a mapping: reason codes are values here, never response keys.
            deferred_reasons=[dict(reason=reason, count=count) for reason, count in sorted(reasons.items())],
            unscanned_count=plan['unscanned_count'], unscanned_reason=plan['unscanned_reason'],
            bounds=schedule, budget=budget, budget_basis=budget_basis, model=model, model_route=route,
            availability_basis='OPERATOR_ASSUMPTION_FOR_PREVIEW' if assumed else 'NOT_VERIFIED',
            estimate_basis='STORED_BYTES_PLUS_OPERATOR_ALLOWANCE' if allowance is not None else 'STORED_CONTENT_BYTES_ONLY',
            request_allowance=allowance,
            # What was not consulted: no dollar cap is configured in this process, no resource check exists
            # for a catch-up, and nothing here authorizes a paid call.
            spending_basis='RECORDED_DAILY_REQUEST_AND_TOKEN_BUDGET_ONLY', resource_basis='NOT_EVALUATED',
            paid_inference_permitted=False,
            # No catch-up worker exists, so no completed analysis has been acknowledged against a revision.
            processed_state='NO_COMPLETED_ANALYSIS_RECORDED', collection_independent=plan['collection_independent'],
            inference_calls=plan['inference_calls'], budget_reserved=plan['budget_reserved'], authority=AUTHORITY)

    # ------------------------------------------------------------------ local intelligence
    def intelligence(self, *, as_of=None, symbol=None, limit=None) -> dict:
        """The scheduled local worker's derived outputs known at a cutoff. Read-only; no model is loaded here."""
        import os
        from pathlib import Path

        from ..news.local_intelligence import DIRECTORY_ENV, read_view

        label, instant = self.cutoff(as_of)
        rows = _bound(limit, 'INVALID_EVIDENCE_LIMIT', default=100, minimum=1, maximum=MAX_KNOWLEDGE_ROWS)
        directory = (os.environ.get(DIRECTORY_ENV) or '').strip()
        view = read_view(Path(directory) if directory else None, as_of=instant.timestamp(),
                         symbol=symbol.strip().upper() if symbol else None, limit=rows)
        return dict(view, schema_version='evidence-review-intelligence/1', as_of=label, authority=AUTHORITY)

    # ------------------------------------------------------------------ decision journal
    def journal(self, *, day=None, as_of=None, decision_id=None) -> dict:
        from ..intelligence.news_strategy_evaluation.journal import build_daily_journal, capture_decision_snapshot

        as_of, instant = self.cutoff(as_of)
        try:
            selected = date.fromisoformat(day) if day else instant.astimezone(NEW_YORK).date()
        except (TypeError, ValueError) as exc:
            raise ValueError('INVALID_JOURNAL_DAY') from exc
        mode = 'PAPER'  # Action Decision receipts are Paper-account records; the action service traces them as PAPER
        account = self.store.paper_ledger.paper_account_id
        snapshots, unjournaled = [], []
        for decision in self.actions().evaluation_decisions(account, as_of):
            try:
                if _instant(decision['decision_time'], 'JOURNAL_CLOCK_INVALID').astimezone(NEW_YORK).date() != selected:
                    continue
                snapshots.append(capture_decision_snapshot(decision=decision, mode=mode))
            except Exception as exc:  # noqa: BLE001 - one unreadable receipt must not hide the rest of the day
                # A receipt the journal contract refuses is listed, never repaired or dropped silently.
                unjournaled.append(dict(decision_id=decision.get('decision_id'), instrument_id=decision.get('instrument_id'),
                                        decision_time=decision.get('decision_time'),
                                        reason=str(exc) if isinstance(exc, ValueError) and str(exc) else type(exc).__name__))
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
                        # The Paper episode this decision opened, where the ledger holds one. A decision that
                        # closed a position carries none: the episode is reported on its opening decision.
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
                later_evidence=later_evidence(entry['decision_id'])))
        return dict(schema_version='evidence-review-journal/1', day=journal['day'], day_basis=journal['day_basis'],
                    observation_as_of=as_of, account_id=account, mode=mode, items=items, unjournaled=unjournaled,
                    source='ACTION_DECISION_RECEIPTS', later_evidence_source='PROSPECTIVE_EVALUATION_PROJECTION',
                    # What this view does not read, so an empty field is never mistaken for a finding.
                    operator_action_source='DECISION_TRACE_NOT_READ_BY_THIS_VIEW',
                    research_outcomes='NOT_READ_BY_THIS_VIEW', operator_reviews='NOT_READ_BY_THIS_VIEW',
                    realized_pnl_source='PAPER_LEDGER_EPISODE_IN_LATER_EVIDENCE_NOT_COMPUTED_HERE',
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
        if chosen is None:
            raise ValueError('REPLAY_DAY_NOT_IN_FIXTURE')
        as_of = as_of or chosen['clocks'][-1]
        if _instant(as_of, 'REPLAY_CLOCK_INVALID') > self.now():
            raise ValueError('INVALID_EVIDENCE_CUTOFF')
        harness = EvaluationReplayHarness()
        view = harness.snapshot_at(replay_date=replay_date, as_of=as_of, pack=pack)
        again = harness.snapshot_at(replay_date=replay_date, as_of=as_of, pack=pack)
        decisions = []
        for sample in view['decisions']:
            policies = [dict(policy_id=item['policy_id'], policy_version=item['policy_version'],
                             classification=item['policy_classification'], decision=item['decision'],
                             directional_units=item['normalized_directional_units'], decision_id=item['decision_id'],
                             inference_record_ids=item['inference_record_ids']) for item in sample['policy_decisions']]
            first = sample['policy_decisions'][0]
            decisions.append(dict(sample_id=sample['sample_id'], as_of=sample['as_of'], instrument_id=first['instrument_id'],
                                  news_event_ids=first['news_event_ids'], market_snapshot_ref=first['market_snapshot_ref'],
                                  feature_snapshot_id=first['feature_snapshot_id'], policies=policies,
                                  ai_output_admitted=any(item['inference_record_ids'] for item in policies),
                                  policies_differ=len({item['decision'] for item in policies}) > 1))
        admitted = sum(row['ai_output_admitted'] for row in decisions)
        limitations = list(view['limitations'])
        if view['coverage']['withheld_inference'] and not admitted:
            # The curated pack's stored AI output carries no article lineage, so the as-of view admits none
            # of it and the AI-enhanced policy decides on the same inputs as the baseline.
            limitations.append('FIXTURE_AI_OUTPUT_NOT_ADMITTED_WITHOUT_ARTICLE_LINEAGE')
        return dict(schema_version='evidence-review-replay/1', evidence_class='SOFTWARE_FIXTURE_ONLY',
                    replay_date=view['replay_date'], as_of=view['as_of'], timezone=view['timezone'],
                    market_data_ref=view['market_data_ref'], config_hash=view['config_hash'], coverage=view['coverage'],
                    ai_output_admitted_samples=admitted, decisions=decisions, gaps=view['gaps'], limitations=limitations,
                    snapshot_hash=view['snapshot_hash'], rebuild_identical=view == again, available=available,
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
    if view == 'intelligence':
        return service.intelligence(as_of=first('as_of'), symbol=first('symbol'), limit=first('limit'))
    if view == 'journal':
        return service.journal(day=first('day'), as_of=first('as_of'), decision_id=first('decision_id'))
    if view == 'replay':
        return service.replay(replay_date=first('date'), as_of=first('as_of'))
    raise ValueError('EVIDENCE_ROUTE_NOT_FOUND')


__all__ = ['AUTHORITY', 'EvidenceReviewService', 'evidence_review_service', 'read_evidence']
