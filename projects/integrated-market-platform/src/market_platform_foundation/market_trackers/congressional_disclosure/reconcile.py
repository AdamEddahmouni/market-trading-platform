"""Primary-source PIT reconciliation: chamber PTR authority over Market Trackers clocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

_DATE_START_SUFFIX = "T00:00:00Z"


def _date_start_ns(date_text: str) -> int:
    from ...intelligence.normalization.timestamps import iso_string_to_ns

    text = str(date_text).strip()[:10]
    if len(text) != 10:
        return 0
    ns, diag = iso_string_to_ns(text + _DATE_START_SUFFIX, field_name="date")
    if diag is not None or ns is None:
        return 0
    return ns


def _date_end_ns(date_text: str) -> int:
    from ...intelligence.normalization.timestamps import date_only_end_of_day_utc_ns

    text = str(date_text).strip()[:10]
    if len(text) != 10:
        return 0
    ns, diag = date_only_end_of_day_utc_ns(text, field_name="date")
    if diag is not None or ns is None:
        return 0
    return ns


def _iso_ns(value: str, *, field_name: str) -> int:
    from ...intelligence.normalization.timestamps import iso_string_to_ns

    text = str(value or "").strip()
    if not text:
        return 0
    ns, diag = iso_string_to_ns(text, field_name=field_name)
    if diag is not None or ns is None:
        return 0
    return ns


@dataclass(frozen=True, slots=True)
class PtrPrimaryFiling:
    """Optional chamber PTR metadata keyed to docId."""

    filing_date: str
    published_at: str = ""
    document_retrieved_time: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> PtrPrimaryFiling:
        filing_date = str(raw.get("filing_date") or raw.get("filingDate") or raw.get("filedAt") or "")
        if not filing_date:
            raise ValueError("PTR_FILING_DATE_REQUIRED")
        return cls(
            filing_date=filing_date,
            published_at=str(raw.get("published_at") or raw.get("publishedAt") or ""),
            document_retrieved_time=str(
                raw.get("document_retrieved_time") or raw.get("documentRetrievedTime") or ""
            ),
        )


@dataclass(frozen=True, slots=True)
class ReconciledCongressionalClocks:
    """Five-clock bundle plus derived availability (transaction date excluded from availability)."""

    economic_event_time_ns: int
    filing_publication_time_ns: int
    ptr_primary_publication_time_ns: int
    aggregator_retrieved_time_ns: int
    platform_received_time_ns: int
    available_time_ns: int
    available_time_basis: str
    reconcile_flags: tuple[str, ...]
    aggregator_filing_date: str
    primary_filing_date: str

    def to_payload_clocks(self) -> dict[str, Any]:
        return {
            "economic_event_time_ns": self.economic_event_time_ns,
            "filing_publication_time_ns": self.filing_publication_time_ns,
            "ptr_primary_publication_time_ns": self.ptr_primary_publication_time_ns,
            "aggregator_retrieved_time_ns": self.aggregator_retrieved_time_ns,
            "platform_received_time_ns": self.platform_received_time_ns,
            "available_time_ns": self.available_time_ns,
            "available_time_basis": self.available_time_basis,
            "aggregator_filing_date": self.aggregator_filing_date,
            "primary_filing_date": self.primary_filing_date,
        }


def reconcile_congressional_clocks(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
    ptr_primary: PtrPrimaryFiling | Mapping[str, Any] | None = None,
) -> ReconciledCongressionalClocks:
    """Reconcile Market Trackers row clocks with optional chamber PTR primary evidence."""
    aggregator_filed_at = str(row.get("filedAt") or "").strip()
    if not aggregator_filed_at:
        raise ValueError("MARKET_TRACKERS_FILED_AT_REQUIRED")

    transacted = str(row.get("transactedAt") or "").strip()
    if not transacted:
        raise ValueError("MARKET_TRACKERS_TRANSACTED_AT_REQUIRED")

    primary = None
    if ptr_primary is not None:
        primary = (
            ptr_primary
            if isinstance(ptr_primary, PtrPrimaryFiling)
            else PtrPrimaryFiling.from_mapping(ptr_primary)
        )

    primary_filing_date = primary.filing_date if primary else aggregator_filed_at
    flags: list[str] = [
        "PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE",
        "MARKET_TRACKERS_REPLACEABLE",
        "STOCK_ACT_REPORTING_LAG_EXPECTED",
    ]
    if primary:
        flags.append("PRIMARY_SOURCE_PTR_WINS")
        if primary.filing_date != aggregator_filed_at:
            flags.append("AGGREGATOR_FILING_DATE_OVERRIDDEN_BY_PTR_PRIMARY")
    else:
        flags.append("PTR_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY")
        flags.append("AGGREGATOR_FILING_PUBLICATION_ONLY")

    economic_ns = _date_start_ns(transacted)
    if economic_ns:
        flags.append("ECONOMIC_DATE_PRESENT")

    filing_publication_ns = _date_start_ns(primary_filing_date)
    ptr_publication_ns = 0
    if primary:
        if primary.published_at:
            ptr_publication_ns = _iso_ns(primary.published_at, field_name="ptr_primary.published_at")
            if ptr_publication_ns:
                flags.append("PTR_PUBLICATION_FROM_PRIMARY")
        else:
            flags.append("PTR_PUBLICATION_MISSING_DAY_BOUNDED_FILING")
    else:
        flags.append("PTR_PRIMARY_PUBLICATION_NOT_AVAILABLE_AGGREGATOR_PATH")

    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    retrieved_ns = _iso_ns(str(provenance.get("retrievedAt") or ""), field_name="provenance.retrievedAt")

    lawful_candidates: list[tuple[int, str]] = []
    if primary:
        if ptr_publication_ns:
            lawful_candidates.append((ptr_publication_ns, "ptr_primary.published_at"))
        else:
            end_day = _date_end_ns(primary_filing_date)
            if end_day:
                lawful_candidates.append((end_day, "ptr_primary.filing_date_end_of_utc_day"))
    else:
        end_day = _date_end_ns(aggregator_filed_at)
        if end_day:
            lawful_candidates.append((end_day, "market_trackers.filedAt_end_of_utc_day"))
    if retrieved_ns:
        lawful_candidates.append((retrieved_ns, "market_trackers.provenance.retrievedAt"))
    if platform_received_time_ns:
        lawful_candidates.append((platform_received_time_ns, "imp.platform_received_time_ns"))

    if not lawful_candidates:
        raise ValueError("UNDETERMINABLE_LAWFUL_AVAILABILITY")

    available_ns, basis = max(lawful_candidates, key=lambda item: item[0])

    if economic_ns and available_ns == economic_ns:
        raise ValueError("TRANSACTION_DATE_CANNOT_BE_AVAILABLE_TIME")

    return ReconciledCongressionalClocks(
        economic_event_time_ns=economic_ns,
        filing_publication_time_ns=filing_publication_ns,
        ptr_primary_publication_time_ns=ptr_publication_ns,
        aggregator_retrieved_time_ns=retrieved_ns,
        platform_received_time_ns=platform_received_time_ns,
        available_time_ns=available_ns,
        available_time_basis=basis,
        reconcile_flags=tuple(dict.fromkeys(flags)),
        aggregator_filing_date=aggregator_filed_at,
        primary_filing_date=primary_filing_date,
    )


__all__ = [
    "PtrPrimaryFiling",
    "ReconciledCongressionalClocks",
    "reconcile_congressional_clocks",
]
