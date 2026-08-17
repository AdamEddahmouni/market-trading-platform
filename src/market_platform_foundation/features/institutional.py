"""Institutional evidence vocabulary interfaces per ADR-WHALE-001."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers.whale_ledger import WhaleLedger

WHALE_FAMILIES = (
    "fund_etf_cross_asset",
    "futures_positioning",
    "large_transactions",
    "order_book",
    "order_flow",
    "options",
    "public_catalyst",
    "regulatory_disclosure",
)

NO_ENTITLED_SOURCE = "WHALE_NO_ENTITLED_SOURCE"
REGULATORY_DISCLOSURE_FAMILY = "regulatory_disclosure"

_LEDGER: WhaleLedger | None = None


def configure_institutional_ledger(ledger: WhaleLedger | None) -> None:
    global _LEDGER
    _LEDGER = ledger


def get_institutional_ledger() -> WhaleLedger | None:
    return _LEDGER


def query_institutional_evidence(
    family: str,
    *,
    prediction_cutoff: int,
    instrument_id: str | None = None,
) -> dict[str, object]:
    if family not in WHALE_FAMILIES:
        return {
            "direction": "unavailable",
            "family": family,
            "prediction_cutoff": prediction_cutoff,
            "reason_code": "WHALE_UNKNOWN_FAMILY",
            "status": "unavailable",
        }
    if family == REGULATORY_DISCLOSURE_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_DISCLOSURE

        events = _LEDGER.query_events(
            family=family,
            instrument_id=instrument_id,
            prediction_cutoff=prediction_cutoff,
        )
        if events:
            return {
                "direction": "neutral",
                "event_count": len(events),
                "family": family,
                "prediction_cutoff": prediction_cutoff,
                "reason_code": WHALE_ENTITLED_DISCLOSURE,
                "status": "available",
            }
    return {
        "direction": "unavailable",
        "family": family,
        "prediction_cutoff": prediction_cutoff,
        "reason_code": NO_ENTITLED_SOURCE,
        "status": "unavailable",
    }


def query_all_institutional(
    *,
    prediction_cutoff: int,
    instrument_id: str | None = None,
) -> list[dict[str, object]]:
    return [
        query_institutional_evidence(
            family,
            prediction_cutoff=prediction_cutoff,
            instrument_id=instrument_id,
        )
        for family in WHALE_FAMILIES
    ]
