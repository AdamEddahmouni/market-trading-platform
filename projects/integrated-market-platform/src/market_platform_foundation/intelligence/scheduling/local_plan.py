"""Optional session policy and bounded plans over already retrieved local records.

This is planning policy, not a worker or a second scheduler. It has no provider, collection,
state-store or execution access. The existing adaptive decision remains authoritative when
supplied. A dry run neither reserves budget nor acknowledges a processed revision.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..inference.synthesis_engines import offline_model_route


def inference_session(now: datetime, session_is_trading_day: bool | None) -> dict[str, Any]:
    """Resolve an explicit instant in New York; unknown calendar/timezone facts fail closed."""
    base = dict(timezone='America/New_York', allowed=False, window='UNAVAILABLE', reason=None)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return dict(base, reason='TIMEZONE_REQUIRED')
    try:
        local = now.astimezone(ZoneInfo('America/New_York'))
    except ZoneInfoNotFoundError:
        return dict(base, reason='TIMEZONE_DATA_UNAVAILABLE')
    # A constructed zoneinfo wall time can denote a nonexistent spring hour. Round-trip the
    # supplied timezone before classifying: a fabricated wall clock never becomes an instant.
    roundtrip = now.astimezone(timezone.utc).astimezone(now.tzinfo)
    if roundtrip.replace(tzinfo=None) != now.replace(tzinfo=None):
        return dict(base, reason='INVALID_LOCAL_TIME')
    base.update(local_time=local.isoformat(), session_date=local.date().isoformat())
    if local.weekday() >= 5:
        return dict(base, window='CLOSED', reason='WEEKEND')
    if session_is_trading_day is False:
        return dict(base, window='CLOSED', reason='MARKET_HOLIDAY')
    if session_is_trading_day is not True:
        return dict(base, reason='MARKET_CALENDAR_NOT_VERIFIED')
    minute = local.hour * 60 + local.minute
    window = ('INFERENCE_PAUSE' if minute >= 1200 or minute < 210 else
              'CATCH_UP' if minute < 240 else 'PREMARKET' if minute < 570 else
              'REGULAR' if minute < 960 else 'AFTER_HOURS')
    return dict(base, window=window, allowed=window != 'INFERENCE_PAUSE',
                reason='INFERENCE_PAUSE' if window == 'INFERENCE_PAUSE' else None)


def _remaining_budget(budget: dict[str, Any]) -> tuple[int, int] | None:
    """DailyBudget.status already includes held requests/tokens; never subtract holds twice."""
    fields = ('requests', 'tokens', 'max_requests', 'max_tokens')
    if not isinstance(budget, dict) or any(type(budget.get(k)) is not int or budget[k] < 0 for k in fields):
        return None
    if budget.get('usage_overrun'):
        return None
    return max(0, budget['max_requests'] - budget['requests']), max(0, budget['max_tokens'] - budget['tokens'])


def plan_local_inference_dry_run(records: Sequence[dict[str, Any]], *, now: datetime,
                                 schedule: dict[str, Any], session_is_trading_day: bool | None,
                                 engine: str, model: str, provider_configured: bool,
                                 provider_available: bool | None, resource_allowed: bool,
                                 budget_status: dict[str, Any], provider_gate: dict[str, Any],
                                 previous: dict[str, Any] | None = None,
                                 adaptive_facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Plan bounded local revisions, with explicit owner workload bounds and upstream gates.

    ``max_requests``, ``max_tokens``, ``max_backlog`` must be owner-supplied nonnegative ints.
    Record tokens require token_estimate_scope=REQUEST_AND_OUTPUT_BOUND and supplied worst-case
    estimates (including output/reasoning/schema), not
    tokenizer measurements. ``provider_gate`` carries existing spending/dollar/provider policy;
    absence refuses. No monetary allowance is invented. The caller must acknowledge actual
    completed work separately using ``processed_revision_ids`` pairs; watermark alone is never
    sufficient to suppress late-arriving records. Only the bounded input prefix is inspected.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError('LOCAL_RECORD_SEQUENCE_REQUIRED')
    bounds = ('max_requests', 'max_tokens', 'max_backlog')
    if any(type(schedule.get(k)) is not int or schedule[k] < 0 for k in bounds):
        raise ValueError('INFERENCE_WORKLOAD_BOUNDS_REQUIRED')
    restart = deepcopy(previous) if previous is not None else dict(processed_revision_ids=[], watermark_ns=None)
    if not isinstance(restart, dict) or not isinstance(restart.get('processed_revision_ids'), list):
        raise ValueError('INFERENCE_RESTART_STATE_INVALID')
    pairs = restart['processed_revision_ids']
    if any(not isinstance(p, (list, tuple)) or len(p) != 2 or any(not isinstance(v, str) or not v for v in p) for p in pairs):
        raise ValueError('INFERENCE_RESTART_STATE_INVALID')
    watermark = restart.get('watermark_ns')
    if watermark is not None and (type(watermark) is not int or watermark < 0):
        raise ValueError('INFERENCE_RESTART_STATE_INVALID')
    session = inference_session(now, session_is_trading_day)
    remaining = _remaining_budget(budget_status)
    budget_allowed = remaining is not None and min(remaining) > 0
    upstream_budget_block = provider_gate.get('kind') == 'BUDGET' and provider_gate.get('allowed') is not True
    route = offline_model_route(engine, model, configured=provider_configured,
                                available=provider_available, budget_allowed=budget_allowed and not upstream_budget_block)
    reason = session['reason']
    if reason is None and provider_gate.get('allowed') is not True:
        reason = provider_gate.get('reason') or 'PROVIDER_GATE_NOT_VERIFIED'
    if reason is None and route['state'] != 'SUPPORTED':
        reason = route['reason']
    if reason is None and resource_allowed is not True:
        reason = 'RESOURCE_BLOCKED'
    adaptive = None
    if adaptive_facts is not None:
        from ..inference.paper_automation import should_run_universe

        adaptive = should_run_universe(dict(adaptive_facts, inference_session=session))
        if reason is None and adaptive['decision'] != 'RUN':
            reason = adaptive['reason_codes'][0]
    requests_left, tokens_left = remaining or (0, 0)
    request_bound = min(schedule['max_requests'], requests_left)
    token_bound = min(schedule['max_tokens'], tokens_left)
    scanned = min(len(records), schedule['max_backlog'])
    planned, deferred, duplicates = [], [], []
    seen = {tuple(p) for p in pairs}
    total_tokens = 0
    now_ns = int(now.timestamp() * 1_000_000_000) if session.get('local_time') else None
    for row in records[:scanned]:
        valid = (isinstance(row, dict) and all(isinstance(row.get(k), str) and row[k] for k in ('record_id', 'revision_id'))
                 and type(row.get('estimated_tokens')) is int and row['estimated_tokens'] > 0
                 and type(row.get('available_at_ns')) is int and row['available_at_ns'] >= 0)
        identity = dict(record_id=row.get('record_id'), revision_id=row.get('revision_id')) if isinstance(row, dict) else {}
        if not valid:
            deferred.append(dict(identity, reason='LOCAL_RECORD_INVALID'))
            continue
        key = row['record_id'], row['revision_id']
        if key in seen:
            duplicates.append(dict(identity, reason='REVISION_ALREADY_SEEN'))
            continue
        seen.add(key)
        row_reason = reason
        if row_reason is None and row.get('token_estimate_scope') != 'REQUEST_AND_OUTPUT_BOUND':
            row_reason = 'TOKEN_ESTIMATE_NOT_VERIFIED'
        if row_reason is None and (now_ns is None or row['available_at_ns'] > now_ns):
            row_reason = 'LOCAL_RECORD_NOT_AVAILABLE'
        if row_reason is None and len(planned) >= request_bound:
            row_reason = 'REQUEST_BOUND'
        if row_reason is None and total_tokens + row['estimated_tokens'] > token_bound:
            row_reason = 'TOKEN_BOUND'
        if row_reason:
            deferred.append(dict(identity, reason=row_reason))
        else:
            planned.append(deepcopy(row))
            total_tokens += row['estimated_tokens']
    return dict(schema_version='local-inference-dry-run/1', dry_run=True, session=session,
                collection_independent=True, model_route=route, planned=planned, deferred=deferred,
                duplicates=duplicates, scanned_count=scanned, unscanned_count=len(records) - scanned,
                unscanned_reason='BACKLOG_BOUND' if len(records) > scanned else None,
                planned_requests=len(planned), planned_tokens=total_tokens, restart_state=restart,
                inference_calls=0, budget_reserved=False, adaptive_decision=adaptive)
