"""SEC EDGAR whale evidence vocabulary — professor brief + ADR-WHALE-001 alignment."""

from __future__ import annotations

from enum import Enum
from typing import Any


class WhaleEventType(str, Enum):
    INSIDER_BUY = "insider_buy"
    INSIDER_SELL = "insider_sell"
    BENEFICIAL_OWNER_CHANGE = "beneficial_owner_change"
    INSTITUTIONAL_HOLDING_SNAPSHOT = "institutional_holding_snapshot"
    PUBLIC_STATEMENT = "public_statement"
    COPY_PLATFORM_SIGNAL = "copy_platform_signal"


class EpistemicClass(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"


FORM_TYPE_MAP = {
    "4": WhaleEventType.INSIDER_BUY,  # direction resolved separately
    "3": WhaleEventType.BENEFICIAL_OWNER_CHANGE,
    "13D": WhaleEventType.BENEFICIAL_OWNER_CHANGE,
    "13G": WhaleEventType.BENEFICIAL_OWNER_CHANGE,
    "13F-HR": WhaleEventType.INSTITUTIONAL_HOLDING_SNAPSHOT,
}


def normalize_edgar_filing(
    *,
    form_type: str,
    filer: str,
    issuer: str,
    accepted_at: str,
    source_url: str,
    is_amendment: bool = False,
    transaction_code: str | None = None,
) -> dict[str, Any]:
    base_type = FORM_TYPE_MAP.get(form_type.upper().replace("/A", ""), WhaleEventType.PUBLIC_STATEMENT)
    event_type = base_type
    if form_type.upper().startswith("4") and transaction_code:
        if transaction_code.upper() in {"P", "A"}:
            event_type = WhaleEventType.INSIDER_BUY
        elif transaction_code.upper() in {"S", "D"}:
            event_type = WhaleEventType.INSIDER_SELL
    return {
        "event_type": event_type.value,
        "epistemic_class": EpistemicClass.OBSERVED.value,
        "filer": filer,
        "issuer": issuer,
        "accepted_at": accepted_at,
        "source_url": source_url,
        "is_amendment": is_amendment,
        "disclosure_lag_note": "SEC filings are delayed public disclosures, not a live tape.",
        "research_only": True,
    }


def is_actionable_claim(event: dict[str, Any]) -> bool:
    """Whale lane remains research-only by default."""
    return bool(event.get("research_only"))
