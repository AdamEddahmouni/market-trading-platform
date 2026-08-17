"""Read-only disclosure projections for UI-001."""

from __future__ import annotations

from typing import Any

from ..features.institutional import get_institutional_ledger


def disclosure_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family="regulatory_disclosure",
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def build_workspace_disclosure_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Institutional disclosure not entitled. Fail-closed per ADR-WHALE-001.",
            "events": [],
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    events = ledger.query_disclosure_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not events:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible disclosure events for this symbol at replay cutoff.",
            "events": [],
            "reason": "WHALE_NO_PIT_ELIGIBLE_DISCLOSURE",
            "research_only": True,
            "symbol": instrument_id,
        }
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "SEC filings are delayed public disclosures, not a live tape. "
            "Research-only per ADR-WHALE-001."
        ),
        "disclosure_lag_note": "SEC filings are delayed public disclosures, not a live tape.",
        "events": events,
        "event_count": len(events),
        "ledger_id": ledger.ledger_id,
        "provider_id": "sec.edgar.fixture",
        "research_only": True,
        "symbol": instrument_id,
    }


__all__ = [
    "build_workspace_disclosure_payload",
    "disclosure_available",
]
