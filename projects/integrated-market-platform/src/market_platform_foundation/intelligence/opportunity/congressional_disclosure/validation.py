"""Fail-closed validation for congressional PTR disclosure assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from ...contracts import EventV1, QualityState, SnapshotV1
from .adapters import accepts_congressional_disclosure_event, extract_congressional_disclosure_facts
from .constants import RUNTIME_CLOCK_KEYS
from .facts import CongressionalDisclosureFacts


class CongressionalDisclosureFailureCode(StrEnum):
    EVENT_NOT_ACCEPTED = "CONGRESSIONAL_PTR_EVENT_NOT_ACCEPTED"
    FACTS_UNAVAILABLE = "CONGRESSIONAL_PTR_FACTS_UNAVAILABLE"
    DOC_ID_REQUIRED = "CONGRESSIONAL_PTR_DOC_ID_REQUIRED"
    EVENT_CLOCKS_INVALID = "CONGRESSIONAL_PTR_EVENT_CLOCKS_INVALID"
    SNAPSHOT_BEFORE_AVAILABILITY = "CONGRESSIONAL_PTR_SNAPSHOT_BEFORE_AVAILABILITY"
    EVENT_QUALITY_INVALID = "CONGRESSIONAL_PTR_EVENT_QUALITY_INVALID"


@dataclass(frozen=True, slots=True)
class CongressionalDisclosureValidation:
    ok: bool
    reason_codes: tuple[str, ...] = ()
    facts: CongressionalDisclosureFacts | None = None


def _validate_payload_clocks(event: EventV1) -> tuple[bool, tuple[str, ...]]:
    clocks = event.payload.get("clocks")
    if not isinstance(clocks, Mapping):
        return False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,)
    for key in RUNTIME_CLOCK_KEYS:
        if key not in clocks:
            return False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,)
    filing_pub = clocks.get("filing_publication_time_ns")
    platform_recv = clocks.get("platform_received_time_ns")
    if not isinstance(filing_pub, int) or filing_pub <= 0:
        return False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,)
    if not isinstance(platform_recv, int) or platform_recv <= 0:
        return False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,)
    economic = clocks.get("economic_event_time_ns")
    if isinstance(economic, int) and economic > 0:
        if event.available_time_ns <= economic:
            return False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,)
    return True, ()


def validate_congressional_disclosure_inputs(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
) -> CongressionalDisclosureValidation:
    if event.quality.state == QualityState.INVALID:
        return CongressionalDisclosureValidation(False, (CongressionalDisclosureFailureCode.EVENT_QUALITY_INVALID.value,))
    if event.event_time_ns <= 0 or event.available_time_ns <= 0:
        return CongressionalDisclosureValidation(False, (CongressionalDisclosureFailureCode.EVENT_CLOCKS_INVALID.value,))
    clocks_ok, clock_reasons = _validate_payload_clocks(event)
    if not clocks_ok:
        return CongressionalDisclosureValidation(False, clock_reasons)
    if snapshot.decision_time_ns < event.available_time_ns:
        return CongressionalDisclosureValidation(
            False,
            (CongressionalDisclosureFailureCode.SNAPSHOT_BEFORE_AVAILABILITY.value,),
        )
    if not accepts_congressional_disclosure_event(event):
        return CongressionalDisclosureValidation(False, (CongressionalDisclosureFailureCode.EVENT_NOT_ACCEPTED.value,))
    facts = extract_congressional_disclosure_facts(event)
    if facts is None:
        return CongressionalDisclosureValidation(False, (CongressionalDisclosureFailureCode.FACTS_UNAVAILABLE.value,))
    if not facts.doc_id.strip():
        return CongressionalDisclosureValidation(False, (CongressionalDisclosureFailureCode.DOC_ID_REQUIRED.value,))
    return CongressionalDisclosureValidation(True, (), facts)


__all__ = [
    "CongressionalDisclosureFailureCode",
    "CongressionalDisclosureValidation",
    "validate_congressional_disclosure_inputs",
]
