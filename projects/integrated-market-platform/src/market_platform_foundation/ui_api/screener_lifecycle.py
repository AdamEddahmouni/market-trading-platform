"""OCT1-10 trade lifecycle read model: one trader story from the existing authorities.

READ-ONLY DERIVED STATE. Every request re-derives the lifecycle from the
candidate runs, action decisions, reevaluation receipts, stop records and the
Paper ledger. Nothing is persisted, no model is called, no provider is asked
for evidence, and no order can be prepared or submitted from here.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from ..intelligence.inference.trade_lifecycle import (
    DEFAULT_CLOSED, LINEAGE_UNAVAILABLE, LIST_SCHEMA, MAX_ACTIVE, MAX_CLOSED, MAX_DECISIONS, MAX_PRIOR_EPISODES, MAX_SELECTED,
    MAX_TIMELINE, MAX_UNLINKED, SCHEMA, assign_decisions, candidate_identity, decision_view, entry_block, episodes_from_trades,
    evidence_view, exit_block, iso_ns, stage_of, timeline_rows,
)
from ..paper.ledger import CURRENT_MARK_QUALITIES
from ..risk.sma_trailing_stop import minor_to_display

_STOP_FIELDS = ('stop_state_id', 'policy_id', 'sma_window_bars', 'bar_interval', 'sma_value', 'active_stop', 'previous_stop', 'candidate_stop',
                'stop_as_of', 'last_updated_at', 'last_evaluated_at', 'distance_to_stop', 'distance_bps', 'reference_price', 'reference_as_of',
                'trigger_state', 'trigger_price', 'triggered_at', 'clamp_count', 'tighten_count', 'closed_at', 'closed_reason')


def _iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z')


class _Context:
    """One request's reads. Each canonical store is read once and never written."""

    def __init__(self, service, run_id):
        self.service, store = service, service.store
        self.ledger = ledger = store.paper_ledger
        self.account = ledger.paper_account_id
        self.now = service.clock()
        self.limitations = []
        self.deferred = bool(getattr(store, 'execution_deferred', False))
        self.scoped = bool(ledger.is_portfolio_scoped())
        self.scale = int(ledger.policy.get('price_scale', 100))
        self.currency = str(ledger.policy.get('currency', 'USD'))
        try:
            # The same current-mark projection the Paper portfolio read uses.
            from . import live_projections
            live_projections.apply_live_marks_to_ledger(store)
        except Exception:  # noqa: BLE001 — a mark that cannot refresh stays as the ledger last recorded it
            self.limitations.append('MARK_REFRESH_UNAVAILABLE')
        self.orders = ledger.project_orders()
        self.positions = None if self.deferred else {str(p['instrument_id']): p for p in ledger.project_positions() if p.get('quantity')}
        if self.scoped:
            trades = ledger.project_trades()
        else:
            trades = []
            self.limitations.append('PAPER_EXPERIMENT_REQUIRED')
        if self.deferred:
            self.limitations.append('POSITION_SNAPSHOT_UNAVAILABLE')
        self.episodes = episodes_from_trades(trades, account_id=self.account, experiment_id=ledger.experiment_id)
        self.by_instrument = {}
        for episode in self.episodes:
            self.by_instrument.setdefault(episode['instrument_id'], []).append(episode)
        self.run = self._ai_run(run_id) if run_id else None
        if run_id and self.run is None:
            self.limitations.append('CANDIDATE_RUN_NOT_FOUND')
        self._runs, self._assigned, self._cycles = {}, {}, None

    def _ai_run(self, run_id):
        run = self.service.actions.repository.get('candidate_run', run_id)
        return run if run and not run.get('origin') else None

    def run_record(self, run_id):
        if run_id not in self._runs:
            self._runs[run_id] = self.service.actions.repository.get('candidate_run', run_id) if run_id else None
        return self._runs[run_id]

    def origin_run(self, decision):
        """The AI Screener run a decision descends from, through its own run references only."""
        run = self.run_record((decision.get('evidence_snapshot') or {}).get('candidate_run_id'))
        hops = 0
        while run and run.get('origin') == 'REEVALUATION' and run.get('source_run_id') and hops < 8:
            run, hops = self.run_record(run['source_run_id']), hops + 1
        return run if run and not run.get('origin') else None

    def origin_id(self, decision):
        run = self.origin_run(decision)
        return run['run_id'] if run else None

    def assignment(self, instrument):
        if instrument not in self._assigned:
            chain = list(reversed(self.service.actions.history(instrument)))
            self._assigned[instrument] = (*assign_decisions(chain, self.by_instrument.get(instrument, []), self.origin_id), chain)
        return self._assigned[instrument]

    def cycles(self):
        """Reevaluation receipts indexed by the decision each transition appended."""
        if self._cycles is None:
            self._cycles = {}
            try:
                repository = self.service.reevaluation.repository
                loop = repository.latest_loop(self.account)
                for cycle in (repository.cycles(loop['loop_id'], limit=100) if loop else []):
                    for transition in cycle.get('transitions', []):
                        if transition.get('new_decision_id'):
                            self._cycles.setdefault(transition['new_decision_id'], dict(
                                cycle_id=cycle['cycle_id'], classification=transition.get('classification'), trigger=cycle.get('trigger')))
            except Exception:  # noqa: BLE001 — receipts are context; their absence never invents a transition
                self.limitations.append('REEVALUATION_HISTORY_UNAVAILABLE')
        return self._cycles


class TradeLifecycleService:
    def __init__(self, store, *, actions=None, stops=None, reevaluation=None, clock=time.time):
        self.store, self.clock = store, clock
        self._actions, self._stops, self._reevaluation = actions, stops, reevaluation

    @property
    def actions(self):
        if self._actions is None:
            from .screener_action import action_service
            self._actions = action_service(self.store)
        return self._actions

    @property
    def stops(self):
        if self._stops is None:
            from .paper_risk_control import risk_control_service
            self._stops = risk_control_service(self.store)
        return self._stops

    @property
    def reevaluation(self):
        if self._reevaluation is None:
            from .screener_reevaluation import reevaluation_service
            self._reevaluation = reevaluation_service(self.store)
        return self._reevaluation

    # --- blocks -----------------------------------------------------------------
    def _candidate(self, run, instrument, *, current):
        pick = next((p for p in run['candidates'] if p['instrument_id'] == instrument), None) if run else None
        packet = next((p for p in run['evidence'] if p['instrument']['instrument_id'] == instrument), None) if run else None
        if pick is None:
            return None, None, None
        return dict(
            selected=True, selected_in_current_run=current, rank=pick.get('rank'), run_id=run['run_id'], run_state=run.get('state'),
            selected_at=run.get('generated_at') or run.get('decision_cutoff'), decision_cutoff=run.get('decision_cutoff'),
            valid_until=run.get('valid_until'), rationale=pick.get('rationale'), uncertainties=list(pick.get('uncertainties') or [])[:8],
            provider_id=run.get('provider_id'), model_id=run.get('model_id'), prompt_id=run.get('prompt_id'),
            prompt_version=run.get('prompt_version'), simulated=bool(run.get('simulated')), lineage='CANDIDATE_RUN'), pick, packet

    def _snapshot_candidate(self, decision):
        """A candidate rebuilt from what its decision froze, when the run itself cannot be resolved."""
        snapshot = decision.get('evidence_snapshot') or {}
        selection = snapshot.get('selection') or {}
        return dict(
            selected=True, selected_in_current_run=False, rank=snapshot.get('candidate_rank'), run_id=snapshot.get('candidate_run_id'),
            run_state=None, selected_at=None, decision_cutoff=snapshot.get('cutoff'), valid_until=None, rationale=selection.get('rationale'),
            uncertainties=list(selection.get('uncertainties') or [])[:8], provider_id=None, model_id=None, prompt_id=None, prompt_version=None,
            simulated=False, lineage='DECISION_SNAPSHOT'), selection, snapshot.get('evidence')

    def _position(self, ctx, instrument, episode):
        if ctx.positions is None:
            return dict(state='UNAVAILABLE', quantity=None, mark=None), None
        if episode is not None and not episode['open']:
            return dict(state='FLAT', quantity=0, mark=None, closed=True), None
        row = ctx.positions.get(instrument)
        if row is None or (ctx.scoped and episode is None):
            return dict(state='FLAT', quantity=0, mark=None), None
        quality = str(row.get('mark_quality') or 'UNAVAILABLE').upper()
        as_of = row.get('mark_as_of_ns')
        mark = dict(
            price_minor=row.get('mark_minor'), as_of=iso_ns(as_of), source=row.get('mark_source') or row.get('mark_provider'),
            source_quality=quality, age_ms=max(0, int(ctx.now * 1000 - int(as_of) / 1e6)) if as_of else None,
            quality='UNAVAILABLE' if row.get('mark_minor') is None else 'CURRENT' if quality in CURRENT_MARK_QUALITIES
            else 'STALE' if quality in ('STALE', 'RESTORED', 'DISCONNECTED') else 'DEGRADED')
        short = row.get('side') == 'SHORT' or int(row['quantity']) < 0
        return dict(state='SHORT' if short else 'LONG', quantity=abs(int(row['quantity'])), average_entry_minor=row.get('average_fill_minor'),
                    first_entry_time=iso_ns(row.get('first_entry_time_ns')), latest_fill_time=iso_ns(row.get('latest_fill_time_ns')),
                    market_value_minor=row.get('market_value_minor'), mark=mark), row

    def _risk(self, ctx, instrument, episode, decisions):
        """OCT1-08 stop facts as that service projects them. No level is computed here."""
        ids = []
        for decision in decisions:
            for block in (decision.get('risk_control'), decision.get('server_exit')):
                if block and block.get('stop_state_id') and block['stop_state_id'] not in ids:
                    ids.append(block['stop_state_id'])
        for fill in (episode['fills'] if episode else []):
            for ref in fill.get('lineage_refs') or []:
                if ref.get('kind') == 'SMA_STOP_STATE' and ref.get('id') not in ids:
                    ids.append(ref['id'])
        base = dict(method='SMA_TRAILING_STOP', origin='DETERMINISTIC_RISK_CONTROL', model='none', reason_codes=[], policy=None, stop=None,
                    exit_decision_id=None, lineage='STOP_STATE')
        try:
            if episode is None or ctx.positions is None:
                configured = self.stops.config_view()
                return dict(base, status='NOT_APPLICABLE', configured=bool(configured.get('enabled')), lineage='NOT_APPLICABLE'), ids
            if episode['open']:
                status = self.stops.status(instrument)
                view = status.get('stop')
                if view and view.get('stop_state_id') and view['stop_state_id'] not in ids:
                    ids.append(view['stop_state_id'])
                policy = status.get('policy') or {}
                return dict(base, status=status['status'], configured=status['status'] != 'NOT_CONFIGURED', reason_codes=list(status.get('reason_codes') or []),
                            policy=dict(policy_id=policy.get('policy_id'), sma_window_bars=policy.get('sma_window_bars'),
                                        bar_interval=policy.get('bar_interval')) if policy else None,
                            stop={k: view.get(k) for k in _STOP_FIELDS} if view else None,
                            exit_decision_id=((view or {}).get('exit_decision') or {}).get('decision_id'),
                            monitoring=(status.get('monitoring') or {}).get('state')), ids
            state = next((s for s in (self.stops.repository.get('state', i) for i in reversed(ids)) if s), None)
            if state is None or state.get('account_id') != ctx.account or state.get('instrument_id') != instrument:
                # No stop record names this closed episode: it is not guessed from the ticker.
                return dict(base, status='NO_STOP_RECORD', configured=None, lineage=LINEAGE_UNAVAILABLE), ids
            view = self.stops._stop_view(state)
            return dict(base, status=state['status'], configured=True, reason_codes=list(state.get('reason_codes') or []),
                        policy=dict(policy_id=state.get('policy_id'), sma_window_bars=state.get('sma_window_bars'), bar_interval=state.get('bar_interval')),
                        stop={k: view.get(k) for k in _STOP_FIELDS}), ids
        except Exception:  # noqa: BLE001 — an unreadable stop is reported unavailable, never as a level
            return dict(base, status='UNAVAILABLE', configured=None, lineage=LINEAGE_UNAVAILABLE), ids

    def _stop_events(self, ctx, instrument, ids):
        if not ids:
            return []
        try:
            return [e for e in self.stops.repository.events(ctx.account, instrument, limit=100) if e.get('stop_state_id') in ids]
        except Exception:  # noqa: BLE001
            ctx.limitations.append('STOP_HISTORY_UNAVAILABLE')
            return []

    def _reevaluation_view(self):
        try:
            status = self.reevaluation.status()
        except Exception:  # noqa: BLE001
            return dict(worker_state='UNAVAILABLE', worker_label='Unavailable', requested_cadence_seconds=None, effective_cadence_seconds=None,
                        last_completed=None)
        return dict(worker_state=status.get('worker_state'), worker_label=status.get('worker_label'),
                    requested_cadence_seconds=status.get('requested_cadence_seconds'), effective_cadence_seconds=status.get('effective_cadence_seconds'),
                    last_completed=(status.get('liveness') or {}).get('last_completed'))

    def _experiment(self, ctx):
        if not ctx.scoped:
            return None
        from .paper_experiment import active_experiment
        record = active_experiment(self.store) or {}
        valuation = ctx.ledger.project_valuation()
        return dict(experiment_id=ctx.ledger.experiment_id, name=record.get('name'), status=record.get('status'), capital_kind='SIMULATED',
                    live_capital=False, execution='INTERNAL_SIMULATION' if ctx.ledger.execution_mode == 'INTERNAL_SIMULATION' else str(ctx.ledger.execution_mode),
                    market_data=str(ctx.ledger.data_mode), equity_minor=valuation.get('equity_minor'), cash_minor=valuation.get('cash_minor'),
                    valuation_quality=valuation.get('quality'))

    # --- one lifecycle ------------------------------------------------------------
    def _lifecycle(self, ctx, *, instrument, episode, run, group, detail):
        assigned, flat, unplaced, _ = ctx.assignment(instrument)
        limitations = []
        if episode is not None:
            decisions = assigned[episode['episode_id']]
            opening = next((d for d in decisions if d['decision_id'] == episode['opening_decision_id']), None)
            origin = ctx.origin_run(opening) if opening else None
        else:
            decisions = [d for d in flat if run is not None and ctx.origin_id(d) == run['run_id']]
            opening, origin = None, run
        if unplaced:
            limitations.append('DECISION_EPISODE_LINEAGE_UNAVAILABLE')
        # The newest run's selection describes a card in its own list only. A closed or
        # separately managed episode keeps the selection it was opened from.
        current_pick = next((p for p in run['candidates'] if p['instrument_id'] == instrument), None) if run and group == 'SELECTED' else None
        source = run if current_pick is not None else origin
        candidate, pick, packet = self._candidate(source, instrument, current=current_pick is not None)
        if candidate is None and opening is not None:
            candidate, pick, packet = self._snapshot_candidate(opening)
        if candidate is not None:
            candidate['evidence'] = evidence_view(packet, supporting=pick.get('supporting_refs') or [], conflicting=pick.get('conflicting_refs') or [],
                                                  weak=pick.get('weak_refs') or [], missing=pick.get('missing_capabilities') or [], detail=detail)
        now_ns = int(ctx.now * 1e9)
        entry = entry_block(decisions, episode, ctx.orders, now_ns=now_ns)
        exit_ = exit_block(decisions, episode, ctx.orders)
        position, row = self._position(ctx, instrument, episode)
        risk, stop_ids = self._risk(ctx, instrument, episode, decisions)
        latest = decisions[-1] if decisions else None
        if episode is None:
            pnl = dict(realized_minor=None, unrealized_minor=None, costs_minor=None, quality='NOT_APPLICABLE')
        else:
            mark = position.get('mark') or {}
            pnl = dict(realized_minor=episode['realized_pnl_minor'], costs_minor=episode['costs_minor'],
                       unrealized_minor=row.get('unrealized_pnl_minor') if row is not None and episode['open'] else None,
                       quality='REALIZED' if not episode['open'] else mark.get('quality') or 'UNAVAILABLE')
        pnl.update(currency=ctx.currency, basis='PAPER_LEDGER_FILLS', realized_includes_costs=True)
        valid_until = latest.get('valid_until') if latest else None
        expiry = None if valid_until is None else datetime.fromisoformat(valid_until.replace('Z', '+00:00')).timestamp()
        origin_id = origin['run_id'] if origin else None
        linked = episode is None or opening is not None
        lifecycle = dict(
            schema_version=SCHEMA, lifecycle_id=episode['episode_id'] if episode else candidate_identity(account_id=ctx.account, run_id=run['run_id'], instrument_id=instrument),
            kind='POSITION_EPISODE' if episode else 'CANDIDATE', group=group, instrument_id=instrument,
            symbol=(episode or {}).get('symbol') or ((packet or {}).get('instrument') or {}).get('symbol') or instrument,
            stage=stage_of(decisions, episode, entry, exit_), ai_selected=candidate is not None,
            position_origin=None if episode is None else 'AI_DECISION_GOVERNED' if linked else 'UNLINKED_PAPER_ACTIVITY',
            candidate=candidate, decision=decision_view(latest, detail=detail) if latest else None, entry=entry, position=position,
            risk_control=risk, exit=exit_, pnl=pnl,
            origin=dict(run_id=origin_id, same_as_current_run=bool(run and origin_id == run['run_id']),
                        lineage='CANDIDATE_RUN' if origin_id else 'NOT_APPLICABLE' if episode is None else LINEAGE_UNAVAILABLE),
            freshness=dict(projection='DERIVED_ON_READ', decision_valid_until=valid_until,
                           decision_current=None if expiry is None else expiry > ctx.now, mark_quality=(position.get('mark') or {}).get('quality')),
            lineage=dict(basis='PAPER_FILL_AND_DECISION_IDS' if episode else 'CANDIDATE_RUN_ID', account_id=ctx.account, experiment_id=ctx.ledger.experiment_id,
                         episode_id=episode['episode_id'] if episode else None, opening_fill_id=episode['opening_fill_id'] if episode else None,
                         opening_decision_id=episode['opening_decision_id'] if episode else None,
                         opening_basis=episode['opening_basis'] if episode else None, origin_run_id=origin_id, decision_count=len(decisions),
                         stop_state_ids=stop_ids, candidate=candidate['lineage'] if candidate else LINEAGE_UNAVAILABLE if episode else 'NOT_APPLICABLE'),
            limitations=limitations, as_of=_iso(ctx.now), currency=ctx.currency, price_scale=ctx.scale)
        if not detail:
            for block in (entry, exit_):
                block.pop('fills', None)
            return lifecycle
        fills = episode['fills'] if episode else []
        order_ids = {f.get('order_id') for f in fills}
        decision_ids = {d['decision_id'] for d in decisions}
        orders = [o for o in ctx.orders if o.get('order_id') in order_ids
                  or any(isinstance(r, dict) and r.get('code') == 'ACTION_DECISION' and r.get('label') in decision_ids
                         for r in ((o.get('decision_source_snapshot') or {}).get('reasons') or []))]
        cycles = ctx.cycles()
        selections = []
        for selected_run in (origin, source):
            chosen = next((p for p in selected_run['candidates'] if p['instrument_id'] == instrument), None) if selected_run else None
            if chosen is not None and all(selected_run['run_id'] != seen['run_id'] for seen, _ in selections):
                selections.append((selected_run, chosen))
        rows = timeline_rows(selections=selections, decisions=decisions,
                             cycle_of=cycles, stop_events=self._stop_events(ctx, instrument, stop_ids), orders=orders, fills=fills,
                             scale=ctx.scale, minor_display=minor_to_display)
        others = [e for e in ctx.by_instrument.get(instrument, []) if episode is None or e['episode_id'] != episode['episode_id']]
        lifecycle.update(
            decisions=[decision_view(d, detail=True) for d in decisions[-MAX_DECISIONS:]], decisions_truncated=max(0, len(decisions) - MAX_DECISIONS),
            timeline=rows[-MAX_TIMELINE:], timeline_truncated=max(0, len(rows) - MAX_TIMELINE),
            prior_episodes=[dict(lifecycle_id=e['episode_id'], open=e['open'], opened_at=iso_ns(e['fills'][0].get('fill_time_ns')),
                                 closed_at=iso_ns(e['fills'][-1].get('fill_time_ns')) if not e['open'] else None,
                                 realized_pnl_minor=e['realized_pnl_minor'], ai_selected=bool(e['opening_decision_id']))
                            for e in sorted(others, key=lambda e: e['opening_sequence'], reverse=True)[:MAX_PRIOR_EPISODES]],
            prior_episodes_truncated=max(0, len(others) - MAX_PRIOR_EPISODES),
            reevaluation=self._reevaluation_view(), experiment=self._experiment(ctx))
        return lifecycle

    def _linked(self, ctx, episode):
        """AI-governed only when the opening fill names a decision this account actually recorded."""
        if not episode['opening_decision_id']:
            return False
        record = self.actions.repository.get('decision', episode['opening_decision_id'])
        return bool(record and record['instrument_id'] == episode['instrument_id'] and record['position']['account_id'] == ctx.account)

    # --- reads --------------------------------------------------------------------
    def list(self, *, run_id=None, closed_limit=DEFAULT_CLOSED, closed_before=None):
        if run_id is not None and (not isinstance(run_id, str) or not run_id or len(run_id) > 120):
            raise ValueError('INVALID_LIFECYCLE_REQUEST')
        limit = max(0, min(int(closed_limit), MAX_CLOSED))
        ctx = _Context(self, run_id)
        open_by_instrument = {e['instrument_id']: e for e in ctx.episodes if e['open']}
        build = lambda **kw: self._lifecycle(ctx, detail=False, **kw)
        selected = [build(instrument=p['instrument_id'], episode=open_by_instrument.get(p['instrument_id']), run=ctx.run, group='SELECTED')
                    for p in (ctx.run['candidates'][:MAX_SELECTED] if ctx.run else [])]
        shown = {row['instrument_id'] for row in selected}
        active, unlinked = [], []
        for episode in sorted(open_by_instrument.values(), key=lambda e: e['opening_sequence'], reverse=True):
            if episode['instrument_id'] in shown:
                continue
            (active if self._linked(ctx, episode) else unlinked).append(episode)
        closed = sorted((e for e in ctx.episodes if not e['open']), key=lambda e: e['closing_sequence'], reverse=True)
        linked_closed = [e for e in closed if self._linked(ctx, e)]
        page = [e for e in linked_closed if closed_before is None or e['closing_sequence'] < int(closed_before)][:limit]
        unlinked.extend(e for e in closed if e not in linked_closed)
        episode_rows = lambda episodes, group: [build(instrument=e['instrument_id'], episode=e, run=ctx.run, group=group) for e in episodes]
        run = ctx.run
        return dict(
            schema_version=LIST_SCHEMA, as_of=_iso(ctx.now), account_id=ctx.account, experiment_id=ctx.ledger.experiment_id,
            currency=ctx.currency, price_scale=ctx.scale,
            run=dict(run_id=run['run_id'], state=run.get('state'), valid_until=run.get('valid_until'), generated_at=run.get('generated_at'),
                     selected_count=len(run['candidates'])) if run else None,
            selected=selected, active_managed=episode_rows(active[:MAX_ACTIVE], 'ACTIVE_MANAGED'),
            recent_closed=episode_rows(page, 'RECENT_CLOSED'), unlinked=episode_rows(unlinked[:MAX_UNLINKED], 'UNLINKED_PAPER_ACTIVITY'),
            counts=dict(selected=len(selected), active_managed=len(active), recent_closed=len(linked_closed), unlinked=len(unlinked)),
            next_closed_before=page[-1]['closing_sequence'] if page and len(page) == limit and page[-1] is not linked_closed[-1] else None,
            bounds=dict(selected=MAX_SELECTED, active_managed=MAX_ACTIVE, recent_closed=MAX_CLOSED, unlinked=MAX_UNLINKED),
            experiment=self._experiment(ctx), reevaluation=self._reevaluation_view(),
            market_data=str(ctx.ledger.data_mode), execution='SIMULATED_PAPER', limitations=list(dict.fromkeys(ctx.limitations)))

    def detail(self, lifecycle_id, *, run_id=None):
        if not isinstance(lifecycle_id, str) or not lifecycle_id or len(lifecycle_id) > 120 or \
                (run_id is not None and (not isinstance(run_id, str) or not run_id or len(run_id) > 120)):
            raise ValueError('INVALID_LIFECYCLE_REQUEST')
        ctx = _Context(self, run_id)
        episode = next((e for e in ctx.episodes if e['episode_id'] == lifecycle_id), None)
        instrument = episode['instrument_id'] if episode else None
        if episode is None and ctx.run is not None:
            instrument = next((p['instrument_id'] for p in ctx.run['candidates']
                               if candidate_identity(account_id=ctx.account, run_id=ctx.run['run_id'], instrument_id=p['instrument_id']) == lifecycle_id), None)
            # A candidate that has since been filled is its position episode now, never a flat card.
            episode = next((e for e in ctx.by_instrument.get(instrument, []) if e['open']), None) if instrument else None
        if instrument is None:
            raise ValueError('LIFECYCLE_NOT_FOUND')
        picked = bool(ctx.run and any(p['instrument_id'] == instrument for p in ctx.run['candidates']))
        group = 'SELECTED' if picked and (episode is None or episode['open']) else 'UNLINKED_PAPER_ACTIVITY' if not self._linked(ctx, episode) \
            else 'ACTIVE_MANAGED' if episode['open'] else 'RECENT_CLOSED'
        lifecycle = self._lifecycle(ctx, instrument=instrument, episode=episode, run=ctx.run, group=group, detail=True)
        lifecycle['limitations'] = list(dict.fromkeys([*lifecycle['limitations'], *ctx.limitations]))
        return lifecycle


def lifecycle_service(store):
    service = getattr(store, '_trade_lifecycle_service', None)
    if not isinstance(service, TradeLifecycleService):
        service = TradeLifecycleService(store)
        store._trade_lifecycle_service = service
    return service


__all__ = ['TradeLifecycleService', 'lifecycle_service']
