"""AUTO-01 pure autonomous Paper automation policy: owner configuration, sizing bounds, risk gates, status.

No clock, provider, model, ledger or order access. Nothing here is a default trading
setting: every risk, schedule and spending field is supplied by the owner, and a
missing one is an incomplete policy, not a silently chosen value.
"""
from __future__ import annotations

from enum import StrEnum

from .hashing import input_hash_from_dict

POLICY_SCHEMA = 'paper-automation-policy/1.0.0'
ARM_ACKNOWLEDGEMENT = 'ARM_PAPER_ONLY_AUTOMATION'
# The stop monitor, the completed-bar feed and the fill model are regular-session contracts.
SUPPORTED_SESSIONS = ('REGULAR',)
# The experiment account values share positions only.
SUPPORTED_UNIVERSES = ('US_EQUITIES', 'US_ETFS')
# The governed handoff and the deterministic exit are MARKET_NOW_IF_GATES_PASS.
SUPPORTED_ORDER_TYPES = ('MARKET',)
REGULAR_SESSION_MINUTES = 390


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


class IntentState(StrEnum):
    CREATED = 'CREATED'
    PREVIEWED = 'PREVIEWED'
    SUBMITTED = 'SUBMITTED'
    BLOCKED = 'BLOCKED'      # refused before any order existed; a later decision may be tried again
    DEFERRED = 'DEFERRED'    # required evidence unavailable; nothing was forced
    FAILED = 'FAILED'


# An intent in one of these states already produced (or may have produced) an order: never repeated.
INTENT_TERMINAL = frozenset({IntentState.SUBMITTED})

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
_INT_BOUNDS = dict(
    cadence_seconds=(60, 3600), universe_evaluation_interval_seconds=(300, 86400),
    no_new_entries_minutes_before_close=(0, REGULAR_SESSION_MINUTES),
    max_position_notional_minor=(1, 10 ** 13), max_aggregate_exposure_minor=(1, 10 ** 13), max_open_positions=(1, 50),
    max_daily_loss_minor=(1, 10 ** 13), max_per_trade_risk_minor=(1, 10 ** 13), assumed_adverse_move_bps=(1, 10000),
    max_paid_requests_per_day=(0, 100000), max_paid_tokens_per_day=(0, 10 ** 10), max_consecutive_failures=(1, 20),
)


def required_fields():
    """Every owner decision the policy needs, as section.field paths."""
    return ['scope', *(f'{section}.{field}' for section, fields in _SECTIONS.items() for field in fields)]


def build_policy(body, *, account_id, experiment_id, initial_capital_minor, ledger_policy):
    """Validate one complete owner policy and bind it to one Paper experiment account.

    Missing fields are named together (``AUTOMATION_POLICY_INCOMPLETE:a,b``) so the
    owner is asked once. Unknown fields are rejected, not ignored.
    """
    if not isinstance(body, dict) or set(body) - {'scope', *_SECTIONS}:
        raise ValueError('AUTOMATION_POLICY_INVALID')
    if not account_id or not experiment_id:
        raise ValueError('AUTOMATION_PAPER_EXPERIMENT_REQUIRED')
    missing = [] if isinstance(body.get('scope'), dict) else ['scope']
    for section, fields in _SECTIONS.items():
        value = body.get(section)
        if not isinstance(value, dict):
            missing.extend(f'{section}.{field}' for field in fields)
            continue
        if set(value) - set(fields):
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
    schedule, risk, ai = policy['schedule'], policy['risk'], policy['ai']
    for field, allowed, code in (('sessions', SUPPORTED_SESSIONS, 'AUTOMATION_SESSION_UNSUPPORTED'),):
        if not schedule[field] or len(set(schedule[field])) != len(schedule[field]) or set(schedule[field]) - set(allowed):
            raise ValueError(code)
    for field, allowed, code in (('allowed_universes', SUPPORTED_UNIVERSES, 'AUTOMATION_INSTRUMENT_SCOPE_UNSUPPORTED'),
                                 ('order_types', SUPPORTED_ORDER_TYPES, 'AUTOMATION_ORDER_TYPE_UNSUPPORTED')):
        if not risk[field] or len(set(risk[field])) != len(risk[field]) or set(risk[field]) - set(allowed):
            raise ValueError(code)
    if policy['scope'].get('universe') not in risk['allowed_universes']:
        raise ValueError('AUTOMATION_SCOPE_OUTSIDE_ALLOWED_INSTRUMENTS')
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
        if not position.get('quantity'):
            continue
        mark = position.get('mark_minor')
        if not isinstance(mark, int) or mark <= 0:
            return None
        total += abs(int(position['quantity'])) * mark
    return total


def entry_risk_blockers(policy, *, positions, valuation, day_start_equity_minor, pending_orders, minutes_to_close):
    """Portfolio-level reasons a new entry may not be attempted now. Exits are never gated here."""
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
    if pending_orders:
        blockers.append('WORKING_ORDERS_PRESENT')
    if minutes_to_close is None or minutes_to_close <= policy['schedule']['no_new_entries_minutes_before_close']:
        blockers.append('ENTRY_WINDOW_CLOSED')
    return blockers


def size_entry(policy, *, price_minor, positions, buying_power_minor, ledger_policy):
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
