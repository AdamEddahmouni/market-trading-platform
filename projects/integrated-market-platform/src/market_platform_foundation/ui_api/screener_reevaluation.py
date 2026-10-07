"""OCT1-07 governed reevaluation: one core cycle, an explicit worker, truthful cadence.

The cycle reads evidence deterministically, gates on material change, and only
then asks the unchanged OCT1-06 action service for a new immutable decision.
It has no order, preview, handoff or submission path: Paper stays manual.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import UTC, datetime

from ..intelligence.inference.action_decision import POLICY_ID as ACTION_POLICY_ID
from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.inference.reevaluation import (
    CYCLE_SCHEMA, DEFAULT_POLICY, MAX_RECEIPT_BYTES, MAX_TRANSITIONS, POLICY_ID, STOP_BOOKKEEPING_REASONS, CycleStatus, ReevaluationTrigger,
    TransitionClass, build_policy, cadence_readiness, effective_cadence, loop_identity, material_change,
    material_fingerprint, missed_slots, provider_states, reevaluation_pick, slot_at_or_after,
    stability_decision, worst_case_calls,
)
from ..local_state.reevaluation import reevaluation_repository
from ..market_data.freshness_contract import timestamp
from ..market_sessions import ET, us_equity_session_label
from .paper_risk_control import quote_from_candidate

LOOP_SCHEMA = 'reevaluation-loop/1.0.0'
STATUS_SCHEMA = 'reevaluation-status/1.0.0'
HISTORY_SCHEMA = 'reevaluation-history/1.0.0'
RUN_SCHEMA = 'reevaluation-candidate-run/1.0.0'
_COMMITTED = ('ENTER', 'EXIT', 'HOLD')
_CODE = re.compile(r'[A-Z][A-Z0-9_]{2,63}')


def _iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z') if seconds is not None else None


def consumed_opportunities(ledger):
    """Same ledger provenance the OCT1-06 entry-risk check treats as consumed."""
    consumed = set()
    for order in ledger.project_orders():
        source = order.get('decision_source_snapshot') or {}
        if source.get('source_type') == 'watched_opportunity': consumed.add(source.get('source_id'))
        correlation = order.get('correlation_id') or ''
        if correlation.startswith('opportunity:'): consumed.add(correlation.split(':', 1)[1])
        legacy = (order.get('metadata') or {}).get('opportunity_id')
        if legacy: consumed.add(legacy)
    return consumed


class ReevaluationService:
    def __init__(self, store, *, repository=None, actions=None, ai=None, clock=time.time, owner_id=None):
        self.store = store
        self.repository = repository or reevaluation_repository()
        self._actions, self._ai = actions, ai
        self.clock = clock
        self.owner_id = owner_id or uuid.uuid4().hex
        self.cycle_lock = threading.Lock()
        self.worker = None

    @property
    def actions(self):
        if self._actions is None:
            from .screener_action import action_service
            self._actions = action_service(self.store)
        return self._actions

    @property
    def ai(self):
        if self._ai is None:
            from .screener_ai import screener_ai_service
            self._ai = screener_ai_service()
        return self._ai

    def _account(self):
        return self.store.paper_ledger.paper_account_id

    @property
    def stops(self):
        """OCT1-08 stop monitor: the same instance the action service reads its risk facts from."""
        if self.actions.risk_control is None:
            from .paper_risk_control import risk_control_service
            self.actions.risk_control = risk_control_service(self.store)
        return self.actions.risk_control

    def _loop(self):
        loop = self.repository.latest_loop(self._account())
        if loop is None:
            raise ValueError('REEVALUATION_NOT_CONFIGURED')
        return loop

    def engine_lock(self):
        """The engine choice is machine-wide. While a loop holds its lease the choice is locked, so a running
        session never changes model between cycles. Reads the lease only."""
        loop = self.repository.latest_loop(self._account())
        leased = bool(loop and loop['owner_id'] and loop['lease_until'] and loop['lease_until'] > self.clock())
        return dict(locked=leased, reason='REEVALUATION_LOOP_RUNNING' if leased else None)

    def engine_state(self):
        """Selected engine and its hard budget; never a fallback to another provider."""
        provider = self.actions._provider()
        if provider is None:
            return dict(state='NOT_CONFIGURED', reason='MODEL_UNAVAILABLE', provider_id=None, model_id=None, runtime=None, budget=None)
        reader = getattr(provider, 'budget_status', None)
        budget = reader() if callable(reader) else None
        exhausted = bool(budget and (budget['requests'] >= budget['max_requests'] or budget['tokens'] >= budget['max_tokens']))
        return dict(state='UNAVAILABLE' if exhausted else 'AVAILABLE',
                    reason='SYNTHESIS_DAILY_BUDGET_EXHAUSTED' if exhausted else None,
                    provider_id=getattr(provider, 'provider_id', None), model_id=getattr(provider, 'model_id', None),
                    runtime=getattr(provider, 'runtime', None) or 'PAID_API', budget=budget)

    def session_state(self, scope, epoch):
        if scope.get('universe') in ('US_EQUITIES', 'US_ETFS'):
            return us_equity_session_label(datetime.fromtimestamp(epoch, UTC))
        return 'NO_SESSION_CALENDAR'

    # --- operator controls ------------------------------------------------------
    def configure(self, body):
        if not isinstance(body, dict) or set(body) - {'scope', 'requested_cadence_seconds', 'policy'} or 'scope' not in body:
            raise ValueError('INVALID_REEVALUATION_CONFIG')
        if self.cycle_lock.locked():
            raise ValueError('CYCLE_IN_PROGRESS')
        if self.worker and self.worker.alive():
            raise ValueError('REEVALUATION_RUNNING_STOP_FIRST')  # one loop per process; never retarget a running worker
        scope = self.ai._query(body['scope'])
        policy = build_policy(body.get('policy'))
        cadence = effective_cadence(body.get('requested_cadence_seconds'), policy)
        loop_id, scope_hash = loop_identity(self._account(), scope)
        now = self.clock()
        existing = self.repository.get_loop(loop_id)
        if existing and existing['owner_id'] and existing['lease_until'] and existing['lease_until'] > now:
            raise ValueError('REEVALUATION_RUNNING_STOP_FIRST')
        base = existing or dict(schema_version=LOOP_SCHEMA, loop_id=loop_id, account_id=self._account(), scope_hash=scope_hash,
                                desired_state='STOPPED', clean_stop=True, anchor_epoch=None, tracked={}, selected=[], ranks={},
                                intake={}, last_reduction_epoch=None, last_reduction_run_id=None, last_scheduled_epoch=None,
                                last_started_epoch=None, last_completed_epoch=None, last_success_epoch=None, last_error=None,
                                last_status=None, missed_ticks=0, heartbeat_at=None, cycle_count=0)
        loop = dict(base, scope=scope, policy=policy, updated_epoch=now, configured_at=_iso(now),
                    requested_cadence_seconds=cadence['requested_cadence_seconds'],
                    effective_cadence_seconds=cadence['effective_cadence_seconds'], cadence=cadence)
        self.repository.save_loop(loop)
        return self.status(readiness=True)

    def _readiness(self, loop):
        """Deterministic evidence read only; no model, no provider refresh."""
        _, candidates, now, _ = self.ai._packet(loop['scope'], include_flow=True)
        states = provider_states(candidates, now=now, requested=loop['requested_cadence_seconds'])
        return dict(evaluated_at=now, provider_states=states,
                    **cadence_readiness(states, ai_state=self.engine_state(), cadence=loop['cadence']))

    def status(self, *, readiness=False):
        loop = self.repository.latest_loop(self._account())
        engine = self.engine_state()
        if loop is None:
            return dict(schema_version=STATUS_SCHEMA, worker_state='NOT_CONFIGURED', worker_label='Not configured',
                        engine=engine, durability=self.repository.durability, paper_execution='MANUAL_ONLY')
        now = self.clock()
        leased = bool(loop['owner_id'] and loop['lease_until'] and loop['lease_until'] > now)
        mine = leased and loop['owner_id'] == self.owner_id
        alive = bool(self.worker and self.worker.alive() and self.worker.loop_id == loop['loop_id'])
        effective = loop['effective_cadence_seconds']
        if mine and alive:
            # Measured from this run's own start: a pre-stop cycle is not evidence of delay.
            reference = max(loop['last_completed_epoch'] or 0, loop['anchor_epoch'] or 0) or now
            state = 'DELAYED' if now - reference > 2 * effective else 'RUNNING'
        elif mine:
            state = 'STALLED'
        elif leased:
            state = 'RUNNING_ELSEWHERE'
        elif loop['desired_state'] == 'RUNNING':
            state = 'INTERRUPTED'
        else:
            state = 'STOPPED'
        labels = dict(RUNNING='Running', DELAYED='Running — delayed', STALLED='Stalled — worker not alive',
                      RUNNING_ELSEWHERE='Running in another process', INTERRUPTED='Interrupted — not running; start explicitly to resume',
                      STOPPED='Stopped')
        latest = self.repository.cycles(loop['loop_id'], limit=1)
        last = latest[0] if latest else None
        next_slot = slot_at_or_after(loop['anchor_epoch'], effective, now) if state in ('RUNNING', 'DELAYED') and loop['anchor_epoch'] else None
        preview = self._readiness(loop) if readiness else None
        return dict(
            schema_version=STATUS_SCHEMA, loop_id=loop['loop_id'], account_id=loop['account_id'], scope=loop['scope'],
            scope_ref=loop['scope_hash'], policy=loop['policy'], worker_state=state, worker_label=labels[state],
            desired_state=loop['desired_state'], requested_cadence_seconds=loop['requested_cadence_seconds'],
            effective_cadence_seconds=effective, cadence=loop['cadence'],
            liveness=dict(last_scheduled=_iso(loop['last_scheduled_epoch']), last_started=_iso(loop['last_started_epoch']),
                          last_completed=_iso(loop['last_completed_epoch']), last_success=_iso(loop['last_success_epoch']),
                          last_error=loop['last_error'], last_status=loop['last_status'], missed_ticks=loop['missed_ticks'],
                          heartbeat_at=_iso(loop['heartbeat_at']), lease_until=_iso(loop['lease_until']) if leased else None,
                          owner='THIS_PROCESS' if mine else 'OTHER_PROCESS' if leased else None, cycle_count=loop['cycle_count']),
            next_scheduled=_iso(next_slot), last_cycle=last, engine=engine,
            readiness=preview or (dict(evaluated_at=last['evidence_cutoff'], provider_states=last['provider_states'], **last['readiness'])
                                  if last and last.get('readiness') else None),
            projection=worst_case_calls(loop['policy'], effective), tracked_candidates=loop['selected'],
            durability=self.repository.durability, paper_execution='MANUAL_ONLY', live_execution='UNCHANGED',
            evaluated_at=_iso(now))

    def start(self, *, wait=None, threaded=True):
        loop = self._loop()
        now = self.clock()
        if self.worker and self.worker.alive():
            raise ValueError('REEVALUATION_ALREADY_RUNNING')
        self.repository.acquire_lease(loop['loop_id'], self.owner_id, now=now, lease_seconds=loop['policy']['lease_seconds'])
        loop = self.repository.get_loop(loop['loop_id'])
        last = loop['last_scheduled_epoch']
        if last is not None and (not loop['clean_stop'] or now - last >= loop['effective_cadence_seconds']):
            # Downtime stays downtime: one gap receipt, zero reconstructed decisions.
            missed = 0 if loop['clean_stop'] else missed_slots(last, loop['effective_cadence_seconds'], now)
            self.repository.put_cycle(self._gap(loop, last, now, missed, 'OPERATOR_STOPPED' if loop['clean_stop'] else 'PROCESS_DOWNTIME'))
            loop['missed_ticks'] += missed
        loop.update(desired_state='RUNNING', clean_stop=False, anchor_epoch=now, updated_epoch=now, heartbeat_at=now)
        self.repository.save_loop(loop, owner_id=self.owner_id)
        self.worker = ReevaluationWorker(self, loop['loop_id'], wait=wait)
        if threaded:
            self.worker.start()
        return self.status()

    def stop(self):
        loop = self._loop()
        if loop['owner_id'] and loop['owner_id'] != self.owner_id and loop['lease_until'] and loop['lease_until'] > self.clock():
            raise ValueError('REEVALUATION_LOOP_ALREADY_OWNED')  # only the owning process can stop its worker
        ran = bool(self.worker and self.worker.loop_id == loop['loop_id'])
        if self.worker:
            self.worker.stop()
        # An in-flight cycle finishes and records its own receipt; it re-reads these control fields.
        loop = self.repository.get_loop(loop['loop_id'])
        loop.update(desired_state='STOPPED', updated_epoch=self.clock(), clean_stop=bool(loop['clean_stop'] or ran))
        self.repository.save_loop(loop)
        self.repository.release_lease(loop['loop_id'], self.owner_id)
        self.worker = None
        return self.status()

    def run_once(self):
        loop = self._loop()
        now = self.clock()
        if loop['owner_id'] and loop['owner_id'] != self.owner_id and loop['lease_until'] and loop['lease_until'] > now:
            raise ValueError('REEVALUATION_LOOP_ALREADY_OWNED')
        return self.evaluate_cycle(ReevaluationTrigger.MANUAL, now)

    def history(self, *, limit=20, before=None, session_date=None):
        loop = self._loop()
        if session_date is not None and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', session_date):
            raise ValueError('INVALID_REEVALUATION_HISTORY')
        cycles = self.repository.cycles(loop['loop_id'], limit=limit, before=before, session_date=session_date)
        return dict(schema_version=HISTORY_SCHEMA, loop_id=loop['loop_id'], cycles=cycles,
                    next_before=cycles[-1]['scheduled_epoch'] if len(cycles) >= max(1, min(int(limit), 100)) else None,
                    durability=self.repository.durability)

    def heartbeat(self, loop_id):
        try:
            self.repository.heartbeat(loop_id, self.owner_id, now=self.clock(), lease_seconds=self.repository.get_loop(loop_id)['policy']['lease_seconds'])
            return True
        except ValueError:
            return False

    # --- receipts ---------------------------------------------------------------
    def _receipt(self, loop, *, trigger, scheduled, started, status, **fields):
        cutoff = fields.pop('evidence_cutoff', None)
        return dict(
            schema_version=CYCLE_SCHEMA, loop_id=loop['loop_id'], account_id=loop['account_id'],
            cycle_id='RC-' + input_hash_from_dict(dict(loop=loop['loop_id'], scheduled=scheduled, started=started, trigger=str(trigger), status=str(status)))[:32],
            trigger=str(trigger), scheduled_for=_iso(scheduled), scheduled_epoch=scheduled, started_at=_iso(started),
            completed_at=None, start_drift_ms=int(round((started - scheduled) * 1000)), duration_ms=None,
            requested_cadence_seconds=loop['requested_cadence_seconds'], effective_cadence_seconds=loop['effective_cadence_seconds'],
            session_state=self.session_state(loop['scope'], scheduled),
            session_date=datetime.fromtimestamp(scheduled, ET).date().isoformat(), scope_ref=loop['scope_hash'],
            policy_id=POLICY_ID, evidence_cutoff=cutoff, position_count=0, candidate_count=0, intake_count=0,
            material_change_count=0, unchanged_count=0, model_call_count=0, missed_ticks_before=0,
            counters=dict(proposed_transitions=0, accepted_transitions=0, duplicate_suppressions=0,
                          churn_suppressions=0, model_calls_avoided=0),
            transitions=[], transitions_truncated=False, provider_states=[], readiness=None, budget_state=None,
            not_observed=None, cycle_status=str(status), reason_codes=[], **fields)

    def _gap(self, loop, start, end, missed, reason):
        receipt = self._receipt(loop, trigger=ReevaluationTrigger.SCHEDULED_CADENCE, scheduled=start, started=end,
                                status=CycleStatus.NOT_OBSERVED)
        receipt.update(completed_at=_iso(end), start_drift_ms=0, duration_ms=0, reason_codes=[reason],
                       not_observed=dict(observed_from=_iso(start), observed_to=_iso(end), missed_scheduled_cycles=missed,
                                         reason=reason, decisions_backfilled=0))
        return receipt

    # --- the single core cycle --------------------------------------------------
    def evaluate_cycle(self, trigger, scheduled_for, *, missed=0, overran=False, loop_id=None):
        """Used unchanged by Run Once and by the worker. Never overlaps itself."""
        trigger = ReevaluationTrigger(trigger)
        if not self.cycle_lock.acquire(blocking=False):
            raise ValueError('CYCLE_IN_PROGRESS')
        try:
            # A worker is bound to the loop it leased, whatever was configured since.
            loop = self.repository.get_loop(loop_id) if loop_id else self._loop()
            started = self.clock()
            # A scheduled cycle writes only while this process still owns the loop.
            fence = None if trigger is ReevaluationTrigger.MANUAL else self.owner_id
            if fence and loop['owner_id'] != fence:
                raise ValueError('REEVALUATION_LEASE_LOST')
            loop.update(last_scheduled_epoch=scheduled_for, last_started_epoch=started)
            self.repository.save_loop(loop, owner_id=fence)
            spent = dict(model_calls=0)

            def guard():
                """Before a model call: renew the lease, or stop if another process took the loop."""
                if fence and not self.heartbeat(loop['loop_id']) and self.repository.get_loop(loop['loop_id'])['owner_id'] is not None:
                    raise ValueError('REEVALUATION_LEASE_LOST')  # an operator Stop releases the lease; that cycle still finishes
            try:
                receipt = self._cycle(loop, trigger, scheduled_for, started, guard=guard, spent=spent)
            except Exception as exc:  # a failed cycle is recorded, never silently retried
                code = str(exc) if _CODE.fullmatch(str(exc)) else type(exc).__name__
                receipt = self._receipt(loop, trigger=trigger, scheduled=scheduled_for, started=started, status=CycleStatus.FAILED)
                receipt.update(reason_codes=[code], model_call_count=spent['model_calls'])  # a spent call stays counted
                loop['last_error'] = dict(at=_iso(started), code=code)
            completed = self.clock()
            receipt.update(completed_at=_iso(completed), duration_ms=int(round((completed - started) * 1000)), missed_ticks_before=missed)
            if overran:
                receipt['reason_codes'].append('CYCLE_OVERRAN')
            if completed - started > loop['effective_cadence_seconds']:
                receipt['reason_codes'].append('CYCLE_EXCEEDED_CADENCE')
            control = self.repository.get_loop(loop['loop_id'])
            if fence and control['owner_id'] not in (None, fence):
                # Displaced mid-cycle: the receipt is append-only truth, the loop now belongs to someone else.
                receipt['cycle_status'] = str(CycleStatus.FAILED)
                if 'REEVALUATION_LEASE_LOST' not in receipt['reason_codes']:
                    receipt['reason_codes'].append('REEVALUATION_LEASE_LOST')
                self._bound(receipt)
                self.repository.put_cycle(receipt)
                raise ValueError('REEVALUATION_LEASE_LOST')
            self._bound(receipt)
            self.repository.put_cycle(receipt)
            loop.update(last_completed_epoch=completed, last_status=receipt['cycle_status'], updated_epoch=completed,
                        missed_ticks=loop['missed_ticks'] + missed, cycle_count=loop['cycle_count'] + 1)
            if receipt['cycle_status'] != CycleStatus.FAILED:
                loop['last_success_epoch'] = completed
            # Start/Stop during the cycle wins; so does the lease heartbeat taken before a model call.
            loop.update({key: control[key] for key in ('desired_state', 'clean_stop', 'anchor_epoch', 'heartbeat_at')})
            self.repository.save_loop(loop, owner_id=fence if control['owner_id'] == fence else None)
            return receipt
        finally:
            self.cycle_lock.release()

    @staticmethod
    def _bound(receipt):
        receipt['transitions_truncated'] = len(receipt['transitions']) > MAX_TRANSITIONS
        receipt['transitions'] = receipt['transitions'][:MAX_TRANSITIONS]
        while len(json.dumps(receipt).encode('utf-8')) > MAX_RECEIPT_BYTES and (receipt['provider_states'] or receipt['transitions']):
            (receipt['provider_states'] or receipt['transitions']).pop()
            receipt['transitions_truncated'] = True

    def _context(self, candidate, now):
        iid = candidate['instrument']['instrument_id']
        opportunity = self.actions._opportunity(candidate, int(timestamp(now).timestamp() * 1e9))
        ledger = self.store.paper_ledger
        context = dict(position=self.actions._position(iid, now), candidate_valid_until=None,
                       opportunity_id=(opportunity or {}).get('opportunity_id'), authority=self.actions._authority(),
                       policy_id=ACTION_POLICY_ID + ':' + input_hash_from_dict(ledger.policy)[:16])
        risk = self.actions._risk_facts(iid)
        if risk:
            context['risk_control'] = risk
        return context

    def _blind_cycle(self, loop, trigger, scheduled, started, held, exc):
        """The evidence read failed: no decisions, but held positions keep their deterministic stop monitor."""
        receipt = self._receipt(loop, trigger=trigger, scheduled=scheduled, started=started, status=CycleStatus.REEVALUATION_BLOCKED)
        reasons = receipt['reason_codes']
        reasons.extend(['EVIDENCE_READ_FAILED', str(exc) if _CODE.fullmatch(str(exc)) else type(exc).__name__])
        stops = self.stops
        for iid in dict.fromkeys([*held, *stops.open_instruments()]):
            try:
                stops.evaluate(iid)  # no Screener quote: the stop service reads its own bar and quote sources
            except ValueError as error:
                reasons.append('STOP_EVALUATION_FAILED_' + (str(error) if _CODE.fullmatch(str(error)) else 'ERROR')[:40])
        receipt.update(position_count=len(held), candidate_count=len(loop['selected']))
        loop['last_error'] = dict(at=_iso(started), code=reasons[1])
        return receipt

    def _cycle(self, loop, trigger, scheduled, started, *, guard=lambda: None, spent=None):
        policy, scope, actions = loop['policy'], loop['scope'], self.actions
        ledger = self.store.paper_ledger
        positions = [p for p in ledger.project_positions() if p.get('quantity')]
        held = [p['instrument_id'] for p in positions]
        # Held instruments keep their own quote subscription whether or not any page is showing them.
        subscribed = True
        try:
            from .live_projections import keep_portfolio_marks_current
            keep_portfolio_marks_current(self.store)
        except Exception:
            subscribed = False
        try:
            _, candidates, now, _ = self.ai._packet(scope, include_flow=True)
        except Exception as exc:
            return self._blind_cycle(loop, trigger, scheduled, started, held, exc)
        by_id = {c['instrument']['instrument_id']: c for c in candidates}
        # Every held position is looked at, least recently seen first, up to the per-cycle bound.
        seen = loop.setdefault('held_seen', {})
        for iid in [i for i in seen if i not in held]:
            del seen[iid]
        bound = policy.get('max_held_per_cycle', DEFAULT_POLICY['max_held_per_cycle'])
        watched = sorted(held, key=lambda i: seen.get(i, 0))[:bound]
        for position in [p for p in positions if p['instrument_id'] in watched and p['instrument_id'] not in by_id]:
            # A held instrument outside the bounded intake gets one targeted read, not a universe sweep.
            if position.get('symbol'):
                try:
                    _, extra, _, _ = self.ai._packet(dict(scope, search=str(position['symbol'])[:120], filters=[], result_set=None), include_flow=True)
                except Exception:
                    continue  # recorded below as HELD_INSTRUMENT_EVIDENCE_UNAVAILABLE; the stop is still evaluated
                by_id.update({c['instrument']['instrument_id']: c for c in extra if c['instrument']['instrument_id'] == position['instrument_id']})
        engine = self.engine_state()
        usable = engine['state'] == 'AVAILABLE'
        hour = self.repository.model_calls_since(loop['account_id'], started - 3600)
        day = self.repository.model_calls_since(loop['account_id'], started - 86400)
        window_left = min(policy['max_model_calls_per_hour'] - hour, policy['max_model_calls_per_day'] - day)
        state = spent if spent is not None else {}
        state.update(remaining=max(0, min(policy['max_model_calls_per_cycle'], window_left)) if usable else 0,
                     model_calls=0, action_calls=0, material=0, unchanged=0)
        receipt = self._receipt(loop, trigger=trigger, scheduled=scheduled, started=started,
                                status=CycleStatus.NO_MATERIAL_CHANGE, evidence_cutoff=now)
        counters, transitions, reasons = receipt['counters'], receipt['transitions'], receipt['reason_codes']
        if len(held) > len(watched):
            reasons.append('HELD_POSITION_CAP_EXCEEDED')
        if held and not subscribed:
            reasons.append('HELD_QUOTE_SUBSCRIPTION_FAILED')
        noted = loop.setdefault('unavailable_noted', {})
        for iid in [i for i in noted if i not in held]:
            del noted[iid]
        consumed = consumed_opportunities(ledger)
        stops, scale = self.stops, int(ledger.policy.get('price_scale', 100))
        # Stops whose position is no longer held are closed here; they never carry into a later position.
        for iid in stops.open_instruments():
            if iid not in held:
                stops.evaluate(iid)
        blocked_class = TransitionClass.BUDGET_BLOCKED if engine['reason'] == 'SYNTHESIS_DAILY_BUDGET_EXHAUSTED' or (usable and window_left <= 0) else TransitionClass.MODEL_UNAVAILABLE

        def note(instrument, classification, codes, **extra):
            transitions.append(dict(dict(instrument_id=instrument, classification=str(classification), reason_codes=list(dict.fromkeys(codes)),
                                         prior_decision_id=None, new_decision_id=None, prior_state=None, new_state=None,
                                         position_state=None, model_call=False, safety=False), **extra))

        def plan(iid):
            candidate = by_id.get(iid)
            history = actions.history(iid)
            if iid in held:
                # OCT1-08: position -> completed bars -> stop -> breach check, before any model is considered.
                try:
                    stops.evaluate(iid, quote=quote_from_candidate(candidate, now, scale) if candidate else None)
                except ValueError as exc:
                    reasons.append('STOP_EVALUATION_FAILED_' + (str(exc) if _CODE.fullmatch(str(exc)) else 'ERROR')[:40])
            if candidate is None:
                return dict(iid=iid, candidate=None, history=history, reasons=[], fingerprint=None)
            context = self._context(candidate, now)
            fingerprint = material_fingerprint(candidate, context, now)
            baseline = loop['tracked'].get(iid)
            changes = material_change(baseline if isinstance(baseline, dict) else None, fingerprint, policy)
            if not changes and history and (timestamp(now) - timestamp(history[0]['decision_time'])).total_seconds() >= policy['decision_max_age_seconds']:
                changes = ['DECISION_AGED_OUT']
            return dict(iid=iid, candidate=candidate, history=history, reasons=changes, fingerprint=fingerprint, context=context)

        def execute(item):
            iid, history, changes, fingerprint = item['iid'], item['history'], item['reasons'], item['fingerprint']
            prior = history[0] if history else None
            if item['candidate'] is None:
                breached = (actions._risk_facts(iid) or {}).get('status') == 'BREACHED'
                marker = 'EVIDENCE_UNAVAILABLE_STOP_BREACHED' if breached else 'EVIDENCE_UNAVAILABLE'
                # Said again once the last note is as old as a decision may be: a blind holding never goes quiet.
                if loop['tracked'].get(iid) != marker or started - noted.get(iid, started) >= policy['decision_max_age_seconds']:
                    noted[iid] = started
                    state['material'] += 1
                    # The breach is recorded on the stop itself; a decision still needs admissible evidence.
                    note(iid, TransitionClass.REVALIDATION_REQUIRED,
                         ['HELD_INSTRUMENT_EVIDENCE_UNAVAILABLE', *(['SMA_TRAILING_STOP_BREACHED'] if breached else [])], safety=breached)
                    loop['tracked'][iid] = marker
                return
            if not changes:
                state['unchanged'] += 1; counters['model_calls_avoided'] += 1
                return
            state['material'] += 1; counters['proposed_transitions'] += 1
            position = item['context']['position']
            base = dict(prior_decision_id=prior['decision_id'] if prior else None, prior_state=prior['action_state'] if prior else None,
                        position_state=position['state'])
            if set(changes) <= STOP_BOOKKEEPING_REASONS:
                # A routine stop update is deterministic state, not a question for a model.
                counters['model_calls_avoided'] += 1
                transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.MATERIAL_EVIDENCE_CHANGED),
                                        reason_codes=[*changes, 'DETERMINISTIC_STOP_UPDATE'], new_decision_id=None, new_state=None,
                                        model_call=False, safety=False, **base))
                loop['tracked'][iid] = fingerprint
                return
            # A breached stop is a server risk exit: no forced revalidation, no model budget, no model veto.
            server_exit = (fingerprint.get('stop') or [None])[0] == 'BREACHED'
            recorded = (prior or {}).get('server_exit') or {}
            if server_exit and recorded.get('stop_state_id') == item['context']['risk_control']['stop_state_id']                     and prior['position']['quantity'] == position['quantity'] and timestamp(prior['valid_until']) > timestamp(now):
                # The same breach on the same holding already has its current EXIT record: do not fork a second one.
                counters['duplicate_suppressions'] += 1; counters['model_calls_avoided'] += 1
                transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.DUPLICATE_SUPPRESSED),
                                        reason_codes=[*changes, 'STOP_EXIT_ALREADY_RECORDED'], new_decision_id=None, new_state=None,
                                        model_call=False, safety=True, **base))
                loop['tracked'][iid] = fingerprint
                return
            changed_at = next((d['decision_time'] for d in history if d['action_state'] != d['previous_state']), None)
            committed = prior is not None and prior['action_state'] in _COMMITTED
            # A quote coming back is a recovery: it waits out the dwell since the loss was recorded, so a
            # flapping quote buys at most one model call per dwell instead of one per recovery.
            since = changed_at if committed else prior['decision_time'] if prior and 'QUOTE_RESTORED' in changes else None
            stability = stability_decision(changes, now=now, last_state_change=since, policy=policy)
            if not stability['evaluate']:
                counters['churn_suppressions'] += 1; counters['model_calls_avoided'] += 1
                transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.CHURN_SUPPRESSED),
                                        reason_codes=[*changes, *stability['reason_codes']], new_decision_id=None, new_state=None,
                                        model_call=False, safety=False, dwell_remaining_seconds=stability['dwell_remaining_seconds'], **base))
                return
            forced = None
            if server_exit:
                pass
            elif position['pending']:
                forced = 'PENDING_ORDER_REVALIDATION'
            elif fingerprint['quote'] != 'MET':
                forced = 'QUOTE_STALE_OR_UNAVAILABLE'
            elif 'AUTHORITY_LOST' in changes:
                forced = 'PAPER_AUTHORITY_UNAVAILABLE'
            if forced is None and position['state'] == 'FLAT':
                duplicate = None
                if fingerprint['opportunity'] and fingerprint['opportunity'] in consumed:
                    duplicate = 'OPPORTUNITY_ALREADY_CONSUMED'
                elif prior and prior['action_state'] == 'ENTER' and timestamp(prior['valid_until']) > timestamp(now) \
                        and set(changes) <= {'PRICE_MOVED', 'DECISION_AGED_OUT'}:
                    duplicate = 'ACTIVE_ENTER_UNEXPIRED'
                if duplicate:
                    counters['duplicate_suppressions'] += 1; counters['model_calls_avoided'] += 1
                    transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.DUPLICATE_SUPPRESSED),
                                            reason_codes=[*changes, duplicate], new_decision_id=None, new_state=None,
                                            model_call=False, safety=False, **base))
                    loop['tracked'][iid] = fingerprint
                    return
            if forced is None and not server_exit:
                if not usable or (window_left <= 0):
                    transitions.append(dict(instrument_id=iid, classification=str(blocked_class), reason_codes=[*changes, engine['reason'] or 'MODEL_CALL_CAP_REACHED'],
                                            new_decision_id=None, new_state=None, model_call=False, safety=stability['safety'], **base))
                    return
                if state['remaining'] <= 0 or state['action_calls'] >= policy['max_action_calls_per_cycle']:
                    transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.DEFERRED), reason_codes=[*changes, 'PER_CYCLE_CALL_CAP'],
                                            new_decision_id=None, new_state=None, model_call=False, safety=stability['safety'], **base))
                    return
            candidate = item['candidate']
            deadlines = [timestamp(e['valid_until']).timestamp() for e in (*candidate['current_market_evidence'], *candidate['reference_evidence']) if timestamp(e.get('valid_until'))]
            digest = input_hash_from_dict(dict(candidate=candidate, loop=loop['loop_id'], scheduled=scheduled, started=started))
            run = dict(schema_version=RUN_SCHEMA, run_id='RR-' + digest[:40], origin='REEVALUATION', state='CURRENT', decision_cutoff=now,
                       generated_at=now, scope=scope, input_hash=digest, source_run_id=loop['last_reduction_run_id'],
                       valid_until=_iso(min([timestamp(now).timestamp() + 1800, *deadlines])), evidence=[candidate],
                       candidates=[reevaluation_pick(candidate, int(loop['ranks'].get(iid, 0)))], limitations=[], simulated=False)
            actions.repository.put('candidate_run', run['run_id'], run)
            if forced is None and not server_exit:
                guard()
            try:
                decision = actions.run(dict(run_id=run['run_id'], instrument_id=iid), revalidation_reason=forced)
            except ValueError as exc:  # one instrument failing closed must not hide the others
                code = str(exc) if _CODE.fullmatch(str(exc)) else 'ACTION_EVALUATION_FAILED'
                transitions.append(dict(instrument_id=iid, classification=str(TransitionClass.REVALIDATION_REQUIRED), reason_codes=[*changes, code],
                                        new_decision_id=None, new_state=None, model_call=False, safety=stability['safety'], **base))
                return
            # A budget refusal returns before any network request and is not a model call.
            called = decision['cache'] == 'MISS' and 'latency_ms' in decision['model'] and 'PROVIDER_RATE_LIMIT' not in decision['blocker_codes']
            if called:
                state['model_calls'] += 1; state['action_calls'] += 1; state['remaining'] -= 1
            else:
                counters['model_calls_avoided'] += 1
            proposal = decision.get('model_proposal') or {}
            codes = [*changes, *stability['reason_codes'], *decision['blocker_codes']]
            if decision['cache'] == 'HIT':
                classification = TransitionClass.UNCHANGED
            elif (position['state'] == 'FLAT' and position['pending']) or (position['state'] != 'FLAT' and proposal.get('proposal_state') == 'ENTER'):
                classification = TransitionClass.DUPLICATE_SUPPRESSED; counters['duplicate_suppressions'] += 1
                codes.append('ENTRY_PATH_ALREADY_OCCUPIED')
            elif 'PROVIDER_RATE_LIMIT' in decision['blocker_codes']:
                classification = TransitionClass.BUDGET_BLOCKED
            elif decision['action_state'] == 'REVALIDATION_REQUIRED':
                classification = TransitionClass.REVALIDATION_REQUIRED
            elif 'POSITION_CHANGED' in changes:
                classification = TransitionClass.POSITION_CHANGED
            elif prior is None or prior['action_state'] != decision['action_state']:
                classification = TransitionClass.STATE_CHANGED
            else:
                classification = TransitionClass.MATERIAL_EVIDENCE_CHANGED
            if classification not in (TransitionClass.UNCHANGED, TransitionClass.DUPLICATE_SUPPRESSED, TransitionClass.BUDGET_BLOCKED):
                counters['accepted_transitions'] += 1
            transitions.append(dict(instrument_id=iid, classification=str(classification), reason_codes=list(dict.fromkeys(codes)),
                                    new_decision_id=decision['decision_id'], new_state=decision['action_state'], model_call=called,
                                    safety=stability['safety'], execution_readiness=decision['execution_readiness'], **base))
            loop['tracked'][iid] = fingerprint

        # 1. Existing positions first: HOLD/EXIT work is never starved by new candidates.
        for iid in watched:
            seen[iid] = started
            execute(plan(iid))
        # 2. Is there a new candidate? Re-reduce only on material intake change, rate limited.
        flat = dict(position=dict(state='FLAT', quantity=0, pending=False), candidate_valid_until=None)
        intake = {c['instrument']['instrument_id']: material_fingerprint(c, flat, now) for c in candidates}
        intake_changed = set(intake) != set(loop['intake']) or any(material_change(loop['intake'][i], intake[i], policy) for i in intake)
        if loop['last_reduction_epoch'] is None or intake_changed:
            if loop['last_reduction_epoch'] is not None and started - loop['last_reduction_epoch'] < policy['candidate_refresh_min_seconds']:
                reasons.append('CANDIDATE_REFRESH_DEFERRED')
            elif not usable or window_left <= 0:
                state['material'] += 1
                note(None, blocked_class, ['CANDIDATE_REDUCTION', engine['reason'] or 'MODEL_CALL_CAP_REACHED'])
            elif state['remaining'] <= 0:
                reasons.append('CANDIDATE_REFRESH_DEFERRED')
            else:
                state['material'] += 1
                guard()
                result = self.ai.run(scope, refresh_news=False)
                if result.get('cache') != 'HIT' and 'latency_ms' in result:
                    state['model_calls'] += 1; state['remaining'] -= 1
                loop.update(last_reduction_epoch=started, intake=intake, last_reduction_run_id=result.get('run_id'))
                if result.get('state') in ('CURRENT', 'NO_GROUNDED_CANDIDATES'):
                    chosen = [p['instrument_id'] for p in result.get('candidates', [])][:5]
                    for iid in chosen:
                        if iid not in loop['selected']:
                            note(iid, TransitionClass.CANDIDATE_ADDED, ['AI_SCREENER_SELECTED'], candidate_run_id=result.get('run_id'))
                    for iid in loop['selected']:
                        if iid not in chosen:
                            # History is preserved; only this loop's working baseline is dropped.
                            note(iid, TransitionClass.CANDIDATE_REMOVED, ['AI_SCREENER_NO_LONGER_SELECTED'], candidate_run_id=result.get('run_id'))
                            if iid not in held:
                                loop['tracked'].pop(iid, None)
                    loop['selected'] = chosen
                    loop['ranks'] = {p['instrument_id']: p['rank'] for p in result.get('candidates', [])[:5]}
                else:
                    reasons.append('CANDIDATE_REDUCTION_' + str(result.get('state')))
        # 3. Aged-out decisions, then materially new/changed selected candidates.
        plans = [plan(iid) for iid in loop['selected'] if iid not in held and iid in by_id]
        for item in sorted(plans, key=lambda p: 0 if p['reasons'] == ['DECISION_AGED_OUT'] else 1):
            execute(item)

        states = provider_states([by_id[i] for i in by_id], now=now, requested=loop['requested_cadence_seconds'])
        classes = {t['classification'] for t in transitions}
        status = CycleStatus.BUDGET_BLOCKED if TransitionClass.BUDGET_BLOCKED in classes else \
            CycleStatus.MODEL_UNAVAILABLE if TransitionClass.MODEL_UNAVAILABLE in classes else \
            CycleStatus.MATERIAL_CHANGE if state['material'] else CycleStatus.NO_MATERIAL_CHANGE
        receipt.update(position_count=len(held), candidate_count=len(loop['selected']), intake_count=len(candidates),
                       material_change_count=state['material'], unchanged_count=state['unchanged'],
                       model_call_count=state['model_calls'], provider_states=states,
                       readiness=cadence_readiness(states, ai_state=engine, cadence=loop['cadence']),
                       budget_state=dict(engine_state=engine['state'], engine_reason=engine['reason'], provider_budget=engine['budget'],
                                         calls_last_hour=hour + state['model_calls'], calls_last_day=day + state['model_calls'],
                                         max_per_cycle=policy['max_model_calls_per_cycle'], max_per_hour=policy['max_model_calls_per_hour'],
                                         max_per_day=policy['max_model_calls_per_day']),
                       cycle_status=str(status))
        return receipt


class ReevaluationWorker:
    """Schedule loop only. Slots are anchor + n*cadence; overruns skip, never overlap."""

    def __init__(self, service, loop_id, *, wait=None):
        self.service, self.loop_id = service, loop_id
        self.stop_event = threading.Event()
        self.wait = wait or self.stop_event.wait
        self.thread = None
        self.finished = False
        self.exit_reason = None
        self.slot, self.missed, self.overran, self.previous_session = None, 0, False, None

    def start(self):
        self.thread = threading.Thread(target=self.run, name='imp-reevaluation', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def alive(self):
        return not self.finished and not self.stop_event.is_set() and (self.thread is None or self.thread.is_alive())

    def run(self, max_cycles=None):
        service = self.service
        try:
            loop = service.repository.get_loop(self.loop_id)
            cadence, anchor, lease = loop['effective_cadence_seconds'], loop['anchor_epoch'], loop['policy']['lease_seconds']
            slot, missed, overran, previous, done = anchor if self.slot is None else self.slot, self.missed, self.overran, self.previous_session, 0
            while not self.stop_event.is_set() and (max_cycles is None or done < max_cycles):
                while not self.stop_event.is_set() and slot - service.clock() > 0:
                    self.wait(min(slot - service.clock(), lease / 3))
                    if not service.heartbeat(self.loop_id):
                        self.exit_reason = 'REEVALUATION_LEASE_LOST'
                        return
                if self.stop_event.is_set():
                    break
                now = service.clock()
                stalled = int((now - slot) // cadence)
                if stalled > 0:
                    # The runtime itself was not scheduling (suspend, starvation): unobserved, not reconstructed.
                    current = service.repository.get_loop(self.loop_id)
                    service.repository.put_cycle(service._gap(current, slot, slot + stalled * cadence, stalled, 'RUNTIME_STALLED'))
                    missed += stalled
                    slot += stalled * cadence
                session = service.session_state(loop['scope'], slot)
                trigger = ReevaluationTrigger.SESSION_START if previous not in (None, 'REGULAR') and session == 'REGULAR' else \
                    ReevaluationTrigger.SESSION_END if previous == 'REGULAR' and session != 'REGULAR' else ReevaluationTrigger.SCHEDULED_CADENCE
                previous = session
                if not service.heartbeat(self.loop_id):
                    self.exit_reason = 'REEVALUATION_LEASE_LOST'
                    return
                try:
                    service.evaluate_cycle(trigger, slot, missed=missed, overran=overran, loop_id=self.loop_id)
                    missed, overran = 0, False
                except ValueError as exc:
                    if str(exc) != 'CYCLE_IN_PROGRESS':
                        self.exit_reason = str(exc) if _CODE.fullmatch(str(exc)) else 'CYCLE_REJECTED'
                        return
                    missed += 1  # a manual cycle held the single cycle slot
                done += 1
                finished = service.clock()
                following = slot + cadence if finished <= slot + cadence else slot_at_or_after(anchor, cadence, finished)
                skipped = int(round((following - slot) / cadence)) - 1
                if skipped > 0:
                    missed += skipped
                    overran = True
                slot = following
                self.slot, self.missed, self.overran, self.previous_session = slot, missed, overran, previous
        except Exception as exc:  # the loop died: say so in liveness instead of looking merely idle
            try:
                current = service.repository.get_loop(self.loop_id)
                current['last_error'] = dict(at=_iso(service.clock()), code='WORKER_' + type(exc).__name__)
                service.repository.save_loop(current)
            except Exception:
                pass
            self.finished = True
        finally:
            self.finished = self.finished or max_cycles is None or self.stop_event.is_set() or self.exit_reason is not None


def reevaluation_service(store):
    service = getattr(store, '_reevaluation_service', None)
    if service is None:
        service = ReevaluationService(store)
        store._reevaluation_service = service
    return service
