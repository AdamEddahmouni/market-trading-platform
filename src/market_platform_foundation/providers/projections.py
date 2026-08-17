"""Read-only disclosure and order-flow projections for UI-001."""

from __future__ import annotations

from typing import Any

from ..features.institutional import get_institutional_ledger
from ..providers.whale_ledger import OPTIONS_FAMILY, ORDER_FLOW_FAMILY


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


def order_flow_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=ORDER_FLOW_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def options_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=OPTIONS_FAMILY,
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


def build_workspace_order_flow_payload(
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
            "bars": [],
            "disclaimer": "Order-flow evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    bars = ledger.query_order_flow_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not bars:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "bars": [],
            "disclaimer": "No PIT-eligible order-flow events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_ORDER_FLOW",
            "research_only": True,
            "symbol": instrument_id,
        }
    return {
        "as_of_context": as_of_context,
        "available": True,
        "bars": bars,
        "bar_count": len(bars),
        "disclaimer": (
            "Order-flow metrics are derived from admitted fixture trade classification. "
            "Unknown aggressor remains unknown. Research-only per ADR-WHALE-003."
        ),
        "ledger_id": ledger.ledger_id,
        "provider_id": "cvd.fixture.order_flow",
        "research_only": True,
        "symbol": instrument_id,
    }


def build_workspace_options_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Options evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    activities = ledger.query_options_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not activities:
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible options events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_OPTIONS",
            "research_only": True,
            "symbol": instrument_id,
        }
    return {
        "activities": activities,
        "activity_count": len(activities),
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "Unusual options volume is not directional intent. "
            "Direction labels remain ambiguous unless explicitly supported. "
            "Research-only per ADR-WHALE-004."
        ),
        "ledger_id": ledger.ledger_id,
        "provider_id": "options.fixture.activity",
        "research_only": True,
        "symbol": instrument_id,
    }


__all__ = [
    "build_workspace_disclosure_payload",
    "build_workspace_options_payload",
    "build_workspace_order_flow_payload",
    "disclosure_available",
    "options_available",
    "order_flow_available",
]
