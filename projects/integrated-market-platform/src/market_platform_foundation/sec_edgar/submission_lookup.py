"""Locate a filing row inside SEC submissions JSON (data.sec.gov)."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .identity import normalize_accession, pad_cik


def _recent_block(submissions: Mapping[str, Any]) -> dict[str, Any]:
    filings = submissions.get("filings")
    if not isinstance(filings, Mapping):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    return dict(recent)


def find_accession_index(submissions: Mapping[str, Any], accession: str) -> int | None:
    """Return index in filings.recent parallel arrays for normalized accession, else None."""
    target = normalize_accession(accession)
    recent = _recent_block(submissions)
    accessions = recent.get("accessionNumber") or []
    if not isinstance(accessions, list):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    for index, raw in enumerate(accessions):
        try:
            if normalize_accession(str(raw)) == target:
                return index
        except ValueError:
            continue
    return None


def submission_row_at(
    submissions: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    """Extract parallel-array fields for one recent filing index."""
    recent = _recent_block(submissions)
    accessions = list(recent.get("accessionNumber") or [])
    if index < 0 or index >= len(accessions):
        raise ValueError("SEC_SUBMISSION_INDEX_OUT_OF_RANGE")

    def _at(key: str, default: str = "") -> str:
        values = recent.get(key) or []
        if not isinstance(values, list) or index >= len(values):
            return default
        return str(values[index])

    cik = pad_cik(str(submissions.get("cik") or ""))
    accession = normalize_accession(str(accessions[index]))
    return {
        "cik": cik,
        "accession_number": accession,
        "form_type": _at("form"),
        "filing_date": _at("filingDate"),
        "report_date": _at("reportDate"),
        "acceptance_datetime": _at("acceptanceDateTime"),
        "primary_document": _at("primaryDocument"),
    }


def load_submissions_payload(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    return data


def edgar_primary_mapping_for_accession(
    submissions: Mapping[str, Any],
    accession: str,
    *,
    observed_time: str,
    document_retrieved_time: str = "",
) -> dict[str, str]:
    """Build reconcile-compatible EDGAR primary dict from submissions JSON."""
    index = find_accession_index(submissions, accession)
    if index is None:
        raise ValueError("SEC_ACCESSION_NOT_IN_SUBMISSIONS")
    row = submission_row_at(submissions, index)
    if not row["filing_date"]:
        raise ValueError("SEC_FILING_DATE_MISSING")
    return {
        "accession_number": row["accession_number"],
        "filing_date": row["filing_date"],
        "acceptance_datetime": row["acceptance_datetime"],
        "cik": row["cik"],
        "form_type": row["form_type"],
        "primary_document": row["primary_document"],
        "observed_time": observed_time,
        "document_retrieved_time": document_retrieved_time,
    }


__all__ = [
    "edgar_primary_mapping_for_accession",
    "find_accession_index",
    "load_submissions_payload",
    "submission_row_at",
]
