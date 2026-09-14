"""Fail-closed validation for SEC insider disclosure assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from ...contracts import EventV1, QualityState, SnapshotV1
from .adapters import accepts_sec_insider_event, extract_sec_insider_facts, is_lane_b_insider_ownership_event
from .constants import LANE_B_CLOCK_KEYS
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


def _validate_lane_b_payload_clocks(event: EventV1) -> tuple[bool, tuple[str, ...]]:
    if not is_lane_b_insider_ownership_event(event):
        return True, ()
    clocks = event.payload.get("clocks")
    if not isinstance(clocks, Mapping):
        return False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,)
    for key in LANE_B_CLOCK_KEYS:
        if key not in clocks:
            return False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,)
    filing_pub = clocks.get("filing_publication_time_ns")
    platform_recv = clocks.get("platform_received_time_ns")
    if not isinstance(filing_pub, int) or filing_pub <= 0:
        return False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,)
    if not isinstance(platform_recv, int) or platform_recv <= 0:
        return False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,)
    economic = clocks.get("economic_event_time_ns")
    if isinstance(economic, int) and economic > 0:
        if event.available_time_ns <= economic:
            return False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,)
    return True, ()


def validate_sec_insider_inputs(*, event: EventV1, snapshot: SnapshotV1) -> SecInsiderValidation:
    if event.quality.state == QualityState.INVALID:
        return SecInsiderValidation(False, (SecInsiderFailureCode.EVENT_QUALITY_INVALID.value,))
    if event.event_time_ns <= 0 or event.available_time_ns <= 0:
        return SecInsiderValidation(False, (SecInsiderFailureCode.EVENT_CLOCKS_INVALID.value,))
    clocks_ok, clock_reasons = _validate_lane_b_payload_clocks(event)
    if not clocks_ok:
        return SecInsiderValidation(False, clock_reasons)
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
