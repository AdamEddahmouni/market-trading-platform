"""Fail-closed validation for SEC insider disclosure assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ...contracts import EventV1, QualityState, SnapshotV1
from .adapters import accepts_sec_insider_event, extract_sec_insider_facts
from .facts import SecInsiderDisclosureFacts


class SecInsiderFailureCode(StrEnum):
    EVENT_NOT_ACCEPTED = "SEC_INSIDER_EVENT_NOT_ACCEPTED"
    FACTS_UNAVAILABLE = "SEC_INSIDER_FACTS_UNAVAILABLE"
    ACCESSION_REQUIRED = "SEC_INSIDER_ACCESSION_REQUIRED"
    EVENT_CLOCKS_INVALID = "SEC_INSIDER_EVENT_CLOCKS_INVALID"
    SNAPSHOT_BEFORE_AVAILABILITY = "SEC_INSIDER_SNAPSHOT_BEFORE_AVAILABILITY"
    EVENT_QUALITY_INVALID = "SEC_INSIDER_EVENT_QUALITY_INVALID"


@dataclass(frozen=True, slots=True)
class SecInsiderValidation:
    ok: bool
    reason_codes: tuple[str, ...] = ()
    facts: SecInsiderDisclosureFacts | None = None


def validate_sec_insider_inputs(*, event: EventV1, snapshot: SnapshotV1) -> SecInsiderValidation:
    if event.quality.state == QualityState.INVALID:
        return SecInsiderValidation(False, (SecInsiderFailureCode.EVENT_QUALITY_INVALID.value,))
    if event.event_time_ns <= 0 or event.available_time_ns <= 0:
        return SecInsiderValidation(False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,))
    if snapshot.decision_time_ns < event.available_time_ns:
        return SecInsiderValidation(
            False,
            (SecInsiderFailureCode.SNAPSHOT_BEFORE_AVAILABILITY.value,),
        )
    if not accepts_sec_insider_event(event):
        return SecInsiderValidation(False, (SecInsiderFailureCode.EVENT_NOT_ACCEPTED.value,))
    facts = extract_sec_insider_facts(event)
    if facts is None:
        return SecInsiderValidation(False, (SecInsiderFailureCode.FACTS_UNAVAILABLE.value,))
    if not facts.accession_number.strip():
        return SecInsiderValidation(False, (SecInsiderFailureCode.ACCESSION_REQUIRED.value,))
    return SecInsiderValidation(True, (), facts)


__all__ = ["SecInsiderFailureCode", "SecInsiderValidation", "validate_sec_insider_inputs"]
