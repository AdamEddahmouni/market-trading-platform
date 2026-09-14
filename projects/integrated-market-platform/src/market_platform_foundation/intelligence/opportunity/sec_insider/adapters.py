"""EventV1 payload adapters — no EventV1 schema changes."""

from __future__ import annotations

from typing import Any, Mapping

from ...contracts import EventV1
from .constants import LANE_PAYLOAD_KIND, PAYLOAD_SECTION
from .facts import SecInsiderDisclosureFacts, facts_from_market_trackers_row


def accepts_sec_insider_event(event: EventV1) -> bool:
    payload = event.payload
    section = payload.get(PAYLOAD_SECTION)
    if not isinstance(section, Mapping):
        return False
    if payload.get("lane_payload_kind") == LANE_PAYLOAD_KIND:
        return True
    if str(event.event_type).upper() == "FILING":
        return True
    return payload.get("lane_payload_kind") == LANE_PAYLOAD_KIND


def extract_sec_insider_facts(event: EventV1) -> SecInsiderDisclosureFacts | None:
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
    body = dict(filing_payload)
    body["lane_payload_kind"] = lane_payload_kind
    body[PAYLOAD_SECTION] = dict(sec_insider_row)
    return body


__all__ = [
    "accepts_sec_insider_event",
    "extract_sec_insider_facts",
    "filing_payload_with_sec_insider_section",
]
