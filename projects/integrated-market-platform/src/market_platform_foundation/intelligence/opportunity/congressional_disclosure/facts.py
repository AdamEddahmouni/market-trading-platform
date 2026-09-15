"""Congressional PTR disclosure facts from normalized EventV1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from ...contracts import EventV1
from .constants import STRATEGY_FAMILY


@dataclass(frozen=True, slots=True)
class CongressionalDisclosureFacts:
    row_id: str
    doc_id: str
    chamber: str
    instrument_id: str | None
    member_bioguide_id: str | None
    disclosed_side: str
    amount_range_text: str
    transacted_date: str | None
    filing_date: str | None
    filing_lag_days: int | None
    primary_source_url: str
    uncertainty_flags: tuple[str, ...]
    strategy_family: str = STRATEGY_FAMILY


def _parse_iso_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _filing_lag_days(transacted: str | None, filed: str | None) -> int | None:
    start = _parse_iso_date(transacted)
    end = _parse_iso_date(filed)
    if start is None or end is None:
        return None
    return (end - start).days


def facts_from_runtime_event(event: EventV1) -> CongressionalDisclosureFacts | None:
    payload = event.payload
    doc_id = str(payload.get("doc_id") or "")
    if not doc_id:
        return None
    evidence = payload.get("public_record_evidence")
    uncertainty: tuple[str, ...] = ()
    primary_url = ""
    if isinstance(evidence, Mapping):
        flags = evidence.get("uncertainty_flags")
        if isinstance(flags, list):
            uncertainty = tuple(str(item) for item in flags)
        primary_url = str(evidence.get("primary_source_url") or "")

    return CongressionalDisclosureFacts(
        row_id=event.source.source_record_id or str(payload.get("source_record_id") or ""),
        doc_id=doc_id,
        chamber=str(payload.get("chamber") or ""),
        instrument_id=event.instrument_id,
        member_bioguide_id=str(payload.get("member_bioguide_id") or "") or None,
        disclosed_side=str(payload.get("disclosed_side") or ""),
        amount_range_text=str(payload.get("amount_range_text") or ""),
        transacted_date=str(payload.get("transacted_at") or "") or None,
        filing_date=str(payload.get("filed_at") or "") or None,
        filing_lag_days=_filing_lag_days(
            str(payload.get("transacted_at") or "") or None,
            str(payload.get("filed_at") or "") or None,
        ),
        primary_source_url=primary_url,
        uncertainty_flags=uncertainty,
    )


__all__ = ["CongressionalDisclosureFacts", "facts_from_runtime_event"]
