"""Institutional evidence vocabulary interfaces per ADR-WHALE-001."""

from __future__ import annotations

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


def query_institutional_evidence(family: str, *, prediction_cutoff: int) -> dict[str, object]:
    if family not in WHALE_FAMILIES:
        return {
            "direction": "unavailable",
            "family": family,
            "prediction_cutoff": prediction_cutoff,
            "reason_code": "WHALE_UNKNOWN_FAMILY",
            "status": "unavailable",
        }
    return {
        "direction": "unavailable",
        "family": family,
        "prediction_cutoff": prediction_cutoff,
        "reason_code": NO_ENTITLED_SOURCE,
        "status": "unavailable",
    }


def query_all_institutional(*, prediction_cutoff: int) -> list[dict[str, object]]:
    return [
        query_institutional_evidence(family, prediction_cutoff=prediction_cutoff)
        for family in WHALE_FAMILIES
    ]
