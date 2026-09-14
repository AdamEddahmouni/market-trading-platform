"""Normalized SEC Form 3/4/5 disclosure facts for Lane C detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from .constants import STRATEGY_FAMILY


@dataclass(frozen=True, slots=True)
class SecInsiderDisclosureFacts:
    accession_number: str
    form_type: str
    instrument_id: str | None
    row_id: str | None
    transaction_code: str | None
    acquired_disposed: str | None
    shares: float | None
    price_per_share: float | None
    notional_usd: float | None
    shares_owned_after: float | None
    transacted_date: str | None
    filing_date: str | None
    filing_lag_days: int | None
    role_flags: tuple[str, ...]
    insider_count_in_cluster: int
    is_derivative: bool
    primary_source_url: str
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


def _coerce_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def _role_flags_from_mapping(insider: Mapping[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []
    if insider.get("isDirector"):
        flags.append("REPORTING_PERSON_DIRECTOR")
    if insider.get("isOfficer"):
        flags.append("REPORTING_PERSON_OFFICER")
    if insider.get("isTenPctOwner"):
        flags.append("REPORTING_PERSON_TEN_PCT_OWNER")
    return tuple(flags)


def facts_from_market_trackers_row(row: Mapping[str, Any]) -> SecInsiderDisclosureFacts:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    insider = row.get("insider") if isinstance(row.get("insider"), Mapping) else {}
    shares = _coerce_float(row.get("shares"))
    price = _coerce_float(row.get("pricePerShare"))
    notional = shares * price if shares is not None and price is not None else None
    transacted = row.get("transactedAt")
    filed = row.get("filedAt") or row.get("filing_date")
    cluster = row.get("cluster_insider_count") or row.get("insider_count_in_cluster") or 1
    try:
        cluster_count = max(1, int(cluster))
    except (TypeError, ValueError):
        cluster_count = 1
    instrument = row.get("instrument_id") or row.get("ticker")
    instrument_id = f"US:{instrument}" if instrument and ":" not in str(instrument) else (
        str(instrument) if instrument else None
    )
    return SecInsiderDisclosureFacts(
        accession_number=str(row.get("accessionNumber") or row.get("accession_number") or ""),
        form_type=str(row.get("formType") or row.get("form_type") or ""),
        instrument_id=instrument_id,
        row_id=str(row.get("id") or ""),
        transaction_code=str(row.get("code")) if row.get("code") not in (None, "") else None,
        acquired_disposed=str(row.get("acquiredDisposed")) if row.get("acquiredDisposed") not in (None, "") else None,
        shares=shares,
        price_per_share=price,
        notional_usd=notional,
        shares_owned_after=_coerce_float(row.get("sharesOwnedAfter")),
        transacted_date=str(transacted) if transacted not in (None, "") else None,
        filing_date=str(filed) if filed not in (None, "") else None,
        filing_lag_days=_filing_lag_days(
            str(transacted) if transacted not in (None, "") else None,
            str(filed) if filed not in (None, "") else None,
        ),
        role_flags=_role_flags_from_mapping(insider),
        insider_count_in_cluster=cluster_count,
        is_derivative=bool(row.get("isDerivative")),
        primary_source_url=str(provenance.get("sourceUrl") or provenance.get("source_url") or ""),
    )


__all__ = ["SecInsiderDisclosureFacts", "facts_from_market_trackers_row"]
