"""AUTO-01 pure autonomous Paper automation policy: owner configuration, sizing bounds, risk gates, status.

No clock, provider, model, ledger or order access. Nothing here is a default trading
setting: every risk, schedule and spending field is supplied by the owner, and a
missing one is an incomplete policy, not a silently chosen value.
"""
from __future__ import annotations

from enum import StrEnum
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING

from .hashing import input_hash_from_dict

POLICY_SCHEMA = 'paper-automation-policy/1.0.0'
UNIVERSE_FINGERPRINT_SCHEMA = 'universe-fingerprint/1.0.0'
ARM_ACKNOWLEDGEMENT = 'ARM_PAPER_ONLY_AUTOMATION'
# The stop monitor, the completed-bar feed and the fill model are regular-session contracts.
SUPPORTED_SESSIONS = ('REGULAR',)
# The experiment account values share positions only.
SUPPORTED_UNIVERSES = ('US_EQUITIES', 'US_ETFS', 'CRYPTO', 'FUTURES', 'BONDS')
UNIVERSE_SESSIONS = dict(US_EQUITIES=('REGULAR',), US_ETFS=('REGULAR',),
                         CRYPTO=('CONTINUOUS',), FUTURES=('TRADING',), BONDS=('REFERENCE_ONLY',))
# The governed handoff and the deterministic exit are MARKET_NOW_IF_GATES_PASS.
SUPPORTED_ORDER_TYPES = ('MARKET',)
REGULAR_SESSION_MINUTES = 390
# The automation refuses an entry below one whole unit of a share-counted instrument. A spot pair's floor is the
# venue's own minimum order (ordermin, on its lot step), which ``order_quantity`` validates again at the ledger.
MIN_ENTRY_QUANTITY = 1


def minimum_entry_quantity(instrument=None):
    """The smallest entry the automation sends for this instrument; one rule for the order path and the pre-model floor."""
    if (instrument or {}).get('instrument_kind') == 'CRYPTO_PAIR':
        try:
            minimum = Decimal(str(instrument['minimum_quantity']))
        except (KeyError, InvalidOperation):
            return None  # no venue minimum: no entry is sized (INSTRUMENT_QUANTITY_RULES_UNAVAILABLE upstream)
        return minimum if minimum.is_finite() and minimum > 0 else None
    return Decimal(MIN_ENTRY_QUANTITY)


def entry_below_minimum(quantity, instrument=None):
    minimum = minimum_entry_quantity(instrument)
    return minimum is None or Decimal(str(quantity)) <= 0 or Decimal(str(quantity)) < minimum


class AutomationStatus(StrEnum):
    NOT_CONFIGURED = 'NOT_CONFIGURED'
    DISARMED = 'DISARMED'
    STOPPED = 'STOPPED'
    PAUSED = 'PAUSED'
    EMERGENCY_STOPPED = 'EMERGENCY_STOPPED'
    WAITING_FOR_MARKET = 'WAITING_FOR_MARKET'
    BLOCKED_BY_AUTHORITY = 'BLOCKED_BY_AUTHORITY'
    BLOCKED_BY_DATA = 'BLOCKED_BY_DATA'
    BLOCKED_BY_RISK = 'BLOCKED_BY_RISK'
    BLOCKED_BY_BUDGET = 'BLOCKED_BY_BUDGET'
    RUNNING = 'RUNNING'
    ERROR = 'ERROR'


class UniverseDecision(StrEnum):
    """The four outcomes of one adaptive full-universe scheduling decision.

    RUN starts an evaluation; DEFER can start later, possibly without any owner action;
    SKIP has nothing worth paying for because the current selection is still valid; BLOCK
    cannot start without a change the controller cannot make on its own (exhausted daily
    allowance, closed session). Every one of them carries its exact reason codes.
    """
    RUN = 'RUN'
    DEFER = 'DEFER'
    SKIP = 'SKIP'
    BLOCK = 'BLOCK'


class IntentState(StrEnum):
    CREATED = 'CREATED'
    PREVIEWED = 'PREVIEWED'
    SUBMITTED = 'SUBMITTED'
    BLOCKED = 'BLOCKED'      # refused before any order existed; a later decision may be tried again
    DEFERRED = 'DEFERRED'    # required evidence unavailable; nothing was forced
    FAILED = 'FAILED'


# An intent in one of these states already produced (or may have produced) an order: never repeated.
INTENT_TERMINAL = frozenset({IntentState.SUBMITTED})

# Adaptive full-universe scheduling is optional and additive. A body that omits these keys keeps the exact
# fixed minimum-separation behaviour of the original schema, with the same policy id; supplying them enables
# the adaptive policy in ``should_run_universe`` and yields a new policy id, as any content change must.
# ``universe_evaluation_interval_seconds`` is the MINIMUM SEPARATION between two broad runs; it was always a
# floor, and this only names it.
_SCHEDULE_OPTIONAL = dict(universe_max_age_seconds=int, universe_material_change_trigger=bool,
                          universe_max_runs_per_day=int)
# Selective overnight holds (owner decision 6, rebuild step 7) are optional and additive in the same way: a body
# without them keeps its exact policy id and carries nothing over the close. The three are supplied together.
_RISK_OPTIONAL = dict(max_overnight_positions=int, max_overnight_exposure_minor=int, max_hold_sessions=int)
_SECTIONS = dict(
    schedule=dict(sessions=list, cadence_seconds=int, universe_evaluation_interval_seconds=int,
                  no_new_entries_minutes_before_close=int),
    risk=dict(max_position_notional_minor=int, max_aggregate_exposure_minor=int, max_open_positions=int,
              max_daily_loss_minor=int, max_per_trade_risk_minor=int, assumed_adverse_move_bps=int,
              allowed_universes=list, order_types=list, allow_long=bool, allow_short=bool,
              allow_entries=bool, allow_exits=bool),
    exits=dict(on_stop_breach=bool, on_thesis_exit=bool),
    ai=dict(allow_local_inference=bool, allow_paid_inference=bool, max_paid_requests_per_day=int,
            max_paid_tokens_per_day=int),
    emergency_stop=dict(max_consecutive_failures=int),
)
# Every allowed key per section, required and optional. Unknown keys are still rejected, never ignored.
_ALLOWED = {section: set(fields) for section, fields in _SECTIONS.items()}
_ALLOWED['schedule'] = set(_SECTIONS['schedule']) | set(_SCHEDULE_OPTIONAL)
_ALLOWED['risk'] = set(_SECTIONS['risk']) | set(_RISK_OPTIONAL)
_INT_BOUNDS = dict(
    max_overnight_positions=(0, 5), max_overnight_exposure_minor=(0, 2_500_000), max_hold_sessions=(1, 5),
    cadence_seconds=(60, 3600), universe_evaluation_interval_seconds=(300, 86400),
    no_new_entries_minutes_before_close=(0, REGULAR_SESSION_MINUTES),
    universe_max_age_seconds=(300, 86400), universe_max_runs_per_day=(1, 100),
    max_position_notional_minor=(1, 10 ** 13), max_aggregate_exposure_minor=(1, 10 ** 13), max_open_positions=(1, 50),
    max_daily_loss_minor=(1, 10 ** 13), max_per_trade_risk_minor=(1, 10 ** 13), assumed_adverse_move_bps=(1, 10000),
    max_paid_requests_per_day=(0, 100000), max_paid_tokens_per_day=(0, 10 ** 10), max_consecutive_failures=(1, 20),
)


def required_fields():
    """Every owner decision the policy needs, as section.field paths."""
    return ['scope', *(f'{section}.{field}' for section, fields in _SECTIONS.items() for field in fields)]


def optional_fields():
    """Owner decisions that enable adaptive scheduling or overnight holds. Omitting one is a choice, never a default."""
    return ['scopes', *sorted(f'schedule.{field}' for field in _SCHEDULE_OPTIONAL),
            *sorted(f'risk.{field}' for field in _RISK_OPTIONAL)]


def universe_scopes(policy):
    """Explicit asset-specific scopes; old policies keep their exact content and identity."""
    return policy.get('scopes') or [dict(scope=policy['scope'], sessions=policy['schedule']['sessions'])]


def build_policy(body, *, account_id, experiment_id, initial_capital_minor, ledger_policy):
    """Validate one complete owner policy and bind it to one Paper experiment account.

    Missing fields are named together (``AUTOMATION_POLICY_INCOMPLETE:a,b``) so the
    owner is asked once. Unknown fields are rejected, not ignored.
    """
    if not isinstance(body, dict) or set(body) - {'scope', 'scopes', *_SECTIONS}:
        raise ValueError('AUTOMATION_POLICY_INVALID')
    if not account_id or not experiment_id:
        raise ValueError('AUTOMATION_PAPER_EXPERIMENT_REQUIRED')
    missing = [] if isinstance(body.get('scope'), dict) else ['scope']
    for section, fields in _SECTIONS.items():
        value = body.get(section)
        if not isinstance(value, dict):
            missing.extend(f'{section}.{field}' for field in fields)
            continue
        if set(value) - _ALLOWED[section]:
            raise ValueError('AUTOMATION_POLICY_INVALID')
        missing.extend(f'{section}.{field}' for field in fields if field not in value)
    if missing:
        raise ValueError('AUTOMATION_POLICY_INCOMPLETE:' + ','.join(missing))
    policy = dict(scope=dict(body['scope']))
    for section, fields in _SECTIONS.items():
        policy[section] = {}
        for field, kind in fields.items():
            value = body[section][field]
            if type(value) is not kind:
                raise ValueError('AUTOMATION_POLICY_FIELD_INVALID:' + f'{section}.{field}')
            if field in _INT_BOUNDS and not _INT_BOUNDS[field][0] <= value <= _INT_BOUNDS[field][1]:
                raise ValueError('AUTOMATION_POLICY_FIELD_OUT_OF_RANGE:' + f'{section}.{field}')
            policy[section][field] = list(value) if kind is list else value
    for field, kind in _SCHEDULE_OPTIONAL.items():
        if field not in body['schedule']:
            continue
        value = body['schedule'][field]
        if type(value) is not kind:
            raise ValueError('AUTOMATION_POLICY_FIELD_INVALID:' + f'schedule.{field}')
        if field in _INT_BOUNDS and not _INT_BOUNDS[field][0] <= value <= _INT_BOUNDS[field][1]:
            raise ValueError('AUTOMATION_POLICY_FIELD_OUT_OF_RANGE:' + f'schedule.{field}')
        policy['schedule'][field] = value
    overnight = [field for field in _RISK_OPTIONAL if field in body['risk']]
    if overnight and len(overnight) != len(_RISK_OPTIONAL):
        raise ValueError('AUTOMATION_POLICY_INCOMPLETE:' + ','.join(f'risk.{field}' for field in _RISK_OPTIONAL
                                                                    if field not in body['risk']))
    for field in overnight:
        value = body['risk'][field]
        if type(value) is not int:
            raise ValueError('AUTOMATION_POLICY_FIELD_INVALID:' + f'risk.{field}')
        if not _INT_BOUNDS[field][0] <= value <= _INT_BOUNDS[field][1]:
            raise ValueError('AUTOMATION_POLICY_FIELD_OUT_OF_RANGE:' + f'risk.{field}')
        policy['risk'][field] = value
    schedule, risk, ai = policy['schedule'], policy['risk'], policy['ai']
    if overnight and (risk['max_overnight_positions'] > risk['max_open_positions']
                      or risk['max_overnight_exposure_minor'] > risk['max_aggregate_exposure_minor']):
        raise ValueError('AUTOMATION_OVERNIGHT_LIMIT_EXCEEDS_PORTFOLIO_LIMIT')
    for field, allowed, code in (('sessions', SUPPORTED_SESSIONS, 'AUTOMATION_SESSION_UNSUPPORTED'),):
        if not schedule[field] or len(set(schedule[field])) != len(schedule[field]) or set(schedule[field]) - set(allowed):
            raise ValueError(code)
    for field, allowed, code in (('allowed_universes', SUPPORTED_UNIVERSES, 'AUTOMATION_INSTRUMENT_SCOPE_UNSUPPORTED'),
                                 ('order_types', SUPPORTED_ORDER_TYPES, 'AUTOMATION_ORDER_TYPE_UNSUPPORTED')):
        if not risk[field] or len(set(risk[field])) != len(risk[field]) or set(risk[field]) - set(allowed):
            raise ValueError(code)
    if policy['scope'].get('universe') not in risk['allowed_universes']:
        raise ValueError('AUTOMATION_SCOPE_OUTSIDE_ALLOWED_INSTRUMENTS')
    if 'scopes' in body:
        scopes = body['scopes']
        if not isinstance(scopes, list) or not scopes or len(scopes) > len(SUPPORTED_UNIVERSES):
            raise ValueError('AUTOMATION_SCOPES_INVALID')
        seen, admitted = set(), []
        for item in scopes:
            if not isinstance(item, dict) or set(item) != {'scope', 'sessions'} or not isinstance(item['scope'], dict):
                raise ValueError('AUTOMATION_SCOPES_INVALID')
            universe, sessions = item['scope'].get('universe'), item['sessions']
            if universe in seen:
                raise ValueError('AUTOMATION_DUPLICATE_UNIVERSE_SCOPE')
            if universe not in risk['allowed_universes']:
                raise ValueError('AUTOMATION_SCOPE_OUTSIDE_ALLOWED_INSTRUMENTS')
            if not isinstance(sessions, list) or not sessions or len(set(sessions)) != len(sessions) \
                    or set(sessions) - set(UNIVERSE_SESSIONS.get(universe, ())):
                raise ValueError('AUTOMATION_SCOPE_SESSION_UNSUPPORTED')
            if item['scope'].get('method') == 'STAGED_LOCAL_FIRST_EXPERIMENTAL':
                raise ValueError('EXPERIMENTAL_METHOD_UNAPPROVED')
            seen.add(universe)
            admitted.append(dict(scope=dict(item['scope']), sessions=list(sessions)))
        if admitted[0]['scope'] != policy['scope'] or admitted[0]['sessions'] != schedule['sessions']:
            raise ValueError('AUTOMATION_PRIMARY_SCOPE_MISMATCH')
        policy['scopes'] = admitted
    elif policy['scope'].get('universe') not in ('US_EQUITIES', 'US_ETFS'):
        raise ValueError('AUTOMATION_EXPLICIT_ASSET_SESSIONS_REQUIRED')
    if policy['scope'].get('method') == 'STAGED_LOCAL_FIRST_EXPERIMENTAL':
        raise ValueError('EXPERIMENTAL_METHOD_UNAPPROVED')  # separately gated; never reachable from automation
    if risk['allow_short'] and not ledger_policy.get('allow_short', False):
        raise ValueError('AUTOMATION_SHORT_NOT_PERMITTED_BY_PAPER_ACCOUNT')
    if not (risk['allow_long'] or risk['allow_short']) and risk['allow_entries']:
        raise ValueError('AUTOMATION_ENTRY_DIRECTION_REQUIRED')
    if risk['max_position_notional_minor'] > risk['max_aggregate_exposure_minor']:
        raise ValueError('AUTOMATION_POSITION_EXCEEDS_AGGREGATE_EXPOSURE')
    if risk['max_aggregate_exposure_minor'] > int(initial_capital_minor):
        raise ValueError('AUTOMATION_EXPOSURE_EXCEEDS_PAPER_CAPITAL')  # the experiment account has no leverage
    if schedule['universe_evaluation_interval_seconds'] < schedule['cadence_seconds']:
        raise ValueError('AUTOMATION_SCHEDULE_INVALID')
    if schedule.get('universe_max_age_seconds') is not None \
            and schedule['universe_max_age_seconds'] < schedule['universe_evaluation_interval_seconds']:
        # A maximum useful age below the minimum separation can never be reached without first waiting out the
        # separation, so it is a contradiction rather than a tighter schedule.
        raise ValueError('AUTOMATION_SCHEDULE_INVALID')
    if ai['allow_paid_inference'] and not (ai['max_paid_requests_per_day'] and ai['max_paid_tokens_per_day']):
        raise ValueError('AUTOMATION_PAID_SPENDING_LIMIT_REQUIRED')
    if not ai['allow_paid_inference'] and (ai['max_paid_requests_per_day'] or ai['max_paid_tokens_per_day']):
        raise ValueError('AUTOMATION_PAID_SPENDING_NOT_AUTHORIZED')
    policy.update(schema_version=POLICY_SCHEMA, account_id=str(account_id), experiment_id=str(experiment_id),
                  initial_capital_minor=int(initial_capital_minor),
                  execution=dict(mode='INTERNAL_SIMULATION', provider='INTERNAL', live_capital=False),
                  ledger_risk_policy_id=str(ledger_policy.get('risk_policy_identity_hash', '')))
    policy['policy_id'] = 'PAP-' + input_hash_from_dict(policy)[:32]
    return policy


def spending_gate(policy, engine):
    """Whether this policy lets the selected engine be called at all. A refusal sends no request."""
    if engine.get('state') == 'NOT_CONFIGURED':
        return dict(allowed=False, reason='MODEL_UNAVAILABLE')
    ai = policy['ai']
    if engine.get('runtime') == 'LOCAL_MODEL':
        return dict(allowed=bool(ai['allow_local_inference']),
                    reason=None if ai['allow_local_inference'] else 'AUTONOMOUS_LOCAL_INFERENCE_NOT_AUTHORIZED')
    if not ai['allow_paid_inference']:
        return dict(allowed=False, reason='AUTONOMOUS_SPENDING_NOT_AUTHORIZED')
    budget = engine.get('budget')
    if not budget:
        # A paid engine whose usage cannot be read is never assumed to have headroom.
        return dict(allowed=False, reason='AUTONOMOUS_SPENDING_BUDGET_UNREADABLE')
    if engine.get('state') != 'AVAILABLE':
        return dict(allowed=False, reason=engine.get('reason') or 'MODEL_UNAVAILABLE')
    # The owner's cap applies to the shared daily usage itself: it can only tighten the existing allowance.
    used_requests = int(budget.get('requests', 0)) + int(budget.get('held_requests') or 0)
    used_tokens = int(budget.get('tokens', 0)) + int(budget.get('held_tokens') or 0)
    if used_requests >= min(ai['max_paid_requests_per_day'], int(budget['max_requests'])) \
            or used_tokens >= min(ai['max_paid_tokens_per_day'], int(budget['max_tokens'])):
        return dict(allowed=False, reason='AUTONOMOUS_SPENDING_LIMIT_REACHED')
    return dict(allowed=True, reason=None)


def exposure_minor(positions):
    """Gross marked exposure. None when any open position has no mark: an unknown is never zero."""
    total = 0
    for position in positions:
        try:
            quantity = Decimal(str(position.get('quantity', 0)))
            multiplier = Decimal(str(position.get('contract_multiplier', '1')))
            scale = Decimal(str(position.get('price_scale', 100)))
        except (ValueError, InvalidOperation):
            return None
        if not quantity.is_finite() or not multiplier.is_finite() or multiplier <= 0 or not scale.is_finite() or scale <= 0:
            return None
        if not quantity:
            continue
        mark = position.get('mark_minor')
        if not isinstance(mark, int) or mark <= 0:
            return None
        total += int((abs(quantity) * mark * multiplier * 100 / scale).to_integral_value(rounding=ROUND_CEILING))
    return total


def entry_risk_blockers(policy, *, positions, valuation, day_start_equity_minor, pending_orders, minutes_to_close,
                        session_label='REGULAR', carry_pending=False, close_guard_minutes=0):
    """Portfolio-level reasons a new entry may not be attempted now. Exits are never gated here.

    ``carry_pending``: an automation position was left open over a close it was not approved to carry; nothing is
    added until it is closed. ``close_guard_minutes``: the controller's own end-of-day close-out window, so an entry
    can never land where it would be closed again minutes later, whatever the owner's entry cutoff.
    """
    risk, blockers = policy['risk'], []
    if not risk['allow_entries']:
        blockers.append('AUTOMATION_ENTRIES_DISABLED')
    held = [p for p in positions if p.get('quantity')]
    if len(held) >= risk['max_open_positions']:
        blockers.append('MAX_OPEN_POSITIONS_REACHED')
    exposure = exposure_minor(held)
    if exposure is None or valuation.get('quality') != 'CURRENT' or valuation.get('equity_minor') is None:
        blockers.append('PORTFOLIO_VALUATION_NOT_CURRENT')
    elif exposure >= risk['max_aggregate_exposure_minor']:
        blockers.append('MAX_AGGREGATE_EXPOSURE_REACHED')
    equity = valuation.get('equity_minor')
    if day_start_equity_minor is None:
        blockers.append('DAY_START_EQUITY_UNAVAILABLE')
    elif equity is not None and day_start_equity_minor - equity >= risk['max_daily_loss_minor']:
        blockers.append('MAX_DAILY_LOSS_REACHED')
    if valuation.get('maintenance_breached'):
        blockers.append('SHORT_MAINTENANCE_MARGIN_BREACH')  # nothing is added while shorts are under-margined
    if pending_orders:
        blockers.append('WORKING_ORDERS_PRESENT')
    if carry_pending:
        blockers.append('UNPLANNED_CARRY_PENDING')
    cutoff = max(policy['schedule']['no_new_entries_minutes_before_close'], int(close_guard_minutes))
    if session_label not in ('CONTINUOUS', 'TRADING') and (minutes_to_close is None or minutes_to_close <= cutoff):
        blockers.append('ENTRY_WINDOW_CLOSED')
    return blockers


def overnight_limits(policy):
    """The owner's overnight-hold limits, or None when this policy carries nothing over the close."""
    risk = policy['risk']
    if not risk.get('max_overnight_positions'):
        return None
    return dict(max_positions=int(risk['max_overnight_positions']),
                max_exposure_minor=int(risk['max_overnight_exposure_minor']),
                max_hold_sessions=int(risk['max_hold_sessions']))


def sessions_held(entry_date, session_date, is_trading_day):
    """Trading sessions a position has been open in, the entry session counted as 1 (ISO dates, ET)."""
    from datetime import date, timedelta
    start, end = date.fromisoformat(entry_date), date.fromisoformat(session_date)
    if end < start:
        return 1
    count, day = 0, start
    while day <= end:
        count += 1 if is_trading_day(day) else 0
        day += timedelta(days=1)
    return max(count, 1)


def select_overnight_carry(candidates, limits):
    """Deterministic choice of what is carried: best unrealized return first, inside both owner caps.

    ``candidates`` are dicts with ``instrument_id``, ``exposure_minor`` and ``return_bps``. A candidate that does not
    fit the remaining position count or exposure is refused with its reason and the next one is tried.
    """
    kept, refused, exposure = [], [], 0
    for candidate in sorted(candidates, key=lambda c: (-int(c['return_bps']), str(c['instrument_id']))):
        if len(kept) >= limits['max_positions']:
            refused.append(dict(candidate, reason='OVERNIGHT_POSITION_LIMIT_REACHED'))
        elif exposure + int(candidate['exposure_minor']) > limits['max_exposure_minor']:
            refused.append(dict(candidate, reason='OVERNIGHT_EXPOSURE_LIMIT_REACHED'))
        else:
            kept.append(candidate)
            exposure += int(candidate['exposure_minor'])
    return kept, refused


def size_entry(policy, *, price_minor, positions, buying_power_minor, ledger_policy, instrument=None):
    """Largest whole quantity inside every owner and Paper-account bound, and which bound binds.

    ``max_per_trade_risk_minor`` bounds the loss of an adverse move of the owner's
    ``assumed_adverse_move_bps``. It is a sizing bound, not a loss guarantee: a stop is
    not a guaranteed fill. The existing pre-trade risk engine and Paper risk path still
    decide independently afterwards and may only reduce this quantity.
    """
    risk = policy['risk']
    if not isinstance(price_minor, int) or price_minor <= 0:
        return dict(quantity=0, binding='REFERENCE_PRICE_UNAVAILABLE', bounds={})
    exposure = exposure_minor(positions)
    if exposure is None:
        return dict(quantity=0, binding='PORTFOLIO_VALUATION_NOT_CURRENT', bounds={})
    if instrument and instrument.get('instrument_kind') in ('CRYPTO_PAIR', 'FUTURE_CONTRACT', 'OPTION_CONTRACT'):
        try:
            step = Decimal(str(instrument.get('quantity_step', '1' if instrument['instrument_kind'] != 'CRYPTO_PAIR' else 'NaN')))
            minimum = Decimal(str(instrument.get('minimum_quantity', step)))
            multiplier = Decimal(str(instrument.get('contract_multiplier', 'NaN')))
            scale = Decimal(str(instrument.get('price_scale', 100)))
            if any(not value.is_finite() or value <= 0 for value in (step, minimum, multiplier, scale)):
                raise ValueError('invalid economics')
        except (ValueError, InvalidOperation):
            return dict(quantity=0, binding='INSTRUMENT_QUANTITY_RULES_UNAVAILABLE', bounds={})
        unit_cost = Decimal(price_minor) * multiplier * int(ledger_policy.get('price_scale', 100)) / scale
        amounts = dict(MAX_POSITION_NOTIONAL=risk['max_position_notional_minor'],
                       MAX_PER_TRADE_RISK=Decimal(risk['max_per_trade_risk_minor']) * 10000 / risk['assumed_adverse_move_bps'],
                       MAX_AGGREGATE_EXPOSURE=max(0, risk['max_aggregate_exposure_minor'] - exposure),
                       BUYING_POWER=max(0, int(buying_power_minor)))
        # Share-count caps remain upper bounds in base units/contracts; no allowance is multiplied per scope.
        bounds = {name: (Decimal(value) / unit_cost / step).to_integral_value(rounding=ROUND_FLOOR) * step
                  for name, value in amounts.items()}
        if instrument['instrument_kind'] == 'CRYPTO_PAIR' and ledger_policy.get('crypto_caps_version'):
            # The account's frozen crypto terms replace the unit caps with dollar caps (owner decision 5).
            caps = dict(PAPER_ACCOUNT_MAX_ORDER_NOTIONAL=ledger_policy['crypto_max_order_notional_minor'],
                        PAPER_ACCOUNT_MAX_POSITION_NOTIONAL=ledger_policy['crypto_max_position_notional_minor'])
            bounds.update({name: (Decimal(value) / unit_cost / step).to_integral_value(rounding=ROUND_FLOOR) * step
                           for name, value in caps.items()})
        else:
            bounds.update(PAPER_ACCOUNT_MAX_ORDER_SHARES=Decimal(ledger_policy['max_order_shares']),
                          PAPER_ACCOUNT_MAX_POSITION_SHARES=Decimal(ledger_policy['max_position_shares']))
        binding = min(bounds, key=lambda name: (bounds[name], name))
        quantity = (bounds[binding] / step).to_integral_value(rounding=ROUND_FLOOR) * step
        quantity = quantity if quantity >= minimum else Decimal(0)
        fractional = instrument['instrument_kind'] == 'CRYPTO_PAIR'
        return dict(quantity=format(quantity, 'f') if fractional else int(quantity), binding=binding,
                    bounds={key: format(value, 'f') for key, value in bounds.items()})
    bounds = dict(
        MAX_POSITION_NOTIONAL=risk['max_position_notional_minor'] // price_minor,
        MAX_PER_TRADE_RISK=(risk['max_per_trade_risk_minor'] * 10000 // risk['assumed_adverse_move_bps']) // price_minor,
        MAX_AGGREGATE_EXPOSURE=max(0, risk['max_aggregate_exposure_minor'] - exposure) // price_minor,
        BUYING_POWER=max(0, int(buying_power_minor)) // price_minor,
        PAPER_ACCOUNT_MAX_ORDER_SHARES=int(ledger_policy['max_order_shares']),
        PAPER_ACCOUNT_MAX_POSITION_SHARES=int(ledger_policy['max_position_shares']),
    )
    binding = min(bounds, key=lambda name: (bounds[name], name))
    return dict(quantity=int(bounds[binding]), binding=binding, bounds=bounds)


def unsizeable_from_flat(order_bounds, *, price_minor, instrument=None):
    """None when an entry from a flat account could be sized under these caps; otherwise the binding bound.

    ``order_bounds`` holds the owner's ``risk`` and the Paper account's ``paper_account`` caps. Account state is
    left out (no positions, buying power at the aggregate cap): it changes from cycle to cycle, the caps do not, so
    only an instrument that no entry could ever size is named. The order path still sizes and gates every entry."""
    risk = order_bounds['risk']
    sizing = size_entry(dict(risk=risk), price_minor=price_minor, positions=[],
                        buying_power_minor=risk['max_aggregate_exposure_minor'],
                        ledger_policy=order_bounds['paper_account'], instrument=instrument)
    quantity = Decimal(str(sizing['quantity']))
    if entry_below_minimum(quantity, instrument):
        return sizing['binding']  # the reason ``execute_decision`` would record with SIZING_BELOW_MINIMUM
    minimum = (instrument or {}).get('minimum_notional')
    if minimum is not None and quantity * Decimal(price_minor) / Decimal(str(instrument['price_scale'])) < Decimal(str(minimum)):
        return 'VENUE_MINIMUM_NOTIONAL'
    return None


def decision_permitted(policy, decision):
    """Whether the owner's policy lets this already-gated Action Decision reach the Paper adapter."""
    state, risk = decision.get('action_state'), policy['risk']
    if state == 'ENTER':
        if not risk['allow_entries']:
            return 'AUTOMATION_ENTRIES_DISABLED'
        if decision.get('direction') == 'LONG' and not risk['allow_long']:
            return 'AUTOMATION_LONG_NOT_PERMITTED'
        if decision.get('direction') == 'SHORT' and not risk['allow_short']:
            return 'AUTOMATION_SHORT_NOT_PERMITTED'
        if decision.get('direction') not in ('LONG', 'SHORT'):
            return 'AUTOMATION_DIRECTION_UNAVAILABLE'
        if (decision.get('instrument') or {}).get('universe') not in risk['allowed_universes']:
            return 'AUTOMATION_INSTRUMENT_NOT_ALLOWED'
        return None
    if state == 'EXIT':
        if not risk['allow_exits']:
            return 'AUTOMATION_EXITS_DISABLED'
        server = bool(decision.get('server_exit'))
        if server and not policy['exits']['on_stop_breach']:
            return 'AUTOMATION_STOP_EXIT_DISABLED'
        if not server and not policy['exits']['on_thesis_exit']:
            return 'AUTOMATION_THESIS_EXIT_DISABLED'
        return None
    return 'ACTION_NOT_EXECUTABLE'


def derive_status(*, configured, armed, desired, emergency, error, blockers, session_eligible):
    """One primary state. RUNNING only when the controller can evaluate evidence and act on it."""
    if not configured:
        return AutomationStatus.NOT_CONFIGURED
    if emergency:
        return AutomationStatus.EMERGENCY_STOPPED
    if not armed:
        return AutomationStatus.DISARMED
    if desired == 'STOPPED':
        return AutomationStatus.STOPPED
    if desired == 'PAUSED':
        return AutomationStatus.PAUSED
    if error:
        return AutomationStatus.ERROR
    for category, status in (('AUTHORITY', AutomationStatus.BLOCKED_BY_AUTHORITY),):
        if any(b['category'] == category for b in blockers):
            return status
    if not session_eligible:
        return AutomationStatus.WAITING_FOR_MARKET
    for category, status in (('DATA', AutomationStatus.BLOCKED_BY_DATA), ('RISK', AutomationStatus.BLOCKED_BY_RISK),
                             ('BUDGET', AutomationStatus.BLOCKED_BY_BUDGET)):
        if any(b['category'] == category for b in blockers):
            return status
    return AutomationStatus.RUNNING


def intent_identity(account_id, decision_id):
    """One Paper intent per Action Decision per account: the order's idempotency key."""
    return 'PAI-' + input_hash_from_dict(dict(account=account_id, decision=decision_id))[:40]


def universe_fingerprint(*, scope_hash, session_date, universe_count=None):
    """The facts a complete selection is only valid for, as a small comparable record.

    Only things the controller can observe without paying for a model. ``universe_count`` is
    ``None`` whenever the current row count has not been read, and an unobserved fact is
    never reported as a change: the scheduler does not invent membership movement it did
    not see. ``scope_hash`` and ``session_date`` are always known, so a new trading session
    or a changed Screener scope is always a material change of the evaluated universe.
    """
    return dict(schema=UNIVERSE_FINGERPRINT_SCHEMA, scope=scope_hash, session_date=session_date,
                universe_count=universe_count)


def universe_material_change(prior, current):
    """Reason codes for a material difference between two universe fingerprints; empty means unchanged.

    ``prior is None`` is the absence of a completed selection, not a change; the scheduler
    treats that case as its own RUN reason instead of a material change.
    """
    if prior is None or current is None:
        return []
    reasons = []
    if current.get('session_date') != prior.get('session_date'):
        reasons.append('NEW_SESSION')
    if current.get('scope') != prior.get('scope'):
        reasons.append('SCOPE_CHANGED')
    before, after = prior.get('universe_count'), current.get('universe_count')
    if before is not None and after is not None and before != after:
        reasons.append('UNIVERSE_MEMBERSHIP_CHANGED')
    return reasons


def should_run_universe(facts):
    """Pure adaptive decision: should the full-universe AI evaluation start now?

    Deterministic and side-effect free: it reads only facts the controller already computed and
    never touches the clock, a provider, a model, the ledger or a repository. Distinct from the
    fixed ``universe_evaluation_interval_seconds`` timer it replaces, it separates four outcomes
    and always states the exact reason:

    * ``DEFER`` — worth running, but not now and possibly without any owner action (an active run,
      a retry backoff, an unhealthy provider, the minimum separation not yet elapsed).
    * ``SKIP`` — nothing worth paying for: the last complete selection is still inside its maximum
      useful age and the evaluation inputs have not materially changed.
    * ``BLOCK`` — cannot start without a change the controller cannot make itself (the daily run
      limit or the daily allowance is exhausted, the plan cannot fit the remaining allowance, the
      session is not eligible).
    * ``RUN`` — start one now.

    An owner policy that supplies no adaptive fields keeps the legacy behaviour exactly: after the
    minimum separation elapses the run happens (``UNIVERSE_MIN_SEPARATION_ELAPSED``).
    """
    schedule = facts['schedule']
    now = float(facts['now'])
    minimum = int(schedule['universe_evaluation_interval_seconds'])
    max_age = schedule.get('universe_max_age_seconds')

    def verdict(decision, codes, next_eligible=None, **detail):
        return dict(decision=str(decision), reason_codes=list(dict.fromkeys(codes)),
                    next_eligible_epoch=next_eligible, detail=detail)

    if facts.get('active_run_id'):
        return verdict(UniverseDecision.DEFER, ['UNIVERSE_RUN_ACTIVE'], run_id=facts['active_run_id'])
    # Optional inference-only hours never change collection or legacy Paper session authority.
    inference_hours = facts.get('inference_session')
    if inference_hours is not None and inference_hours.get('allowed') is not True:
        return verdict(UniverseDecision.DEFER, [inference_hours.get('reason') or 'INFERENCE_SESSION_NOT_VERIFIED'])
    if facts.get('session_label') not in (facts.get('sessions') or ()):
        return verdict(UniverseDecision.BLOCK, ['UNIVERSE_SESSION_NOT_ELIGIBLE'],
                       session_label=facts.get('session_label'))
    backoff_until = facts.get('backoff_until')
    if backoff_until is not None and now < float(backoff_until):
        return verdict(UniverseDecision.DEFER, ['UNIVERSE_RETRY_BACKOFF'], next_eligible=float(backoff_until),
                       consecutive_failures=facts.get('consecutive_failures'),
                       last_failure_code=facts.get('last_failure_code'))
    gate = facts.get('provider_gate') or {}
    if not gate.get('allowed'):
        reason = gate.get('reason') or 'UNIVERSE_RESOURCE_GATE'
        if gate.get('kind') == 'BUDGET':
            return verdict(UniverseDecision.BLOCK, [reason], gate='DAILY_ALLOWANCE')
        return verdict(UniverseDecision.DEFER, [reason], gate='PROVIDER_HEALTH')
    cap = schedule.get('universe_max_runs_per_day')
    started = int((facts.get('runs_today') or {}).get('started') or 0)
    if cap is not None and started >= int(cap):
        # A higher interval cannot fix this: the owner's own daily workload ceiling has been spent.
        return verdict(UniverseDecision.BLOCK, ['UNIVERSE_DAILY_RUN_LIMIT_REACHED'],
                       runs_started=started, runs_per_day=int(cap))
    feasibility = facts.get('feasibility') or {}
    if feasibility and feasibility.get('feasible') is False:
        # A plan that cannot fit today's remaining allowance cannot fit later today either: usage only grows.
        return verdict(UniverseDecision.BLOCK, ['UNIVERSE_PLAN_INFEASIBLE'], **feasibility)
    last_started = facts.get('last_started_epoch')
    if last_started is not None and now - float(last_started) < minimum:
        return verdict(UniverseDecision.DEFER, ['UNIVERSE_MIN_SEPARATION'], next_eligible=float(last_started) + minimum,
                       remaining_seconds=int(minimum - (now - float(last_started))), minimum_separation_seconds=minimum)
    complete = facts.get('last_complete')
    if complete is None or complete.get('finished_at_epoch') is None:
        return verdict(UniverseDecision.RUN, ['UNIVERSE_NO_COMPLETE_SELECTION'])
    reasons = list(facts.get('material_change') or [])
    if schedule.get('universe_material_change_trigger') and reasons:
        return verdict(UniverseDecision.RUN, ['UNIVERSE_MATERIAL_CHANGE', *reasons], material_change=reasons)
    if max_age is None:
        # Legacy policy: no maximum useful age was configured, so the minimum separation is the whole schedule.
        return verdict(UniverseDecision.RUN, ['UNIVERSE_MIN_SEPARATION_ELAPSED'], minimum_separation_seconds=minimum)
    age = now - float(complete['finished_at_epoch'])
    if age >= int(max_age):
        return verdict(UniverseDecision.RUN, ['UNIVERSE_SELECTION_MAX_AGE_EXCEEDED'],
                       selection_age_seconds=int(age), max_age_seconds=int(max_age))
    return verdict(UniverseDecision.SKIP, ['UNIVERSE_SELECTION_FRESH_AND_UNCHANGED'],
                   next_eligible=float(complete['finished_at_epoch']) + int(max_age),
                   selection_age_seconds=int(age), max_age_seconds=int(max_age),
                   material_change=reasons or ['NO_MATERIAL_CHANGE_OBSERVED'])


def plan_local_inference_dry_run(records, **facts):
    """Optional offline local-record plan; retains existing adaptive/provider/budget boundaries."""
    from ..scheduling.local_plan import plan_local_inference_dry_run as plan

    return plan(records, **facts)
