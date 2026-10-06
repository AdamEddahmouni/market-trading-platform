"""OCT1-08 SMA trailing stop: pure deterministic position risk-control policy.

No clock, ledger, provider, model or order access. Prices are integer minor
units; the SMA is an exact integer sum over completed bars. A stop derived
from bar k is effective only for observations at or after bar k's availability
time, and a stop may tighten or hold but never move away from protection.

This is a stop *monitor*, not a resting broker order: a breach is a server risk
fact that a governed EXIT decision may cite. Nothing here submits anything.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from ..intelligence.inference.hashing import input_hash_from_dict

POLICY_SCHEMA = 'sma-trailing-stop-policy/1.0.0'
STATE_SCHEMA = 'sma-trailing-stop-state/1.0.0'
METHOD = 'SMA_TRAILING'
BREACH_CONDITION = 'SMA_TRAILING_STOP_BREACHED'
EVALUATION_FILL_MODEL = 'stop-exit-bar-conservative/1.0.0'
INTERVAL_SECONDS = {'1m': 60, '5m': 300, '15m': 900}
WINDOW_BOUNDS = (2, 200)
# One reference software-evaluation configuration, fixed before any outcome was
# read. It is not optimized, calibrated, recommended or claimed superior.
REFERENCE_TEST_CONFIG = dict(sma_window_bars=20, bar_interval='1m')
STATUSES = ('NOT_CONFIGURED', 'WARMING_UP', 'ACTIVE', 'STALE', 'BLOCKED', 'BREACHED', 'CLOSED')
TERMINAL = ('BREACHED', 'CLOSED')
# A break this long between consecutive bars is a session boundary, not missing data.
SESSION_BREAK_NS = 6 * 3600 * 1_000_000_000
_SIDES = ('LONG', 'SHORT')


def config_label(window, interval):
    reference = window == REFERENCE_TEST_CONFIG['sma_window_bars'] and interval == REFERENCE_TEST_CONFIG['bar_interval']
    return 'REFERENCE_TEST_CONFIG' if reference else 'OPERATOR_BOUNDED_CONFIG'


def build_policy(*, sma_window_bars, bar_interval='1m', tick_minor=1, session_scope='RTH', created_at=None):
    """Bounded parameters only. Every behavioural field is part of the identity."""
    if type(sma_window_bars) is not int or not WINDOW_BOUNDS[0] <= sma_window_bars <= WINDOW_BOUNDS[1]:
        raise ValueError('INVALID_SMA_WINDOW')
    if bar_interval not in INTERVAL_SECONDS:
        raise ValueError('UNSUPPORTED_BAR_INTERVAL')
    if type(tick_minor) is not int or tick_minor < 1 or session_scope not in ('RTH', 'EXTENDED'):
        raise ValueError('INVALID_STOP_POLICY')
    body = dict(
        schema_version=POLICY_SCHEMA, method=METHOD, sma_window_bars=sma_window_bars, bar_interval=bar_interval,
        session_scope=session_scope, price_basis='COMPLETED_BAR_CLOSE',
        trigger_basis=dict(current='LAST_TRADE_PRICE', replay='BAR_LOW_FOR_LONG_BAR_HIGH_FOR_SHORT'),
        tick_rounding_policy=dict(tick_minor=tick_minor, long='CEIL_TO_TICK', short='FLOOR_TO_TICK',
                                  observation='HALF_EVEN_TO_MINOR_UNIT'),
        long_behavior='ACTIVE=MAX(PREVIOUS_ACTIVE,CANDIDATE); BREACH_IF_PRICE<=ACTIVE',
        short_behavior='ACTIVE=MIN(PREVIOUS_ACTIVE,CANDIDATE); BREACH_IF_PRICE>=ACTIVE',
        update_timing='AFTER_BAR_AVAILABLE; EFFECTIVE_FOR_LATER_OBSERVATIONS_ONLY',
        warmup_requirement='FULL_WINDOW_OF_COMPLETED_BARS',
        gap_policy='MISSING_INTRASESSION_BAR_IN_WINDOW_BLOCKS_UPDATE; WINDOW_MAY_SPAN_SESSION_BREAK',
        evaluation_fill_model=EVALUATION_FILL_MODEL)
    return dict(body, policy_id='STP-' + input_hash_from_dict(body)[:32],
                config_label=config_label(sma_window_bars, bar_interval), created_at=created_at)


def price_to_minor(value, scale=100):
    """Observation prices only. Exact for prices quoted to the minor unit."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('INVALID_PRICE')
    try:
        amount = Decimal(str(value))
    except ArithmeticError as exc:
        raise ValueError('INVALID_PRICE') from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError('INVALID_PRICE')
    return int((amount * scale).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def minor_to_display(minor, scale=100):
    return None if minor is None else format(Decimal(minor) / Decimal(scale), 'f')


def normalize_bars(bars, *, cutoff_ns, interval):
    """Deterministic completed-bar series at an evaluation cutoff.

    Ordered by availability, deduplicated by identity, future and partial bars
    excluded. Two different bars claiming one identity or one slot fail closed:
    the series is not silently repaired.
    """
    step = INTERVAL_SECONDS[interval] * 1_000_000_000
    by_id, by_slot = {}, {}
    excluded = dict(future=0, partial=0, duplicate=0, invalid=0)
    for bar in bars:
        try:
            facts = dict(bar_id=str(bar['bar_id']), event_time=int(bar['event_time']), available_time=int(bar['available_time']),
                         **{k: bar[k] for k in ('open', 'high', 'low', 'close')})
        except (KeyError, TypeError, ValueError):
            excluded['invalid'] += 1
            continue
        prices = [facts[k] for k in ('open', 'high', 'low', 'close')]
        if any(type(p) is not int or p <= 0 for p in prices) or facts['low'] > min(facts['open'], facts['close']) \
                or facts['high'] < max(facts['open'], facts['close']) or facts['available_time'] - facts['event_time'] != step:
            excluded['invalid'] += 1
            continue
        if bar.get('complete') is False:
            excluded['partial'] += 1
            continue
        if facts['available_time'] > cutoff_ns:
            excluded['future'] += 1
            continue
        seen = by_id.get(facts['bar_id']) or by_slot.get(facts['event_time'])
        if seen is not None:
            if seen != facts:
                raise ValueError('BAR_IDENTITY_CONFLICT')
            excluded['duplicate'] += 1
            continue
        by_id[facts['bar_id']] = by_slot[facts['event_time']] = facts
    return dict(bars=sorted(by_id.values(), key=lambda b: (b['available_time'], b['bar_id'])), excluded=excluded)


def window_at(bars, index, policy):
    """The N bars ending at index, or the reason the SMA is not admissible there."""
    window = policy['sma_window_bars']
    if index + 1 < window:
        return None, 'INSUFFICIENT_HISTORY'
    chosen = bars[index + 1 - window:index + 1]
    step = INTERVAL_SECONDS[policy['bar_interval']] * 1_000_000_000
    for earlier, later in zip(chosen, chosen[1:]):
        gap = later['event_time'] - earlier['event_time']
        if gap != step and gap < SESSION_BREAK_NS:
            return None, 'BAR_GAP_IN_WINDOW'  # a missing bar is never replaced by an invented close
    return chosen, None


def sma_candidate(closes, side, tick_minor=1):
    """(candidate stop, close sum). Rounding is toward protection, never away from it."""
    if side not in _SIDES or not closes:
        raise ValueError('INVALID_STOP_INPUT')
    total, count = sum(closes), len(closes)
    units = total // (count * tick_minor) if side == 'SHORT' else -(-total // (count * tick_minor))
    return units * tick_minor, total


def sma_display(total, count, scale=100):
    return format((Decimal(total) / Decimal(count * scale)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN), 'f')


def trail(side, previous, candidate):
    """Monotonic trailing rule: (active stop, clamped)."""
    if previous is None:
        return candidate, False
    active = max(previous, candidate) if side == 'LONG' else min(previous, candidate)
    return active, active != candidate


def tighter(side, new, old):
    return new > old if side == 'LONG' else new < old


def initial_state(*, account_id, session_id, instrument_id, position_epoch_id, epoch_basis, side, quantity,
                  policy, activated_at, activation_reason, price_scale=100):
    if side not in _SIDES:
        raise ValueError('INVALID_STOP_SIDE')
    identity = dict(account=account_id, instrument=instrument_id, epoch=position_epoch_id, policy=policy['policy_id'],
                    activated_at=activated_at)
    return dict(
        schema_version=STATE_SCHEMA, stop_state_id='STS-' + input_hash_from_dict(identity)[:32], method=METHOD,
        account_id=account_id, session_id=session_id, instrument_id=instrument_id, position_epoch_id=position_epoch_id,
        epoch_basis=epoch_basis, side=side, quantity=quantity, policy_id=policy['policy_id'],
        sma_window_bars=policy['sma_window_bars'], bar_interval=policy['bar_interval'], config_label=policy['config_label'],
        price_scale=price_scale, activated_at=activated_at, activation_reason=activation_reason,
        sma_value=None, sma_close_sum=None, candidate_stop=None, active_stop=None, previous_stop=None,
        effective_after_ns=None, previous_effective_after_ns=None, stop_as_of=None, bar_id=None, bar_available_at_ns=None,
        bars_available=0, update_count=0, tighten_count=0, clamp_count=0,
        status='WARMING_UP', trigger_state='NOT_ARMED', reason_codes=['INSUFFICIENT_HISTORY'], trigger_reason_codes=[],
        triggered_at=None, trigger_price=None, trigger_evidence=None, last_updated_at=None, last_evaluated_at=None)


def advance(state, bars, policy, *, latest_only=False):
    """Fold newly completed bars into the stop. Returns (state, events).

    latest_only is used after an unobserved interval: the stop resumes from the
    latest completed bar and no intermediate update is reconstructed.
    """
    if state['status'] in TERMINAL:
        return state, []
    state, events = dict(state), []
    side, tick, scale = state['side'], policy['tick_rounding_policy']['tick_minor'], state['price_scale']
    state['bars_available'] = len(bars)
    last = state['bar_available_at_ns']
    fresh = [i for i, b in enumerate(bars) if last is None or b['available_time'] > last]
    if latest_only or last is None:
        # A new episode starts from the latest completed bar: history before activation is never replayed into it.
        fresh = fresh[-1:]
    blocked = None
    for index in fresh:
        chosen, reason = window_at(bars, index, policy)
        if chosen is None:
            blocked = reason
            continue
        blocked = None
        bar = bars[index]
        candidate, total = sma_candidate([b['close'] for b in chosen], side, tick)
        active, clamped = trail(side, state['active_stop'], candidate)
        first = state['active_stop'] is None
        moved = first or active != state['active_stop']
        if moved:
            state.update(previous_stop=state['active_stop'], previous_effective_after_ns=state['effective_after_ns'],
                         active_stop=active, effective_after_ns=bar['available_time'], last_updated_at=bar['available_time'])
        was_clamped, was_stale = 'MONOTONIC_CLAMP' in state['reason_codes'], state['status'] == 'STALE'
        state.update(sma_value=sma_display(total, len(chosen), scale), sma_close_sum=total, candidate_stop=candidate,
                     stop_as_of=bar['available_time'], bar_id=bar['bar_id'], bar_available_at_ns=bar['available_time'],
                     update_count=state['update_count'] + 1, status='ACTIVE',
                     reason_codes=['MONOTONIC_CLAMP'] if clamped else [])
        if was_stale:
            events.append(_event(state, 'RESUMED', bar['available_time']))
        if first:
            events.append(_event(state, 'ACTIVATED', bar['available_time']))
        elif moved:
            state['tighten_count'] += 1
            events.append(_event(state, 'TIGHTENED', bar['available_time']))
        elif clamped:
            state['clamp_count'] += 1
            if not was_clamped:
                events.append(_event(state, 'CLAMPED', bar['available_time']))
    if blocked:
        if state['active_stop'] is None:
            warming = blocked == 'INSUFFICIENT_HISTORY'
            state.update(status='WARMING_UP' if warming else 'BLOCKED', reason_codes=[blocked])
        else:
            state = mark_stale(state, blocked, events, at_ns=bars[fresh[-1]]['available_time'])
    return state, events


def mark_stale(state, reason, events=None, *, at_ns=None):
    """The level stays known; only the ability to update it is degraded."""
    if state['status'] in TERMINAL:
        return state
    state = dict(state)
    if state['active_stop'] is None:
        state.update(status='BLOCKED', reason_codes=[reason])
        return state
    entering = state['status'] != 'STALE'
    state.update(status='STALE', reason_codes=['STOP_UPDATE_STALE', reason])
    if entering and events is not None:
        events.append(_event(state, 'STALE', at_ns))
    return state


def effective_stop(state, observed_ns):
    """The stop that was already in force at the observation time, if any."""
    if state['active_stop'] is None or state['effective_after_ns'] is None:
        return None
    if observed_ns >= state['effective_after_ns']:
        return state['active_stop']
    if state['previous_stop'] is not None and state['previous_effective_after_ns'] is not None \
            and observed_ns >= state['previous_effective_after_ns']:
        return state['previous_stop']
    return None


def _crossed(side, price, stop):
    return price <= stop if side == 'LONG' else price >= stop


def check_quote_trigger(state, quote, *, events=None):
    """Current-market trigger on the last-trade price. Returns the new state.

    A stale or inadmissible quote proves neither a breach nor safety.
    """
    if state['status'] in TERMINAL or state['active_stop'] is None:
        return state
    state = dict(state)
    if not quote or not quote.get('admissible') or type(quote.get('price_minor')) is not int:
        state.update(trigger_state='TRIGGER_UNAVAILABLE',
                     trigger_reason_codes=['REVALIDATION_REQUIRED', (quote or {}).get('reason') or 'QUOTE_STALE_OR_UNAVAILABLE'])
        return state
    state['trigger_reason_codes'] = []
    stop = effective_stop(state, quote['as_of_ns'])
    if stop is None:
        state['trigger_state'] = 'NOT_ARMED'  # the quote predates the stop: no retroactive trigger
        return state
    state['trigger_state'] = 'ARMED'
    if _crossed(state['side'], quote['price_minor'], stop):
        first = state['update_count'] == 1 and stop == state['active_stop']
        evidence = dict(kind='QUOTE', basis='LAST_TRADE_PRICE', price_minor=quote['price_minor'], as_of_ns=quote['as_of_ns'],
                        source=quote.get('source'), evidence_ref=quote.get('evidence_ref'), stop=stop, bar_id=state['bar_id'])
        state.update(status='BREACHED', trigger_state='BREACHED', triggered_at=quote['as_of_ns'],
                     trigger_price=quote['price_minor'], trigger_evidence=evidence,
                     reason_codes=[BREACH_CONDITION, *(['IMMEDIATE_EXIT_CONDITION'] if first else [])])
        if events is not None:
            events.append(_event(state, 'BREACHED', quote['as_of_ns']))
    return state


def check_bar_trigger(state, bar):
    """Replay trigger on a later bar's range. Returns breach facts or None.

    Only a stop already effective at the bar's start is eligible: the stop a
    bar produces is never tested against that same bar's own range.
    """
    stop = effective_stop(state, bar['event_time'])
    if stop is None or state['status'] in TERMINAL:
        return None
    side = state['side']
    if not _crossed(side, bar['low'] if side == 'LONG' else bar['high'], stop):
        return None
    return dict(stop=stop, bar_id=bar['bar_id'], bar_event_time=bar['event_time'], bar_available_time=bar['available_time'],
                open=bar['open'], high=bar['high'], low=bar['low'], close=bar['close'],
                gap_through_stop=_crossed(side, bar['open'], stop),
                # OHLC does not order the extremes: where inside the bar the stop was touched is unknown.
                intrabar_sequence='UNKNOWN')


def close_state(state, reason, at_ns, events=None):
    if state['status'] == 'CLOSED':
        return state
    state = dict(state, status='CLOSED', trigger_state='NOT_ARMED', closed_at=at_ns, closed_reason=reason,
                 reason_codes=list(dict.fromkeys([*([BREACH_CONDITION] if state['status'] == 'BREACHED' else []), reason])))
    if events is not None:
        events.append(_event(state, 'CLOSED', at_ns))
    return state


def _event(state, kind, at_ns, **extra):
    return dict(kind=kind, at_ns=at_ns, stop_state_id=state['stop_state_id'], policy_id=state['policy_id'],
                position_epoch_id=state['position_epoch_id'], side=state['side'], status=state['status'],
                sma_value=state['sma_value'], candidate_stop=state['candidate_stop'], active_stop=state['active_stop'],
                previous_stop=state['previous_stop'], bar_id=state['bar_id'], reason_codes=list(state['reason_codes']),
                trigger_price=state.get('trigger_price'), **extra)


event = _event


def loosens(side, previous, new):
    """True when a stored stop would move away from protection."""
    if previous is None or new is None:
        return previous is not None and new is None
    return new < previous if side == 'LONG' else new > previous


def position_epoch(events, *, account_id, session_id, instrument_id, side):
    """Deterministic position episode from the ledger's own fill lineage.

    The epoch starts at the fill that took the net position from flat (or the
    opposite side) to this side. Partial reductions keep it; flat or reversal
    ends it. Returns None when the ledger carries no such lineage.
    """
    opening, previous = None, 0
    for item in events:
        if item.get('event_type') != 'PositionChanged':
            continue
        shares = int((item.get('payload') or {}).get('position_shares', 0))
        if shares == 0:
            opening = None
        elif previous == 0 or (previous > 0) != (shares > 0):
            opening = item
        previous = shares
    if opening is None or (previous > 0) != (side == 'LONG'):
        return None
    lineage = dict(account=account_id, session=session_id, instrument=instrument_id, side=side,
                   fill_id=opening['payload'].get('fill_id'), sequence=opening.get('sequence'))
    return dict(position_epoch_id='PE-' + input_hash_from_dict(lineage)[:32], epoch_basis='LEDGER_OPENING_FILL',
                opened_at_ns=opening.get('event_time'), opening_fill_id=lineage['fill_id'])
