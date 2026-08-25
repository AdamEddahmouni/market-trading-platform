"""Shared persistence query helpers (BUILD 04.5)."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..contracts.evidence import EvidenceV1
from ..contracts.forecast import ForecastV1
from ..contracts.opportunity import OpportunityV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..contracts.signal import SignalV1
from ..temporal.policy import TemporalIntegrityPolicy
from ..temporal.selection import select_events_as_of
from ..temporal.validation import inspect_signal_temporal_integrity

DEFAULT_QUERY_LIMIT = 1000


def validate_limit(limit: int) -> int:
    if limit <= 0:
        raise ValueError("LIMIT_MUST_BE_POSITIVE")
    return limit


def query_events_as_of(
    events: list[EventV1] | tuple[EventV1, ...],
    decision_time_ns: int,
    *,
    instrument_id: str | None = None,
    event_type: str | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    require_usable: bool = False,
    policy: TemporalIntegrityPolicy | None = None,
) -> tuple[EventV1, ...]:
    """Apply BUILD 02 point-in-time semantics with deterministic ordering."""
    active_limit = validate_limit(limit)
    candidates = list(events)
    if instrument_id is not None:
        candidates = [event for event in candidates if event.instrument_id == instrument_id]
    if event_type is not None:
        candidates = [event for event in candidates if event.event_type == event_type]
    selected = select_events_as_of(
        candidates,
        decision_time_ns,
        policy=policy,
        require_usable=require_usable,
    )
    if len(selected) <= active_limit:
        return selected
    return selected[:active_limit]


def query_signals_as_of(
    signals: list[SignalV1] | tuple[SignalV1, ...],
    decision_time_ns: int,
    *,
    instrument_id: str | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    policy: TemporalIntegrityPolicy | None = None,
) -> tuple[SignalV1, ...]:
    """Return signals whose as_of_time is knowable at decision time."""
    _ = policy
    active_limit = validate_limit(limit)
    eligible: list[SignalV1] = []
    for signal in signals:
        report = inspect_signal_temporal_integrity(signal, decision_time_ns=decision_time_ns)
        if not report.eligible:
            continue
        if instrument_id is not None:
            if instrument_id not in signal.scope.instrument_ids:
                continue
        eligible.append(signal)
    ordered = sorted(
        eligible,
        key=lambda signal: (signal.as_of_time_ns, signal.signal_id),
    )
    if len(ordered) <= active_limit:
        return tuple(ordered)
    return tuple(ordered[:active_limit])


def filter_evidence_by_snapshot(
    evidence_rows: list[EvidenceV1] | tuple[EvidenceV1, ...],
    snapshot_id: str,
) -> tuple[EvidenceV1, ...]:
    rows = [row for row in evidence_rows if row.snapshot_id == snapshot_id]
    return tuple(sorted(rows, key=lambda row: row.evidence_id))


def filter_forecasts_by_instrument(
    forecasts: list[ForecastV1] | tuple[ForecastV1, ...],
    instrument_id: str,
    *,
    decision_from_ns: int | None = None,
    decision_to_ns: int | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> tuple[ForecastV1, ...]:
    active_limit = validate_limit(limit)
    rows: list[ForecastV1] = []
    for forecast in forecasts:
        if instrument_id not in forecast.scope.instrument_ids:
            continue
        if decision_from_ns is not None and forecast.decision_time_ns < decision_from_ns:
            continue
        if decision_to_ns is not None and forecast.decision_time_ns > decision_to_ns:
            continue
        rows.append(forecast)
    ordered = sorted(rows, key=lambda row: (row.decision_time_ns, row.forecast_id))
    if len(ordered) <= active_limit:
        return tuple(ordered)
    return tuple(ordered[:active_limit])


def filter_outcomes_by_forecast(
    outcomes: list[OutcomeV1] | tuple[OutcomeV1, ...],
    forecast_id: str,
) -> tuple[OutcomeV1, ...]:
    rows = [row for row in outcomes if row.forecast_id == forecast_id]
    return tuple(sorted(rows, key=lambda row: row.outcome_id))


def filter_prediction_ledger_entries_by_forecast(
    entries: list[PredictionLedgerEntryV1] | tuple[PredictionLedgerEntryV1, ...],
    forecast_id: str,
) -> tuple[PredictionLedgerEntryV1, ...]:
    rows = [row for row in entries if row.forecast_id == forecast_id]
    return tuple(sorted(rows, key=lambda row: row.ledger_entry_id))


def filter_opportunities_by_instrument(
    opportunities: list[OpportunityV1] | tuple[OpportunityV1, ...],
    instrument_id: str,
    *,
    valid_at_ns: int | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> tuple[OpportunityV1, ...]:
    active_limit = validate_limit(limit)
    rows: list[OpportunityV1] = []
    for opportunity in opportunities:
        if instrument_id not in opportunity.scope.instrument_ids:
            continue
        if valid_at_ns is not None:
            if opportunity.valid_until_ns is not None and opportunity.valid_until_ns < valid_at_ns:
                continue
        rows.append(opportunity)
    ordered = sorted(rows, key=lambda row: (row.created_at_ns, row.opportunity_id))
    if len(ordered) <= active_limit:
        return tuple(ordered)
    return tuple(ordered[:active_limit])


def mongo_event_candidate_filter(
    decision_time_ns: int,
    *,
    instrument_id: str | None = None,
    event_type: str | None = None,
) -> dict[str, object]:
    """Mongo prefilter for point-in-time event candidates."""
    query: dict[str, object] = {"available_time_ns": {"$lte": decision_time_ns}}
    if instrument_id is not None:
        query["instrument_id"] = instrument_id
    if event_type is not None:
        query["event_type"] = event_type
    return query


def mongo_event_sort() -> list[tuple[str, int]]:
    return [
        ("available_time_ns", 1),
        ("received_time_ns", 1),
        ("event_time_ns", 1),
        ("event_id", 1),
    ]


def filter_events_by_availability(
    events: list[EventV1] | tuple[EventV1, ...],
    *,
    start_time_ns: int,
    end_time_ns: int,
    instrument_id: str | None = None,
    event_type: str | None = None,
    provider_id: str | None = None,
    limit: int | None = None,
) -> tuple[EventV1, ...]:
    """Return events whose recorded availability falls within [start, end]."""
    if start_time_ns > end_time_ns:
        raise ValueError("AVAILABILITY_RANGE_INVALID")
    candidates: list[EventV1] = []
    for event in events:
        if event.available_time_ns < start_time_ns or event.available_time_ns > end_time_ns:
            continue
        if instrument_id is not None and event.instrument_id != instrument_id:
            continue
        if event_type is not None and event.event_type != event_type:
            continue
        if provider_id is not None and event.source.provider_id != provider_id:
            continue
        candidates.append(event)
    ordered = sorted(candidates, key=lambda row: (row.available_time_ns, row.received_time_ns or 0, row.event_time_ns, row.event_id))
    if limit is None:
        return tuple(ordered)
    active_limit = validate_limit(limit)
    if len(ordered) <= active_limit:
        return tuple(ordered)
    return tuple(ordered[:active_limit])


def mongo_event_availability_range_filter(
    *,
    start_time_ns: int,
    end_time_ns: int,
    instrument_id: str | None = None,
    event_type: str | None = None,
    provider_id: str | None = None,
) -> dict[str, object]:
    """Mongo prefilter for availability-range event loading."""
    if start_time_ns > end_time_ns:
        raise ValueError("AVAILABILITY_RANGE_INVALID")
    query: dict[str, object] = {
        "available_time_ns": {"$gte": start_time_ns, "$lte": end_time_ns},
    }
    if instrument_id is not None:
        query["instrument_id"] = instrument_id
    if event_type is not None:
        query["event_type"] = event_type
    if provider_id is not None:
        query["source.provider_id"] = provider_id
    return query


__all__ = [
    "DEFAULT_QUERY_LIMIT",
    "filter_evidence_by_snapshot",
    "filter_events_by_availability",
    "filter_forecasts_by_instrument",
    "filter_opportunities_by_instrument",
    "filter_outcomes_by_forecast",
    "filter_prediction_ledger_entries_by_forecast",
    "mongo_event_availability_range_filter",
    "mongo_event_candidate_filter",
    "mongo_event_sort",
    "query_events_as_of",
    "query_signals_as_of",
    "validate_limit",
]
