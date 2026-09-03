"""XBRL companyfacts with filing-date availability. Never trust the aggregate blob as historical truth."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .identity import normalize_accession
from .timestamps import clocks_from_submission_row


@dataclass(frozen=True, slots=True)
class XbrlFact:
    tag: str
    value: float | int
    unit: str
    period_end: str
    accession: str
    form: str
    filed: str
    taxonomy: str


def facts_as_of(payload: str | dict[str, Any], *, as_of: str, tag: str) -> tuple[XbrlFact, ...]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise ValueError("SEC_COMPANYFACTS_MALFORMED")
    cutoff = clocks_from_submission_row(
        filing_date=as_of[:10],
        acceptance_datetime=as_of if "T" in as_of else as_of + "T00:00:00Z",
        observed_time=as_of if "T" in as_of else as_of + "T00:00:00Z",
    ).available_time_ns
    selected: list[XbrlFact] = []
    facts = data.get("facts") if isinstance(data.get("facts"), dict) else {}
    for taxonomy, tags in facts.items():
        if not isinstance(tags, dict) or tag not in tags:
            continue
        units = ((tags.get(tag) or {}).get("units") if isinstance(tags.get(tag), dict) else {}) or {}
        if not isinstance(units, dict):
            continue
        for unit, rows in units.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                filed = str(row.get("filed") or "")
                filed_ts = filed + "T00:00:00Z" if len(filed) == 10 else filed
                filed_ns = clocks_from_submission_row(
                    filing_date=filed[:10],
                    acceptance_datetime=filed_ts,
                    observed_time=filed_ts,
                ).acceptance_time_ns
                if filed_ns > cutoff:
                    continue
                value = row.get("val")
                if not isinstance(value, (int, float)):
                    continue
                selected.append(
                    XbrlFact(
                        tag=tag,
                        value=value,
                        unit=str(unit),
                        period_end=str(row.get("end") or ""),
                        accession=normalize_accession(str(row.get("accn") or "")),
                        form=str(row.get("form") or ""),
                        filed=filed,
                        taxonomy=str(taxonomy),
                    )
                )
    return tuple(sorted(selected, key=lambda row: (row.filed, row.accession)))
