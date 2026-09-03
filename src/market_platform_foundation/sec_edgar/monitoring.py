"""SEC event -> observational allocation hint. No vendor names on this path."""

from __future__ import annotations

from .filing import FilingEvent


def filing_to_allocation_hint(filing: FilingEvent, *, instrument_id: str) -> dict[str, str | int]:
    priority = 20
    if filing.form_type.upper().startswith("8-K"):
        priority = 70
    elif filing.family == "CAPITAL_STRUCTURE":
        priority = 60
    elif filing.family == "DISTRESS":
        priority = 80
    return {
        "instrument_id": instrument_id,
        "capability": "US_EQUITY_DEPTH",
        "lane": "regulatory",
        "priority": priority,
        "thesis_id": filing.normalized_accession,
    }
