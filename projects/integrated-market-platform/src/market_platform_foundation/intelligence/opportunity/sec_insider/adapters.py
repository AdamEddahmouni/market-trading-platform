"""EventV1 payload adapters — Lane B primary, legacy compat optional."""

from __future__ import annotations

from typing import Any, Mapping

from ...contracts import EventV1
from .constants import (
    LANE_B_EVENT_TYPE,
    LANE_B_PROVIDER_ID,
    LANE_PAYLOAD_KIND,
    PAYLOAD_SECTION,
)
from .facts import (
    SecInsiderDisclosureFacts,
    facts_from_lane_b_payload,
    facts_from_market_trackers_row,
)


def is_lane_b_insider_ownership_event(event: EventV1) -> bool:
    if str(event.event_type) != LANE_B_EVENT_TYPE:
        return False
    if event.source.provider_id != LANE_B_PROVIDER_ID:
        return False
    clocks = event.payload.get("clocks")
    if not isinstance(clocks, Mapping):
        return False
    return bool(str(event.payload.get("accession_number") or "").strip())


def is_legacy_sec_insider_compat_event(event: EventV1) -> bool:
    payload = event.payload
    section = payload.get(PAYLOAD_SECTION)
    if not isinstance(section, Mapping):
        return False
    if payload.get("lane_payload_kind") == LANE_PAYLOAD_KIND:
        return True
    return str(event.event_type).upper() == "FILING"


def accepts_sec_insider_event(event: EventV1) -> bool:
    return is_lane_b_insider_ownership_event(event) or is_legacy_sec_insider_compat_event(event)


def extract_sec_insider_facts(event: EventV1) -> SecInsiderDisclosureFacts | None:
    if is_lane_b_insider_ownership_event(event):
        return facts_from_lane_b_payload(event)
    payload = event.payload
    section = payload.get(PAYLOAD_SECTION)
    if isinstance(section, Mapping):
        merged: dict[str, Any] = dict(section)
        merged.setdefault(
            "accessionNumber",
            payload.get("accession_number") or payload.get("accessionNumber"),
        )
        merged.setdefault("formType", payload.get("form_type") or payload.get("formType"))
        if event.instrument_id and not merged.get("instrument_id") and not merged.get("ticker"):
            ticker = event.instrument_id.split(":")[-1]
            merged["instrument_id"] = event.instrument_id
            merged.setdefault("ticker", ticker)
        facts = facts_from_market_trackers_row(merged)
        if facts.accession_number:
            return facts
    return None


def filing_payload_with_sec_insider_section(
    filing_payload: Mapping[str, Any],
    *,
    sec_insider_row: Mapping[str, Any],
    lane_payload_kind: str = LANE_PAYLOAD_KIND,
) -> dict[str, Any]:
    """Legacy compat helper — not Lane B production EventV1."""
    body = dict(filing_payload)
    body["lane_payload_kind"] = lane_payload_kind
    body[PAYLOAD_SECTION] = dict(sec_insider_row)
    return body


__all__ = [
    "accepts_sec_insider_event",
    "extract_sec_insider_facts",
    "filing_payload_with_sec_insider_section",
    "is_lane_b_insider_ownership_event",
    "is_legacy_sec_insider_compat_event",
]
