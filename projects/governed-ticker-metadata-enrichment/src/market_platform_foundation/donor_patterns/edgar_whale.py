"""SEC EDGAR whale evidence vocabulary — professor brief + ADR-WHALE-001 alignment."""

from __future__ import annotations

from enum import Enum
from typing import Any

from ..contracts.participant import (
    ActionDirection,
    ParticipantActionType,
    infer_action_from_form4_transaction,
)


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


def _event_type_from_form4(transaction_code: str | None) -> WhaleEventType:
    action_type, direction, _ = infer_action_from_form4_transaction(transaction_code)
    if action_type == ParticipantActionType.OPEN_MARKET_BUY:
        return WhaleEventType.INSIDER_BUY
    if action_type == ParticipantActionType.OPEN_MARKET_SELL:
        return WhaleEventType.INSIDER_SELL
    if direction == ActionDirection.AMBIGUOUS:
        return WhaleEventType.PUBLIC_STATEMENT
    return WhaleEventType.PUBLIC_STATEMENT


def is_13f_form(form_type: str) -> bool:
    return form_type.upper().replace("/A", "").startswith("13F")


def resolve_holding_instrument_id(
    holding: dict[str, Any],
    *,
    default_symbol: str,
) -> str:
    symbol = holding.get("symbol")
    if symbol is not None and str(symbol).strip():
        return str(symbol).strip().upper()
    return default_symbol.upper()


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
        event_type = _event_type_from_form4(transaction_code)
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
