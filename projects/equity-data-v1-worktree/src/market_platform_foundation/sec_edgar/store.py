"""Point-in-time filing store. Amendments do not rewrite history."""

from __future__ import annotations

from .filing import FilingEvent
from .timestamps import clocks_from_submission_row


class FilingStore:
    def __init__(self) -> None:
        self._by_accession: dict[str, FilingEvent] = {}

    def extend(self, filings: tuple[FilingEvent, ...] | list[FilingEvent]) -> None:
        for row in filings:
            self._by_accession.setdefault(row.normalized_accession, row)

    def as_of(self, as_of: str, *, cik: str = "") -> tuple[FilingEvent, ...]:
        cutoff = clocks_from_submission_row(
            filing_date=as_of[:10] if len(as_of) >= 10 else as_of,
            acceptance_datetime=as_of if "T" in as_of else as_of + "T00:00:00Z",
            observed_time=as_of if "T" in as_of else as_of + "T00:00:00Z",
        ).available_time_ns
        rows: list[FilingEvent] = []
        for event in self._by_accession.values():
            if cik and event.cik != cik:
                continue
            event_ns = clocks_from_submission_row(
                filing_date=event.filing_date,
                acceptance_datetime=event.acceptance_datetime,
                observed_time=event.acceptance_datetime or event.observed_time,
            ).acceptance_time_ns
            if event_ns <= cutoff:
                rows.append(event)
        return tuple(sorted(rows, key=lambda row: (row.acceptance_datetime, row.normalized_accession)))
