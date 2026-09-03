"""Latest-filings Atom discovery. Broad universe must not poll every CIK."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .identity import normalize_accession

ATOM = "{http://www.w3.org/2005/Atom}"


def parse_latest_filings_atom(xml_text: str) -> tuple[dict[str, str], ...]:
    root = ET.fromstring(xml_text)
    rows: list[dict[str, str]] = []
    for entry in root.findall(f"{ATOM}entry"):
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        entry_id = (entry.findtext(f"{ATOM}id") or "").strip()
        category = entry.find(f"{ATOM}category")
        form_type = category.get("term") if category is not None else ""
        accession = ""
        if "accession-number=" in entry_id:
            accession = entry_id.split("accession-number=", 1)[1]
        rows.append(
            {
                "title": title,
                "form_type": form_type or (title.split(" - ", 1)[0] if title else ""),
                "normalized_accession": normalize_accession(accession) if accession else "",
                "updated": (entry.findtext(f"{ATOM}updated") or "").strip(),
            }
        )
    return tuple(rows)
