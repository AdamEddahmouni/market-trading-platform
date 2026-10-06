"""OCT1-10 trade lifecycle derivation: pure, read-only, no clocks and no I/O.

Everything here re-reads records other authorities already wrote: candidate
runs, action decisions, Paper fills and stop events. Nothing is decided,
priced or accounted for here. Records are joined by their own identifiers
only; a shared ticker never joins two records.
"""
from __future__ import annotations

from datetime import UTC, datetime

from .hashing import input_hash_from_dict

SCHEMA = 'trade-lifecycle/1.0.0'
LIST_SCHEMA = 'trade-lifecycle-list/1.0.0'
LINEAGE_UNAVAILABLE = 'LINEAGE_UNAVAILABLE'

MAX_SELECTED = 5
MAX_ACTIVE = 25
MAX_UNLINKED = 10
MAX_CLOSED = 20
DEFAULT_CLOSED = 5
MAX_EVIDENCE = 8
MAX_TIMELINE = 200
MAX_DECISIONS = 50
MAX_PRIOR_EPISODES = 5

ENTRY_STATES = ('NOT_PROPOSED', 'CONSIDERED', 'DECIDED_ENTER', 'SUBMITTED_PAPER', 'PARTIALLY_FILLED', 'FILLED', 'BLOCKED', 'EXPIRED')
EXIT_STATES = ('NO_EXIT', 'EXIT_DECIDED', 'EXIT_SUBMITTED', 'PARTIALLY_CLOSED', 'CLOSED', 'BLOCKED')
STAGES = ('SELECTED_NOT_ASSESSED', 'NO_ACTION', 'CONSIDERING_ENTRY', 'ENTER_NOT_EXECUTED', 'ENTRY_SUBMITTED', 'REVALIDATION_REQUIRED',
          'POSITION_OPEN', 'EXIT_NOT_EXECUTED', 'EXIT_SUBMITTED', 'POSITION_CLOSED')
ORIGINS = ('AI_PROPOSAL_SERVER_GATED', 'DETERMINISTIC_RISK_CONTROL', 'SERVER_FAILSAFE')
_TERMINAL_ORDER_STATES = ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'RISK_REJECTED')
_STOP_LABELS = dict(
    EPISODE_STARTED='SMA stop monitoring started', ACTIVATED='SMA stop activated', TIGHTENED='SMA stop tightened',
    CLAMPED='SMA stop held by monotonic clamp', STALE='SMA stop update stale', RESUMED='SMA stop updates resumed',
    BREACHED='SMA trailing stop breached', CLOSED='SMA stop closed', MONITORING_GAP='SMA stop monitoring gap',
    POLICY_CHANGE_REJECTED='SMA stop policy change rejected')
# Same-instant rows read in causal order: a stop breach precedes the exit it causes,
# a decision precedes its order, an order precedes its fill.
_KIND_RANK = dict(CANDIDATE_SELECTED=0, STOP=1, DECISION=2, PAPER_ORDER=3, PAPER_FILL=4)


def iso_ns(value):
    return datetime.fromtimestamp(int(value) / 1e9, UTC).isoformat().replace('+00:00', 'Z') if value is not None else None


def ns_of(value):
    """Nanoseconds of an ISO instant, or None. Never a substituted 'now'."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return int(parsed.timestamp() * 1e9)


def episode_identity(*, account_id, experiment_id, instrument_id, opening_fill_id):
    return 'TE-' + input_hash_from_dict(dict(account=account_id, experiment=experiment_id, instrument=instrument_id, opening_fill=opening_fill_id))[:32]


def candidate_identity(*, account_id, run_id, instrument_id):
    return 'LC-' + input_hash_from_dict(dict(account=account_id, run=run_id, instrument=instrument_id))[:32]


def episodes_from_trades(trades, *, account_id, experiment_id):
    """Position episodes from the ledger's own fill rows, in ledger sequence.

    An episode opens on the fill the ledger classified OPEN and ends on the
    next CLOSE of the same instrument. Its identity is the opening fill, so two
    trades of one instrument are never the same episode.
    """
    current, episodes = {}, []

    def start(fill, basis):
        episode = dict(
            episode_id=episode_identity(account_id=account_id, experiment_id=experiment_id, instrument_id=fill['instrument_id'], opening_fill_id=fill['fill_id']),
            instrument_id=fill['instrument_id'], symbol=fill.get('symbol') or fill['instrument_id'], fills=[], open=True,
            opening_fill_id=fill['fill_id'], opening_basis=basis, opening_sequence=fill['sequence'],
            side='LONG' if fill['position_after'] > 0 else 'SHORT')
        episodes.append(episode)
        current[fill['instrument_id']] = episode
        return episode

    for fill in sorted(trades, key=lambda row: row['sequence']):
        instrument, effect = fill['instrument_id'], fill['position_effect']
        episode = current.get(instrument)
        if effect == 'REVERSE' and episode is not None:
            # One fill both ends the old side and begins the new one.
            episode['fills'].append(fill); episode['open'] = False
            start(fill, 'LEDGER_REVERSE_FILL')['fills'].append(fill)
            continue
        if effect == 'OPEN' or episode is None:
            episode = start(fill, 'LEDGER_OPEN_FILL' if effect == 'OPEN' else LINEAGE_UNAVAILABLE)
        episode['fills'].append(fill)
        if effect == 'CLOSE':
            episode['open'] = False
            current.pop(instrument, None)
    for episode in episodes:
        fills = episode['fills']
        entries = [f for f in fills if f['position_effect'] in ('OPEN', 'ADD') or (f['position_effect'] == 'REVERSE' and f is fills[0])]
        exits = [f for f in fills if f not in entries]
        episode.update(
            entry_fills=entries, exit_fills=exits,
            opening_decision_id=fills[0].get('decision_id') if episode['opening_basis'] != LINEAGE_UNAVAILABLE else None,
            closing_decision_id=exits[-1].get('decision_id') if exits and not episode['open'] else None,
            closing_sequence=fills[-1]['sequence'] if not episode['open'] else None,
            # A reversing fill realizes the side it ended, not the side it began.
            realized_pnl_minor=sum(int(f['realized_pnl_delta_minor']) for f in fills
                                   if not (f is fills[0] and episode['opening_basis'] == 'LEDGER_REVERSE_FILL')),
            costs_minor=sum(int(f['costs_minor']) for f in fills))
    return episodes


def assign_decisions(chain, episodes, origin_id):
    """Place one instrument's decision chain (oldest first) on its episodes.

    A decision belongs to an episode because a fill of that episode names it,
    or because it sits on the predecessor chain between that episode's opening
    and its close. Flat decisions stay with their candidate, not with a trade.
    """
    opening = {e['opening_decision_id']: e for e in episodes if e['opening_decision_id']}
    owner = {f['decision_id']: e for e in episodes for f in e['fills'] if f.get('decision_id')}
    assigned = {e['episode_id']: [] for e in episodes}
    flat, unplaced, current = [], [], None
    for decision in chain:
        identifier = decision['decision_id']
        if identifier in opening:
            episode = opening[identifier]
            origin = origin_id(decision)
            lead = []
            while flat and origin is not None and origin_id(flat[-1]) == origin:
                lead.insert(0, flat.pop())
            assigned[episode['episode_id']].extend([*lead, decision])
            current = episode
        elif identifier in owner:
            episode = owner[identifier]
            assigned[episode['episode_id']].append(decision)
            current = None if identifier == episode['closing_decision_id'] else episode
        elif decision['position']['state'] == 'FLAT':
            current = None
            flat.append(decision)
        elif current is not None:
            assigned[current['episode_id']].append(decision)
        else:
            unplaced.append(decision)
    if unplaced and len(episodes) == 1:
        # One position episode exists for this instrument and account: a
        # positioned decision can only describe it.
        assigned[episodes[0]['episode_id']] = sorted([*assigned[episodes[0]['episode_id']], *unplaced], key=lambda d: chain.index(d))
        unplaced = []
    return assigned, flat, unplaced


def authority_of(decision):
    if decision.get('server_exit') or (decision.get('model') or {}).get('origin') == 'SERVER_RISK_CONTROL':
        return 'DETERMINISTIC_RISK_CONTROL'
    return 'AI_PROPOSAL_SERVER_GATED' if decision.get('model_proposal') else 'SERVER_FAILSAFE'


def _fact_text(item):
    facts = item.get('facts') if isinstance(item.get('facts'), dict) else {}
    if facts.get('headline'):
        return str(facts['headline'])[:240]
    parts = [f'{key}: {value}' for key, value in facts.items() if isinstance(value, (str, int, float, bool))]
    return '; '.join(parts[:4])[:240] or None


def evidence_item(item):
    return dict(evidence_id=item.get('evidence_id'), capability=item.get('capability'), fact=_fact_text(item), source=item.get('source'),
                as_of=item.get('as_of'), freshness_status=item.get('freshness_status'), delivery_mode=item.get('delivery_mode'),
                role=item.get('role'), decision_admissibility=item.get('decision_admissibility'), valid_until=item.get('valid_until'),
                weak_reasons=list(item.get('weak_reasons') or []))


def evidence_view(packet, *, supporting, conflicting, weak, missing, detail):
    """Grounded evidence of one frozen packet, grouped the way it was cited.

    The packet is the candidate packet a run or decision stored; nothing is
    looked up again. Unknown references are reported, never dropped.
    """
    packet = packet or {}
    index = {e.get('evidence_id'): e for e in (*packet.get('current_market_evidence', []), *packet.get('reference_evidence', []))}
    alignments = [a for a in packet.get('alignments', []) if a.get('result') == 'CONFLICTING']
    blocked = list(packet.get('blocked') or packet.get('blocked_evidence') or [])
    counts = dict(supporting=len(supporting), conflicting=len(set(conflicting)) + len(alignments), weak=len(weak),
                  missing=len(missing), blocked=len(blocked))
    if not detail:
        return dict(counts=counts)

    def group(refs):
        refs = list(dict.fromkeys(refs))
        rows = [evidence_item(index[r]) if r in index else dict(evidence_id=r, lineage=LINEAGE_UNAVAILABLE) for r in refs[:MAX_EVIDENCE]]
        return dict(items=rows, truncated=max(0, len(refs) - MAX_EVIDENCE))

    return dict(
        counts=counts, supporting=group(supporting), conflicting=group(conflicting), weak=group(weak),
        conflicting_alignments=[dict(alignment_id=a.get('alignment_id'), kind=a.get('kind'), result=a.get('result'),
                                     observed_direction=a.get('observed_direction'), limitations=list(a.get('limitations') or [])[:4])
                                for a in alignments[:MAX_EVIDENCE]],
        missing=[str(m) for m in missing[:MAX_EVIDENCE * 2]],
        blocked=[dict(capability=b.get('capability'), source=b.get('source'), as_of=b.get('as_of'), freshness_status=b.get('freshness_status'),
                      reason_codes=list(b.get('reason_codes') or [])) for b in blocked[:MAX_EVIDENCE]],
        blocked_truncated=max(0, len(blocked) - MAX_EVIDENCE))


def condition_view(condition):
    return dict(condition_id=condition.get('condition_id'), status=condition.get('status'), source=condition.get('source'),
                valid_until=condition.get('valid_until'), reason_codes=list(condition.get('reason_codes') or []))


def decision_view(decision, *, detail):
    """One decision from its own immutable record. Later decisions cannot reach it."""
    quote = decision.get('reference_quote') or {}
    model = decision.get('model') or {}
    authority = authority_of(decision)
    proposal = decision.get('model_proposal') or {}
    view = dict(
        decision_id=decision['decision_id'], action_state=decision['action_state'], decision_time=decision['decision_time'],
        decision_cutoff=(decision.get('evidence_snapshot') or {}).get('cutoff') or decision['decision_time'],
        valid_until=decision.get('valid_until'), direction=decision.get('direction'), rationale=decision.get('rationale'),
        origin=authority, ai_proposal_state=proposal.get('proposal_state'),
        model=None if authority == 'DETERMINISTIC_RISK_CONTROL' else dict(provider_id=model.get('provider_id'), model_id=model.get('model_id'),
                                                                         prompt_id=model.get('prompt_id'), called=bool(decision.get('model_proposal'))),
        execution_readiness=decision.get('execution_readiness'), blocker_codes=list(decision.get('blocker_codes') or []),
        reason_codes=list(decision.get('reason_codes') or []), previous_state=decision.get('previous_state'),
        position_at_decision=dict(state=decision['position']['state'], quantity=decision['position'].get('quantity')),
        reference_price=None if quote.get('source_value') is None else str(quote['source_value']), reference_as_of=quote.get('as_of'),
        candidate_run_id=(decision.get('evidence_snapshot') or {}).get('candidate_run_id'))
    exit_ = decision.get('server_exit')
    view['risk_exit'] = dict(reason=exit_.get('reason'), stop_state_id=exit_.get('stop_state_id'), policy_id=exit_.get('policy_id'),
                             active_stop=exit_.get('active_stop'), trigger_price=exit_.get('trigger_price'),
                             triggered_at=exit_.get('triggered_at')) if exit_ else None
    if detail:
        snapshot = decision.get('evidence_snapshot') or {}
        view.update(
            entry_conditions=[condition_view(c) for c in decision.get('entry_plan') or []],
            hold_conditions=[condition_view(c) for c in decision.get('hold_plan') or []],
            exit_conditions=[condition_view(c) for c in decision.get('exit_plan') or []],
            evidence_snapshot_id=decision.get('evidence_snapshot_id'), decision_trace_id=decision.get('decision_trace_id'),
            opportunity_id=decision.get('opportunity_id'),
            # The packet this decision froze, not the candidate's evidence today.
            evidence=evidence_view(snapshot.get('evidence'), supporting=decision.get('supporting_refs') or [],
                                   conflicting=decision.get('conflicting_refs') or [], weak=decision.get('weak_refs') or [],
                                   missing=decision.get('missing_capabilities') or [], detail=True))
    return view


def _order_decision(order):
    source = order.get('decision_source_snapshot')
    reasons = source.get('reasons', []) if isinstance(source, dict) else []
    return next((str(r.get('label')) for r in reasons if isinstance(r, dict) and r.get('code') == 'ACTION_DECISION'), None)


def working_orders(orders, decision_ids):
    """Unfilled, non-terminal Paper orders that name one of these decisions."""
    return [o for o in orders if _order_decision(o) in decision_ids and str(o.get('state')) not in _TERMINAL_ORDER_STATES]


def _fill_view(fill):
    return dict(fill_id=fill['fill_id'], order_id=fill.get('order_id'), kind='SIMULATED_PAPER_FILL', price_minor=fill['fill_price_minor'],
                time=iso_ns(fill.get('fill_time_ns')), submitted_at=iso_ns(fill.get('submit_time_ns')), quantity=fill['filled_quantity'],
                side=fill.get('side'), position_effect=fill['position_effect'], decision_id=fill.get('decision_id'),
                decision_source=fill.get('decision_source'), is_market_truth=False)


def _average(fills):
    quantity = sum(int(f['filled_quantity']) for f in fills)
    return sum(int(f['fill_price_minor']) * int(f['filled_quantity']) for f in fills) // quantity if quantity else None


def _reference(decision):
    if decision is None:
        return None
    quote = decision.get('reference_quote') or {}
    return dict(decision_id=decision['decision_id'], decision_time=decision['decision_time'],
                price=None if quote.get('source_value') is None else str(quote['source_value']), as_of=quote.get('as_of'))


def entry_block(decisions, episode, orders, *, now_ns):
    """Execution phase around an ENTER decision. A decision is never a fill."""
    enter = next((d for d in decisions if d['action_state'] == 'ENTER'), None)
    base = dict(decision_reference=_reference(enter), fill=None, fills=[], fill_count=0, quantity=None, average_price_minor=None,
                paper='NO_FILL')
    if episode is not None:
        entries = episode['entry_fills']
        first = entries[0]
        requested = first.get('requested_quantity')
        partial = isinstance(requested, int) and requested > int(first['filled_quantity'])
        return dict(base, status='PARTIALLY_FILLED' if partial else 'FILLED', fill=_fill_view(first), fills=[_fill_view(f) for f in entries],
                    fill_count=len(entries), quantity=sum(int(f['filled_quantity']) for f in entries),
                    average_price_minor=_average(entries), paper='SIMULATED_FILL')
    latest = decisions[-1] if decisions else None
    if latest is None:
        return dict(base, status='NOT_PROPOSED')
    if working_orders(orders, {d['decision_id'] for d in decisions}):
        return dict(base, status='SUBMITTED_PAPER', paper='SUBMITTED_NOT_FILLED')
    state = latest['action_state']
    if state == 'ENTER':
        expiry = ns_of(latest.get('valid_until'))
        status = 'BLOCKED' if latest.get('execution_readiness') == 'BLOCKED' else 'EXPIRED' if expiry is not None and expiry <= now_ns else 'DECIDED_ENTER'
    else:
        status = dict(CONSIDER_ENTRY='CONSIDERED', REVALIDATION_REQUIRED='BLOCKED').get(state, 'NOT_PROPOSED')
    return dict(base, status=status)


def exit_block(decisions, episode, orders):
    """Execution phase around an EXIT decision. EXIT is closed only by a close fill."""
    latest = decisions[-1] if decisions else None
    decided = latest if latest is not None and latest['action_state'] == 'EXIT' else None
    exits = episode['exit_fills'] if episode else []
    closing = exits[-1] if episode and not episode['open'] and exits else None
    reference = decided or next((d for d in reversed(decisions) if d['action_state'] == 'EXIT'), None) if episode else None
    base = dict(decision_reference=_reference(reference), fill=_fill_view(closing) if closing else None, fills=[_fill_view(f) for f in exits],
                fill_count=len(exits), closed_quantity=sum(int(f['filled_quantity']) for f in exits) or None,
                average_price_minor=_average(exits), paper_close='NOT_APPLICABLE')
    if episode is None:
        return dict(base, status='NO_EXIT')
    if not episode['open']:
        return dict(base, status='CLOSED', paper_close='FILLED')
    if decided is not None:
        if working_orders(orders, {decided['decision_id']}):
            return dict(base, status='EXIT_SUBMITTED', paper_close='SUBMITTED_NOT_FILLED')
        if decided.get('execution_readiness') == 'BLOCKED':
            return dict(base, status='BLOCKED', paper_close='NOT_SUBMITTED')
        return dict(base, status='EXIT_DECIDED', paper_close='NOT_SUBMITTED')
    if exits:
        return dict(base, status='PARTIALLY_CLOSED', paper_close='PARTIALLY_FILLED')
    return dict(base, status='NO_EXIT', paper_close='NOT_SUBMITTED')


def stage_of(decisions, episode, entry, exit_):
    if episode is not None:
        if not episode['open']:
            return 'POSITION_CLOSED'
        return dict(EXIT_DECIDED='EXIT_NOT_EXECUTED', BLOCKED='EXIT_NOT_EXECUTED', EXIT_SUBMITTED='EXIT_SUBMITTED').get(exit_['status'], 'POSITION_OPEN')
    if not decisions:
        return 'SELECTED_NOT_ASSESSED'
    if entry['status'] == 'SUBMITTED_PAPER':
        return 'ENTRY_SUBMITTED'
    state = decisions[-1]['action_state']
    return dict(NO_ACTION='NO_ACTION', CONSIDER_ENTRY='CONSIDERING_ENTRY', ENTER='ENTER_NOT_EXECUTED').get(state, 'REVALIDATION_REQUIRED')


def timeline_rows(*, selections, decisions, cycle_of, stop_events, orders, fills, scale, minor_display):
    """One chronological story from the records' own event times."""
    rows = []
    for run, pick in selections:
        rows.append(dict(kind='CANDIDATE_SELECTED', at=run.get('generated_at') or run.get('decision_cutoff'), event='Candidate selected',
                         source='AI Screener', reason=f"Rank #{pick.get('rank')}", ref=dict(type='CANDIDATE_RUN', id=run.get('run_id')),
                         clocks=dict(evidence_cutoff=run.get('decision_cutoff'))))
    for decision in decisions:
        authority = authority_of(decision)
        cycle = cycle_of.get(decision['decision_id'])
        prefix = 'Risk control' if authority == 'DETERMINISTIC_RISK_CONTROL' else 'Reevaluation' if cycle else 'Action decision'
        codes = decision.get('blocker_codes') or [c for c in decision.get('reason_codes') or [] if c != 'BOUNDED_PROPOSAL_ACCEPTED']
        rows.append(dict(
            kind='DECISION', at=decision['decision_time'], event=f"{prefix}: {decision['action_state']}",
            source=dict(DETERMINISTIC_RISK_CONTROL='Deterministic risk control', SERVER_FAILSAFE='Server fail-safe').get(authority, 'AI proposal, server-gated'),
            reason=decision.get('rationale'), reason_codes=list(codes), action_state=decision['action_state'],
            previous_state=decision.get('previous_state'), ref=dict(type='ACTION_DECISION', id=decision['decision_id']),
            clocks=dict(evaluated_at=decision.get('evaluated_at'), reevaluation_cycle=cycle.get('cycle_id') if cycle else None,
                        reevaluation_classification=cycle.get('classification') if cycle else None)))
    for item in stop_events:
        rows.append(dict(
            kind='STOP', at=iso_ns(item.get('at_ns')), event=_STOP_LABELS.get(item.get('kind'), f"SMA stop {item.get('kind')}"),
            source='Deterministic risk control', reason=', '.join(item.get('reason_codes') or []) or None,
            reason_codes=list(item.get('reason_codes') or []), stop_kind=item.get('kind'),
            active_stop=minor_display(item.get('active_stop'), scale), previous_stop=minor_display(item.get('previous_stop'), scale),
            trigger_price=minor_display(item.get('trigger_price'), scale), sequence=item.get('sequence'),
            ref=dict(type='SMA_STOP_STATE', id=item.get('stop_state_id')), clocks={}))
    for order in orders:
        rows.append(dict(kind='PAPER_ORDER', at=iso_ns(order.get('created_time')), event='Paper order submitted (simulation)',
                         source='Paper ledger', reason=f"{order.get('side')} {order.get('desired_quantity')} · {order.get('state')}",
                         sequence=order.get('submitted_sequence'), ref=dict(type='PAPER_ORDER', id=order.get('order_id')),
                         clocks=dict(decision_id=_order_decision(order))))
    labels = dict(OPEN='Paper simulated fill — position opened', ADD='Paper simulated fill — position increased',
                  REDUCE='Paper simulated fill — position reduced', CLOSE='Paper simulated close fill — position closed',
                  REVERSE='Paper simulated fill — position reversed')
    for fill in fills:
        rows.append(dict(kind='PAPER_FILL', at=iso_ns(fill.get('fill_time_ns')), event=labels.get(fill['position_effect'], 'Paper simulated fill'),
                         source='Paper ledger', reason=f"{fill.get('side')} {fill['filled_quantity']} @ {fill.get('fill_price_display')}",
                         position_effect=fill['position_effect'], price_minor=fill['fill_price_minor'], quantity=fill['filled_quantity'],
                         realized_pnl_delta_minor=fill['realized_pnl_delta_minor'], sequence=fill['sequence'],
                         ref=dict(type='PAPER_FILL', id=fill['fill_id']),
                         clocks=dict(submitted_at=iso_ns(fill.get('submit_time_ns')), decision_id=fill.get('decision_id'))))
    return sort_timeline(rows)


def sort_timeline(rows):
    """Event time first. Storage order, row ids and fetch order never decide it."""
    def key(row):
        at = ns_of(row.get('at'))
        return (at is None, at or 0, _KIND_RANK.get(row['kind'], 9), row.get('sequence') or 0, str((row.get('ref') or {}).get('id')))
    return sorted(rows, key=key)


__all__ = [
    'DEFAULT_CLOSED', 'ENTRY_STATES', 'EXIT_STATES', 'LINEAGE_UNAVAILABLE', 'LIST_SCHEMA', 'MAX_ACTIVE', 'MAX_CLOSED',
    'MAX_DECISIONS', 'MAX_EVIDENCE', 'MAX_PRIOR_EPISODES', 'MAX_SELECTED', 'MAX_TIMELINE', 'MAX_UNLINKED', 'ORIGINS', 'SCHEMA', 'STAGES',
    'assign_decisions', 'authority_of', 'candidate_identity', 'decision_view', 'entry_block', 'episode_identity', 'episodes_from_trades',
    'evidence_view', 'exit_block', 'iso_ns', 'ns_of', 'sort_timeline', 'stage_of', 'timeline_rows', 'working_orders',
]
