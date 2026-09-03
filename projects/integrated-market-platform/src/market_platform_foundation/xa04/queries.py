"""XA catalog repository query helpers (IMP-XA-04)."""

from __future__ import annotations

from market_platform_foundation.xa02.admission import eligible_at_decision_time
from market_platform_foundation.xa02.contracts import AdmittedObservation, AdmissionEnvelope


def validate_limit(limit: int) -> int:
    if limit <= 0:
        raise ValueError("LIMIT_MUST_BE_POSITIVE")
    return limit


def envelope_eligible_at_decision_time(envelope: AdmissionEnvelope, decision_time: str) -> bool:
    if not envelope.available_time:
        return False
    return envelope.available_time <= decision_time


def filter_scalar_observations_as_of(
    rows: tuple[AdmittedObservation, ...] | list[AdmittedObservation],
    decision_time: str,
    *,
    canonical_indicator_id: str | None = None,
    limit: int = 1000,
) -> tuple[AdmittedObservation, ...]:
    active_limit = validate_limit(limit)
    filtered = [
        row
        for row in rows
        if eligible_at_decision_time(row, decision_time)
        and (canonical_indicator_id is None or row.canonical_indicator_id == canonical_indicator_id)
    ]
    filtered.sort(key=lambda row: (row.available_time, row.observation_id))
    return tuple(filtered[:active_limit])


def filter_admission_envelopes_as_of(
    rows: tuple[AdmissionEnvelope, ...] | list[AdmissionEnvelope],
    decision_time: str,
    *,
    source_subject_id: str | None = None,
    limit: int = 1000,
) -> tuple[AdmissionEnvelope, ...]:
    active_limit = validate_limit(limit)
    filtered = [
        row
        for row in rows
        if envelope_eligible_at_decision_time(row, decision_time)
        and (source_subject_id is None or row.source_subject_id == source_subject_id)
    ]
    filtered.sort(key=lambda row: (row.available_time, row.observation_id))
    return tuple(filtered[:active_limit])
