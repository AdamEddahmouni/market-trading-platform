"""Anchor (P0) freezing at forecast registration (BUILD 15)."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..contracts.forecast import ForecastV1
from ..persistence.repository import IntelligenceRepository
from ..snapshots.resolver import resolve_snapshot
from .errors import OutcomeRegistrationError
from .observations import event_observation_kind, event_to_tape_row, observation_from_event
from .p6_compat import p6_reference_price
from .policy import OutcomeSettlementPolicy
from .types import PriceObservationReceipt, UnlabelableReason


def _eligible_anchor_events(
    events: tuple[EventV1, ...],
    *,
    decision_time_ns: int,
    instrument_id: str,
    observation_kinds: tuple[str, ...],
) -> tuple[EventV1, ...]:
    allowed = {kind.upper() for kind in observation_kinds}
    rows: list[EventV1] = []
    for event in events:
        if event.instrument_id != instrument_id:
            continue
        if event_observation_kind(event) not in allowed:
            continue
        if event.event_time_ns > decision_time_ns:
            continue
        if event.available_time_ns > decision_time_ns:
            continue
        rows.append(event)
    return tuple(rows)


def _events_for_forecast_context(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
) -> tuple[EventV1, ...]:
    snapshot = repository.get_snapshot(forecast.snapshot_id)
    if snapshot is None:
        raise OutcomeRegistrationError(
            "FORECAST_SNAPSHOT_MISSING",
            details={"snapshot_id": forecast.snapshot_id, "forecast_id": forecast.forecast_id},
        )
    resolved = resolve_snapshot(snapshot, repository, strict=False)
    if resolved.events:
        return resolved.events
    instrument_ids = forecast.scope.instrument_ids
    instrument_id = forecast.target.instrument_id
    if instrument_ids and instrument_id not in instrument_ids:
        raise OutcomeRegistrationError(
            "TARGET_INSTRUMENT_NOT_IN_SCOPE",
            details={"instrument_id": instrument_id},
        )
    return repository.query_events_as_of(
        forecast.decision_time_ns,
        instrument_id=instrument_id,
        limit=10_000,
    )


def freeze_anchor_observation(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
    *,
    policy: OutcomeSettlementPolicy,
) -> PriceObservationReceipt:
    """Resolve and freeze P0 from legal forecast-time context only."""
    instrument_id = forecast.target.instrument_id
    decision_time_ns = forecast.decision_time_ns
    events = _events_for_forecast_context(forecast, repository)
    eligible = _eligible_anchor_events(
        events,
        decision_time_ns=decision_time_ns,
        instrument_id=instrument_id,
        observation_kinds=policy.observation_kinds,
    )
    tape = []
    for event in eligible:
        row = event_to_tape_row(event)
        if row is not None:
            tape.append(row)
    if not tape:
        raise OutcomeRegistrationError(
            UnlabelableReason.NO_VALID_ANCHOR.value,
            details={"forecast_id": forecast.forecast_id},
        )
    ref = p6_reference_price(tape, decision_time_ns=decision_time_ns)
    if ref is None:
        raise OutcomeRegistrationError(
            UnlabelableReason.NO_VALID_ANCHOR.value,
            details={"forecast_id": forecast.forecast_id},
        )
    anchor_event_id = str(ref.get("trade_id") or "")
    anchor_event = next((event for event in eligible if event.event_id == anchor_event_id), None)
    if anchor_event is None:
        raise OutcomeRegistrationError(
            UnlabelableReason.NO_VALID_ANCHOR.value,
            details={"forecast_id": forecast.forecast_id},
        )
    if anchor_event.available_time_ns > decision_time_ns:
        raise OutcomeRegistrationError(
            UnlabelableReason.ANCHOR_TEMPORALLY_INVALID.value,
            details={"forecast_id": forecast.forecast_id},
        )
    receipt = observation_from_event(anchor_event)
    if receipt is None:
        raise OutcomeRegistrationError(
            UnlabelableReason.NO_VALID_ANCHOR.value,
            details={"forecast_id": forecast.forecast_id},
        )
    return receipt


__all__ = ["freeze_anchor_observation"]
