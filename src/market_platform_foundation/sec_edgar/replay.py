"""Replay captured SEC JSONL. Capture is not admission."""

from __future__ import annotations

import json
from pathlib import Path

from .filing import FilingEvent, SCHEMA_VERSION


def replay_captured_filings(path: Path) -> tuple[FilingEvent, ...]:
    rows: list[FilingEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append(
            FilingEvent(
                cik=str(payload.get("cik") or ""),
                entity_name=str(payload.get("entity_name") or ""),
                form_type=str(payload.get("form_type") or ""),
                family=str(payload.get("family") or "CORPORATE_EVENT"),
                raw_accession=str(payload.get("raw_accession") or payload.get("normalized_accession") or ""),
                normalized_accession=str(payload.get("normalized_accession") or ""),
                filing_date=str(payload.get("filing_date") or ""),
                report_date=str(payload.get("report_date") or ""),
                acceptance_datetime=str(payload.get("acceptance_datetime") or payload.get("observed_time") or ""),
                observed_time=str(payload.get("observed_time") or ""),
                primary_document=str(payload.get("primary_document") or ""),
                items=tuple(payload.get("items") or ()),
                item_labels=dict(payload.get("item_labels") or {}),
                is_amendment=bool(payload.get("is_amendment")),
                amends_accession=str(payload.get("amends_accession") or ""),
                is_xbrl=bool(payload.get("is_xbrl")),
                available_time=str(payload.get("observed_time") or ""),
                available_time_ns=int(payload.get("available_time_ns") or 0),
                schema_version=str(payload.get("schema_version") or SCHEMA_VERSION),
                instrument_id=str(payload.get("instrument_id") or ""),
                lifecycle=str(payload.get("lifecycle") or "CAPTURED"),
            )
        )
    return tuple(rows)
