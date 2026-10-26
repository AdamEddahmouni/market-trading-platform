"""AUTO-01 autonomous Paper operations controller.

One server-owned orchestration layer over authorities that already exist: the
Screener and its full-universe AI run, the OCT1-07 reevaluation cycle, the OCT1-06
Action Decision gate, the OCT1-08 stop monitor, and the canonical Paper
preview/risk/submit/ledger path. It adds no decision logic, no risk engine, no
simulator and no order route. What it adds is an owner policy, an explicit arming
record, a schedule, and an adapter that walks an already-gated Action Decision
through the same preview and submit the Workspace uses.

Paper only: every submission is refused unless the bound account is the internal
simulator's active Paper experiment. No broker or live route is imported here.
"""
from __future__ import annotations

from ..paper.contracts import quantity_number, quantity_wire

import copy
import json
import re
import sqlite3
import threading
import time
import traceback
import uuid
from contextvars import ContextVar
from decimal import Decimal
from datetime import UTC, datetime

from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.inference.paper_automation import (
    ARM_ACKNOWLEDGEMENT, AutomationStatus, IntentState, build_policy, decision_permitted, derive_status,
    entry_risk_blockers, exposure_minor, intent_identity, optional_fields, required_fields, should_run_universe,
    size_entry, spending_gate, universe_fingerprint, universe_material_change, universe_scopes,
    overnight_limits, sessions_held, select_overnight_carry,
)
from ..local_state.paper_automation import paper_automation_repository
from ..market_data.freshness_contract import timestamp
from ..market_sessions import ET, us_equity_session_label

CONTROLLER_SCHEMA = 'paper-automation-controller/1.0.0'
STATUS_SCHEMA = 'paper-automation-status/1.0.0'
HISTORY_SCHEMA = 'paper-automation-history/1.0.0'
REPORT_SCHEMA = 'paper-automation-report/1.0.0'
DRIVER = 'PAPER_AUTOMATION'
LEASE_SECONDS = 180
# Consecutive busy/locked shared-store errors outside a cycle's own accounting before the worker ends.
TRANSIENT_STORE_RETRIES = 5
LEASE_GRACE_SECONDS = 5  # a restarted process retries this long after its predecessor's lease expiry
# Unattended restart (owner decision 3, 2026-10-23). A startup refusal that time can clear -- another owner's lease
# or loop that will expire, a busy store -- is retried every STARTUP_RESUME_RETRY_SECONDS for at most
# STARTUP_RESUME_RETRY_LIMIT_SECONDS; every other refusal is final at once, as before.
STARTUP_RESUME_RETRY_SECONDS = 30
STARTUP_RESUME_RETRY_LIMIT_SECONDS = 900
TRANSIENT_RESUME_CODES = frozenset({'AUTOMATION_ALREADY_OWNED', 'REEVALUATION_LOOP_ALREADY_OWNED', 'OperationalError'})
# A worker that ends on its own while the owner still wants it running is started again in-process after
# WORKER_REVIVE_DELAY_SECONDS, at most WORKER_REVIVE_LIMIT times per WORKER_REVIVE_WINDOW_SECONDS.
WORKER_REVIVE_DELAY_SECONDS = 60
WORKER_REVIVE_LIMIT = 3
WORKER_REVIVE_WINDOW_SECONDS = 3600
CANDIDATE_QUOTE_CONSUMER = 'paper-automation-candidates'
_WORKING = ('ACTIVATED', 'WORKING', 'PARTIALLY_FILLED', 'REPLACE_PENDING', 'REPLACED')
_ENDED_UNFILLED = ('REJECTED', 'CANCELLED', 'EXPIRED', 'RISK_REJECTED')
# After an exit order ends without closing the position, the next exit order for that instrument waits
# cadence * 2^n, capped here. A new order always needs a new Action Decision; this only spaces them out.
EXIT_BACKOFF_CAP_SECONDS = 900
# Open equity positions are closed once this close to the regular-session bell (owner policy 2026-10-23).
OVERNIGHT_REVIEW_MINUTES = 45
EOD_MAX_ATTEMPTS = 6
EOD_FLATTEN_MINUTES = 10  # two 300 s cadence slots, so a slow cycle still lands inside the window
# After a full-universe run ends without adopting a selection, the next attempt waits cadence * 2^n, capped here.
# A run that fails for a lasting reason is not relaunched every cycle.
UNIVERSE_BACKOFF_CAP_SECONDS = 900
# Rolling slices (local engine): the first pass of a universe run ends at this fraction of the scope's minimum
# separation, so the slice, its comparison and the other scope's slice all fit one interval. A run that reaches
# every row inside that time is an ordinary complete run.
SLICE_FRACTION = 0.4
# Finished runs a scope keeps for its coverage epoch: their immutable ledger rows give each row's last evaluation.
EPOCH_RUNS_KEPT = 16
# A row too large to send alone has had its turn: it cannot be answered this epoch, and waiting on it would starve the rest.
REFUSED_AT_SEND = 'BATCH_FAILED:LOCAL_CONTEXT_EXCEEDED'
# An adopted selection is a hypothesis for this many separations; after that it is dropped, never acted on.
SELECTION_TTL_SEPARATIONS = 2
# The refusal reasons an unrunnable plan is recorded with: a plan over the owner's cap or the shared allowance.
UNIVERSE_BUDGET_REASONS = ('AUTONOMOUS_SPENDING_NOT_AUTHORIZED', 'AUTONOMOUS_SPENDING_LIMIT_REACHED',
                           'AUTONOMOUS_SPENDING_BUDGET_UNREADABLE', 'SYNTHESIS_DAILY_REQUEST_LIMIT',
                           'SYNTHESIS_DAILY_TOKEN_LIMIT', 'AI_COVERAGE_BUDGET_INSUFFICIENT')
_CODE = re.compile(r'[A-Z][A-Z0-9_]{2,79}')
# Evidence moved between the decision and the order: nothing is forced, the next cycle decides again.
_DEFER_CODES = ('ACTION_INPUT_CHANGED', 'ACTION_DECISION_EXPIRED', 'ACTION_HANDOFF_BLOCKED', 'CANDIDATE_EXPIRED',
                'LIVE_FEED_UNHEALTHY', 'LIVE_RUNTIME_UNAVAILABLE', 'LIVE_INTERNAL_SIMULATION_DEFERRED',
                'RESTORED_SESSION_AWAITING_FRESH_LIVE_HEALTH', 'PREVIEW_', 'ACTION_SOURCE_INVALID', 'REQUIRED_PRICE_MISSING')


def _iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z') if seconds is not None else None


def _utc_day(seconds):
    """The UTC calendar day an epoch falls in: the day the shared AI allowance rolls over on."""
    return datetime.fromtimestamp(float(seconds), UTC).date().isoformat() if seconds is not None else None


def _epoch(value, fallback):
    """An ISO instant as an epoch, or the fallback when it is absent or unparseable."""
    try:
        return timestamp(value).timestamp() if value else fallback
    except (TypeError, ValueError, OverflowError):
        return fallback


def _code(exc):
    text = str(exc).split(':', 1)[0].strip()
    return text if _CODE.fullmatch(text) else type(exc).__name__


def generation_of(controller):
    """The authorization generation a controller row -- or a cycle's own copy of one -- belongs to.

    A generation is exactly what the owner authorized together: the recorded arming and the run that arming
    started. A cycle may read, act on and write back state for its own generation only, so a cycle still in
    flight when the owner disarms, configures, re-arms and starts a different policy can neither act under the
    new authorization nor report over the new controller's state.
    """
    if not controller:
        return (None, None)
    return ((controller.get('arming') or {}).get('arming_id'), (controller.get('run') or {}).get('run_id'))


def market_session(epoch):
    """US regular-session facts from the existing label and the frozen holiday calendar. No date is guessed."""
    from ..intelligence.forward_qualification.evidence01.continuity import _DEFAULT_HOLIDAYS, is_trading_day
    moment = datetime.fromtimestamp(epoch, UTC).astimezone(ET)
    covered = {int(day[:4]) for day in _DEFAULT_HOLIDAYS}
    if moment.year not in covered:
        return dict(label='CALENDAR_UNAVAILABLE', trading_day=False, session_date=moment.date().isoformat(), minutes_to_close=None,
                    early_close_metadata='UNAVAILABLE')
    trading = is_trading_day(moment.date())
    label = us_equity_session_label(moment) if trading else 'CLOSED'
    minutes = 16 * 60 - (moment.hour * 60 + moment.minute) if label == 'REGULAR' else None
    # The canonical calendar has no early-close list; the regular 16:00 close is used and that is stated.
    return dict(label=label, trading_day=trading, session_date=moment.date().isoformat(), minutes_to_close=minutes,
                early_close_metadata='UNAVAILABLE')


def _automation_quantities(ledger):
    """Replay immutable fills into signed automation/manual ownership buckets.

    A reducing fill consumes its owner's bucket first. Any reversal remainder
    belongs to the fill's owner. No order or intent without a fill owns shares.
    """
    buckets = {}
    for event in ledger.events:
        if event.get('event_type') != 'FillRecorded':
            continue
        payload = event.get('payload') or {}
        fill = payload.get('fill') or {}
        order = ledger.lookup_order(str(payload.get('order_id') or '')) or {}
        iid = str(order.get('instrument_id') or fill.get('instrument_id') or '')
        if not iid:
            continue
        amount = quantity_number(fill.get('fill_quantity') or 0)
        delta = amount if order.get('side', fill.get('side')) == 'BUY' else -amount
        owner = 0 if str(order.get('client_order_id') or '').startswith('PAI-') else 1
        parts = buckets.setdefault(iid, [0, 0])
        total = sum(parts)
        if total and total * delta < 0:
            remaining = abs(delta)
            for index in (owner, 1 - owner):
                reduction = min(abs(parts[index]), remaining)
                parts[index] -= reduction if total > 0 else -reduction
                remaining -= reduction
            if remaining:
                parts[owner] = remaining if delta > 0 else -remaining
        else:
            parts[owner] += delta
    return {iid: parts[0] for iid, parts in buckets.items() if parts[0]}


class PaperAutomationService:
    def __init__(self, store, *, repository=None, reevaluation=None, runs=None, clock=time.time, owner_id=None,
                 session=market_session, provider_health=None, submit_lock=None, sleep=time.sleep):
        self.store = store
        self.sleep = sleep
        self.repository = repository or paper_automation_repository()
        self._reevaluation, self._runs = reevaluation, runs
        self.clock = clock
        self.owner_id = owner_id or uuid.uuid4().hex
        self.session = session
        self._provider_health = provider_health
        self._submit_lock = submit_lock
        self.cycle_lock = threading.Lock()
        self.control_lock = threading.RLock()
        self.worker = None
        self._revives = []
        self._scope_services = {}
        self._scope_context = ContextVar('paper_scope_' + self.owner_id, default=None)
        self._session_context = ContextVar('paper_session_' + self.owner_id, default=None)

    # --- collaborators (existing authorities) ---------------------------------------
    @property
    def reevaluation(self):
        scoped = self._scope_context.get()
        if scoped is not None:
            return scoped
        if self._reevaluation is None:
            from .screener_reevaluation import reevaluation_service
            self._reevaluation = reevaluation_service(self.store)
        return self._reevaluation

    def _trace_log_path(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[3] / '.local' / 'paper-automation-scope-errors.log'

    def _scoped_reevaluation(self, scope):
        """A bound loop per scope, sharing account authorities and inference budgets."""
        identity = input_hash_from_dict(scope)
        if identity not in self._scope_services:
            from .screener_reevaluation import ReevaluationService
            base = self.reevaluation
            self._scope_services[identity] = ReevaluationService(
                self.store, repository=base.repository, actions=base.actions, ai=base.ai,
                clock=self.clock, owner_id=self.owner_id + ':' + identity[:12], scope=scope)
        return self._scope_services[identity]

    def _scope_session(self, scope, epoch):
        universe = scope.get('universe')
        if universe in ('US_EQUITIES', 'US_ETFS'):
            return self.session(epoch)
        if universe == 'CRYPTO':
            return dict(label='CONTINUOUS', trading_day=True, session_date=datetime.fromtimestamp(epoch, UTC).astimezone(ET).date().isoformat(),
                        minutes_to_close=None, calendar='KRAKEN_SPOT_CONTINUOUS')
        return dict(label='REFERENCE_ONLY' if universe == 'BONDS' else 'PROVIDER_STATE_UNAVAILABLE', trading_day=False,
                    session_date=datetime.fromtimestamp(epoch, UTC).astimezone(ET).date().isoformat(), minutes_to_close=None)

    @property
    def actions(self):
        return self.reevaluation.actions

    @property
    def runs(self):
        if self._runs is None:
            from .screener_ai_runs import ai_screener_runs
            self._runs = ai_screener_runs()
        return self._runs

    def submit_lock(self):
        if self._submit_lock is None:
            from .server import LEDGER_ROUTE_LOCK  # the same lock the POST /paper/orders route holds
            self._submit_lock = LEDGER_ROUTE_LOCK
        return self._submit_lock

    def _account(self):
        return self.store.paper_ledger.paper_account_id

    def _controller(self):
        controller = self.repository.get_controller(self._account())
        if controller is None:
            raise ValueError('AUTOMATION_NOT_CONFIGURED')
        return controller

    def _event(self, kind, **payload):
        return self.repository.append_event(self._account(), kind, dict(payload, at_iso=_iso(self.clock())), now=self.clock())

    def _save(self, controller, *, fenced=False):
        controller['updated_epoch'] = self.clock()
        self.repository.save_controller(controller, owner_id=self.owner_id if fenced else None)

    # --- Paper-only identity ----------------------------------------------------------
    def paper_identity(self, policy=None):
        """Structural facts that must hold for any automated action. Each failure is a stable code.

        Checked at arm, at start, at every cycle and again immediately before every
        submission. A persisted authorization never substitutes for this check.
        """
        from ..operating_modes import broker_paper_execution_env_enabled, live_execution_env_enabled
        from . import paper_experiment
        ledger, reasons = self.store.paper_ledger, []
        if live_execution_env_enabled():
            reasons.append('LIVE_EXECUTION_ENVIRONMENT_ENABLED')
        if broker_paper_execution_env_enabled():
            reasons.append('BROKER_PAPER_ENVIRONMENT_ENABLED')
        if str(ledger.execution_mode) != 'INTERNAL_SIMULATION':
            reasons.append('EXECUTION_MODE_NOT_INTERNAL_SIMULATION')
        if str(ledger.execution_provider) != 'INTERNAL':
            reasons.append('EXECUTION_PROVIDER_NOT_INTERNAL')
        experiment = paper_experiment.active_experiment(self.store) if ledger.is_portfolio_scoped() else None
        if experiment is None:
            reasons.append('ACTIVE_PAPER_EXPERIMENT_REQUIRED')
        if policy is not None:
            if policy['account_id'] != ledger.paper_account_id or (experiment and policy['experiment_id'] != experiment['experiment_id']):
                reasons.append('AUTOMATION_ACCOUNT_MISMATCH')
            if policy['ledger_risk_policy_id'] != str(ledger.policy.get('risk_policy_identity_hash', '')):
                reasons.append('PAPER_RISK_POLICY_CHANGED')
        return reasons

    def provider_health(self, scope=None):
        if self._provider_health is not None:
            return self._provider_health()
        if scope and scope.get('universe') == 'CRYPTO':
            # The controller's usable crypto supply is the owner-authorized Kraken Spot source (IMP_CRYPTO_LIVE);
            # a verdict without it would strand the scope: candidate demand creation itself needs an admitted run.
            # The observed in-process stream runtime carries execution-grade forward detail (never a verdict).
            from ..crypto_market import kraken_stream
            runtime = kraken_stream._RUNTIME  # observe only; demand creation belongs to the candidate feed
            stream = dict(connection_state=None, last_received_ns=None, instruments={})
            if runtime is not None:
                with runtime._lock:
                    stream = dict(connection_state=str(runtime.lifecycle.connection_state),
                                  last_received_ns=runtime.lifecycle.last_received_ns,
                                  instruments={iid: len(runtime.state.trades_for(iid)) for iid, _cap in set(runtime._consumers)})
            from .screener_crypto import crypto_supply_health
            state, reasons, detail = crypto_supply_health()
            return dict(state=state, reasons=list(reasons), provider='KRAKEN', detail=dict(detail, stream=stream))
        if self.store.data_mode != 'LIVE_OBSERVATIONAL':
            return dict(state='NOT_LIVE', data_mode=str(self.store.data_mode), reasons=[])
        from ..market_data.live_runtime import get_live_runtime
        from ..market_data.provider_lifecycle import ProviderConnectionState
        runtime = get_live_runtime(create=False)
        if runtime is None:
            return dict(state='UNAVAILABLE', data_mode='LIVE_OBSERVATIONAL', reasons=['LIVE_RUNTIME_UNAVAILABLE'])
        state = runtime.lifecycle.connection_state
        bad = state in {ProviderConnectionState.DISCONNECTED, ProviderConnectionState.RECONNECTING,
                        ProviderConnectionState.ERROR, ProviderConnectionState.DISABLED}
        reasons = ['LIVE_FEED_UNHEALTHY'] if bad else []
        # Connected is not flowing: the data-flow watchdog judges by receipts (2026-10-19..22 read CONNECTED for hours).
        watchdog = getattr(runtime, 'feed_watchdog', None)
        if watchdog is not None and watchdog.state in {'SILENT', 'UNRECOVERABLE'}:
            bad = True
            reasons.append('LIVE_FEED_SILENT')
        return dict(state='UNHEALTHY' if bad else 'CONNECTED', data_mode='LIVE_OBSERVATIONAL', connection_state=str(getattr(state, 'value', state)),
                    reasons=reasons, quota=runtime.subscriptions.quota_report())

    # --- operator controls ---------------------------------------------------------------
    def configure(self, body):
        """Store one complete owner policy for the active Paper experiment. Arms nothing, starts nothing."""
        with self.control_lock:
            from . import paper_experiment
            ledger = self.store.paper_ledger
            experiment = paper_experiment.active_experiment(self.store) if ledger.is_portfolio_scoped() else None
            if experiment is None:
                raise ValueError('ACTIVE_PAPER_EXPERIMENT_REQUIRED')
            existing = self.repository.get_controller(self._account())
            if existing and existing.get('arming'):
                raise ValueError('AUTOMATION_ARMED_DISARM_FIRST')
            if not isinstance(body, dict) or not isinstance(body.get('scope'), dict):
                # Named with everything else that is missing, so the owner is asked once.
                build_policy(body if isinstance(body, dict) else None, account_id=ledger.paper_account_id,
                             experiment_id=experiment['experiment_id'], initial_capital_minor=experiment['initial_capital_minor'],
                             ledger_policy=ledger.policy)
            scope = self.reevaluation.ai._query(body['scope'])
            normalized = dict(body, scope=scope)
            if 'scopes' in body:
                normalized['scopes'] = [dict(item, scope=self.reevaluation.ai._query(item['scope'])) for item in body['scopes']]
            policy = build_policy(normalized, account_id=ledger.paper_account_id, experiment_id=experiment['experiment_id'],
                                  initial_capital_minor=experiment['initial_capital_minor'], ledger_policy=ledger.policy)
            now = self.clock()
            self.repository.put_policy(policy, now=now)
            controller = existing or dict(schema_version=CONTROLLER_SCHEMA, account_id=policy['account_id'], desired_state='STOPPED',
                                          clean_stop=True, run=None, last_cycle=None, last_error=None, consecutive_failures=0,
                                          cycle_count=0, day=None, universe=dict(active_run_id=None, last_started_epoch=None, last_result=None,
                                                                              adopted_run_id=None, adopted_at=None),
                                          subscriptions=[], last_scheduled_epoch=None, heartbeat_at=None, last_status=None)
            controller.update(policy_id=policy['policy_id'], experiment_id=policy['experiment_id'], arming=None, emergency=None,
                              desired_state='STOPPED')
            self._save(controller)
            self._event('POLICY_CONFIGURED', policy_id=policy['policy_id'])
            return self.status()

    def arm(self, body):
        """The owner's explicit, recorded authorization of one policy for one Paper account."""
        with self.control_lock:
            if not isinstance(body, dict) or set(body) - {'policy_id', 'acknowledgement', 'operator'} \
                    or body.get('acknowledgement') != ARM_ACKNOWLEDGEMENT or not isinstance(body.get('policy_id'), str):
                raise ValueError('AUTOMATION_ARM_ACKNOWLEDGEMENT_REQUIRED')
            operator = body.get('operator')
            if operator is not None and (not isinstance(operator, str) or len(operator) > 120):
                raise ValueError('AUTOMATION_ARM_ACKNOWLEDGEMENT_REQUIRED')
            controller = self._controller()
            if controller.get('emergency'):
                raise ValueError('AUTOMATION_EMERGENCY_STOPPED_DISARM_FIRST')
            if controller.get('arming'):
                raise ValueError('AUTOMATION_ALREADY_ARMED')
            if body['policy_id'] != controller['policy_id']:
                raise ValueError('AUTOMATION_POLICY_NOT_CURRENT')  # the owner arms exactly what is configured now
            policy = self.repository.get_policy(controller['policy_id'])
            reasons = self.paper_identity(policy)
            if reasons:
                raise ValueError(reasons[0])
            now = self.clock()
            controller['arming'] = dict(
                arming_id='PAA-' + input_hash_from_dict(dict(policy=policy['policy_id'], armed=now, nonce=uuid.uuid4().hex))[:32],
                policy_id=policy['policy_id'], account_id=policy['account_id'], experiment_id=policy['experiment_id'],
                armed_at=_iso(now), acknowledgement=ARM_ACKNOWLEDGEMENT, operator=operator, scope='INTERNAL_PAPER_SIMULATION_ONLY')
            self._save(controller)
            self._event('ARMED', policy_id=policy['policy_id'], arming_id=controller['arming']['arming_id'], operator=operator)
            return self.status()

    def disarm(self):
        with self.control_lock:
            controller = self._controller()
            self._halt(controller, reason='DISARMED')
            controller = self._controller()
            previous = (controller.get('arming') or {}).get('arming_id')
            controller.update(arming=None, emergency=None, desired_state='STOPPED')
            self._save(controller)
            self._event('DISARMED', arming_id=previous)
            return self.status()

    def start(self, *, threaded=True, wait=None):
        with self.control_lock:
            controller = self._controller()
            policy = self._armed_policy(controller)
            if self.worker and self.worker.alive():
                raise ValueError('AUTOMATION_ALREADY_RUNNING')
            reasons = self.paper_identity(policy)
            if reasons:
                raise ValueError(reasons[0])
            now = self.clock()
            self.repository.acquire_lease(controller['account_id'], self.owner_id, now=now, lease_seconds=LEASE_SECONDS)
            try:
                for item in universe_scopes(policy):
                    service = self._scoped_reevaluation(item['scope']) if policy.get('scopes') else self.reevaluation
                    service.attach_driver(DRIVER, scope=item['scope'], requested_cadence_seconds=policy['schedule']['cadence_seconds'])
            except Exception:
                for service in self._scope_services.values():
                    service.detach_driver()
                self.repository.release_lease(controller['account_id'], self.owner_id)
                raise
            controller = self._controller()
            last = controller.get('last_scheduled_epoch')
            if last is not None and not controller.get('clean_stop'):
                # Downtime stays downtime: one record, nothing evaluated or ordered for the missed period.
                cadence = policy['schedule']['cadence_seconds']
                self._event('NOT_OBSERVED', reason='PROCESS_DOWNTIME', observed_from=_iso(last), observed_to=_iso(now),
                            missed_scheduled_cycles=max(0, int((now - last) // cadence)), evaluations_backfilled=0, orders_backfilled=0)
            # A new run starts with no observed cycle of its own. The last cycle belongs to the generation that just
            # ended: leaving it in place would let a superseded generation's failure make the new run read as ERROR
            # and would mask the new run's own blockers. The history of those cycles stays in the audit events.
            controller.update(desired_state='RUNNING', clean_stop=False, heartbeat_at=now, last_error=None, last_cycle=None,
                              consecutive_failures=0,
                              run=dict(run_id='PAR-' + uuid.uuid4().hex[:24], started_at=_iso(now), policy_id=policy['policy_id'],
                                       arming_id=controller['arming']['arming_id'], owner_id=self.owner_id))
            self._save(controller, fenced=True)
            self._event('STARTED', run_id=controller['run']['run_id'], policy_id=policy['policy_id'])
            self.worker = AutomationWorker(self, controller['account_id'], cadence=policy['schedule']['cadence_seconds'], anchor=now, wait=wait)
            if threaded:
                self.worker.start()
            return self.status()

    def pause(self):
        return self._set_desired('PAUSED', 'PAUSED', ('RUNNING',))

    def resume(self):
        with self.control_lock:
            controller = self._controller()
            self._armed_policy(controller)
            if not (self.worker and self.worker.alive()):
                raise ValueError('AUTOMATION_NOT_RUNNING_START_FIRST')
        return self._set_desired('RUNNING', 'RESUMED', ('PAUSED',))

    def _set_desired(self, desired, kind, allowed):
        with self.control_lock:
            # The desired state changes under the submit lock, so a Pause or Resume cannot land between a
            # cycle's control re-read and the submission that follows it.
            with self.submit_lock():
                controller = self._controller()
                if controller['desired_state'] not in allowed:
                    raise ValueError('AUTOMATION_STATE_TRANSITION_INVALID')
                controller['desired_state'] = desired
                self._save(controller)
            self._event(kind)
            return self.status()

    def stop(self):
        with self.control_lock:
            controller = self._controller()
            self._halt(controller, reason='STOPPED')
            self._event('STOPPED')
            return self.status()

    def emergency_stop(self, body=None):
        """Latch first, then halt. Working automation orders are cancelled; positions are never liquidated."""
        with self.control_lock:
            reason = (body or {}).get('reason') if isinstance(body, dict) else None
            if reason is not None and (not isinstance(reason, str) or len(reason) > 200):
                raise ValueError('AUTOMATION_EMERGENCY_REASON_INVALID')
            controller = self._controller()
            controller['emergency'] = dict(at=_iso(self.clock()), reason=reason or 'OPERATOR_EMERGENCY_STOP', source='OPERATOR')
            controller['desired_state'] = 'STOPPED'
            self._save(controller)  # the latch is durable before anything else is attempted
            self._event('EMERGENCY_STOP', reason=controller['emergency']['reason'], source='OPERATOR')
            self._halt(self._controller(), reason='EMERGENCY_STOP')
            cancelled = self._cancel_working_orders('EMERGENCY_STOP')
            return dict(self.status(), cancelled_orders=cancelled)

    def _armed_policy(self, controller):
        if controller.get('emergency'):
            raise ValueError('AUTOMATION_EMERGENCY_STOPPED_DISARM_FIRST')
        if not controller.get('arming'):
            raise ValueError('AUTOMATION_NOT_ARMED')
        if controller['arming']['policy_id'] != controller['policy_id']:
            raise ValueError('AUTOMATION_POLICY_NOT_CURRENT')
        policy = self.repository.get_policy(controller['policy_id'])
        if policy is None:
            raise ValueError('AUTOMATION_POLICY_MISSING')
        return policy

    def _halt(self, controller, *, reason):
        """Stop scheduling, stop an AI run in progress, release the loop, the quotes and the lease."""
        if self.worker:
            self.worker.stop()
        states = [controller, *(controller.get('universes') or {}).values()]
        for state in states:
            universe = state.get('universe') or {}
            if universe.get('active_run_id') and universe.get('origin') == 'AUTOMATION':
                try:
                    self.runs.stop(controller['account_id'], universe['active_run_id'])
                except Exception:  # noqa: BLE001 - stopping never depends on the run tracker
                    pass
            self._release_candidate_quotes(state.get('subscriptions') or [])
        try:
            self.reevaluation.detach_driver()
            for service in self._scope_services.values():
                service.detach_driver()
        except Exception:  # noqa: BLE001
            pass
        self._release_candidate_quotes(controller.get('subscriptions') or [])
        # An in-flight cycle re-reads these control fields before every order and at its end. The flip happens
        # under the submit lock so a Stop, Disarm or Emergency Stop can never be overtaken by a submission that
        # has already passed its control re-read.
        with self.submit_lock():
            controller = self._controller()
            mine = controller.get('owner_id') in (None, self.owner_id)
            controller.update(desired_state='STOPPED', clean_stop=True if mine else controller.get('clean_stop'), subscriptions=[])
            self._save(controller)
        self.repository.release_lease(controller['account_id'], self.owner_id)
        self.worker = None

    def resume_on_startup(self, *, threaded=True):
        """After a restart: continue only a policy that was armed and running, and only if every check still passes.

        Nothing is replayed for the time the process was down, and a failed check leaves
        the controller stopped with the reason recorded; it is never worked around.
        """
        controller = self.repository.get_controller(self._account())
        if controller is None or not controller.get('arming'):
            return dict(resumed=False, reason='NOT_ARMED')
        if controller['desired_state'] != 'RUNNING':
            return dict(resumed=False, reason='NOT_RUNNING_BEFORE_RESTART')
        try:
            self.start(threaded=threaded)
        except (ValueError, sqlite3.OperationalError) as exc:
            code = _code(exc)
            if code not in TRANSIENT_RESUME_CODES:
                return self._refuse_resume(code)
            deadline = self.clock() + STARTUP_RESUME_RETRY_LIMIT_SECONDS
            remaining = (controller.get('lease_until') or 0) - self.clock()
            if code == 'AUTOMATION_ALREADY_OWNED' and 0 < remaining <= LEASE_SECONDS and controller.get('owner_id') != self.owner_id:
                # A restarted process meets its predecessor's unexpired lease (a stop does not run the predecessor's
                # cleanup). The contract is to wait that lease out, then take the same atomic start: a live owner
                # that keeps renewing still wins, and every start check is evaluated again at that time.
                wait, reason = remaining + LEASE_GRACE_SECONDS, 'WAITING_FOR_PREVIOUS_LEASE'
                self._event('STARTUP_RESUME_WAITING_FOR_LEASE', lease_until=_iso(controller['lease_until']),
                            wait_seconds=round(wait, 3))
            else:
                wait, reason = STARTUP_RESUME_RETRY_SECONDS, 'RETRYING'
                self._event('STARTUP_RESUME_RETRYING', reason=code, attempt=1, retry_in_seconds=wait,
                            gives_up_at=_iso(deadline))
            if threaded:
                threading.Thread(target=self._resume_after_lease, args=(wait, True, deadline),
                                 name='paper-automation-resume', daemon=True).start()
                return dict(resumed=False, reason=reason)
            return self._resume_after_lease(wait, False, deadline)
        self._event('STARTUP_RESUMED', run_id=self._controller()['run']['run_id'])
        return dict(resumed=True, reason=None)

    def _refuse_resume(self, code):
        self._event('STARTUP_RESUME_REFUSED', reason=code)
        with self.control_lock:
            fresh = self._controller()
            fresh['last_error'] = dict(at=_iso(self.clock()), code=code)
            self._save(fresh)
        return dict(resumed=False, reason=code)

    def _resume_after_lease(self, wait_seconds, threaded, deadline=None):
        """The retries after a refusal time can clear. Each re-reads everything; the last refusal is recorded."""
        attempt = 1
        while True:
            self.sleep(max(0.0, float(wait_seconds)))
            controller = self.repository.get_controller(self._account())
            if controller is None or not controller.get('arming') or controller['desired_state'] != 'RUNNING' or controller.get('emergency'):
                # The operator stopped, paused, disarmed or latched it while this process waited: nothing is resumed.
                reason = 'NOT_ARMED' if controller is None or not controller.get('arming') else 'NOT_RUNNING_BEFORE_RESTART'
                self._event('STARTUP_RESUME_REFUSED', reason=reason)
                return dict(resumed=False, reason=reason)
            if self.worker and self.worker.alive():
                return dict(resumed=True, reason=None)
            try:
                self.start(threaded=threaded)
            except (ValueError, sqlite3.OperationalError) as exc:
                code = _code(exc)
                if code in TRANSIENT_RESUME_CODES and deadline is not None and self.clock() + STARTUP_RESUME_RETRY_SECONDS <= deadline:
                    attempt += 1
                    wait_seconds = STARTUP_RESUME_RETRY_SECONDS
                    if attempt % 2 == 0:  # one record a minute, not one per attempt
                        self._event('STARTUP_RESUME_RETRYING', reason=code, attempt=attempt, retry_in_seconds=wait_seconds,
                                    gives_up_at=_iso(deadline))
                    continue
                return self._refuse_resume(code)
            self._event('STARTUP_RESUMED', run_id=self._controller()['run']['run_id'], after_lease_wait=True, attempts=attempt)
            return dict(resumed=True, reason=None)

    def _worker_ended(self, worker, *, threaded=True):
        """A worker ended on its own. While the owner still wants it running, record why and start it again.

        Never revived: a requested stop, a lost lease (another owner holds the account), an emergency latch, a
        controller that is no longer armed and running, or a fourth end inside the hour. Each revive is the
        ordinary start, so every start check is evaluated again and the downtime is recorded, not backfilled.
        """
        if worker is not self.worker or worker.stop_event.is_set():
            return None
        reason = worker.exit_reason or 'WORKER_ENDED'
        try:
            controller = self.repository.get_controller(self._account())
        except Exception:  # noqa: BLE001 - an unreadable store leaves the worker ended, as before
            return None
        if not controller or not controller.get('arming') or controller['desired_state'] != 'RUNNING' or controller.get('emergency'):
            return None
        self._event('WORKER_EXITED', reason=reason, run_id=(controller.get('run') or {}).get('run_id'))
        if reason == 'AUTOMATION_LEASE_LOST':
            return dict(revived=False, reason=reason)
        now = self.clock()
        self._revives = [at for at in self._revives if now - at < WORKER_REVIVE_WINDOW_SECONDS]
        if len(self._revives) >= WORKER_REVIVE_LIMIT:
            self._event('WORKER_REVIVE_BUDGET_SPENT', reason=reason, revives=len(self._revives),
                        window_seconds=WORKER_REVIVE_WINDOW_SECONDS)
            return dict(revived=False, reason='WORKER_REVIVE_BUDGET_SPENT')
        self._revives.append(now)
        if threaded:
            threading.Thread(target=self._revive_worker, args=(worker, reason, True),
                             name='paper-automation-revive', daemon=True).start()
            return dict(revived=None, reason='WORKER_REVIVE_SCHEDULED')
        return self._revive_worker(worker, reason, False)

    def _revive_worker(self, worker, reason, threaded):
        self.sleep(WORKER_REVIVE_DELAY_SECONDS)
        with self.control_lock:
            if self.worker is not worker:
                return dict(revived=False, reason='SUPERSEDED')  # the operator stopped or started it meanwhile
            controller = self.repository.get_controller(self._account())
            if not controller or not controller.get('arming') or controller['desired_state'] != 'RUNNING' or controller.get('emergency'):
                return dict(revived=False, reason='NOT_RUNNING_ANY_MORE')
            try:
                self.start(threaded=threaded)
            except (ValueError, sqlite3.OperationalError) as exc:
                self._event('WORKER_REVIVE_REFUSED', reason=_code(exc), exited_for=reason)
                return dict(revived=False, reason=_code(exc))
            self._event('WORKER_REVIVED', exited_for=reason, run_id=self._controller()['run']['run_id'])
            return dict(revived=True, reason=None)

    # --- the cycle --------------------------------------------------------------------------
    def run_cycle(self, *, scheduled=None, trigger='SCHEDULED_CADENCE', missed=0):
        """One unattended pass. Never overlaps itself; every refusal is recorded with its reason."""
        if not self.cycle_lock.acquire(blocking=False):
            raise ValueError('AUTOMATION_CYCLE_IN_PROGRESS')
        try:
            # The lease is renewed by the cycle itself, so a long cycle cannot be taken over half way through.
            if self._controller().get('owner_id') != self.owner_id or not self.heartbeat():
                raise ValueError('AUTOMATION_LEASE_LOST')
            controller = self._controller()
            now = self.clock()
            scheduled = now if scheduled is None else scheduled
            summary = dict(cycle_id='PAC-' + input_hash_from_dict(dict(account=controller['account_id'], scheduled=scheduled, started=now))[:32],
                           run_id=(controller.get('run') or {}).get('run_id'), trigger=trigger, scheduled_for=_iso(scheduled),
                           started_at=_iso(now), missed_cycles_before=missed, blockers=[], actions=[], session=None, provider=None,
                           reevaluation=None, universe=None, risk=None, error=None)
            if controller['desired_state'] != 'RUNNING' or controller.get('emergency') or not controller.get('arming'):
                summary['skipped'] = 'NOT_RUNNING'
                return summary
            policy = self.repository.get_policy(controller['policy_id'])
            work = dict(controller)
            try:
                self._cycle(work, policy, summary, now, scheduled, missed)
                work.update(consecutive_failures=0)
            except Exception as exc:  # a failed cycle is recorded, never silently retried
                code = _code(exc)
                summary['error'] = code
                work['consecutive_failures'] = int(work.get('consecutive_failures') or 0) + 1
                work['last_error'] = dict(at=_iso(now), code=code)
                if work['consecutive_failures'] >= policy['emergency_stop']['max_consecutive_failures']:
                    work['emergency'] = dict(at=_iso(self.clock()), reason='CONSECUTIVE_CYCLE_FAILURES', source='CONTROLLER', last_error=code)
            completed = self.clock()
            session = summary['session'] or {}
            status = derive_status(configured=True, armed=True, desired='RUNNING', emergency=bool(work.get('emergency')),
                                   error=bool(summary['error']), blockers=summary['blockers'],
                                   session_eligible=summary.get('session_eligible', session.get('label') in policy['schedule']['sessions']))
            summary.update(status=str(status), completed_at=_iso(completed), duration_ms=int(round((completed - now) * 1000)))
            # Operator commands issued while the cycle ran win; only cycle-owned fields are written back. The
            # control lock makes this read-modify-write atomic against a Pause, Stop, Disarm or Emergency Stop.
            with self.control_lock:
                fresh = self._controller()
                # A cycle may write back only while the controller is still the same authorization generation it
                # started under, still RUNNING and still leased here. An operator Stop or Pause during the cycle, a
                # Disarm/Configure/re-Arm/Start of a different policy, or a lost lease, all end this cycle's
                # authority to record cycle-owned state (in particular candidate quote subscriptions it may
                # already have released).
                superseded = (generation_of(fresh) != generation_of(work)
                              or fresh.get('desired_state') != 'RUNNING'
                              or fresh.get('owner_id') != self.owner_id)
                if not superseded:
                    for key in ('consecutive_failures', 'last_error', 'day', 'universe', 'universes', 'last_universe_started_epoch', 'subscriptions', 'exit_backoff', 'carry'):
                        fresh[key] = work.get(key)
                    if summary['error'] is None:
                        fresh['last_error'] = None
                    fresh.update(last_cycle=summary, last_scheduled_epoch=scheduled, cycle_count=int(fresh.get('cycle_count') or 0) + 1,
                                 heartbeat_at=completed)
                previous = fresh.get('last_status')
                if not superseded:
                    fresh['last_status'] = str(status)
                    if work.get('emergency') and not fresh.get('emergency'):
                        fresh.update(emergency=work['emergency'], desired_state='STOPPED')
                    self._save(fresh, fenced=fresh.get('owner_id') == self.owner_id)
                    self.heartbeat()  # a no-op when an operator Stop released the lease during the cycle
            if superseded:
                # This cycle's generation was replaced, stopped or lost while the cycle ran: its record is not
                # written over the new controller's state. If its own failures tripped the controller latch, that
                # latch must not stop the new generation, but it must not vanish silently either. It is recorded,
                # with the failure that caused it and the generation that replaced it, so the evidence survives and
                # the new run continues under its own authorization and its own failure count.
                summary['superseded'] = True
                if work.get('emergency'):
                    self._event('EMERGENCY_LATCH_SUPERSEDED', cycle_id=summary['cycle_id'], run_id=summary['run_id'],
                                reason=work['emergency'].get('reason'), last_error=work['emergency'].get('last_error'),
                                consecutive_failures=work.get('consecutive_failures'),
                                superseded_by_generation=dict(arming_id=generation_of(fresh)[0], run_id=generation_of(fresh)[1]))
                return summary
            if summary['actions'] or summary['error'] or previous != str(status):
                self._event('CYCLE', **{key: summary[key] for key in ('cycle_id', 'run_id', 'trigger', 'scheduled_for', 'status', 'error',
                                                                         'blockers', 'actions', 'session', 'missed_cycles_before')})
            if fresh.get('emergency') and fresh['emergency'].get('source') == 'CONTROLLER' and previous != str(AutomationStatus.EMERGENCY_STOPPED):
                self._event('EMERGENCY_STOP', reason=fresh['emergency']['reason'], source='CONTROLLER')
                if self.worker:
                    self.worker.stop()
            return summary
        finally:
            self.cycle_lock.release()

    def _block(self, summary, category, code):
        if not any(b['code'] == code for b in summary['blockers']):
            summary['blockers'].append(dict(category=category, code=code))

    def _cycle(self, work, policy, summary, now, scheduled, missed):
        if not policy.get('scopes'):
            return self._cycle_scope(work, policy, summary, now, scheduled, missed)
        for code in self.paper_identity(policy):
            self._block(summary, 'AUTHORITY', code)
        if summary['blockers']:
            return
        states = copy.deepcopy(work.get('universes') or {})
        primary = policy['scope']['universe']
        if primary not in states:
            states[primary] = {key: copy.deepcopy(work.get(key)) for key in ('universe', 'subscriptions', 'exit_backoff', 'last_cycle')}
        summary['universes'], summary['session_eligible'] = {}, False
        for item in universe_scopes(policy):
            universe = item['scope']['universe']
            state = states.setdefault(universe, {})
            scoped = dict(work, **state)
            # The day-start loss anchor and risk remain account-wide, independent of venue session boundaries.
            scoped['day'] = work.get('day')
            scoped['carry'] = work.get('carry')
            scoped['_global_universe_active'] = any((value.get('universe') or {}).get('active_run_id')
                                                    for key, value in states.items() if key != universe)
            scoped['_peer_waiting'] = self._peer_waiting(policy, states, universe, now)
            selected = dict(policy, scope=item['scope'], schedule=dict(policy['schedule'], sessions=item['sessions']))
            receipt = dict(actions=[], blockers=[], error=None, session=None, universe=None, provider=None)
            token = self._scope_context.set(self._scoped_reevaluation(item['scope']))
            session_token = self._session_context.set(self._scope_session(item['scope'], now))
            try:
                self._cycle_scope(scoped, selected, receipt, now, scheduled, missed)
                state.update(last_error=None, consecutive_failures=0)
            except Exception as exc:
                receipt['error'] = _code(exc)
                import pathlib as _pathlib
                with _pathlib.Path(self._trace_log_path()).open('a', encoding='utf-8') as _log:
                    _log.write('=== %s scope=%s failure=%s\n' % (_iso(now), item['scope'].get('universe'), receipt['error']))
                    _log.write(traceback.format_exc())
                self._block(receipt, 'DATA', receipt['error'])
                state['consecutive_failures'] = int(state.get('consecutive_failures') or 0) + 1
                state['last_error'] = dict(at=_iso(now), code=receipt['error'])
            finally:
                self._session_context.reset(session_token)
                self._scope_context.reset(token)
            for key in ('universe', 'subscriptions', 'exit_backoff'):
                state[key] = scoped.get(key)
            state['last_cycle'] = receipt
            work['day'] = scoped.get('day')
            work['carry'] = scoped.get('carry')
            started = (scoped.get('universe') or {}).get('last_started_epoch')
            if started is not None:
                work['last_universe_started_epoch'] = max(work.get('last_universe_started_epoch') or 0, started)
            summary['universes'][universe] = receipt
            summary['actions'].extend(receipt['actions'])
            if receipt.get('close_retry_pending'):
                summary['close_retry_pending'] = True
            eligible = (receipt.get('session') or {}).get('label') in item['sessions']
            summary['session_eligible'] |= eligible
            if eligible:
                for blocker in receipt['blockers']:
                    summary['blockers'].append(dict(blocker, universe=universe))
            if scoped.get('emergency'):
                work['emergency'] = scoped['emergency']
                break
        work['universes'] = states
        # Preserve the primary legacy projection; authoritative per-scope records are additive.
        work['universe'] = (states.get(primary) or {}).get('universe')
        summary['session'] = dict(label='MULTI_UNIVERSE', eligible=summary['session_eligible'])

    def _cycle_scope(self, work, policy, summary, now, scheduled, missed):
        for code in self.paper_identity(policy):
            self._block(summary, 'AUTHORITY', code)
        session = self._session_context.get() or self.session(now)
        summary['session'] = session
        if summary['blockers']:
            return  # the account is not the one that was armed: nothing is evaluated and nothing is ordered
        self._carry_rollover(work, session, now)
        self.actions.overnight_review = lambda iid: self._review_context(iid, work, policy)
        if session['label'] not in policy['schedule']['sessions']:
            after_close = session['label'] in ('AFTER_HOURS', 'POST_MARKET') or (
                session['label'] == 'CLOSED' and session.get('trading_day')
                and datetime.fromtimestamp(now, UTC).astimezone(ET).hour >= 16)
            if after_close:
                self._detect_unplanned_carry(work, session['session_date'])
            self._release_candidate_quotes(work.get('subscriptions') or [])
            work['subscriptions'] = []
            # Nothing is evaluated outside the session, so no data, risk or budget blocker can change. The blockers
            # the last evaluating cycle observed are carried, with the cycle that observed them, so a closed session
            # never hides a spending, data or risk block that will still be there at the open. Nothing is invented:
            # they are the previous cycle's own entries, and their provenance is reported with them.
            previous = work.get('last_cycle') or {}
            carried = previous.get('blockers') or []
            if carried:
                summary['blockers'].extend(blocker for blocker in carried if blocker not in summary['blockers'])
                summary['blockers_from_cycle_id'] = previous.get('blockers_from_cycle_id') or previous.get('cycle_id')
                summary['blockers_observed_at'] = previous.get('blockers_observed_at') or previous.get('completed_at')
            self._reconcile_universe_run(work, policy, summary, now)
            return
        from . import paper_projections
        paper_projections.maybe_release_execution_gate(self.store)  # the existing live-health gate; grants nothing on its own
        if not self.actions._authority():
            self._block(summary, 'AUTHORITY', 'PAPER_AUTHORITY_UNAVAILABLE')
        health = self.provider_health(policy['scope'])
        summary['provider'] = health
        for code in health.get('reasons') or []:
            self._block(summary, 'DATA', code)
        self._reconcile_working_orders(summary)
        ledger = self.store.paper_ledger
        valuation = ledger.project_valuation()
        if not work.get('day') or work['day'].get('session_date') != session['session_date']:
            # First cycle of the session date; a restart inside the day keeps the persisted value.
            previous_date = (work.get('day') or {}).get('session_date')
            if previous_date:
                # Shorts still open from the previous session were held over its close: one day's simulated borrow
                # fee each, idempotent per instrument and date. A no-op when the account does not allow shorts.
                for fee in ledger.accrue_short_borrow_fees(accrual_date=previous_date, as_of_ns=int(now * 1e9)):
                    self._event('SHORT_BORROW_FEE_ACCRUED', **fee['payload'])
                valuation = ledger.project_valuation()
            previous = work.get('day') or {}
            holding = any(p.get('quantity') for p in ledger.project_positions())
            anchor = previous.get('last_equity_minor') if holding and previous_date else valuation.get('equity_minor')
            basis = 'PREVIOUS_SESSION_LAST_CURRENT' if holding and previous_date else 'SESSION_FIRST_VALUATION'
            work['day'] = dict(session_date=session['session_date'], start_equity_minor=anchor,
                               captured_at=_iso(now), basis=basis)
            if anchor is None:
                self._block(summary, 'RISK', 'DAY_START_EQUITY_UNAVAILABLE')
            self._event('SESSION_ACTIVATED', session_date=session['session_date'], session=session['label'],
                        start_equity_minor=anchor, equity_basis=basis, valuation_quality=valuation['quality'])
        elif work['day'].get('start_equity_minor') is None and valuation['equity_minor'] is not None and work['day'].get('basis') != 'PREVIOUS_SESSION_LAST_CURRENT':
            work['day'].update(start_equity_minor=valuation['equity_minor'], captured_at=_iso(now))
        if valuation.get('quality') == 'CURRENT' and valuation.get('equity_minor') is not None:
            work['day']['last_equity_minor'] = valuation['equity_minor']
        self._close_carry_at_open(work, policy, summary, session, now)
        self._eod_flatten(work, policy, summary, session, now)
        self._maintenance_cover(work, policy, summary, session, now)
        self._prepare_overnight_reviews(work, policy, session, now, health)
        gate = dict(spending_gate(policy, self.reevaluation.engine_state()), kind='BUDGET')
        if not gate['allowed']:
            self._block(summary, 'BUDGET', gate['reason'])
        unhealthy = bool(health.get('reasons'))
        if unhealthy:
            # Unhealthy input withholds inference and AI orders; deterministic closes still use canonical price gates.
            # The deterministic part of the cycle still runs so held positions keep their stop monitor.
            gate = dict(allowed=False, reason=str(health['reasons'][0]), kind='DATA')
        self._universe(work, policy, summary, now, session, gate)
        self._candidate_quotes(work, summary)
        from ..intelligence.inference.reevaluation import ReevaluationTrigger
        # Action decisions are not withheld while a universe run is active: the local runtime admits one request at a
        # time, so a decision waits behind at most the batch in flight and is then measured on its own fresh evidence.
        model_gate = gate
        receipt = self.reevaluation.driven_cycle(ReevaluationTrigger.SCHEDULED_CADENCE, scheduled, missed=missed, model_gate=model_gate)
        summary['reevaluation'] = dict(cycle_id=receipt['cycle_id'], cycle_status=receipt['cycle_status'], reason_codes=receipt['reason_codes'][:12],
                                       position_count=receipt['position_count'], candidate_count=receipt['candidate_count'],
                                       model_call_count=receipt['model_call_count'], candidate_source=receipt.get('candidate_source'),
                                       readiness=(receipt.get('readiness') or {}).get('readiness'))
        if receipt['cycle_status'] in ('REEVALUATION_BLOCKED', 'FAILED'):
            self._block(summary, 'DATA', (receipt['reason_codes'] or ['REEVALUATION_FAILED'])[0])
        if (receipt.get('readiness') or {}).get('readiness') == 'REEVALUATION_BLOCKED' and 'QUOTE_STALE_OR_UNAVAILABLE' in receipt['readiness']['reason_codes']:
            self._block(summary, 'DATA', 'QUOTE_STALE_OR_UNAVAILABLE')
        if unhealthy:
            summary['execution'] = 'WITHHELD_PROVIDER_UNHEALTHY'
            return
        self._execute_pending(work, policy, summary, session)

    # --- full-universe AI evaluation -----------------------------------------------------------
    def _remaining_allowance(self, policy, engine):
        """The tighter of the owner's cap and the shared allowance, minus what is already used or held."""
        if engine.get('runtime') == 'LOCAL_MODEL' or not engine.get('budget'):
            return None
        budget, ai = engine['budget'], policy['ai']
        return dict(requests=max(0, min(ai['max_paid_requests_per_day'], int(budget['max_requests'])) - int(budget['requests']) - int(budget.get('held_requests') or 0)),
                    tokens=max(0, min(ai['max_paid_tokens_per_day'], int(budget['max_tokens'])) - int(budget['tokens']) - int(budget.get('held_tokens') or 0)))

    def _universe_runs_today(self, now):
        """How many full-universe runs this controller has started inside the current UTC day."""
        today = _utc_day(now)
        events = self.repository.events(self._account(), limit=200, kinds=['UNIVERSE_RUN_STARTED'])
        return sum(1 for event in events if _utc_day(event.get('at')) == today)

    def _universe_feasibility(self, policy, universe, engine):
        """Whether a run of the last known plan size still fits today's remaining allowance.

        The requirement predicted is the last complete run's own plan. With no such run there is nothing to
        predict, and the authoritative check stays where it belongs: the coverage method refuses an infeasible
        plan before it holds anything or calls a model.
        """
        required = (universe.get('last_result') or {}).get('required') or {}
        available = self._remaining_allowance(policy, engine)
        if available is None or not required.get('requests') or not required.get('tokens'):
            return None
        return dict(feasible=int(required['requests']) <= available['requests'] and int(required['tokens']) <= available['tokens'],
                    required_requests=int(required['requests']), required_tokens=int(required['tokens']),
                    available_requests=available['requests'], available_tokens=available['tokens'])

    def _universe_facts(self, policy, universe, *, now, session, gate, engine):
        """Every fact the adaptive decision reads, and the fingerprint the selection it would produce is valid for.

        The current row count is not read here: the controller does not query the Screener just to decide whether
        to query the Screener, so an unobserved count stays ``None`` and never reports membership movement.
        """
        fingerprint = universe_fingerprint(scope_hash=input_hash_from_dict(policy['scope']), session_date=session.get('session_date'))
        failure = universe.get('failure') or {}
        facts = dict(
            now=now, schedule=policy['schedule'], sessions=policy['schedule']['sessions'], session_label=session.get('label'),
            active_run_id=universe.get('active_run_id'), last_started_epoch=universe.get('last_started_epoch'),
            last_complete=universe.get('last_complete'),
            material_change=universe_material_change(universe.get('last_complete_fingerprint'), fingerprint),
            provider_gate=dict(gate, kind=gate.get('kind') or ('BUDGET' if gate.get('reason') in UNIVERSE_BUDGET_REASONS else 'DATA')),
            runs_today=dict(started=self._universe_runs_today(now)), feasibility=self._universe_feasibility(policy, universe, engine),
            backoff_until=failure.get('backoff_until'), consecutive_failures=failure.get('count'), last_failure_code=failure.get('code'))
        return facts, fingerprint

    def _peer_waiting(self, policy, states, universe, now):
        """True when another scope, inside its own session, waited on the shared run slot at its latest cycle and
        last started before this one did: this scope then yields one cycle so it cannot take the freed slot first.

        Scopes run in policy order and each closes only its own run handle, so the cycle in which a run finishes
        shows that run to every scope evaluated before its owner. Without this, a continuous scope whose slice
        outlasts the minimum separation restarts in that same cycle and a session-limited peer never gets a turn.
        A peer's decision older than two cadences, or a peer outside its session, never makes anyone wait.
        """
        mine = (states.get(universe, {}).get('universe') or {}).get('last_started_epoch') or 0
        horizon = 2 * int(policy['schedule'].get('cadence_seconds') or 300)
        for item in universe_scopes(policy):
            peer = item['scope']['universe']
            if peer == universe:
                continue
            state = states.get(peer, {}).get('universe') or {}
            decision = state.get('last_decision') or {}
            if decision.get('decision') != 'DEFER' or (decision.get('detail') or {}).get('run_id') != 'SHARED_ACCOUNT_RUN_ACTIVE':
                continue
            try:
                decided = datetime.fromisoformat(str(decision.get('at_iso')).replace('Z', '+00:00')).timestamp()
            except ValueError:
                continue
            if now - decided > horizon or (state.get('last_started_epoch') or 0) >= mine:
                continue
            if self._scope_session(item['scope'], now).get('label') in item['sessions']:
                return True
        return False

    def _reconcile_universe_run(self, work, policy, summary, now):
        """Close this scope's run handle once its run has finished or its owner is gone; a running run keeps it.

        Runs outside the scope's session too: another scope reads this handle as the shared account's active run,
        so a finished run must not keep it after the close. Nothing is started, evaluated or ordered here.
        """
        universe = dict(work.get('universe') or {})
        active = universe.get('active_run_id')
        if active:
            snapshot = self.runs.read(work['account_id'], active)
            if snapshot is None:
                # The process that owned the run is gone. The run tracker closes it INTERRUPTED on its next write.
                universe.update(active_run_id=None, last_result=dict(run_id=active, status='INTERRUPTED', reason='SERVER_RESTARTED_DURING_RUN',
                                                                     coverage_complete=False, adopted=False, finished_at=_iso(now)))
                self._event('UNIVERSE_RUN_INTERRUPTED', run_id=active)
            elif snapshot['state'] == 'RUNNING':
                summary['universe'] = dict(state='RUNNING', run_id=active, stage=snapshot.get('stage'), progress=snapshot.get('progress'))
            else:
                universe.update(active_run_id=None, last_result=self._finish_universe(snapshot, universe, now=now, policy=policy))
        work['universe'] = universe
        return universe

    def _universe(self, work, policy, summary, now, session, gate):
        """One adaptive scheduling decision, then at most one run. Never a fixed timer dressed up as one."""
        universe = self._reconcile_universe_run(work, policy, summary, now)
        account = work['account_id']
        result = universe.get('last_result') or {}
        if result.get('status') == 'AI_COVERAGE_BUDGET_INSUFFICIENT':
            self._block(summary, 'BUDGET', 'AI_COVERAGE_BUDGET_INSUFFICIENT')
        engine = self.reevaluation.engine_state()
        facts, fingerprint = self._universe_facts(policy, universe, now=now, session=session, gate=gate, engine=engine)
        if work.get('_global_universe_active'):
            facts['active_run_id'] = 'SHARED_ACCOUNT_RUN_ACTIVE'
        decision = should_run_universe(facts)
        if decision['decision'] == 'RUN' and work.get('_peer_waiting'):
            # Only a run yields: a block or deferral keeps its own reason.
            decision = dict(decision='DEFER', reason_codes=['UNIVERSE_PEER_WAITING'], next_eligible_epoch=None,
                            detail=dict(run_id='SHARED_ACCOUNT_PEER_WAITING'))
        previous = universe.get('last_decision') or {}
        universe['last_decision'] = dict(decision, at_iso=_iso(now), next_eligible_iso=_iso(decision['next_eligible_epoch']))
        if decision['decision'] == 'RUN' and not universe.get('active_run_id') and gate['allowed']:
            limit = self._remaining_allowance(policy, engine)
            slice_plan = self._slice_plan(universe, policy, now, engine)
            started = self.runs.start(account, policy['scope'], spend_limit=limit, origin='AUTOMATION',
                                      **({'slice_plan': slice_plan} if slice_plan else {}))
            universe.update(active_run_id=started['run_id'], last_started_epoch=now, withheld=None, run_fingerprint=fingerprint,
                            origin='OPERATOR' if started.get('joined') else 'AUTOMATION')
            self._event('UNIVERSE_RUN_STARTED', run_id=started['run_id'], joined=bool(started.get('joined')), spend_limit=limit,
                        engine=started.get('engine'), decision='RUN', reason_codes=decision['reason_codes'],
                        slice=None if not slice_plan else dict(epoch=slice_plan['epoch'], deadline=_iso(slice_plan['deadline_epoch']),
                                                               rows_with_prior_evaluation=len(slice_plan['last_evaluated'])))
            summary['universe'] = dict(state='STARTED', run_id=started['run_id'])
        elif decision['decision'] != 'RUN':
            kind = {'DEFER': 'UNIVERSE_RUN_DEFERRED', 'SKIP': 'UNIVERSE_RUN_SKIPPED', 'BLOCK': 'UNIVERSE_RUN_BLOCKED'}[decision['decision']]
            if not gate['allowed']:
                # The gate refused, so no run starts whatever the schedule says; the refusal keeps its reason.
                universe['withheld'] = dict(at=_iso(now), reason=gate['reason'])
            if (previous.get('decision'), tuple(previous.get('reason_codes') or ())) != (decision['decision'], tuple(decision['reason_codes'])):
                # One receipt per change of decision, not one per cycle: the audit stays readable and bounded.
                self._event(kind, **{key: value for key, value in decision.items() if key != 'detail'},
                            next_eligible_iso=_iso(decision['next_eligible_epoch']), **decision['detail'])
            if decision['decision'] == 'BLOCK':
                category = 'BUDGET' if decision['detail'].get('gate') == 'DAILY_ALLOWANCE' else 'DATA'
                self._block(summary, category, decision['reason_codes'][0])
        if summary.get('universe') is None:
            summary['universe'] = dict(state='IDLE', last_result=universe.get('last_result'), withheld=universe.get('withheld'),
                                       decision=decision, next_due=_iso(decision['next_eligible_epoch']))
        work['universe'] = universe

    def _slice_plan(self, universe, policy, now, engine):
        """A rolling slice for the local engine: a first-pass deadline and each row's last evaluation. None otherwise."""
        if engine.get('runtime') != 'LOCAL_MODEL':
            return None
        epoch = universe.get('epoch') or dict(number=1, started_at=_iso(now), started_epoch=now, completed=0, runs=[])
        universe['epoch'] = epoch
        separation = int(policy['schedule']['universe_evaluation_interval_seconds'])
        return dict(deadline_epoch=now + separation * SLICE_FRACTION, epoch=epoch['number'], last_evaluated=self._last_evaluated(epoch),
                    last_turn=self._last_evaluated(epoch, turns=True))

    def _row_records(self, run_id):
        records = getattr(self.runs, 'row_records', None)
        if callable(records):
            return records(run_id)
        outcomes = getattr(self.runs, 'row_outcomes', None)
        return {key: (name, []) for key, name in (outcomes(run_id) if callable(outcomes) else {}).items()}

    @staticmethod
    def _had_turn(name, reasons):
        """The model answered (accepted or rejected), or the row alone could not be sent. A row merely not reached
        (deferred, stopped) has not had its turn."""
        return name in ('AI_EVALUATED', 'AI_REJECTED') or name == 'UNPROCESSED' and REFUSED_AT_SEND in reasons

    def _last_evaluated(self, epoch, *, turns=False):
        """Instrument id -> when its most recent kept run evaluated it (or, with ``turns``, gave it its turn), from
        those runs' immutable ledger rows."""
        last = {}
        for item in epoch.get('runs') or []:
            for key, (name, reasons) in self._row_records(item['run_id']).items():
                if name == 'AI_EVALUATED' or turns and self._had_turn(name, reasons):
                    last[key] = float(item['evaluated_epoch'])
        return last

    def _advance_epoch(self, universe, record, now):
        """Add a finished run to the scope's coverage epoch; the epoch completes when every row this run found
        eligible has had its turn since the epoch began. A row the validator keeps rejecting, or one too large to
        send, would otherwise hold the epoch open for ever and head every slice. The report keeps evaluated and
        turns apart. Returns what the receipt reports."""
        epoch = universe.get('epoch')
        if epoch is None:
            return None
        # A row this run evaluated was evaluated no earlier than the run started, on this controller's clock.
        evaluated_at = float(universe.get('last_started_epoch') or now)
        epoch['runs'] = [*(epoch.get('runs') or []), dict(run_id=record['run_id'], evaluated_epoch=evaluated_at)][-EPOCH_RUNS_KEPT:]
        rows = self._row_records(record['run_id'])
        eligible = [key for key, (name, _) in rows.items() if name in ('AI_EVALUATED', 'AI_REJECTED', 'UNPROCESSED', 'ELIGIBLE')]
        start = float(epoch['started_epoch'])
        last, turns = self._last_evaluated(epoch), self._last_evaluated(epoch, turns=True)
        evaluated = sum(1 for key in eligible if last.get(key, -1.0) >= start)
        taken = sum(1 for key in eligible if turns.get(key, -1.0) >= start)
        report = dict(number=epoch['number'], eligible=len(eligible), evaluated_in_epoch=evaluated, turns_in_epoch=taken,
                      completed=epoch.get('completed', 0))
        if eligible and taken == len(eligible):
            epoch.update(number=epoch['number'] + 1, started_epoch=now, started_at=_iso(now), completed=int(epoch.get('completed') or 0) + 1,
                         last_completed_at=_iso(now))
            report.update(epoch_completed=True, completed=epoch['completed'])
            self._event('UNIVERSE_EPOCH_COMPLETED', number=report['number'], eligible=report['eligible'], evaluated=evaluated,
                        turns=taken, run_id=record['run_id'])
        return report

    def _finish_universe(self, snapshot, universe, *, now, policy):
        """Record what the run really covered. Only a complete selection is adopted; a partial one never is."""
        result = snapshot.get('result') or {}
        coverage = result.get('universe_coverage') or {}
        error = (snapshot.get('error') or {}).get('code')
        record = dict(run_id=snapshot['run_id'], status=coverage.get('status') or ('FAILED' if error else snapshot['state']),
                      reason=coverage.get('reason') or error, finished_at=snapshot.get('finished_at'),
                      universe_count=coverage.get('universe_count'), eligible_count=coverage.get('eligible_count'),
                      ai_evaluated_count=coverage.get('ai_evaluated_count'), ai_coverage_pct=coverage.get('ai_coverage_pct'),
                      coverage_complete=bool(coverage.get('coverage_complete')), selection_complete=bool(coverage.get('selection_complete')),
                      selected=[p['instrument_id'] for p in result.get('candidates', [])], provisional_count=len(result.get('provisional') or []),
                      model=dict(provider_id=result.get('provider_id'), model_id=result.get('model_id'), runtime=result.get('runtime')),
                      tokens_input=(coverage.get('budget') or {}).get('tokens_input'),
                      tokens_output=(coverage.get('budget') or {}).get('tokens_output'),
                      model_calls=coverage.get('model_calls'), candidate_run_id=result.get('run_id') if result.get('candidates') else None,
                      required=(coverage.get('plan') or {}).get('required'), adopted=False,
                      slice_complete=bool(coverage.get('slice_complete')), slice=coverage.get('slice'),
                      ai_rejected_count=coverage.get('ai_rejected_count'))
        record['epoch'] = self._advance_epoch(universe, record, now)
        complete = record['coverage_complete'] and record['selection_complete']
        if complete or (record['slice_complete'] and record['status'] == 'SLICE_SELECTION_COMPLETE'):
            try:
                ttl = SELECTION_TTL_SEPARATIONS * int(policy['schedule']['universe_evaluation_interval_seconds'])
                self.reevaluation.adopt_selection(result, ttl_seconds=ttl)
                record['adopted'] = True
                universe.update(adopted_run_id=result.get('run_id'), adopted_at=record['finished_at'])
                universe.pop('failure', None)
            except ValueError as exc:
                record['adoption_refused'] = _code(exc)
        if complete and record['adopted']:
            # The selection is only valid for the inputs it was produced from, so the fingerprint observed when
            # the run started becomes the baseline the next decision compares against.
            universe.update(last_complete=dict(run_id=record['run_id'], finished_at_epoch=min(_epoch(record['finished_at'], now), now),
                                               finished_at=record['finished_at'], universe_count=record['universe_count'],
                                               candidate_run_id=record['candidate_run_id']),
                            last_complete_fingerprint=universe.get('run_fingerprint'))
        elif record['slice_complete']:
            # A finished slice is the method working as designed; the next slice starts after the separation.
            universe.pop('failure', None)
        elif not complete:
            # A partial, failed, stopped or interrupted run is not retried every cycle: it backs off.
            failure = universe.get('failure') or {}
            count = int(failure.get('count') or 0) + 1
            delay = min(policy['schedule']['cadence_seconds'] * 2 ** (count - 1), UNIVERSE_BACKOFF_CAP_SECONDS)
            universe['failure'] = dict(count=count, code=record['reason'] or record['status'], backoff_until=now + delay)
        self._event('UNIVERSE_RUN_FINISHED', **record)
        return record

    def _crypto_stream_runtime(self, *, create):
        """The CRYPTO scope's own in-process Kraken Spot evidence stream.

        Kraken Spot is public and unauthenticated, but persistence stays one-owner: when this process holds the
        canonical kraken collector writer, only the existing runtime (if any) is observed, never a second
        collector stream. With no local kraken writer the controller may create demand for the pairs it owns.
        """
        from ..market_data.persistence import active_writer
        from ..crypto_market import kraken_stream
        if not create:
            return kraken_stream._RUNTIME
        writer = active_writer()
        if writer is not None and 'kraken' in writer.sources:
            return kraken_stream._RUNTIME
        from ..crypto_market.kraken_stream import kraken_stream_runtime
        from .screener_crypto import _stream_pair
        return kraken_stream_runtime(_stream_pair)

    # --- server-owned candidate quotes ----------------------------------------------------------
    def _candidate_quotes(self, work, summary):
        """Selected candidates keep a quote without any browser window. Held instruments are already owned by the loop."""
        universe = (self.reevaluation.bound_scope or {}).get('universe')
        if self.store.data_mode != 'LIVE_OBSERVATIONAL' or universe not in (None, 'US_EQUITIES', 'US_ETFS', 'CRYPTO'):
            return
        if universe == 'CRYPTO':
            self._crypto_candidate_quotes(work, summary)
            return
        from ..market_data.live_runtime import get_live_runtime
        runtime = get_live_runtime(create=False)
        if runtime is None:
            return
        loop = self.reevaluation._loop() or {}
        wanted = [*(loop.get('selected') or []), *((loop.get('pending_selection') or {}).get('chosen') or [])]
        wanted = list(dict.fromkeys(wanted))[:10]
        current = list(work.get('subscriptions') or [])
        self._release_candidate_quotes([iid for iid in current if iid not in wanted])
        kept = [iid for iid in current if iid in wanted]
        for iid in [i for i in wanted if i not in kept]:
            try:
                results = runtime.subscribe(instrument_id=iid, capabilities=['BASIC_QUOTE'], consumer_id=CANDIDATE_QUOTE_CONSUMER)
            except Exception:  # noqa: BLE001 - a failed subscribe leaves that candidate without a current quote
                results = [dict(accepted=False, reason='SUBSCRIBE_FAILED')]
            if all(r.get('accepted') for r in results):
                kept.append(iid)
            else:
                # Vendor quota or entitlement: recorded, never worked around. The candidate stays unquoted.
                summary.setdefault('quote_refusals', []).append(dict(instrument_id=iid, reason=str(results[0].get('reason'))))
        work['subscriptions'] = kept

    def _crypto_candidate_quotes(self, work, summary):
        """Crypto candidates subscribe the controller's own Kraken Spot evidence stream (BOOK+TRADES)."""
        runtime = self._crypto_stream_runtime(create=True)
        if runtime is None:
            summary.setdefault('quote_refusals', []).append(dict(universe='CRYPTO', reason='CRYPTO_RUNTIME_UNAVAILABLE'))
            return
        loop = self.reevaluation._loop() or {}
        wanted = [*(loop.get('selected') or []), *((loop.get('pending_selection') or {}).get('chosen') or [])]
        wanted = list(dict.fromkeys(wanted))[:10]
        current = list(work.get('subscriptions') or [])
        self._release_candidate_quotes([iid for iid in current if iid not in wanted])
        kept = [iid for iid in current if iid in wanted]
        for iid in [i for i in wanted if i not in kept]:
            try:
                results = runtime.subscribe(instrument_id=iid, capabilities=['BOOK', 'TRADES'], consumer_id=CANDIDATE_QUOTE_CONSUMER)
            except Exception:  # noqa: BLE001 - a failed subscribe leaves that candidate without a current quote
                results = [dict(accepted=False, reason='SUBSCRIBE_FAILED')]
            if all(r.get('accepted') for r in results):
                kept.append(iid)
            else:
                # Venue refusal or unresolvable pair: recorded, never worked around. The candidate stays unquoted.
                summary.setdefault('quote_refusals', []).append(dict(universe='CRYPTO', instrument_id=iid, reason=str(results[0].get('reason'))))
        work['subscriptions'] = kept

    def _release_candidate_quotes(self, instruments):
        if not instruments or self.store.data_mode != 'LIVE_OBSERVATIONAL':
            return
        if (self.reevaluation.bound_scope or {}).get('universe') == 'CRYPTO':
            runtime = self._crypto_stream_runtime(create=False)
            if runtime is None:
                return
            for iid in instruments:
                try:
                    runtime.unsubscribe(instrument_id=iid, capabilities=['BOOK', 'TRADES'], consumer_id=CANDIDATE_QUOTE_CONSUMER)
                except Exception:  # noqa: BLE001
                    pass
            return
        from ..market_data.live_runtime import get_live_runtime
        runtime = get_live_runtime(create=False)
        for iid in instruments if runtime is not None else []:
            try:
                runtime.unsubscribe(instrument_id=iid, capabilities=['BASIC_QUOTE'], consumer_id=CANDIDATE_QUOTE_CONSUMER)
            except Exception:  # noqa: BLE001
                pass

    # --- Paper automation adapter -----------------------------------------------------------------
    def _still_permitted(self, work):
        """Re-read immediately before any order: Pause, Stop, Emergency Stop and Disarm take effect at once.

        The run and the arming must be the ones this cycle started under, so a cycle still in flight when the
        owner disarms and arms a different policy can never place an order under the new authorization.
        """
        controller = self._controller()
        arming_id = (controller.get('arming') or {}).get('arming_id')
        run_id = (controller.get('run') or {}).get('run_id')
        work_arming = (work.get('arming') or {}).get('arming_id')
        work_run = (work.get('run') or {}).get('run_id')
        # Spelled out rather than chained, so the arming and run fences never depend on comparison parsing.
        return (controller['desired_state'] == 'RUNNING' and not controller.get('emergency')
                and work_arming is not None and arming_id == work_arming
                and work_run is not None and run_id == work_run
                and controller.get('owner_id') == self.owner_id and self.heartbeat())

    def _execute_pending(self, work, policy, summary, session):
        ledger = self.store.paper_ledger
        now = _iso(self.clock())
        loop = self.reevaluation._loop() or {}
        positions = [p for p in ledger.project_positions() if p.get('quantity')]
        held = [p['instrument_id'] for p in positions]
        queue = []
        for iid in dict.fromkeys([*held, *(loop.get('selected') or [])]):
            history = self.actions.history(iid)
            latest = history[0] if history else None
            if not latest or latest['action_state'] not in ('ENTER', 'EXIT') or timestamp(latest['valid_until']) <= timestamp(now):
                continue
            queue.append(latest)
        valuation = ledger.project_valuation()
        day = work.get('day') or {}
        summary['risk'] = self.risk_utilization(policy, positions=positions, valuation=valuation, day=day)
        if day.get('start_equity_minor') is not None and valuation.get('equity_minor') is not None \
                and day['start_equity_minor'] - valuation['equity_minor'] >= policy['risk']['max_daily_loss_minor']:
            self._block(summary, 'RISK', 'MAX_DAILY_LOSS_REACHED')
        # Exits before entries: reducing exposure is never queued behind adding it.
        for decision in sorted(queue, key=lambda d: 0 if d['action_state'] == 'EXIT' else 1):
            if not self._still_permitted(work):
                summary['actions'].append(dict(decision_id=decision['decision_id'], instrument_id=decision['instrument_id'],
                                               action=decision['action_state'], outcome='NOT_ATTEMPTED', reason_codes=['AUTOMATION_HALTED_BY_OPERATOR']))
                continue
            outcome = self.execute_decision(decision, policy, work, session)
            if outcome is not None:
                summary['actions'].append(outcome)
            if outcome and outcome.get('emergency'):
                work['emergency'] = dict(at=_iso(self.clock()), reason=outcome['emergency'], source='CONTROLLER')
                break

    def execute_decision(self, decision, policy, work, session):
        """Walk one gated Action Decision through the canonical Paper preview and submit. Never a second time."""
        from . import paper_projections
        ledger, repo = self.store.paper_ledger, self.repository
        account, decision_id, state = ledger.paper_account_id, decision['decision_id'], decision['action_state']
        intent_id = intent_identity(account, decision_id)
        existing = repo.get_intent(intent_id)
        base = dict(decision_id=decision_id, instrument_id=decision['instrument_id'], action=state, intent_id=intent_id)
        if existing and existing['state'] == IntentState.SUBMITTED:
            # One decision is one order, ever. An exit whose order ended without being filled (no bar to fill
            # against, or a cancelled remainder) leaves the risk open, so the loop is asked to decide again.
            if state == 'EXIT' and str((ledger.lookup_order(str(existing.get('order_id') or '')) or {}).get('state')) in _ENDED_UNFILLED:
                self.reevaluation.request_redecision(decision['instrument_id'], 'EXIT_ORDER_ENDED_UNFILLED')
            return None
        intent = dict(existing or dict(intent_id=intent_id, account_id=account, decision_id=decision_id, created_at=_iso(self.clock()),
                                       attempts=0), instrument_id=decision['instrument_id'], action=state,
                      policy_id=policy['policy_id'], arming_id=work['arming']['arming_id'],
                      run_id=(work.get('run') or {}).get('run_id'), evidence_snapshot_id=decision.get('evidence_snapshot_id'),
                      decision_origin='DETERMINISTIC_RISK_CONTROL' if decision.get('server_exit') else 'MODEL_PROPOSAL_GATED',
                      model=dict(provider_id=(decision.get('model') or {}).get('provider_id'), model_id=(decision.get('model') or {}).get('model_id')))

        def finish(state_name, codes, **extra):
            codes = list(dict.fromkeys(codes))
            previous = (existing or {}).get('state'), tuple((existing or {}).get('reason_codes') or [])
            intent.update(state=str(state_name), reason_codes=codes, updated_at=_iso(self.clock()), updated_epoch=self.clock(), **{k: quantity_wire(v) if k in ('quantity', 'filled_quantity') else v for k,v in extra.items()})
            repo.put_intent(intent, now=self.clock())
            if previous == (str(state_name), tuple(codes)):
                return None  # the same refusal for the same reason is recorded once, not every cycle
            outcome = dict(base, outcome=str(state_name), reason_codes=codes,
                           **{k: quantity_wire(extra[k]) if k in ('quantity', 'filled_quantity') else extra[k] for k in ('quantity', 'side', 'order_id', 'order_state', 'filled_quantity', 'fill_price_minor', 'sizing') if k in extra})
            self._event('PAPER_INTENT_' + str(state_name), **outcome)
            return outcome

        recorded = ledger.lookup_idempotent_order(intent_id)
        if recorded:
            # A crash after the ledger wrote the order and before this record: adopt it, never submit again.
            order = ledger.lookup_order(recorded) or {}
            return finish(IntentState.SUBMITTED, ['RECOVERED_EXISTING_ORDER'], order_id=recorded, order_state=order.get('state'),
                          filled_quantity=quantity_wire(order.get('cumulative_filled_quantity') or 0))
        identity = self.paper_identity(policy)
        if identity or not self.actions._authority():
            return finish(IntentState.BLOCKED, identity or ['PAPER_AUTHORITY_UNAVAILABLE'])
        refusal = decision_permitted(policy, decision)
        if refusal:
            return finish(IntentState.BLOCKED, [refusal])
        if decision.get('execution_readiness') != 'PREVIEW_ALLOWED':
            return finish(IntentState.BLOCKED, ['ACTION_NOT_PREVIEW_ALLOWED', *decision.get('blocker_codes', [])][:8])
        positions = [p for p in ledger.project_positions() if p.get('quantity')]
        pending = [o for o in ledger.project_orders() if str(o.get('state')) in _WORKING]
        if state == 'ENTER':
            blockers = entry_risk_blockers(policy, positions=positions, valuation=ledger.project_valuation(),
                                           day_start_equity_minor=(work.get('day') or {}).get('start_equity_minor'),
                                           pending_orders=pending, minutes_to_close=session.get('minutes_to_close'), session_label=session.get('label'),
                                           carry_pending=bool((work.get('carry') or {}).get('pending')), close_guard_minutes=EOD_FLATTEN_MINUTES)
            if blockers:
                return finish(IntentState.BLOCKED, blockers)
        backoff = work.get('exit_backoff') or {}
        work['exit_backoff'] = backoff
        waiting = backoff.get(decision['instrument_id']) if state == 'EXIT' else None
        if waiting and self.clock() < waiting['until']:
            return finish(IntentState.DEFERRED, ['EXIT_ORDER_BACKOFF'])
        intent['attempts'] = int(intent.get('attempts') or 0) + 1
        try:
            draft = self.actions.handoff(dict(decision_id=decision_id))  # revalidates evidence, expiry, position and authority
        except ValueError as exc:
            code = _code(exc)
            if code == 'ACTION_INPUT_CHANGED':
                # The account moved since this decision was made. It is never executed as it stands: the loop is
                # asked to decide again from current inputs, and that new decision gets its own single order.
                self.reevaluation.request_redecision(decision['instrument_id'], code)
            return finish(IntentState.DEFERRED, [code])
        quantity, sizing = quantity_number(draft['quantity']), None
        if state == 'EXIT':
            owned = _automation_quantities(ledger).get(decision['instrument_id'], 0)
            signed = quantity_number((decision.get('position') or {}).get('quantity') or 0)
            if not owned or owned * signed <= 0:
                return finish(IntentState.BLOCKED, ['AUTOMATION_POSITION_NOT_OWNED'])
            quantity = min(quantity, abs(owned))
        instrument = paper_projections._admit_focus_instrument(self.store, draft['instrumentId'])
        if state == 'ENTER':
            from ..numeric import decimal_to_minor_units
            scale = int(instrument.get('price_scale', ledger.policy.get('price_scale', 100)))
            reference = (decision.get('reference_quote') or {}).get('source_value')
            price = decimal_to_minor_units(str(reference), scale=scale) if isinstance(reference, (int, float)) and reference > 0 else None
            sizing = size_entry(policy, price_minor=price, positions=positions,
                                buying_power_minor=ledger.project_account()['buying_power_minor'], ledger_policy=ledger.policy, instrument=instrument)
            quantity = quantity_number(sizing['quantity'])
            carried = intent.get('pretrade_approved_quantity')
            if carried is not None and 0 < quantity_number(carried) < quantity:
                # An earlier attempt was reduced by the pre-trade risk engine and could not be re-previewed then.
                sizing = dict(sizing, pretrade_reduced_from=quantity_wire(quantity), binding='PRETRADE_RISK_ENGINE')
                quantity = quantity_number(carried)
            if quantity < 1:
                return finish(IntentState.BLOCKED, ['SIZING_BELOW_MINIMUM', sizing['binding']], sizing=sizing)
        correlation = str(draft['sourceAttentionId'])
        opportunity = correlation.startswith('opportunity:')
        context = draft['sourceContext']
        snapshot = dict(source_type='watched_opportunity' if opportunity else 'workspace_lane',
                        source_id=correlation.split(':', 1)[1], headline=str(context['headline'])[:240], source_time=context['source_time'],
                        reasons=[*context['reasons'], dict(code='PAPER_AUTOMATION_POLICY', label=policy['policy_id']),
                                 dict(code='PAPER_AUTOMATION_ARMING', label=work['arming']['arming_id'])])
        if not opportunity:
            snapshot['source_module'] = snapshot['source_id']

        def body(units):
            return dict(instrument_id=draft['instrumentId'], side=draft['side'], quantity=quantity_wire(units), order_type='MARKET',
                        client_order_id=intent_id, idempotency_key=intent_id, correlation_id=correlation, decision_source_snapshot=snapshot)

        from ..intelligence.persistence.errors import RepositoryError
        from . import paper_projections
        try:
            preview = paper_projections.preview_paper_order(self.store, body(quantity))['preview']
            risk = preview.get('action_risk_decision') or {}
            approved = quantity_number(risk.get('approved_quantity') or 0)
            if state == 'ENTER' and risk.get('decision') in ('APPROVE', 'REDUCE') and 0 < approved < quantity:
                # The existing sizing authority reduced the order: the documented step is a fresh preview at that size.
                sizing = dict(sizing, pretrade_reduced_from=quantity_wire(quantity), binding='PRETRADE_RISK_ENGINE')
                quantity = approved
                intent['pretrade_approved_quantity'] = quantity_wire(approved)
                try:
                    preview = paper_projections.preview_paper_order(self.store, body(quantity))['preview']
                except RepositoryError:
                    # The risk engine's immutable proposal record for this instant already exists at the larger size.
                    # Nothing is overwritten; the next cycle previews once at the approved size.
                    return finish(IntentState.DEFERRED, ['PRETRADE_REDUCED_REPREVIEW_NEXT_CYCLE'], quantity=quantity,
                                  side=draft['side'], sizing=sizing)
            if preview.get('risk_status') != 'PASS':
                return finish(IntentState.BLOCKED, ['PAPER_PREVIEW_RISK_' + str(preview.get('decision')), *preview.get('reason_codes', [])][:8],
                              quantity=quantity, side=draft['side'], sizing=sizing)
            intent.update(state=str(IntentState.PREVIEWED), preview_id=preview['preview_id'], quantity=quantity_wire(quantity), side=draft['side'],
                          updated_at=_iso(self.clock()), updated_epoch=self.clock())
            repo.put_intent(intent, now=self.clock())
            with self.submit_lock():
                # The controls are re-read inside the same lock the submission holds, so an operator Stop, Pause,
                # Disarm or Emergency Stop that flips state cannot land between this guard and the order.
                if not self._still_permitted(work):
                    return finish(IntentState.BLOCKED, ['AUTOMATION_HALTED_BY_OPERATOR'], quantity=quantity, side=draft['side'])
                submission = self._submit(dict(body(quantity), preview_id=preview['preview_id']))
        except ValueError as exc:
            code = _code(exc)
            deferred = any(code.startswith(prefix) for prefix in _DEFER_CODES)
            return finish(IntentState.DEFERRED if deferred else IntentState.BLOCKED, [code], quantity=quantity, side=draft['side'], sizing=sizing)
        order = submission.get('order') or {}
        fill = submission.get('fill') or {}
        outcome = finish(IntentState.SUBMITTED, ['PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION', *(order.get('reason_codes') or [])][:8],
                         quantity=quantity, side=draft['side'], sizing=sizing, order_id=submission.get('order_id'), order_state=order.get('state'),
                         filled_quantity=quantity_wire(order.get('cumulative_filled_quantity') or fill.get('fill_quantity') or 0),
                         fill_price_minor=fill.get('fill_price_minor'), preview_id=preview['preview_id'],
                         risk_decision_id=submission.get('risk_decision_id'), fill_kind='SIMULATED_FILL', is_market_truth=False)
        if str(order.get('state')) in _WORKING:
            # The simulator fills once, at submission. A working remainder would block every later decision on this
            # instrument, so it is cancelled; fills already recorded stay, and the next cycle decides on what is held.
            self._cancel_order(str(submission.get('order_id')), 'UNFILLED_REMAINDER')
        if state == 'EXIT':
            if str(order.get('state')) == 'FILLED':
                backoff.pop(decision['instrument_id'], None)
            else:
                count = int((waiting or {}).get('count') or 0) + 1
                delay = min(policy['schedule']['cadence_seconds'] * 2 ** (count - 1), EXIT_BACKOFF_CAP_SECONDS)
                backoff[decision['instrument_id']] = dict(count=count, until=self.clock() + delay, last_order_state=str(order.get('state')))
                self.reevaluation.request_redecision(decision['instrument_id'], 'EXIT_ORDER_ENDED_UNFILLED')
        return outcome

    def _submit(self, body):
        """The controller's only order route: the canonical Workspace Paper submit, under the caller's submit lock."""
        from . import paper_projections
        return paper_projections.submit_paper_order(self.store, body)['submission']

    def _owned_positions(self):
        quantities = _automation_quantities(self.store.paper_ledger)
        rows = []
        for position in self.store.paper_ledger.project_positions():
            iid = str(position['instrument_id'])
            held = quantity_number(position.get('quantity') or 0)
            if position.get('side') == 'SHORT':
                held = -abs(held)
            own = quantities.get(iid, 0)
            if not own or held * own <= 0:
                continue
            from . import paper_projections
            try:
                instrument = paper_projections._admit_focus_instrument(self.store, iid)
            except ValueError:
                # Retain unknown owned exposure as blocked carry; canonical preview
                # will refuse its close without aborting other instruments.
                rows.append(dict(position, quantity=quantity_wire(min(abs(own), abs(held)) * (1 if held > 0 else -1)),
                                 instrument_admission_unavailable=True))
                continue
            if instrument.get('instrument_kind') != 'TRADABLE_SECURITY' or instrument.get('asset_class') not in ('EQUITY', 'ETF'):
                continue
            rows.append(dict(position, quantity=quantity_wire(min(abs(own), abs(held)) * (1 if held > 0 else -1))))
        return rows

    def _detect_unplanned_carry(self, work, closing_date):
        carry = work['carry']
        owned = {p['instrument_id']: p for p in self._owned_positions()}
        for iid in list(carry['pending']):
            if iid not in owned:
                carry['pending'].pop(iid, None)
        for iid, p in owned.items():
            approved = carry['approved'].get(iid) or {}
            if (approved.get('session_date') == closing_date and approved.get('quantity') == p['quantity']
                    and approved.get('entry_ns') == p.get('first_entry_time_ns')):
                continue
            # A position opened today before the bell is not yesterday's carry.
            entry = p.get('first_entry_time_ns')
            if entry and datetime.fromtimestamp(entry / 1e9, UTC).astimezone(ET).date().isoformat() > closing_date:
                continue
            if iid not in carry['pending']:
                carry['pending'][iid] = dict(quantity=p['quantity'], entry_ns=entry, session_date=closing_date)
                self._event('PAPER_UNPLANNED_CARRY', instrument_id=iid, **carry['pending'][iid])

    def _carry_rollover(self, work, session, now):
        # Carry is for US equities/ETFs. A continuous crypto scope cannot advance
        # its trading calendar or erase a Friday approval over the weekend.
        if session.get('label') == 'CONTINUOUS':
            session = self.session(now)
        day = session['session_date']
        first_cycle = not work.get('carry')
        carry = work.get('carry') or dict(session_date=(work.get('day') or {}).get('session_date', day),
                                          approved={}, reviewed={}, pending={}, closing=[], blocked=[])
        work['carry'] = carry
        if first_cycle or carry['session_date'] != day or not session.get('trading_day'):
            from datetime import date, timedelta
            from ..intelligence.forward_qualification.evidence01.continuity import is_trading_day
            previous = date.fromisoformat(day) - timedelta(days=1)
            while not is_trading_day(previous):
                previous -= timedelta(days=1)
            self._detect_unplanned_carry(work, previous.isoformat())
            # A holiday/weekend detects missed closes but never erases a valid
            # approval from the most recent completed equity session.
            if session.get('trading_day'):
                carry.update(session_date=day, approved={}, reviewed={}, closing=[], blocked=[])

    def _hold_sessions(self, position, session):
        from ..intelligence.forward_qualification.evidence01.continuity import is_trading_day, _DEFAULT_HOLIDAYS
        entry = position.get('first_entry_time_ns')
        if not entry:
            return 999  # unknown position age cannot authorize an overnight hold
        entry_date = datetime.fromtimestamp(entry / 1e9, UTC).astimezone(ET).date().isoformat()
        if entry_date > session['session_date']:
            return 999
        years = {int(day[:4]) for day in _DEFAULT_HOLIDAYS}
        if any(year not in years for year in range(int(entry_date[:4]), int(session['session_date'][:4]) + 1)):
            return 999
        return sessions_held(entry_date, session['session_date'], is_trading_day)

    def _review_context(self, iid, work, policy):
        session = self.session(self.clock())
        minutes = session.get('minutes_to_close')
        carry = work.get('carry') or {}
        review = (carry.get('reviewed') or {}).get(iid)
        if (not review or session.get('label') != 'REGULAR' or minutes is None
                or not 0 <= minutes <= OVERNIGHT_REVIEW_MINUTES or session['session_date'] != review['session_date']):
            return None
        p = next((p for p in self._owned_positions() if p['instrument_id'] == iid), None)
        if not p or p['quantity'] != review['automation_quantity'] or p.get('first_entry_time_ns') != review['entry_ns']:
            return None
        return review

    def _prepare_overnight_reviews(self, work, policy, session, now, health):
        limits = overnight_limits(policy)
        minutes = session.get('minutes_to_close')
        if (not limits or session['label'] != 'REGULAR' or minutes is None
                or not EOD_FLATTEN_MINUTES < minutes <= OVERNIGHT_REVIEW_MINUTES or health.get('reasons')):
            return
        carry = work['carry']
        rows = sorted(self._owned_positions(), key=lambda p: (-self._return_bps(p), p['instrument_id']))
        for p in rows:
            iid = p['instrument_id']
            if len(carry['reviewed']) >= 10:
                break
            if iid in carry['reviewed'] or iid in carry['pending'] or self._hold_sessions(p, session) >= limits['max_hold_sessions']:
                continue
            risk = self.actions._risk_facts(iid) or {}
            if risk.get('status') == 'BREACHED':
                continue
            carry['reviewed'][iid] = dict(review_id='POR-' + input_hash_from_dict(dict(account=self._account(), iid=iid,
                day=session['session_date'], entry=p.get('first_entry_time_ns')))[:32],
                session_date=session['session_date'], requested_at=now, sessions_held=self._hold_sessions(p, session),
                max_hold_sessions=limits['max_hold_sessions'], automation_quantity=p['quantity'], entry_ns=p.get('first_entry_time_ns'))
            self.reevaluation.request_redecision(iid, 'OVERNIGHT_REVIEW')

    @staticmethod
    def _return_bps(position):
        basis = abs(quantity_number(position['quantity'])) * int(position.get('average_fill_minor') or 0)
        # Net-book P&L percentage is the same for each owner's pro-rata shares.
        mark, avg = position.get('mark_minor'), position.get('average_fill_minor')
        if not basis or not mark or not avg:
            return -10**12
        return int((mark - avg) * (1 if quantity_number(position['quantity']) > 0 else -1) * 10000 / avg)

    def _carry_candidate(self, position, work, policy, session, now):
        iid = position['instrument_id']
        limits = overnight_limits(policy)
        review = work['carry']['reviewed'].get(iid)
        if position.get('instrument_admission_unavailable') or not limits or not review or iid in work['carry']['closing'] or iid in work['carry']['pending']:
            return None
        valuation = self.store.paper_ledger.project_valuation()
        day = work.get('day') or {}
        health = self.provider_health(policy['scope'])
        if (health.get('reasons') or valuation.get('quality') != 'CURRENT'
                or day.get('start_equity_minor') is None or valuation.get('equity_minor') is None
                or day['start_equity_minor'] - valuation['equity_minor'] >= policy['risk']['max_daily_loss_minor']
                or self.store.paper_ledger.short_margin_status().get('maintenance_breached')
                or self._hold_sessions(position, session) >= limits['max_hold_sessions']):
            return None
        history = self.actions.history(iid)
        d = history[0] if history else {}
        reasoned = d.get('model_reasoning_wire') or {}
        context = (d.get('evidence_snapshot') or {}).get('context') or {}
        if (d.get('action_state') != 'HOLD' or not (d.get('overnight_carry') or {}).get('qualified')
                or (reasoned.get('rationale') or {}).get('assessment') != 'EVIDENCE_SUFFICIENT'
                or (context.get('overnight_review') or {}).get('review_id') != review['review_id']
                or review['session_date'] != session['session_date']
                or _epoch(d.get('decision_time'), 0) < review['requested_at']
                or _epoch(d.get('decision_time'), now + 1) > now
                or _epoch(d.get('valid_until'), 0) <= now
                or quantity_number((d.get('position') or {}).get('quantity') or 0) != quantity_number(position['quantity'])
                or review['automation_quantity'] != position['quantity'] or review['entry_ns'] != position.get('first_entry_time_ns')
                or d.get('conflicting_refs') or d.get('weak_refs') or d.get('missing_capabilities')
                or d.get('server_exit') or any(c.get('condition_id') == 'SMA_TRAILING_STOP_BREACHED' and c.get('status') == 'MET'
                                             for c in d.get('conditions') or [])):
            return None
        evidence = (d.get('evidence_snapshot') or {}).get('evidence') or {}
        from ..intelligence.inference.action_decision import _current
        current_evidence = [*evidence.get('current_market_evidence', []), *evidence.get('reference_evidence', [])]
        quote = next((e for e in current_evidence if e.get('capability') == 'QUOTE' and _current(e, _iso(now))), None)
        if not quote:
            return None
        quote_lifetime = _epoch(quote.get('valid_until'), 0) - _epoch(quote.get('as_of'), 0)
        mark_age = now - float(position.get('mark_as_of_ns') or 0) / 1e9
        if not -1 <= mark_age < quote_lifetime:
            return None
        refs = [e['evidence_id'] for e in current_evidence
                if e.get('capability') != 'QUOTE' and (reasoned.get('evidence_stance') or {}).get(e['evidence_id']) == 'SUPPORTING'
                and e['evidence_id'] in d.get('supporting_refs', []) and not e.get('weak_reasons')
                and e.get('decision_admissibility') == 'ADMISSIBLE' and _current(e, _iso(now))]
        # Refresh the existing deterministic monitor before deciding to carry.
        # It advances completed bars and uses its own current-quote provider.
        self.actions._risk_facts(iid)  # initialize the shared risk-control service if needed
        stops = getattr(self.actions, 'risk_control', None)
        if stops is not None:
            stops.evaluate(iid)
        risk = self.actions._risk_facts(iid) or {}
        if not refs or risk.get('status') == 'BREACHED':
            return None
        exposure = exposure_minor([position])
        if exposure is None:
            return None
        return dict(instrument_id=iid, quantity=position['quantity'], entry_ns=position.get('first_entry_time_ns'),
                    exposure_minor=exposure, return_bps=self._return_bps(position), decision_id=d['decision_id'],
                    evidence_refs=refs, sessions_held=self._hold_sessions(position, session), session_date=session['session_date'])

    def _close_retry(self, work, policy, summary, session, now, position, opening=False):
        ledger = self.store.paper_ledger
        iid = position['instrument_id']
        prefix = ('PAI-OPEN-' if opening else 'PAI-EOD-') + input_hash_from_dict(dict(account=self._account(),
            iid=iid, day=session['session_date']))[:24] + '-'
        attempts = [o for o in ledger.project_orders() if str(o.get('client_order_id') or '').startswith(prefix)]
        latest = max((float((o.get('decision_source_snapshot') or {}).get('source_time') or o.get('created_time') or 0) / 1e9 for o in attempts), default=0)
        retry_after = work['carry'].setdefault('retry_after', {})
        if now < max(float(retry_after.get(prefix) or 0), latest + 60 if attempts else 0):
            summary['close_retry_pending'] = True
            return
        if len(attempts) >= EOD_MAX_ATTEMPTS:
            tag = prefix + 'EXHAUSTED'
            if tag not in work['carry']['blocked']:
                work['carry']['blocked'].append(tag)
                self._event('PAPER_CLOSE_ATTEMPTS_EXHAUSTED', instrument_id=iid, session_date=session['session_date'])
            return
        if any(o.get('instrument_id') == iid and str(o.get('state')) in _WORKING for o in ledger.project_orders()):
            return
        retry_after[prefix] = now + 60
        action = 'OPEN_CLOSE' if opening else 'EOD_FLATTEN'
        outcome = self._close_position(work, policy, summary, now, iid=iid, held=quantity_number(position['quantity']),
            key=prefix + str(len(attempts) + 1), action=action, event='PAPER_' + action,
            headline='Unplanned carry: close at open' if opening else 'End-of-day flatten (owner policy)',
            reason=dict(code='PAPER_AUTOMATION_' + action, label=session['session_date']))
        summary['close_retry_pending'] = True
        if outcome.get('outcome') == 'BLOCKED':
            tag = prefix + '|'.join(outcome.get('reason_codes') or [])
            if tag not in work['carry']['blocked']:
                work['carry']['blocked'].append(tag)
                self._event('PAPER_EOD_FLATTEN_BLOCKED', **outcome)

    def _close_carry_at_open(self, work, policy, summary, session, now):
        if session['label'] != 'REGULAR':
            return
        owned = {p['instrument_id']: p for p in self._owned_positions()}
        for iid in list(work['carry']['pending']):
            p = owned.get(iid)
            if p is None:
                work['carry']['pending'].pop(iid, None)
                continue
            try:
                self._close_retry(work, policy, summary, session, now, p, opening=True)
            except Exception as exc:  # a bad symbol never prevents the other closes
                self._block(summary, 'DATA', 'PAPER_CLOSE_' + _code(exc))
        remaining = {p['instrument_id'] for p in self._owned_positions()}
        work['carry']['pending'] = {k: v for k, v in work['carry']['pending'].items() if k in remaining}
        if work['carry']['pending']:
            self._block(summary, 'RISK', 'UNPLANNED_CARRY_PENDING')

    def _eod_flatten(self, work, policy, summary, session, now):
        minutes = session.get('minutes_to_close')
        if session['label'] != 'REGULAR' or minutes is None or not 0 <= minutes <= EOD_FLATTEN_MINUTES:
            return
        if not self.actions._authority():
            return
        positions = self._owned_positions()
        candidates = []
        for p in positions:
            try:
                candidate = self._carry_candidate(p, work, policy, session, now)
                if candidate:
                    candidates.append(candidate)
            except (ValueError, TypeError, KeyError):
                pass  # an invalid review cannot authorize carrying risk
        limits = overnight_limits(policy)
        kept, _ = select_overnight_carry(candidates, limits) if limits else ([], [])
        selected = {p['instrument_id']: p for p in kept}
        carry = work['carry']
        for iid in list(carry['approved']):
            if iid not in selected:
                carry['approved'].pop(iid, None)
        for iid, candidate in selected.items():
            if carry['approved'].get(iid) != candidate:
                self._event('PAPER_OVERNIGHT_HOLD', **candidate)
                carry['approved'][iid] = candidate
        for p in positions:
            iid = p['instrument_id']
            if iid in selected or iid in carry['pending']:
                continue
            if iid not in carry['closing']:
                carry['closing'].append(iid)
            try:
                self._close_retry(work, policy, summary, session, now, p)
            except Exception as exc:
                self._block(summary, 'DATA', 'PAPER_CLOSE_' + _code(exc))


    def _maintenance_cover(self, work, policy, summary, session, now):
        """Rebuild step 6: a short book under its maintenance margin buys back its largest-loss short.

        One cover per cycle, through the canonical preview and submit, idempotent per short position. The
        breach is only declared from complete marks (``PaperExecutionLedger.short_margin_status``).
        """
        ledger = self.store.paper_ledger
        if not ledger.allows_short() or not self.actions._authority():
            return
        status = ledger.short_margin_status()
        if not status['maintenance_breached']:
            return
        self._block(summary, 'RISK', 'SHORT_MAINTENANCE_MARGIN_BREACH')
        working = {str(o.get('instrument_id')) for o in ledger.project_orders() if str(o.get('state')) in _WORKING}
        entries = {p['instrument_id']: p.get('first_entry_time_ns') for p in ledger.project_positions()}
        shorts = sorted((s for s in status['short_positions'] if s['instrument_id'] not in working),
                        key=lambda s: (s['unrealized_pnl_minor'] if s['unrealized_pnl_minor'] is not None else 0, s['instrument_id']))
        for short in shorts:
            iid = str(short['instrument_id'])
            key = 'PAI-MARGIN-' + input_hash_from_dict(dict(account=ledger.paper_account_id, instrument=iid,
                                                            entry=entries.get(iid)))[:32]
            if ledger.lookup_idempotent_order(key):
                continue
            self._event('SHORT_MAINTENANCE_MARGIN_BREACH', instrument_id=iid, equity_minor=status['equity_minor'],
                        maintenance_requirement_minor=status['maintenance_requirement_minor'],
                        short_market_value_minor=status['short_market_value_minor'])
            self._close_position(work, policy, summary, now, iid=iid, held=quantity_number(short['quantity']), key=key,
                                 action='MARGIN_COVER', event='PAPER_MARGIN_COVER',
                                 headline='Short maintenance margin breached: buy to cover',
                                 reason=dict(code='PAPER_AUTOMATION_MARGIN_COVER', label=session['session_date']))
            return

    def _close_position(self, work, policy, summary, now, *, iid, held, key, action, event, headline, reason):
        """One MARKET close of the whole held quantity: SELL a long, BUY to cover a short."""
        from . import paper_projections
        side = 'SELL' if held > 0 else 'BUY'
        quantity = abs(held)
        body = dict(instrument_id=iid, side=side, quantity=quantity_wire(quantity), order_type='MARKET', client_order_id=key,
                    idempotency_key=key, correlation_id='lane:order-flow',
                    decision_source_snapshot=dict(source_type='workspace_lane', source_id='order-flow', source_module='order-flow',
                                                  headline=headline, source_time=int(now * 1e9),
                                                  reasons=[reason,
                                                           dict(code='PAPER_AUTOMATION_POLICY', label=policy['policy_id']),
                                                           dict(code='PAPER_AUTOMATION_ARMING', label=work['arming']['arming_id'])]))
        outcome = dict(decision_id=None, instrument_id=iid, action=action, side=side, quantity=quantity_wire(quantity), client_order_id=key)
        try:
            preview = paper_projections.preview_paper_order(self.store, body)['preview']
            if preview.get('risk_status') != 'PASS':
                outcome.update(outcome='BLOCKED', reason_codes=['PAPER_PREVIEW_RISK_' + str(preview.get('decision')), *preview.get('reason_codes', [])][:8])
            else:
                with self.submit_lock():
                    if not self._still_permitted(work):
                        outcome.update(outcome='NOT_ATTEMPTED', reason_codes=['AUTOMATION_HALTED_BY_OPERATOR'])
                    else:
                        submission = self._submit(dict(body, preview_id=preview['preview_id']))
                        order = self.store.paper_ledger.lookup_order(str(submission.get('order_id'))) or submission.get('order') or {}
                        outcome.update(outcome='SUBMITTED', order_id=submission.get('order_id'), order_state=order.get('state'),
                                       reason_codes=['PAPER_ORDER_SUBMITTED_INTERNAL_SIMULATION'],
                                       filled_quantity=quantity_wire(order.get('cumulative_filled_quantity') or 0))
                        if str(order.get('state')) in _WORKING:
                            self._cancel_order(str(submission.get('order_id')), 'UNFILLED_REMAINDER')
        except ValueError as exc:
            outcome.update(outcome='BLOCKED', reason_codes=[_code(exc)])
        self._event(event, **outcome)
        summary['actions'].append(outcome)
        return outcome

    def _cancel_order(self, order_id, reason):
        from . import paper_projections
        ledger = self.store.paper_ledger
        if str(ledger.execution_mode) != 'INTERNAL_SIMULATION' or str(ledger.execution_provider) != 'INTERNAL':
            # The cancel route has a broker branch. The controller never reaches it, including on Emergency Stop.
            self._event('PAPER_ORDER_CANCEL_FAILED', order_id=order_id, reason=reason, error='EXECUTION_PROVIDER_NOT_INTERNAL')
            return False
        try:
            with self.submit_lock():
                result = paper_projections.cancel_paper_order(self.store, dict(order_id=order_id))['cancellation']
            self._event('PAPER_ORDER_REMAINDER_CANCELLED', order_id=order_id, reason=reason, state=result.get('state'),
                        filled_quantity=result.get('filled_quantity'))
            return True
        except ValueError as exc:
            self._event('PAPER_ORDER_CANCEL_FAILED', order_id=order_id, reason=reason, error=_code(exc))
            return False

    def _automation_working_orders(self):
        return [o for o in self.store.paper_ledger.project_orders()
                if str(o.get('state')) in _WORKING and str(o.get('client_order_id') or '').startswith('PAI-')]

    def _reconcile_working_orders(self, summary):
        """Pending-order reconciliation at the start of a cycle: an automation order left working is cancelled."""
        for order in self._automation_working_orders():
            self._cancel_order(str(order.get('order_id')), 'RECONCILED_WORKING_ORDER')
        manual = [o for o in self.store.paper_ledger.project_orders() if str(o.get('state')) in _WORKING and not str(o.get('client_order_id') or '').startswith('PAI-')]
        if manual:
            summary['manual_working_orders'] = len(manual)  # an operator's own order is never touched

    def _cancel_working_orders(self, reason):
        return sum(1 for order in self._automation_working_orders() if self._cancel_order(str(order.get('order_id')), reason))

    # --- reads ---------------------------------------------------------------------------------------
    def risk_utilization(self, policy, *, positions, valuation, day):
        risk = policy['risk']
        exposure = exposure_minor(positions)
        equity, start = valuation.get('equity_minor'), (day or {}).get('start_equity_minor')
        return dict(open_positions=len(positions), max_open_positions=risk['max_open_positions'],
                    exposure_minor=exposure, max_aggregate_exposure_minor=risk['max_aggregate_exposure_minor'],
                    day_pnl_minor=equity - start if equity is not None and start is not None else None,
                    max_daily_loss_minor=risk['max_daily_loss_minor'], valuation_quality=valuation.get('quality'),
                    equity_minor=equity, cash_minor=valuation.get('cash_minor'), buying_power_minor=valuation.get('buying_power_minor'),
                    realized_pnl_minor=valuation.get('realized_pnl_minor'), unrealized_pnl_minor=valuation.get('unrealized_pnl_minor'),
                    total_pnl_minor=valuation.get('total_pnl_minor'))

    def status(self):
        """What the controller is really able to do right now. Reads only; calls no model and no provider."""
        ledger = self.store.paper_ledger
        controller = self.repository.get_controller(self._account())
        now = self.clock()
        session = self.session(now)
        boundary = dict(execution='INTERNAL_PAPER_SIMULATION_ONLY', live_capital=False, real_money_order_routes='NOT_REACHABLE_FROM_AUTOMATION',
                        execution_mode=str(ledger.execution_mode), execution_provider=str(ledger.execution_provider),
                        execution_authority=str(ledger.execution_authority))
        if controller is None:
            return dict(schema_version=STATUS_SCHEMA, status=str(AutomationStatus.NOT_CONFIGURED), status_label='Not configured',
                        required_configuration=required_fields(), arm_acknowledgement=ARM_ACKNOWLEDGEMENT, session=session,
                        boundary=boundary, identity_blockers=self.paper_identity(), durability=self.repository.durability,
                        evaluated_at=_iso(now))
        policy = self.repository.get_policy(controller['policy_id'])
        leased = bool(controller.get('owner_id') and controller.get('lease_until') and controller['lease_until'] > now)
        mine = leased and controller['owner_id'] == self.owner_id
        alive = bool(self.worker and self.worker.alive())
        last = controller.get('last_cycle') or {}
        blockers = [dict(category='AUTHORITY', code=code) for code in self.paper_identity(policy)]
        eligible = session['label'] in policy['schedule']['sessions']
        cadence = policy['schedule']['cadence_seconds']
        error = False
        if controller['desired_state'] == 'RUNNING' and controller.get('arming') and not controller.get('emergency'):
            if not (mine and alive):
                # Wanted running but nothing is scheduling it here: never shown as RUNNING.
                error = True
                blockers.append(dict(category='AUTHORITY', code='RUNNING_ELSEWHERE' if leased and not mine else 'CONTROLLER_NOT_ALIVE'))
            elif last.get('error'):
                error = True
            elif eligible and controller.get('heartbeat_at') and now - controller['heartbeat_at'] > 3 * cadence:
                error = True
                blockers.append(dict(category='DATA', code='CYCLE_OVERDUE'))
            else:
                blockers.extend(b for b in (last.get('blockers') or []) if b not in blockers)
        status = derive_status(configured=True, armed=bool(controller.get('arming')), desired=controller['desired_state'],
                               emergency=bool(controller.get('emergency')), error=error, blockers=blockers, session_eligible=eligible)
        labels = {AutomationStatus.RUNNING: 'Running — evaluating and able to submit Paper orders',
                  AutomationStatus.WAITING_FOR_MARKET: 'Waiting for the configured market session',
                  AutomationStatus.BLOCKED_BY_AUTHORITY: 'Blocked — Paper authority or account check failed',
                  AutomationStatus.BLOCKED_BY_DATA: 'Blocked — market data not usable', AutomationStatus.BLOCKED_BY_RISK: 'Blocked — owner risk limit reached',
                  AutomationStatus.BLOCKED_BY_BUDGET: 'Blocked — AI budget or spending authorization', AutomationStatus.PAUSED: 'Paused',
                  AutomationStatus.STOPPED: 'Stopped', AutomationStatus.DISARMED: 'Configured — not armed',
                  AutomationStatus.EMERGENCY_STOPPED: 'Emergency stop — disarm to clear', AutomationStatus.ERROR: 'Error'}
        positions = [p for p in ledger.project_positions() if p.get('quantity')]
        valuation = ledger.project_valuation() if ledger.is_portfolio_scoped() else {}
        return dict(
            schema_version=STATUS_SCHEMA, status=str(status), status_label=labels[status], blockers=blockers,
            carry=copy.deepcopy(controller.get('carry') or {}),
            account_id=controller['account_id'], experiment_id=controller.get('experiment_id'), policy=policy,
            armed=bool(controller.get('arming')), arming=controller.get('arming'), emergency=controller.get('emergency'),
            desired_state=controller['desired_state'], run=controller.get('run'), session=session, session_eligible=eligible,
            liveness=dict(owner='THIS_PROCESS' if mine else 'OTHER_PROCESS' if leased else None, worker_alive=alive,
                          heartbeat_at=_iso(controller.get('heartbeat_at')), lease_until=_iso(controller.get('lease_until')) if leased else None,
                          cycle_count=controller.get('cycle_count'), consecutive_failures=controller.get('consecutive_failures'),
                          last_error=controller.get('last_error'), last_scheduled=_iso(controller.get('last_scheduled_epoch'))),
            last_cycle=last or None, universe=controller.get('universe'), candidate_quotes=controller.get('subscriptions') or [],
            risk=self.risk_utilization(policy, positions=positions, valuation=valuation, day=controller.get('day')),
            scheduling=self.scheduling(policy, controller),
            day=controller.get('day'), positions=[{k: p.get(k) for k in ('instrument_id', 'symbol', 'side', 'quantity', 'average_fill_minor',
                                                                           'mark_minor', 'mark_quality', 'unrealized_pnl_minor')} for p in positions],
            working_orders=[{k: o.get(k) for k in ('order_id', 'instrument_id', 'side', 'state', 'client_order_id')}
                            for o in ledger.project_orders() if str(o.get('state')) in _WORKING],
            recent_intents=self.repository.intents(controller['account_id'], limit=10), provider=last.get('provider'),
            engine=self.reevaluation.engine_state(), spending=spending_gate(policy, self.reevaluation.engine_state()),
            required_configuration=required_fields(), arm_acknowledgement=ARM_ACKNOWLEDGEMENT, boundary=boundary,
            durability=self.repository.durability, evaluated_at=_iso(now))

    def scheduling(self, policy, controller):
        """The adaptive scheduler's own state, as the operator has to see it. Reads only; decides nothing.

        Opening the UI must never start an evaluation, so this reports the last decision and when the next one
        becomes eligible, never a new one.
        """
        schedule = policy['schedule']
        universe = controller.get('universe') or {}
        decision = universe.get('last_decision') or None
        return dict(
            policy=dict(min_separation_seconds=schedule['universe_evaluation_interval_seconds'],
                        max_age_seconds=schedule.get('universe_max_age_seconds'),
                        material_change_trigger=schedule.get('universe_material_change_trigger'),
                        max_runs_per_day=schedule.get('universe_max_runs_per_day'), optional_fields=optional_fields()),
            adaptive=schedule.get('universe_max_age_seconds') is not None or schedule.get('universe_material_change_trigger') is not None,
            last_decision=decision, next_eligible_epoch=(decision or {}).get('next_eligible_epoch'),
            next_eligible=_iso((decision or {}).get('next_eligible_epoch')),
            last_complete=universe.get('last_complete'), last_complete_fingerprint=universe.get('last_complete_fingerprint'),
            active_run_id=universe.get('active_run_id'), withheld=universe.get('withheld'), failure=universe.get('failure'),
            runs_today=dict(started=self._universe_runs_today(self.clock()), limit=schedule.get('universe_max_runs_per_day')))

    def history(self, *, limit=50, before=None, kind=None):
        controller = self._controller()
        if kind is not None and not _CODE.fullmatch(str(kind)):
            raise ValueError('INVALID_AUTOMATION_HISTORY')
        events = self.repository.events(controller['account_id'], limit=limit, before=before, kinds=[kind] if kind else None)
        return dict(schema_version=HISTORY_SCHEMA, events=events,
                    next_before=events[-1]['sequence'] if len(events) >= max(1, min(int(limit), 200)) else None,
                    durability=self.repository.durability)

    def report(self):
        """What the automation did, from the ledger's own fills and this controller's own records.

        Simulated outcomes are reported apart from what any model proposed. Nothing here
        is a performance claim, and nothing here feeds back into policy, limits or method.
        """
        controller = self._controller()
        ledger, account = self.store.paper_ledger, controller['account_id']
        trades = [t for t in ledger.project_trades() if str(t.get('order_id') or '') and str((ledger.lookup_order(t['order_id']) or {}).get('client_order_id') or '').startswith('PAI-')]
        closing = [t for t in trades if t['realized_pnl_minor'] is not None]
        wins = [t['realized_pnl_minor'] for t in closing if t['realized_pnl_minor'] > 0]
        losses = [t['realized_pnl_minor'] for t in closing if t['realized_pnl_minor'] < 0]
        intents = self.repository.intents(account, limit=200)
        refusals = {}
        for intent in intents:
            if intent['state'] in ('BLOCKED', 'DEFERRED', 'FAILED'):
                for code in intent.get('reason_codes') or ['UNSPECIFIED']:
                    refusals[code] = refusals.get(code, 0) + 1
        from ..local_state.paper_experiments import paper_experiment_repository
        snapshots = paper_experiment_repository().snapshots(controller['experiment_id'], limit=100) if controller.get('experiment_id') else []
        peak, drawdown = None, 0
        for snapshot in reversed(snapshots):  # oldest first
            equity = snapshot.get('equity_minor')
            if equity is None:
                continue
            peak = equity if peak is None else max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        valuation = ledger.project_valuation()
        positions = [p for p in ledger.project_positions() if p.get('quantity')]
        counts = self.repository.event_counts(account)
        universe = self.repository.events(account, limit=200, kinds=['UNIVERSE_RUN_FINISHED'])
        return dict(
            schema_version=REPORT_SCHEMA, account_id=account, experiment_id=controller.get('experiment_id'), policy_id=controller['policy_id'],
            evidence_class='SIMULATED_PAPER_FILLS_NOT_MARKET_TRUTH',
            statement='Paper P&L is accounting of simulated fills against observed prices. It is not evidence of a profitable '
                      'strategy or a durable edge, and this report changes no policy, limit, model or method.',
            fills=dict(count=len(trades), opening=sum(1 for t in trades if t['position_effect'] in ('OPEN', 'ADD')), closing=len(closing),
                       costs_minor=sum(t['costs_minor'] for t in trades), slippage_model='NOT_SEPARATELY_MODELED'),
            outcomes=dict(closed_fills=len(closing), wins=len(wins), losses=len(losses), flat=len(closing) - len(wins) - len(losses),
                          realized_pnl_minor=sum(t['realized_pnl_minor'] for t in closing), gross_win_minor=sum(wins), gross_loss_minor=sum(losses),
                          largest_win_minor=max(wins) if wins else None, largest_loss_minor=min(losses) if losses else None,
                          sample_note='Counts are fill-level and small samples say nothing about expectancy.'),
            portfolio=dict(equity_minor=valuation.get('equity_minor'), realized_pnl_minor=valuation.get('realized_pnl_minor'),
                           unrealized_pnl_minor=valuation.get('unrealized_pnl_minor'), total_pnl_minor=valuation.get('total_pnl_minor'),
                           valuation_quality=valuation.get('quality'), exposure_minor=exposure_minor(positions), open_positions=len(positions),
                           max_drawdown_minor_last_snapshots=drawdown, drawdown_basis='PERSISTED_EQUITY_SNAPSHOTS_NEWEST_100'),
            decisions=dict(intents=len(intents), submitted=sum(1 for i in intents if i['state'] == 'SUBMITTED'),
                           refused_or_deferred=sum(1 for i in intents if i['state'] != 'SUBMITTED'), refusal_reasons=refusals,
                           by_origin={origin: sum(1 for i in intents if i.get('decision_origin') == origin)
                                      for origin in ('MODEL_PROPOSAL_GATED', 'DETERMINISTIC_RISK_CONTROL')}),
            ai=dict(universe_runs=len(universe), complete_runs=sum(1 for u in universe if u.get('coverage_complete')),
                    incomplete_runs=sum(1 for u in universe if not u.get('coverage_complete')),
                    tokens_input=sum(int(u.get('tokens_input') or 0) for u in universe),
                    tokens_output=sum(int(u.get('tokens_output') or 0) for u in universe),
                    models=sorted({str((u.get('model') or {}).get('model_id')) for u in universe if (u.get('model') or {}).get('model_id')}),
                    reevaluation_model_calls_last_day=self.reevaluation.repository.model_calls_since(account, self.clock() - 86400)),
            activity=counts, generated_at=_iso(self.clock()))

    def heartbeat(self):
        try:
            self.repository.heartbeat(self._account(), self.owner_id, now=self.clock(), lease_seconds=LEASE_SECONDS)
            return True
        except ValueError:
            return False


class AutomationWorker:
    """Schedule only. Slots are anchor + n*cadence; an overrun skips slots, it never overlaps or runs late."""

    def __init__(self, service, account_id, *, cadence, anchor, wait=None):
        self.service, self.account_id, self.cadence, self.anchor = service, account_id, cadence, anchor
        self.stop_event = threading.Event()
        self.wait = wait or self.stop_event.wait
        self.thread = None
        self.finished = False
        self.exit_reason = None
        self.slot, self.missed = anchor, 0
        self.transient_failures = 0

    def start(self):
        self.thread = threading.Thread(target=self.run, name='imp-paper-automation', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def alive(self):
        return not self.finished and not self.stop_event.is_set() and (self.thread is None or self.thread.is_alive())

    def _heartbeat(self):
        """The lease renewal; a transient shared-store error is retried at the next wait, never fatal at once."""
        try:
            alive = self.service.heartbeat()
        except sqlite3.OperationalError as exc:
            self._transient(exc, 'HEARTBEAT')
            return True  # the lease is unchanged by a failed write; its expiry still bounds every other owner
        self.transient_failures = 0
        return alive

    def _transient(self, exc, phase):
        """Record a busy/locked shared-store error with its traceback; end the worker after too many in a row."""
        self.transient_failures += 1
        _record_worker_fault(self.service, exc, phase=phase, transient=True, consecutive=self.transient_failures, slot=self.slot)
        if self.transient_failures >= TRANSIENT_STORE_RETRIES:
            raise exc

    def run(self, max_cycles=None):
        service, done = self.service, 0
        try:
            while not self.stop_event.is_set() and (max_cycles is None or done < max_cycles):
                while not self.stop_event.is_set() and self.slot - service.clock() > 0:
                    self.wait(min(self.slot - service.clock(), LEASE_SECONDS / 3))
                    if not self._heartbeat():
                        self.exit_reason = 'AUTOMATION_LEASE_LOST'
                        return
                if self.stop_event.is_set():
                    break
                now = service.clock()
                stalled = int((now - self.slot) // self.cadence)
                if stalled > 0:
                    self.missed += stalled  # the runtime was not scheduling: unobserved, never reconstructed
                    self.slot += stalled * self.cadence
                if not self._heartbeat():
                    self.exit_reason = 'AUTOMATION_LEASE_LOST'
                    return
                summary = {}
                try:
                    summary = service.run_cycle(scheduled=self.slot, missed=self.missed)
                    self.missed = 0
                    self.transient_failures = 0
                    if summary.get('skipped') and service._controller()['desired_state'] == 'STOPPED':
                        break
                except ValueError as exc:
                    if str(exc) != 'AUTOMATION_CYCLE_IN_PROGRESS':
                        self.exit_reason = _code(exc)
                        return
                    self.missed += 1
                except sqlite3.OperationalError as exc:
                    # Raised outside the cycle's own failure accounting (lease renewal, controller read or the
                    # cycle-owned write-back). That slot is unobserved, like a missed slot; nothing is backfilled.
                    self._transient(exc, 'CYCLE')
                    self.missed += 1
                done += 1
                finished = service.clock()
                interval = min(self.cadence, 60) if summary.get('close_retry_pending') else self.cadence
                steps = max(1, -int(-(finished - self.slot) // interval))  # first slot at or after the finish
                self.missed += steps - 1
                self.slot += steps * interval
        except Exception as exc:  # the worker died: say so in liveness instead of looking merely idle
            _record_worker_fault(service, exc, phase='WORKER_EXIT', transient=False, consecutive=self.transient_failures, slot=self.slot)
            self.exit_reason = 'WORKER_' + type(exc).__name__
            try:
                with service.control_lock:
                    current = service._controller()
                    current['last_error'] = dict(at=_iso(service.clock()), code=self.exit_reason)
                    service._save(current)
            except Exception:  # noqa: BLE001
                pass
            self.finished = True
        finally:
            self.finished = self.finished or max_cycles is None or self.stop_event.is_set() or self.exit_reason is not None
            if self.thread is not None and threading.current_thread() is self.thread:
                # Only the scheduling thread itself reports its end; a direct run() (tests, tools) never revives.
                try:
                    service._worker_ended(self)
                except Exception:  # noqa: BLE001 - reporting the end never raises from a finished worker
                    pass


def _record_worker_fault(service, exc, *, phase, transient, consecutive, slot):
    """Append one traceback with its lease context to the worker fault log. Never raises.

    Holds the exception class, its message (bounded), the stack, the owner, the lease expiry in memory and the
    slot; no environment, credential or request body is read."""
    try:
        from pathlib import Path
        path = Path(service._trace_log_path()).with_name('paper-automation-worker-errors.log')
        path.parent.mkdir(parents=True, exist_ok=True)
        header = dict(at=_iso(service.clock()), phase=phase, transient=transient, consecutive=consecutive,
                      exception=type(exc).__name__, message=str(exc)[:300], owner_id=getattr(service, 'owner_id', None),
                      slot=_iso(slot) if isinstance(slot, (int, float)) else None, thread=threading.current_thread().name)
        with path.open('a', encoding='utf-8') as log:
            log.write('=== ' + json.dumps(header, sort_keys=True) + '\n')
            log.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:  # noqa: BLE001 - the fault record never replaces the fault
        pass


def paper_automation_service(store):
    service = getattr(store, '_paper_automation_service', None)
    if not isinstance(service, PaperAutomationService):
        service = PaperAutomationService(store)
        store._paper_automation_service = service
    return service
