"""Dilution / capital-structure evidence. Unknown quantities stay unknown."""

from __future__ import annotations

from dataclasses import dataclass

from .filing import FilingEvent


@dataclass(frozen=True, slots=True)
class DilutionEvidence:
    normalized_accession: str
    form_type: str
    known_current_shares: float | None
    potential_new_shares: float | None
    known_offering_size: float | None
    convertible_amount: float | None
    conversion_price: float | None
    warrant_count: float | None
    exercise_price: float | None
    max_potential_dilution: float | None
    confidence: float
    source_accession: str
    notes: str


def dilution_from_filing(filing: FilingEvent) -> DilutionEvidence:
    family = filing.family
    confidence = 0.25
    notes = "form_family_only; terms not extracted"
    if filing.form_type.upper() in {"S-1", "S-3"}:
        notes = "shelf_or_registration_capacity_unknown"
        confidence = 0.35
    elif filing.form_type.upper().startswith("424B"):
        notes = "prospectus_supplement_terms_not_parsed"
        confidence = 0.4
    elif family != "CAPITAL_STRUCTURE":
        notes = "not_a_capital_structure_form"
        confidence = 0.1
    return DilutionEvidence(
        normalized_accession=filing.normalized_accession,
        form_type=filing.form_type,
        known_current_shares=None,
        potential_new_shares=None,
        known_offering_size=None,
        convertible_amount=None,
        conversion_price=None,
        warrant_count=None,
        exercise_price=None,
        max_potential_dilution=None,
        confidence=confidence,
        source_accession=filing.normalized_accession,
        notes=notes,
    )
