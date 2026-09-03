"""SEC clocks. Acceptance is not document availability and not observation."""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.equity_bars import iso_to_epoch_ns


def _to_ns(value: str) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T00:00:00Z"
    if text.endswith("Z") is False and "+" not in text[10:] and text.count(":") >= 2:
        if "." in text:
            text = text.split(".")[0] + "Z"
        elif not text.endswith("Z"):
            text = text + "Z" if "T" in text else text
    if text.endswith(".000Z"):
        text = text.replace(".000Z", "Z")
    return iso_to_epoch_ns(text)


@dataclass(frozen=True, slots=True)
class SecClocks:
    filing_date_ns: int
    acceptance_time_ns: int
    observed_time_ns: int
    document_available_time_ns: int
    retrieved_time_ns: int
    available_time_ns: int


def clocks_from_submission_row(
    *,
    filing_date: str,
    acceptance_datetime: str,
    observed_time: str,
    document_retrieved_time: str = "",
) -> SecClocks:
    filing_ns = _to_ns(filing_date)
    acceptance_ns = _to_ns(acceptance_datetime) or filing_ns
    observed_ns = _to_ns(observed_time)
    retrieved_ns = _to_ns(document_retrieved_time)
    # Metadata-only available_time is first observation (or acceptance if already known).
    # Content-using features must wait for document_available_time_ns > 0.
    if retrieved_ns:
        available_ns = retrieved_ns
        document_ns = retrieved_ns
    else:
        available_ns = observed_ns or acceptance_ns
        document_ns = 0
    return SecClocks(
        filing_date_ns=filing_ns,
        acceptance_time_ns=acceptance_ns,
        observed_time_ns=observed_ns,
        document_available_time_ns=document_ns,
        retrieved_time_ns=retrieved_ns,
        available_time_ns=available_ns,
    )
