"""Normalize official submissions JSON into FilingEvent records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .forms import classify_form, eight_k_item_labels, is_amendment_form
from .identity import normalize_accession, pad_cik
from .timestamps import clocks_from_submission_row


SCHEMA_VERSION = "sec_edgar.filing_event/1.0.0"


@dataclass(frozen=True, slots=True)
class FilingEvent:
    cik: str
    entity_name: str
    form_type: str
    family: str
    raw_accession: str
    normalized_accession: str
    filing_date: str
    report_date: str
    acceptance_datetime: str
    observed_time: str
    primary_document: str
    items: tuple[str, ...]
    item_labels: dict[str, str]
    is_amendment: bool
    amends_accession: str
    is_xbrl: bool
    available_time: str
    available_time_ns: int
    schema_version: str = SCHEMA_VERSION
    instrument_id: str = ""
    lifecycle: str = "CAPTURED"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)

    def archive_index_url(self) -> str:
        compact = self.normalized_accession.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
            f"{compact}/{self.normalized_accession}-index.html"
        )


def submissions_to_filings(payload: str | dict[str, Any], *, observed_time: str) -> tuple[FilingEvent, ...]:
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("SEC_SUBMISSIONS_MALFORMED") from exc
    else:
        data = payload
    if not isinstance(data, dict):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    cik = pad_cik(str(data.get("cik", "")))
    entity_name = str(data.get("name") or data.get("entityName") or "")
    recent = ((data.get("filings") or {}) if isinstance(data.get("filings"), dict) else {}).get("recent")
    if not isinstance(recent, dict):
        raise ValueError("SEC_SUBMISSIONS_MALFORMED")
    accessions = list(recent.get("accessionNumber") or [])
    forms = list(recent.get("form") or [])
    filing_dates = list(recent.get("filingDate") or [])
    report_dates = list(recent.get("reportDate") or [])
    accepted = list(recent.get("acceptanceDateTime") or [])
    items = list(recent.get("items") or [])
    primary = list(recent.get("primaryDocument") or [])
    xbrl = list(recent.get("isXBRL") or [])
    events: list[FilingEvent] = []
    originals_by_base: dict[str, str] = {}
    for index, raw_accn in enumerate(accessions):
        form_type = str(forms[index]) if index < len(forms) else ""
        classification = classify_form(form_type)
        normalized = normalize_accession(str(raw_accn))
        filing_date = str(filing_dates[index]) if index < len(filing_dates) else ""
        report_date = str(report_dates[index]) if index < len(report_dates) else ""
        acceptance = str(accepted[index]) if index < len(accepted) else ""
        item_field = str(items[index]) if index < len(items) else ""
        item_keys = tuple(k for k in eight_k_item_labels(item_field))
        clocks = clocks_from_submission_row(
            filing_date=filing_date,
            acceptance_datetime=acceptance,
            observed_time=observed_time,
        )
        amends = ""
        if classification.is_amendment:
            base = form_type.upper().replace("/A", "")
            amends = originals_by_base.get(base, "")
        else:
            originals_by_base[form_type.upper()] = normalized
        events.append(
            FilingEvent(
                cik=cik,
                entity_name=entity_name,
                form_type=form_type,
                family=classification.family,
                raw_accession=str(raw_accn),
                normalized_accession=normalized,
                filing_date=filing_date,
                report_date=report_date,
                acceptance_datetime=acceptance,
                observed_time=observed_time,
                primary_document=str(primary[index]) if index < len(primary) else "",
                items=item_keys,
                item_labels=eight_k_item_labels(item_field),
                is_amendment=is_amendment_form(form_type),
                amends_accession=amends,
                is_xbrl=bool(int(xbrl[index])) if index < len(xbrl) and str(xbrl[index]) not in {"", "None"} else False,
                available_time=observed_time,
                available_time_ns=clocks.available_time_ns,
            )
        )
    return tuple(events)
