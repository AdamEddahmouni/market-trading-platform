"""OCT1-07 next-session snapshots: freeze an action decision, observe later, compare.

Reuses the forward-test lifecycle names, temporal guards and signal/execution
outcome split without campaign activation. A comparison is an observation,
never performance evidence. No order construction or submission.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ..intelligence.forward_qualification.evidence01.continuity import _DEFAULT_HOLIDAYS, is_trading_day
from ..intelligence.inference.action_decision import build_conditions
from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.paper_forward_bridge.evaluation import compute_execution_outcome, compute_signal_outcome
from ..intelligence.paper_forward_bridge.lifecycle import assert_transition
from ..intelligence.paper_forward_bridge.temporal import (
    assert_evaluation_horizon_reached, assert_input_observable_at_decision,
    assert_observation_after_decision, assert_observation_source_after_decision,
    assert_source_time_at_or_before_decision,
)
from ..intelligence.paper_forward_bridge.types import ForwardTestMode, ForwardTestState
from ..local_state.reevaluation import NEXT_SESSION_MUTABLE, reevaluation_repository
from ..market_data.freshness_contract import timestamp
from ..shadow.session import ET, session_bounds_ns

SCHEMA = 'next-session-decision/1.0.0'
VIEW_SCHEMA = 'next-session-view/1.0.0'
SESSION_KIND = 'US_EQUITY_RTH'
# Authorized deterministic rules only; the horizon is frozen at draft, never chosen afterwards.
EVALUATION_POLICIES = {'next-session-open-30m/1.0.0': 1800, 'next-session-close/1.0.0': None}
DEFAULT_EVALUATION_POLICY = 'next-session-open-30m/1.0.0'
_CALENDAR_YEARS = frozenset(day[:4] for day in _DEFAULT_HOLIDAYS)
_NS = 1_000_000_000


def _iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z')


def _ns(value):
    moment = timestamp(value)
    if moment is None:
        raise ValueError('NEXT_SESSION_CLOCK_INVALID')
    return int(moment.timestamp() * _NS)


def next_us_equity_session(cutoff):
    """First regular session opening strictly after the cutoff.

    Weekends and the frozen holiday calendar are honoured. Outside calendar
    coverage the date is refused, never guessed. Early closes are not in the
    canonical calendar and are recorded as unavailable.
    """
    moment = timestamp(cutoff)
    if moment is None:
        raise ValueError('NEXT_SESSION_CLOCK_INVALID')
    cutoff_ns = int(moment.timestamp() * _NS)
    day = moment.astimezone(ET).date()
    for _ in range(12):
        if str(day.year) not in _CALENDAR_YEARS:
            raise ValueError('NEXT_SESSION_CALENDAR_UNAVAILABLE')
        if is_trading_day(day):
            start, end = session_bounds_ns(day.isoformat())
            if start > cutoff_ns:
                return dict(target_session_date=day.isoformat(), target_session_kind=SESSION_KIND,
                            target_timezone='America/New_York', target_session_start=_iso(start / _NS),
                            target_session_end=_iso(end / _NS), early_close_metadata='UNAVAILABLE',
                            calendar_source='evidence01.continuity/us-equity-holidays')
        day += timedelta(days=1)
    raise ValueError('NEXT_SESSION_CALENDAR_UNAVAILABLE')


def evaluation_policy(policy_id, session):
    if policy_id not in EVALUATION_POLICIES:
        raise ValueError('NEXT_SESSION_EVALUATION_POLICY_UNAUTHORIZED')
    start = timestamp(session['target_session_start'])
    seconds = EVALUATION_POLICIES[policy_id]
    end = min(start + timedelta(seconds=seconds), timestamp(session['target_session_end'])) if seconds else timestamp(session['target_session_end'])
    return dict(policy_id=policy_id, observation_start=session['target_session_start'],
                observation_end=end.isoformat().replace('+00:00', 'Z'),
                reference_price_basis='DECISION_REFERENCE_QUOTE',
                observed_price_basis='LAST_ADMISSIBLE_QUOTE_IN_WINDOW',
                decision_state_comparison='LATEST_ACTION_DECISION_AT_EVALUATION')


def content_hash(record):
    return input_hash_from_dict({k: v for k, v in record.items() if k not in NEXT_SESSION_MUTABLE and k != 'content_hash'})


def _default_quote(instrument, now):
    """Current admissible Screener quote; the browser never supplies a price."""
    from .screener_ai import screener_ai_service
    _, candidates, cutoff, _ = screener_ai_service()._packet(dict(universe=instrument.get('universe'), search=instrument.get('symbol', '')))
    candidate = next((c for c in candidates if c['instrument']['instrument_id'] == instrument['instrument_id']), None)
    if candidate is None:
        return None
    quote = build_conditions(candidate, dict(position=dict(state='FLAT')), cutoff)[0]
    if quote['status'] != 'MET':
        return None
    evidence = next(e for e in candidate['current_market_evidence'] if e['evidence_id'] == quote['evidence_refs'][0])
    return dict(price=quote['source_value'], as_of=quote['as_of'], source=evidence.get('source'), delivery_mode=evidence.get('delivery_mode'))


class NextSessionService:
    def __init__(self, store, *, repository=None, actions=None, clock=time.time, quote_reader=None):
        self.store = store
        self.repository = repository or reevaluation_repository()
        self._actions = actions
        self.clock = clock
        self.quote_reader = quote_reader or _default_quote

    @property
    def actions(self):
        if self._actions is None:
            from .screener_action import action_service
            self._actions = action_service(self.store)
        return self._actions

    def _account(self):
        return self.store.paper_ledger.paper_account_id

    def _record(self, body):
        if not isinstance(body, dict) or set(body) != {'snapshot_id'} or not isinstance(body['snapshot_id'], str) or len(body['snapshot_id']) > 120:
            raise ValueError('INVALID_NEXT_SESSION_REQUEST')
        record = self.repository.get_snapshot(body['snapshot_id'])
        if record is None or record['account_id'] != self._account():
            raise ValueError('NEXT_SESSION_NOT_FOUND')
        return record

    def draft(self, body):
        """Freeze by reference to one real action decision; nothing is re-read or refreshed."""
        if not isinstance(body, dict) or 'decision_id' not in body or set(body) - {'decision_id', 'evaluation_policy'} \
                or any(not isinstance(v, str) or not v or len(v) > 160 for v in body.values()):
            raise ValueError('INVALID_NEXT_SESSION_REQUEST')
        decision = self.actions.repository.get('decision', body['decision_id'])
        if decision is None or decision['position']['account_id'] != self._account():
            raise ValueError('ACTION_DECISION_NOT_FOUND')
        if decision['action_state'] == 'REVALIDATION_REQUIRED':
            raise ValueError('ACTION_EVALUATION_UNAVAILABLE')
        if decision['instrument'].get('universe') not in ('US_EQUITIES', 'US_ETFS'):
            raise ValueError('NEXT_SESSION_CALENDAR_UNAVAILABLE')
        now = _iso(self.clock())
        session = next_us_equity_session(decision['decision_time'])
        policy = evaluation_policy(body.get('evaluation_policy', DEFAULT_EVALUATION_POLICY), session)
        snapshot = decision['evidence_snapshot']
        clocks = [e['as_of'] for e in (*snapshot['evidence']['current_market_evidence'], *snapshot['evidence']['reference_evidence']) if timestamp(e.get('as_of'))]
        reference = decision.get('reference_quote') or {}
        identity = 'NS-' + input_hash_from_dict(dict(account=self._account(), decision=decision['decision_id']))[:32]
        record = dict(
            schema_version=SCHEMA, snapshot_id=identity, instrument_id=decision['instrument_id'],
            instrument=decision['instrument'], account_id=self._account(), created_at=now,
            decision_cutoff=decision['decision_time'], evidence_max_time=max(clocks, key=timestamp) if clocks else None,
            **session, action_decision_id=decision['decision_id'], action_state=decision['action_state'],
            direction=decision['direction'], candidate_run_id=snapshot['candidate_run_id'],
            candidate_rank=snapshot['candidate_rank'], evidence_snapshot_ref=decision['evidence_snapshot_id'],
            decision_trace_id=decision['decision_trace_id'], policy_id=decision['policy_id'],
            provider_id=decision['model']['provider_id'], model_id=decision['model']['model_id'],
            prompt_id=decision['model']['prompt_id'], prompt_hash=decision['model']['prompt_hash'],
            input_hash=decision['input_hash'], position_state=decision['position']['state'],
            entry_conditions=[dict(condition_id=c['condition_id'], status=c['status']) for c in decision['entry_plan']],
            hold_conditions=[dict(condition_id=c['condition_id'], status=c['status']) for c in decision['hold_plan']],
            exit_conditions=[dict(condition_id=c['condition_id'], status=c['status']) for c in decision['exit_plan']],
            reference_price=reference.get('source_value') if reference.get('status') == 'MET' else None,
            reference_price_as_of=reference.get('as_of') if reference.get('status') == 'MET' else None,
            evaluation_policy=policy,
            lineage_refs=[dict(type='ActionDecisionV1', id=decision['decision_id']),
                          dict(type='ActionEvidenceSnapshotV1', id=decision['evidence_snapshot_id']),
                          dict(type='ExecutionDecisionTrace', id=decision['decision_trace_id'])],
            run_kind='FORWARD_TEST', test_mode=ForwardTestMode.SIGNAL_ONLY.value,
            state=ForwardTestState.DRAFT.value, lock_state='DRAFT', locked_at=None,
            validity_state='SOURCE_DECISION_CURRENT' if timestamp(decision['valid_until']) > timestamp(now) else 'SOURCE_DECISION_EXPIRED',
            evaluation=None, updated_at=now)
        record['content_hash'] = content_hash(record)
        previous = self.repository.get_snapshot(identity)
        if previous is not None and previous['lock_state'] != 'DRAFT':
            # A locked snapshot is returned as-is when equivalent, refused otherwise.
            if previous['evaluation_policy']['policy_id'] != policy['policy_id']:
                raise ValueError('NEXT_SESSION_LOCKED_IMMUTABLE')
            return self.view(previous)
        if previous is not None and previous['evaluation_policy'] == policy:
            return self.view(previous)
        self.repository.put_snapshot(record)
        return self.view(record)

    def lock(self, body):
        record = self._record(body)
        now = _iso(self.clock())
        if record['lock_state'] == 'LOCKED':
            return self.view(record)
        decision = self.actions.repository.get('decision', record['action_decision_id'])
        if decision is None or decision['evidence_snapshot_id'] != record['evidence_snapshot_ref'] or decision['input_hash'] != record['input_hash']:
            raise ValueError('NEXT_SESSION_SOURCE_DECISION_MISMATCH')
        cutoff = _ns(record['decision_cutoff'])
        snapshot = decision['evidence_snapshot']['evidence']
        for e in (*snapshot['current_market_evidence'], *snapshot['reference_evidence']):
            if e.get('as_of'):
                assert_source_time_at_or_before_decision(source_time_ns=_ns(e['as_of']), decision_time_ns=cutoff)
        start = _ns(record['evaluation_policy']['observation_start'])
        if not cutoff < start or _ns(now) >= start:
            raise ValueError('NEXT_SESSION_LOCK_AFTER_OBSERVATION_START')
        if content_hash(record) != record['content_hash']:
            raise ValueError('NEXT_SESSION_CONTENT_HASH_MISMATCH')
        assert_transition(ForwardTestState(record['state']), ForwardTestState.LOCKED)
        locked = dict(record, state=ForwardTestState.LOCKED.value, lock_state='LOCKED', locked_at=now, updated_at=now,
                      validity_state='SOURCE_DECISION_CURRENT' if timestamp(decision['valid_until']) > timestamp(now) else 'SOURCE_DECISION_EXPIRED')
        self.repository.put_snapshot(locked)
        return self.view(locked)

    def _advance(self, record, now):
        """OBSERVING becomes EVALUABLE only once the frozen horizon has passed."""
        if record['state'] == ForwardTestState.OBSERVING.value and _ns(now) >= _ns(record['evaluation_policy']['observation_end']):
            assert_transition(ForwardTestState.OBSERVING, ForwardTestState.EVALUABLE)
            record = dict(record, state=ForwardTestState.EVALUABLE.value, updated_at=now)
            self.repository.put_snapshot(record)
        return record

    def observe(self, body, *, quote=None):
        """Append one later observation. It never touches the frozen snapshot."""
        record = self._record(body)
        if record['lock_state'] != 'LOCKED':
            raise ValueError('NEXT_SESSION_NOT_LOCKED')
        if record['state'] in (ForwardTestState.EVALUATED.value, ForwardTestState.INSUFFICIENT_DATA.value):
            raise ValueError('NEXT_SESSION_ALREADY_EVALUATED')
        now = _iso(self.clock())
        quote = quote if quote is not None else self.quote_reader(record['instrument'], now)
        if not quote or not isinstance(quote.get('price'), (int, float)) or quote['price'] <= 0:
            raise ValueError('OBSERVATION_QUOTE_UNAVAILABLE')
        cutoff, observed, source = _ns(record['decision_cutoff']), _ns(now), _ns(quote['as_of'])
        assert_observation_after_decision(observation_time_ns=observed, decision_time_ns=cutoff)
        assert_observation_source_after_decision(source_time_ns=source, decision_time_ns=cutoff)
        assert_input_observable_at_decision(effective_time_ns=source, decision_time_ns=observed)
        policy = record['evaluation_policy']
        latest = self.actions.history(record['instrument_id'])
        position = self.actions._position(record['instrument_id'], now)
        observation = dict(
            observation_id='NO-' + input_hash_from_dict(dict(snapshot=record['snapshot_id'], observed=now, source=quote['as_of']))[:32],
            snapshot_id=record['snapshot_id'], observed_at=now, source_time=quote['as_of'], price=quote['price'],
            source=quote.get('source'), delivery_mode=quote.get('delivery_mode'),
            in_window=_ns(policy['observation_start']) <= source <= _ns(policy['observation_end']),
            position_state=position['state'], pending=position['pending'],
            latest_action_decision_id=latest[0]['decision_id'] if latest else None,
            latest_action_state=latest[0]['action_state'] if latest else None)
        self.repository.append_observation(observation)
        if record['state'] == ForwardTestState.LOCKED.value:
            assert_transition(ForwardTestState.LOCKED, ForwardTestState.OBSERVING)
            record = dict(record, state=ForwardTestState.OBSERVING.value, updated_at=now)
            self.repository.put_snapshot(record)
        return self.view(self._advance(record, now))

    def _execution(self, record):
        """Only a real Paper order carrying this decision's provenance is an execution outcome."""
        order = None
        for candidate in self.store.paper_ledger.project_orders():
            reasons = (candidate.get('decision_source_snapshot') or {}).get('reasons', [])
            if any(r.get('code') == 'ACTION_DECISION' and r.get('label') == record['action_decision_id'] for r in reasons):
                order = candidate
        probe = SimpleNamespace(test_mode=ForwardTestMode.EXECUTION if order else ForwardTestMode.SIGNAL_ONLY,
                                paper_order_id=order.get('order_id') if order else None,
                                paper_intent_id=order.get('intent_id') if order else None)
        # P&L lifecycle belongs to OCT1-09; only the existence/fill fact is reported here.
        return compute_execution_outcome(decision=probe, realized_pnl_minor=None, unrealized_pnl_minor=None,
                                         fill_count=1 if order and order.get('state') == 'FILLED' else 0).to_dict()

    def comparison(self, record, observations, now):
        window = [o for o in observations if o['in_window']]
        first, last = (window[0], window[-1]) if window else (None, None)
        reference = record['reference_price']
        signal = compute_signal_outcome(decision=SimpleNamespace(direction=record['direction'] or 'NONE'),
                                        entry_price=float(reference) if reference is not None else None,
                                        exit_price=float(last['price']) if last else None).to_dict()
        latest = self.actions.history(record['instrument_id'])
        later = latest[0] if latest and latest[0]['decision_id'] != record['action_decision_id'] else None
        return dict(
            basis='OBSERVATION_ONLY_NOT_PERFORMANCE_EVIDENCE',
            frozen_action_state=record['action_state'], frozen_direction=record['direction'],
            decision_reference_price=reference, decision_reference_as_of=record['reference_price_as_of'],
            first_observed_price=first['price'] if first else None, last_observed_price=last['price'] if last else None,
            last_observed_at=last['source_time'] if last else None,
            change_pct=round((last['price'] / reference - 1) * 100, 4) if last and reference else None,
            elapsed_seconds=int((timestamp(last['source_time']) - timestamp(record['decision_cutoff'])).total_seconds()) if last else None,
            in_window_observations=len(window), observation_count=len(observations),
            subsequent_action_state=later['action_state'] if later else None,
            subsequent_action_decision_id=later['decision_id'] if later else None,
            conditions_now=[dict(condition_id=c['condition_id'], status=c['status']) for c in later['conditions']] if later else None,
            position_state_now=self.actions._position(record['instrument_id'], now)['state'],
            signal_outcome=signal, execution_outcome=self._execution(record))

    def evaluate(self, body):
        record = self._record(body)
        if record['state'] in (ForwardTestState.EVALUATED.value, ForwardTestState.INSUFFICIENT_DATA.value):
            return self.view(record)
        if record['lock_state'] != 'LOCKED':
            raise ValueError('NEXT_SESSION_NOT_LOCKED')
        now = _iso(self.clock())
        cutoff, end = _ns(record['decision_cutoff']), _ns(record['evaluation_policy']['observation_end'])
        assert_evaluation_horizon_reached(now_ns=_ns(now), decision_time_ns=cutoff, horizon_ns=end - cutoff)
        observations = self.repository.observations(record['snapshot_id'])
        if record['state'] == ForwardTestState.LOCKED.value:
            assert_transition(ForwardTestState.LOCKED, ForwardTestState.OBSERVING)
            record = dict(record, state=ForwardTestState.OBSERVING.value)
        comparison = self.comparison(record, observations, now)
        target = ForwardTestState.INSUFFICIENT_DATA if comparison['signal_outcome']['quality'] == 'INSUFFICIENT_DATA' else ForwardTestState.EVALUATED
        if target is ForwardTestState.EVALUATED and record['state'] == ForwardTestState.OBSERVING.value:
            assert_transition(ForwardTestState.OBSERVING, ForwardTestState.EVALUABLE)
            record = dict(record, state=ForwardTestState.EVALUABLE.value)
        assert_transition(ForwardTestState(record['state']), target)
        evaluated = dict(record, state=target.value, updated_at=now, evaluation=dict(evaluated_at=now, **comparison))
        self.repository.put_snapshot(evaluated)
        return self.view(evaluated)

    def view(self, record):
        now = _iso(self.clock())
        if record['lock_state'] == 'LOCKED':
            record = self._advance(record, now)
        observations = self.repository.observations(record['snapshot_id'])
        return dict(schema_version=VIEW_SCHEMA, snapshot=record, observations=observations[-20:],
                    observation_count=len(observations), durability=self.repository.durability,
                    integrity='VERIFIED' if content_hash(record) == record['content_hash'] else 'CONTENT_HASH_MISMATCH',
                    comparison=record['evaluation'] or (self.comparison(record, observations, now) if observations else None))

    def read(self, snapshot_id):
        return self.view(self._record(dict(snapshot_id=snapshot_id)))

    def history(self, instrument):
        return [self.view(r) for r in self.repository.list_snapshots(self._account(), instrument)]


def next_session_service(store):
    service = getattr(store, '_next_session_service', None)
    if service is None:
        service = NextSessionService(store)
        store._next_session_service = service
    return service
