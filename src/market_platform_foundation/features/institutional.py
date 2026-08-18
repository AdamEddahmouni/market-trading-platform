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
ORDER_FLOW_FAMILY = "order_flow"
OPTIONS_FAMILY = "options"
LARGE_TRANSACTIONS_FAMILY = "large_transactions"
FUTURES_FAMILY = "futures_positioning"
ORDER_BOOK_FAMILY = "order_book"
PUBLIC_CATALYST_FAMILY = "public_catalyst"
FUND_ETF_FAMILY = "fund_etf_cross_asset"

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
    if family == ORDER_FLOW_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_ORDER_FLOW

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
                "reason_code": WHALE_ENTITLED_ORDER_FLOW,
                "status": "available",
            }
    if family == OPTIONS_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_OPTIONS

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
                "reason_code": WHALE_ENTITLED_OPTIONS,
                "status": "available",
            }
    if family == LARGE_TRANSACTIONS_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_LARGE_TRANSACTIONS

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
                "reason_code": WHALE_ENTITLED_LARGE_TRANSACTIONS,
                "status": "available",
            }
    if family == ORDER_BOOK_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_ORDER_BOOK

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
                "reason_code": WHALE_ENTITLED_ORDER_BOOK,
                "status": "available",
            }
    if family == FUTURES_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_FUTURES

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
                "reason_code": WHALE_ENTITLED_FUTURES,
                "status": "available",
            }
    if family == PUBLIC_CATALYST_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_CATALYST

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
                "reason_code": WHALE_ENTITLED_CATALYST,
                "status": "available",
            }
    if family == FUND_ETF_FAMILY and _LEDGER is not None:
        from ..providers.whale_ledger import WHALE_ENTITLED_FUND_ETF

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
                "reason_code": WHALE_ENTITLED_FUND_ETF,
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
