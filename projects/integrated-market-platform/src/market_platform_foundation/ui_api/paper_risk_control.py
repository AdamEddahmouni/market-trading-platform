"""OCT1-08 SMA trailing-stop monitor for open Paper positions.

One deterministic evaluation, used unchanged by Evaluate Stop Now and by the
OCT1-07 reevaluation cycle: position -> completed bars -> stop -> trigger.
A breach is recorded as a server risk fact and may be cited by a governed EXIT
decision. There is no order, preview or submission path here: this is a stop
monitor, not a resting broker stop order.
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from ..intelligence.inference.hashing import input_hash_from_dict
from ..local_state.sma_trailing_stop import sma_stop_repository
from ..market_data.freshness_contract import timestamp
from ..risk.sma_trailing_stop import (
    BREACH_CONDITION, INTERVAL_SECONDS, METHOD, REFERENCE_TEST_CONFIG, advance, build_policy, check_quote_trigger,
    close_state, event, initial_state, mark_stale, minor_to_display, normalize_bars, position_epoch, price_to_minor,
)

CONFIG_SCHEMA = 'sma-stop-config/1.0.0'
STATUS_SCHEMA = 'sma-stop-status/1.0.0'
HISTORY_SCHEMA = 'sma-stop-history/1.0.0'
RUN_SCHEMA = 'risk-control-candidate-run/1.0.0'
BAR_SOURCE = 'MOOMOO_OPEND_CUR_KLINE_1M'
_USABLE_SERIES = ('CURRENT', 'SESSION_CLOSED')


def _iso_ns(value):
    return datetime.fromtimestamp(value / 1e9, UTC).isoformat().replace('+00:00', 'Z') if value is not None else None


def quote_from_candidate(candidate, now, scale=100):
    """The same current last-trade quote fact the action policy admits; nothing else."""
    from ..intelligence.inference.action_decision import _current
    for e in candidate['current_market_evidence']:
        price = e['facts'].get('price') if e['capability'] == 'QUOTE' and e['role'] == 'CURRENT_MARKET' else None
        if isinstance(price, (int, float)) and price > 0:
            observed = timestamp(e.get('as_of'))
            if observed and _current(e, now):
                return dict(admissible=True, price_minor=price_to_minor(price, scale), as_of_ns=int(observed.timestamp() * 1e9),
                            source=e.get('source'), evidence_ref=e['evidence_id'], reason=None)
            return dict(admissible=False, reason='QUOTE_STALE_OR_UNAVAILABLE', source=e.get('source'))
    return dict(admissible=False, reason='QUOTE_STALE_OR_UNAVAILABLE', source=None)


def _provider_quote(instrument, scale):
    from .screener_projections import screener_service
    view = screener_service().quote_for(instrument)
    field = (view.get('fields') or {}).get('price') or {}
    if view.get('state') != 'LIVE' or field.get('value') is None:
        return dict(admissible=False, reason=view.get('reason') or 'QUOTE_' + str(view.get('state')), source=field.get('source'))
    return dict(admissible=True, price_minor=price_to_minor(field['value'], scale), as_of_ns=int(field['as_of_ns']),
                source=field.get('source'), evidence_ref=None, reason=None)


def _provider_bars(instrument, policy, scale):
    """Completed provider bars only; the forming bar is never read."""
    from ..market_data.current_bars import current_bars_service
    series = current_bars_service().read(instrument, timeframe=policy['bar_interval'], scope=policy['session_scope'])
    bars = [dict(bar_id=f"{BAR_SOURCE}:{instrument}:{policy['bar_interval']}:{b.end_ns}", event_time=b.start_ns, available_time=b.end_ns,
                 open=price_to_minor(b.open, scale), high=price_to_minor(b.high, scale), low=price_to_minor(b.low, scale),
                 close=price_to_minor(b.close, scale)) for b in series.bars]
    return dict(state=series.state, reason=series.provider_reason or series.reason, source=BAR_SOURCE, bars=bars)


class SmaStopService:
    def __init__(self, store, *, repository=None, clock=time.time, bars=None, quotes=None, actions=None, ai=None):
        self.store = store
        self.repository = repository or sma_stop_repository()
        self.clock = clock
        self._bars, self._quotes, self._actions, self._ai = bars or _provider_bars, quotes or _provider_quote, actions, ai
        self.lock = threading.RLock()

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

    def _scale(self):
        return int(self.store.paper_ledger.policy.get('price_scale', 100))

    def _config(self):
        config = self.repository.get('config', self._account())
        policy = self.repository.get('policy', config['policy_id']) if config else None
        return config, policy

    def _position(self, instrument):
        """Ledger truth. Quantity is never owned by the stop."""
        if getattr(self.store, 'execution_deferred', False):
            return None
        rows = [p for p in self.store.paper_ledger.project_positions() if p['instrument_id'] == instrument and p.get('quantity')]
        if len(rows) > 1:
            raise ValueError('AMBIGUOUS_POSITION')
        if not rows:
            return dict(state='FLAT', quantity=0, symbol=None)
        short = rows[0].get('side') == 'SHORT' or rows[0]['quantity'] < 0
        return dict(state='SHORT' if short else 'LONG', quantity=abs(int(rows[0]['quantity'])), symbol=rows[0].get('symbol'))

    def _epoch(self, instrument, side, watch):
        ledger = self.store.paper_ledger
        found = position_epoch(ledger.events, account_id=ledger.paper_account_id, session_id=ledger.session_id,
                               instrument_id=instrument, side=side)
        if found:
            return found
        # A projected position with no fill lineage (restored or fixture ledgers): the
        # episode is counted from the flat/reversal observations this monitor made.
        lineage = dict(account=ledger.paper_account_id, session=ledger.session_id, instrument=instrument, side=side,
                       generation=watch['generation'])
        return dict(position_epoch_id='PE-' + input_hash_from_dict(lineage)[:32], epoch_basis='LEDGER_POSITION_WITHOUT_FILL_LINEAGE',
                    opened_at_ns=None, opening_fill_id=None)

    # --- operator configuration ---------------------------------------------------
    def configure(self, body):
        """Bounded parameters only: enabled, window, interval. No formulas, no levels."""
        if not isinstance(body, dict) or set(body) - {'enabled', 'sma_window_bars', 'bar_interval'} or type(body.get('enabled')) is not bool:
            raise ValueError('INVALID_STOP_CONFIG')
        with self.lock:
            now = self.clock()
            now_ns, account = int(now * 1e9), self._account()
            config, current = self._config()
            states = self.repository.open_states(account)
            if not body['enabled']:
                if set(body) != {'enabled'}:
                    raise ValueError('INVALID_STOP_CONFIG')
                if config is None:
                    raise ValueError('STOP_NOT_CONFIGURED')
                for state in states:
                    closing = []
                    self._save(close_state(state, 'OPERATOR_DISABLED', now_ns, closing), closing)
                self.repository.put('config', account, dict(config, enabled=False, updated_at=_iso_ns(now_ns)), updated_at=now_ns)
                return self.config_view()
            policy = build_policy(sma_window_bars=body.get('sma_window_bars', REFERENCE_TEST_CONFIG['sma_window_bars']),
                                  bar_interval=body.get('bar_interval', REFERENCE_TEST_CONFIG['bar_interval']), created_at=_iso_ns(now_ns))
            changed = bool(config and config['enabled'] and config['policy_id'] != policy['policy_id'])
            if changed:
                active = [s for s in states if s['active_stop'] is not None]
                if active:
                    # A methodology change never silently replaces a working stop.
                    for state in active:
                        self.repository.append_events([event(state, 'POLICY_CHANGE_REJECTED', now_ns, requested_policy_id=policy['policy_id'])],
                                                      account_id=account, instrument_id=state['instrument_id'])
                    raise ValueError('STOP_POLICY_CHANGE_REJECTED_WHILE_ACTIVE')
                for state in states:
                    closing = []
                    self._save(close_state(state, 'POLICY_REPLACED_BEFORE_ACTIVATION', now_ns, closing), closing)
            if self.repository.get('policy', policy['policy_id']) is None:
                self.repository.put('policy', policy['policy_id'], policy, updated_at=now_ns)
            self.repository.put('config', account, dict(schema_version=CONFIG_SCHEMA, account_id=account, enabled=True,
                                                        policy_id=policy['policy_id'], enabled_at=_iso_ns(now_ns), updated_at=_iso_ns(now_ns)),
                                updated_at=now_ns)
            return self.config_view()

    def config_view(self):
        config, policy = self._config()
        return dict(schema_version=CONFIG_SCHEMA, configured=config is not None, enabled=bool(config and config['enabled']),
                    policy=policy, reference_config=dict(REFERENCE_TEST_CONFIG, label='REFERENCE_TEST_CONFIG',
                                                         note='Reference software-evaluation configuration. Not optimized, calibrated or recommended.'),
                    bounds=dict(sma_window_bars=[2, 200], bar_interval=sorted(INTERVAL_SECONDS, key=INTERVAL_SECONDS.get)),
                    durability=self.repository.durability)

    def _save(self, state, events):
        now_ns = max(state.get('last_evaluated_at') or 0, state.get('closed_at') or 0)
        self.repository.put('state', state['stop_state_id'], state, updated_at=now_ns)
        self.repository.append_events(events, account_id=state['account_id'], instrument_id=state['instrument_id'])

    # --- the single deterministic evaluation ------------------------------------------
    def evaluate(self, instrument, *, quote=None):
        """Advance the stop from completed bars, then test the current price against it."""
        if not isinstance(instrument, str) or not instrument or len(instrument) > 120:
            raise ValueError('INVALID_STOP_REQUEST')
        with self.lock:
            config, policy = self._config()
            if not config or not config['enabled']:
                return self.status(instrument)
            now_ns, account, scale = int(self.clock() * 1e9), self._account(), self._scale()
            ledger = self.store.paper_ledger
            position = self._position(instrument)
            if position is None:
                return self.status(instrument)  # deferred ledger: nothing is inferred about the position
            watch_id = account + '|' + instrument
            watch = self.repository.get('watch', watch_id) or dict(account_id=account, instrument_id=instrument, generation=0,
                                                                   last_position_state=None, last_evaluated_at_ns=None)
            state, events = self.repository.latest_state(account, instrument), []
            if watch['last_position_state'] not in (None, 'FLAT', position['state']):
                watch['generation'] += 1  # the observed episode ended: flat or reversed
            observed_flat = watch['last_position_state'] == 'FLAT'
            watch.update(last_position_state=position['state'], last_evaluated_at_ns=now_ns)
            if position['state'] == 'FLAT':
                if state:
                    self._save(dict(close_state(state, 'POSITION_FLAT', now_ns, events), last_evaluated_at=now_ns), events)
                self.repository.put('watch', watch_id, watch, updated_at=now_ns)
                return self.status(instrument)
            epoch = self._epoch(instrument, position['state'], watch)
            if state and (state['position_epoch_id'] != epoch['position_epoch_id'] or state['side'] != position['state'] or state['policy_id'] != policy['policy_id']):
                reason = 'POSITION_REVERSED' if state['side'] != position['state'] else \
                    'POSITION_EPOCH_CHANGED' if state['position_epoch_id'] != epoch['position_epoch_id'] else 'POLICY_CHANGED'
                closing = []
                self._save(dict(close_state(state, reason, now_ns, closing), last_evaluated_at=now_ns), closing)
                state = None
            if state is None:
                opened = epoch['opened_at_ns']
                enabled_at = timestamp(config['enabled_at'])
                watched = observed_flat or (opened is not None and enabled_at is not None and int(enabled_at.timestamp() * 1e9) <= opened)
                state = initial_state(account_id=account, session_id=ledger.session_id, instrument_id=instrument,
                                      position_epoch_id=epoch['position_epoch_id'], epoch_basis=epoch['epoch_basis'],
                                      side=position['state'], quantity=position['quantity'], policy=policy, activated_at=now_ns,
                                      activation_reason='POSITION_OPENED' if watched else 'LATE_ACTIVATION', price_scale=scale)
                prior = self.repository.latest_state(account, instrument, open_only=False)
                if prior and prior['position_epoch_id'] == epoch['position_epoch_id'] and prior['side'] == state['side'] \
                        and prior['active_stop'] is not None and prior.get('closed_reason') != 'POSITION_FLAT':
                    # Disable/re-enable on the same position cannot be used to loosen protection.
                    state.update(active_stop=prior['active_stop'], effective_after_ns=now_ns, carried_from=prior['stop_state_id'])
                events.append(event(state, 'EPISODE_STARTED', now_ns, activation_reason=state['activation_reason'],
                                    carried_from=state.get('carried_from')))
            gap_after = max(5 * INTERVAL_SECONDS[policy['bar_interval']], 300) * 1_000_000_000
            unobserved = state['last_evaluated_at'] is not None and now_ns - state['last_evaluated_at'] > gap_after
            if unobserved:
                # Downtime stays downtime: no stop update is reconstructed for it.
                events.append(event(state, 'MONITORING_GAP', now_ns, liveness='NOT_OBSERVED', observed_from_ns=state['last_evaluated_at'],
                                    observed_to_ns=now_ns, updates_backfilled=0))
            series = self._bars(instrument, policy, scale)
            try:
                normalized = normalize_bars(series['bars'], cutoff_ns=now_ns, interval=policy['bar_interval'])
            except ValueError as exc:
                normalized, series = None, dict(series, state='BLOCKED', reason=str(exc))
            if state['status'] not in ('BREACHED', 'CLOSED'):
                if normalized is not None and series['state'] in _USABLE_SERIES:
                    state, advanced = advance(state, normalized['bars'], policy, latest_only=unobserved)
                    events.extend(advanced)
                if series['state'] != 'CURRENT':
                    state = mark_stale(state, series.get('reason') or 'BAR_SOURCE_' + str(series['state']), events, at_ns=now_ns)
                quote = quote if quote is not None else self._quotes(instrument, scale)
                state = check_quote_trigger(state, quote, events=events)
                state['last_observation'] = dict(admissible=bool(quote.get('admissible')), price_minor=quote.get('price_minor'),
                                                 as_of_ns=quote.get('as_of_ns'), source=quote.get('source'), reason=quote.get('reason'))
            state.update(quantity=position['quantity'], last_evaluated_at=now_ns)
            state['bar_source'] = dict(state=series['state'], reason=series.get('reason'), source=series.get('source'),
                                       excluded=normalized['excluded'] if normalized else None)
            self._save(state, events)
            self.repository.put('watch', watch_id, watch, updated_at=now_ns)
            return self.status(instrument)

    def open_instruments(self):
        config, _ = self._config()
        if not config or not config['enabled']:
            return []
        return sorted({s['instrument_id'] for s in self.repository.open_states(self._account())})

    # --- reads ----------------------------------------------------------------------
    def decision_facts(self, instrument):
        """Stable read-only stop facts for the action decision layer. No clocks that tick."""
        config, _ = self._config()
        if not config or not config['enabled']:
            return None
        state = self.repository.latest_state(self._account(), instrument)
        if state is None:
            return None
        scale = state['price_scale']
        facts = dict(method=METHOD, status=state['status'], side=state['side'], policy_id=state['policy_id'],
                     stop_state_id=state['stop_state_id'], position_epoch_id=state['position_epoch_id'],
                     sma_window_bars=state['sma_window_bars'], bar_interval=state['bar_interval'],
                     active_stop=minor_to_display(state['active_stop'], scale), previous_stop=minor_to_display(state['previous_stop'], scale),
                     authority='SERVER_RISK_CONTROL')
        if state['status'] == 'BREACHED':
            facts.update(trigger_price=minor_to_display(state['trigger_price'], scale), triggered_at=_iso_ns(state['triggered_at']),
                         trigger_evidence=state['trigger_evidence'], reason_codes=state['reason_codes'])
        return facts

    def _exit_decision(self, state):
        for record in self.actions.history(state['instrument_id']):
            if (record.get('server_exit') or {}).get('stop_state_id') == state['stop_state_id']:
                return record
        return None

    def _monitoring(self, state, now_ns, policy):
        from .screener_reevaluation import reevaluation_service
        try:
            worker = reevaluation_service(self.store).status()['worker_state']
        except Exception:
            worker = 'UNKNOWN'
        last = state['last_evaluated_at'] if state else None
        gap_after = max(5 * INTERVAL_SECONDS[policy['bar_interval']], 300) * 1_000_000_000
        return dict(state='RUNNING' if worker in ('RUNNING', 'DELAYED') else 'NOT_RUNNING', worker_state=worker,
                    last_evaluated_at=_iso_ns(last),
                    liveness='NOT_OBSERVED' if last is not None and now_ns - last > gap_after else 'OBSERVED' if last is not None else 'NEVER_EVALUATED')

    def status(self, instrument):
        """Read-only projection of the persisted stop state. Never advances or triggers."""
        if not isinstance(instrument, str) or not instrument or len(instrument) > 120:
            raise ValueError('INVALID_STOP_REQUEST')
        config, policy = self._config()
        now_ns, account = int(self.clock() * 1e9), self._account()
        base = dict(schema_version=STATUS_SCHEMA, instrument_id=instrument, account_id=account, method=METHOD,
                    durability=self.repository.durability, paper_execution='MANUAL_ONLY', paper_close='NOT_SUBMITTED',
                    live_execution='UNCHANGED', order_type='NONE_STOP_MONITOR_ONLY', evaluated_at=_iso_ns(now_ns), policy=policy)
        position = self._position(instrument)
        base['position'] = dict(state=position['state'], quantity=position['quantity']) if position else None
        if not config or not config['enabled']:
            return dict(base, status='NOT_CONFIGURED', reason_codes=['STOP_NOT_CONFIGURED' if not config else 'STOP_DISABLED'], stop=None)
        state = self.repository.latest_state(account, instrument, open_only=False)
        if position is None:
            return dict(base, status='BLOCKED', reason_codes=['POSITION_SNAPSHOT_UNAVAILABLE'], stop=self._stop_view(state) if state else None,
                        monitoring=self._monitoring(state, now_ns, policy))
        if state is None or (state['status'] == 'CLOSED' and position['state'] != 'FLAT'):
            return dict(base, status='WARMING_UP' if position['state'] != 'FLAT' else 'CLOSED',
                        reason_codes=['NOT_YET_EVALUATED'] if position['state'] != 'FLAT' else ['NO_OPEN_POSITION'], stop=None,
                        monitoring=self._monitoring(None, now_ns, policy))
        view = self._stop_view(state)
        decision = self._exit_decision(state) if state['status'] == 'BREACHED' else None
        view['exit_decision'] = dict(decision_id=decision['decision_id'], action_state=decision['action_state'],
                                     execution_readiness=decision['execution_readiness'], blocker_codes=decision['blocker_codes'],
                                     decision_time=decision['decision_time']) if decision else None
        return dict(base, status=state['status'], reason_codes=state['reason_codes'], stop=view,
                    monitoring=self._monitoring(state, now_ns, policy))

    @staticmethod
    def _stop_view(state):
        scale = state['price_scale']
        show = lambda key: minor_to_display(state.get(key), scale)
        evidence = state.get('trigger_evidence') or {}
        observed = state.get('last_observation') or {}
        reference = observed.get('price_minor') if observed.get('admissible') else None
        distance = abs(reference - state['active_stop']) if reference is not None and state['active_stop'] is not None else None
        return dict(
            stop_state_id=state['stop_state_id'], position_epoch_id=state['position_epoch_id'], epoch_basis=state['epoch_basis'],
            side=state['side'], quantity=state['quantity'], policy_id=state['policy_id'], sma_window_bars=state['sma_window_bars'],
            bar_interval=state['bar_interval'], config_label=state['config_label'], activated_at=_iso_ns(state['activated_at']),
            activation_reason=state['activation_reason'], sma_value=state['sma_value'], candidate_stop=show('candidate_stop'),
            active_stop=show('active_stop'), previous_stop=show('previous_stop'), stop_as_of=_iso_ns(state['stop_as_of']),
            bar_id=state['bar_id'], bar_available_at=_iso_ns(state['bar_available_at_ns']), bars_available=state['bars_available'],
            last_updated_at=_iso_ns(state['last_updated_at']), last_evaluated_at=_iso_ns(state['last_evaluated_at']),
            update_count=state['update_count'], tighten_count=state['tighten_count'], clamp_count=state['clamp_count'],
            trigger_state=state['trigger_state'], trigger_reason_codes=state['trigger_reason_codes'],
            triggered_at=_iso_ns(state['triggered_at']), trigger_price=show('trigger_price'),
            trigger_evidence=dict(kind=evidence.get('kind'), basis=evidence.get('basis'), source=evidence.get('source'),
                                  evidence_ref=evidence.get('evidence_ref'), bar_id=evidence.get('bar_id'),
                                  as_of=_iso_ns(evidence.get('as_of_ns'))) if evidence else None,
            trigger_basis='LAST_TRADE_PRICE', bar_source=state.get('bar_source'), carried_from=state.get('carried_from'),
            closed_at=_iso_ns(state.get('closed_at')), closed_reason=state.get('closed_reason'),
            reference_price=minor_to_display(reference, scale), reference_as_of=_iso_ns(observed.get('as_of_ns')),
            reference_basis='LAST_TRADE_PRICE', distance_to_stop=minor_to_display(distance, scale),
            distance_bps=round(distance * 10000 / reference, 1) if distance is not None else None)

    def history(self, instrument, *, limit=20, before=None):
        """Bounded, newest first. Never the whole per-minute stop record in one response."""
        if not isinstance(instrument, str) or not instrument or len(instrument) > 120:
            raise ValueError('INVALID_STOP_REQUEST')
        bounded = max(1, min(int(limit), 100))
        rows = self.repository.events(self._account(), instrument, limit=bounded, before=before)
        scale = self._scale()
        for row in rows:
            for key in ('candidate_stop', 'active_stop', 'previous_stop', 'trigger_price'):
                row[key] = minor_to_display(row.get(key), scale)
            row['at'] = _iso_ns(row.pop('at_ns'))
        return dict(schema_version=HISTORY_SCHEMA, instrument_id=instrument, events=rows,
                    next_before=rows[-1]['sequence'] if len(rows) >= bounded else None,
                    total=self.repository.event_count(self._account(), instrument), durability=self.repository.durability)

    # --- explicit operator action ------------------------------------------------------
    def evaluate_now(self, body):
        """Evaluate Stop Now. On a breach, append the deterministic EXIT decision; never an order."""
        if not isinstance(body, dict) or set(body) != {'instrument_id'}:
            raise ValueError('INVALID_STOP_REQUEST')
        result = self.evaluate(body['instrument_id'])
        if result['status'] == 'BREACHED' and not result['stop']['exit_decision']:
            try:
                self.record_exit(body['instrument_id'])
            except ValueError as exc:
                return dict(self.status(body['instrument_id']), exit_decision_error=str(exc)[:64])
            result = self.status(body['instrument_id'])
        return result

    def record_exit(self, instrument):
        """Server-authored EXIT through the unchanged OCT1-06 append path. No model call."""
        from ..intelligence.inference.reevaluation import reevaluation_pick
        state = self.repository.latest_state(self._account(), instrument)
        if not state or state['status'] != 'BREACHED':
            raise ValueError('STOP_NOT_BREACHED')
        existing = self._exit_decision(state)
        if existing:
            return existing
        position = self._position(instrument) or {}
        scope = self.ai._query(dict(universe='US_EQUITIES', search=str(position.get('symbol') or instrument)[:120], filters=[]))
        _, candidates, now, _ = self.ai._packet(scope, include_flow=True)
        candidate = next((c for c in candidates if c['instrument']['instrument_id'] == instrument), None)
        if candidate is None:
            raise ValueError('STOP_EXIT_EVIDENCE_UNAVAILABLE')
        deadlines = [timestamp(e['valid_until']).timestamp() for e in (*candidate['current_market_evidence'], *candidate['reference_evidence']) if timestamp(e.get('valid_until'))]
        digest = input_hash_from_dict(dict(candidate=candidate, stop_state=state['stop_state_id'], cutoff=now))
        horizon = datetime.fromtimestamp(min([timestamp(now).timestamp() + 1800, *deadlines]), UTC).isoformat().replace('+00:00', 'Z')
        run = dict(schema_version=RUN_SCHEMA, run_id='RK-' + digest[:40], origin='RISK_CONTROL', state='CURRENT', decision_cutoff=now,
                   generated_at=now, scope=scope, input_hash=digest, source_run_id=None, valid_until=horizon, evidence=[candidate],
                   candidates=[reevaluation_pick(candidate, 0)], limitations=[], simulated=False)
        self.actions.repository.put('candidate_run', run['run_id'], run)
        return self.actions.run(dict(run_id=run['run_id'], instrument_id=instrument))


def risk_control_service(store):
    service = getattr(store, '_sma_stop_service', None)
    if not isinstance(service, SmaStopService):
        service = SmaStopService(store)
        store._sma_stop_service = service
    return service


__all__ = ['BREACH_CONDITION', 'SmaStopService', 'quote_from_candidate', 'risk_control_service']
