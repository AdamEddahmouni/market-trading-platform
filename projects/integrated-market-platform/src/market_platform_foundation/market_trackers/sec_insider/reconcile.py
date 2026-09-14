"""Primary-source PIT reconciliation: SEC EDGAR authority over Market Trackers clocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...sec_edgar.timestamps import clocks_from_submission_row

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
class EdgarPrimarySubmission:
    """Optional EDGAR submission metadata keyed to the row accession."""

    filing_date: str
    acceptance_datetime: str = ""
    observed_time: str = ""
    document_retrieved_time: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> EdgarPrimarySubmission:
        filing_date = str(raw.get("filing_date") or raw.get("filingDate") or "")
        if not filing_date:
            raise ValueError("EDGAR_FILING_DATE_REQUIRED")
        return cls(
            filing_date=filing_date,
            acceptance_datetime=str(raw.get("acceptance_datetime") or raw.get("acceptanceDateTime") or ""),
            observed_time=str(raw.get("observed_time") or raw.get("observedTime") or ""),
            document_retrieved_time=str(
                raw.get("document_retrieved_time") or raw.get("documentRetrievedTime") or ""
            ),
        )


@dataclass(frozen=True, slots=True)
class ReconciledSecInsiderClocks:
    """Five-clock bundle plus derived availability (transaction date excluded from availability)."""

    economic_event_time_ns: int | None
    filing_publication_time_ns: int
    sec_acceptance_time_ns: int
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
            "sec_acceptance_time_ns": self.sec_acceptance_time_ns,
            "aggregator_retrieved_time_ns": self.aggregator_retrieved_time_ns,
            "platform_received_time_ns": self.platform_received_time_ns,
            "available_time_ns": self.available_time_ns,
            "available_time_basis": self.available_time_basis,
            "aggregator_filing_date": self.aggregator_filing_date,
            "primary_filing_date": self.primary_filing_date,
        }


def reconcile_sec_insider_clocks(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
    edgar_primary: EdgarPrimarySubmission | Mapping[str, Any] | None = None,
) -> ReconciledSecInsiderClocks:
    """Reconcile Market Trackers row clocks with optional EDGAR primary submission evidence."""
    aggregator_filed_at = str(row.get("filedAt") or "").strip()
    if not aggregator_filed_at:
        raise ValueError("MARKET_TRACKERS_FILED_AT_REQUIRED")

    primary = None
    if edgar_primary is not None:
        primary = (
            edgar_primary
            if isinstance(edgar_primary, EdgarPrimarySubmission)
            else EdgarPrimarySubmission.from_mapping(edgar_primary)
        )

    primary_filing_date = primary.filing_date if primary else aggregator_filed_at
    flags: list[str] = [
        "PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE",
        "PRIMARY_SOURCE_EDGAR_WINS",
        "MARKET_TRACKERS_REPLACEABLE",
    ]
    if primary and primary.filing_date != aggregator_filed_at:
        flags.append("AGGREGATOR_FILING_DATE_OVERRIDDEN_BY_EDGAR")

    transacted = row.get("transactedAt")
    economic_ns: int | None = None
    if transacted:
        economic_ns = _date_start_ns(str(transacted))
        if economic_ns:
            flags.append("ECONOMIC_DATE_PRESENT")
    else:
        flags.append("FORM3_OR_HOLDING_ROW_NO_TRANSACTION_DATE")

    filing_publication_ns = _date_start_ns(primary_filing_date)
    sec_acceptance_ns = 0
    if primary:
        sec_clocks = clocks_from_submission_row(
            filing_date=primary.filing_date,
            acceptance_datetime=primary.acceptance_datetime,
            observed_time=primary.observed_time or primary.acceptance_datetime or primary.filing_date,
            document_retrieved_time=primary.document_retrieved_time,
        )
        sec_acceptance_ns = sec_clocks.acceptance_time_ns
        if primary.acceptance_datetime:
            flags.append("SEC_ACCEPTANCE_FROM_PRIMARY")
        else:
            flags.append("SEC_ACCEPTANCE_MISSING_DAY_BOUNDED_FILING")
    else:
        flags.append("SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY")

    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    retrieved_ns = _iso_ns(str(provenance.get("retrievedAt") or ""), field_name="provenance.retrievedAt")

    lawful_candidates: list[tuple[int, str]] = []
    if sec_acceptance_ns:
        lawful_candidates.append((sec_acceptance_ns, "sec_edgar.acceptanceDateTime"))
    else:
        end_day = _date_end_ns(primary_filing_date)
        if end_day:
            lawful_candidates.append((end_day, "sec_edgar.filing_date_end_of_utc_day"))
    if retrieved_ns:
        lawful_candidates.append((retrieved_ns, "market_trackers.provenance.retrievedAt"))
    if platform_received_time_ns:
        lawful_candidates.append((platform_received_time_ns, "imp.platform_received_time_ns"))

    if economic_ns:
        for candidate_ns, _ in lawful_candidates:
            if candidate_ns == economic_ns and not sec_acceptance_ns:
                flags.append("AVAILABLE_TIME_VERIFIED_NOT_TRANSACTION_DATE")

    if not lawful_candidates:
        raise ValueError("UNDETERMINABLE_LAWFUL_AVAILABILITY")

    available_ns, basis = max(lawful_candidates, key=lambda item: item[0])

    if economic_ns is not None and available_ns == economic_ns:
        raise ValueError("TRANSACTION_DATE_CANNOT_BE_AVAILABLE_TIME")

    return ReconciledSecInsiderClocks(
        economic_event_time_ns=economic_ns,
        filing_publication_time_ns=filing_publication_ns,
        sec_acceptance_time_ns=sec_acceptance_ns,
        aggregator_retrieved_time_ns=retrieved_ns,
        platform_received_time_ns=platform_received_time_ns,
        available_time_ns=available_ns,
        available_time_basis=basis,
        reconcile_flags=tuple(dict.fromkeys(flags)),
        aggregator_filing_date=aggregator_filed_at,
        primary_filing_date=primary_filing_date,
    )


__all__ = [
    "EdgarPrimarySubmission",
    "ReconciledSecInsiderClocks",
    "reconcile_sec_insider_clocks",
]
