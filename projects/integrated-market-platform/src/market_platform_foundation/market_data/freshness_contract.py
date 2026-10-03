"""Pure per-capability temporal authority. No provider reads or ambient clock.

Delivery, freshness, and intended-use eligibility are independent. Callers
supply source facts and domain policies; retrieval is never a clock fallback.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

VERSION = 'decision-freshness/1.0.0'
MODES = {'REALTIME', 'DELAYED', 'SNAPSHOT', 'PUBLICATION_BASED', 'HISTORICAL', 'REPLAY', 'UNKNOWN'}


def timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if len(value) == 10:
            return parsed.replace(tzinfo=UTC)  # observation date, not an invented intraday event
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def evaluate(*, capability: str, source: str | None, delivery_mode: str, now: str,
             as_of: str | None = None, stale_after_ms: int | None = None,
             policy: str = 'UNKNOWN_POLICY', basis: str = 'UNKNOWN', state: str | None = None,
             reference: bool = False, received_at: str | None = None, fetched_at: str | None = None,
             reason: str | None = None, **clocks: Any) -> dict[str, Any]:
    cutoff = timestamp(now)
    if cutoff is None:
        raise ValueError('INVALID_EVALUATION_TIME')
    if stale_after_ms is not None and (isinstance(stale_after_ms, bool) or not isinstance(stale_after_ms, int) or stale_after_ms < 0):
        raise ValueError('INVALID_FRESHNESS_THRESHOLD')
    mode = delivery_mode if delivery_mode in MODES else 'UNKNOWN'
    observed = timestamp(as_of)
    age = int((cutoff - observed).total_seconds() * 1000) if observed else None
    reasons = [reason] if reason else []
    status = 'UNKNOWN'
    deadline = None
    if state in ('STALE', 'INVALID', 'DISCONNECTED'):
        status = 'STALE' if state == 'STALE' else 'UNAVAILABLE'
        reasons.append(state)
    elif not source or state in ('UNAVAILABLE', 'NOT_ENTITLED', 'NOT_CONFIGURED', 'PROVIDER_UNAVAILABLE', 'CONNECTING', 'NO_CHAIN', 'NO_RECORD', 'AWAITING_DATA', 'PENDING'):
        status = 'UNAVAILABLE'
        reasons.append(state or 'PROVIDER_UNAVAILABLE')
    elif state == 'PARTIAL':
        reasons.append('INSUFFICIENT_SOURCE_EVIDENCE')
    elif observed is None:
        reasons.append('NO_OBSERVATION_TIME')
    elif age is not None and age < 0:
        reasons.append('FUTURE_OBSERVATION_TIME')
    elif state in ('SESSION_CLOSED', 'MARKET_CLOSED'):
        status = 'SESSION_CLOSED'
        reasons.append('SESSION_CLOSED')
    elif mode in ('HISTORICAL', 'REPLAY', 'UNKNOWN'):
        reasons.append('NON_CURRENT_DELIVERY')
    elif stale_after_ms is not None:
        status = 'STALE' if age >= stale_after_ms else 'CURRENT'
        reasons.append('AGE_EXCEEDS_POLICY' if status == 'STALE' else 'WITHIN_POLICY')
        deadline = (observed + timedelta(milliseconds=stale_after_ms)).isoformat().replace('+00:00', 'Z')
    elif state == 'PUBLICATION_CURRENT' and mode == 'PUBLICATION_BASED':
        status = 'CURRENT'  # delegated source-cadence authority, not fetch recency
        reasons.append('SOURCE_PUBLICATION_POLICY')
    else:
        reasons.append('UNKNOWN_FRESHNESS_POLICY')
    if mode == 'DELAYED':
        reasons.append('PROVIDER_DELAYED')
    if mode == 'PUBLICATION_BASED':
        reasons.append('PUBLICATION_BASED')
    current = status == 'CURRENT' and mode in ('REALTIME', 'SNAPSHOT') and not reference
    reference_ok = reference and observed is not None and age >= 0 and status in ('CURRENT', 'SESSION_CLOSED', 'UNKNOWN') and source is not None and mode not in ('UNKNOWN', 'REPLAY', 'HISTORICAL')
    admissibility = 'ADMISSIBLE' if current or reference_ok and status == 'CURRENT' else 'DEGRADED' if reference_ok or status == 'CURRENT' and mode == 'DELAYED' else 'BLOCKED'
    return dict(schema_version=VERSION, capability=capability, source=source, delivery_mode=mode,
                freshness_status=status, decision_admissibility=admissibility,
                eligible_for_current_decision=current, eligible_for_reference=bool(reference_ok),
                decision_role='REFERENCE_CONTEXT' if reference else 'CURRENT_MARKET',
                basis=basis, as_of=as_of, received_at=received_at, fetched_at=fetched_at,
                age_ms=age, stale_after_ms=stale_after_ms, policy=policy, policy_version=VERSION,
                evaluated_at=now, valid_until=deadline, reason_codes=list(dict.fromkeys(reasons)),
                source_state=state, **clocks)


def eligible_evidence(inputs: list[dict], *, now: str, reference: bool = False) -> list[dict]:
    """Consumer gate: re-evaluate at decision cutoff, never trust cached booleans.

    Returns only statuses; consumers join values by capability/identity. Stale
    evidence is excluded in both current and reference use. No AI is invoked.
    """
    cutoff = timestamp(now)
    if cutoff is None:
        raise ValueError("INVALID_EVALUATION_TIME")
    accepted = []
    for item in inputs:
        evaluated = timestamp(item.get("evaluated_at"))
        if evaluated is None or cutoff < evaluated:
            continue  # A later receipt cannot establish evidence at an earlier decision.
        checked = evaluate(capability=item['capability'], source=item['source'], delivery_mode=item['delivery_mode'],
                           now=now, as_of=item.get('as_of'), stale_after_ms=item.get('stale_after_ms'),
                           policy=item['policy'], basis=item['basis'], state=item.get('source_state'),
                           reference=item.get('decision_role') == 'REFERENCE_CONTEXT',
                           reason=';'.join(item.get('reason_codes', [])) or None)
        if checked['eligible_for_reference' if reference else 'eligible_for_current_decision']:
            accepted.append(item)
    return accepted
