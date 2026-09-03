"""Cheap deterministic SEC snapshot for squeeze / catalyst consumers."""

from __future__ import annotations

from .dilution import dilution_from_filing
from .filing import FilingEvent
from .store import FilingStore


def recent_regulatory_state(
    store: FilingStore,
    *,
    cik: str,
    as_of: str,
) -> dict[str, object]:
    rows: tuple[FilingEvent, ...] = store.as_of(as_of, cik=cik)
    forms = {row.form_type.upper() for row in rows}
    dilution_rows = [
        dilution_from_filing(row)
        for row in rows
        if row.family == "CAPITAL_STRUCTURE"
    ]
    return {
        "cik": cik,
        "as_of": as_of,
        "filing_count": len(rows),
        "fresh_8k": any(form.startswith("8-K") for form in forms),
        "ownership_form4": "4" in forms,
        "beneficial_13d": any("13D" in form for form in forms),
        "beneficial_13g": any("13G" in form for form in forms),
        "delayed_13f": any(form.startswith("13F") for form in forms),
        "capital_structure_filings": len(dilution_rows),
        "dilution_terms_known": any(row.potential_new_shares is not None for row in dilution_rows),
        "accessions": [row.normalized_accession for row in rows],
    }
