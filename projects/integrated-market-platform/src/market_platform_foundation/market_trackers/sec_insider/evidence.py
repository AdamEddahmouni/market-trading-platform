"""Deterministic public-record detector / OE evidence preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .pin import ADAPTER_PREP_VERSION


@dataclass(frozen=True, slots=True)
class PublicRecordEvidencePrep:
    """Observation evidence bundle — descriptive, not directional."""

    detector_id: str
    detector_version: str
    semantic_class: str
    reason_codes: tuple[str, ...]
    uncertainty_flags: tuple[str, ...]
    primary_source_url: str
    accession_number: str
    form_type: str
    transaction_code: str | None
    acquired_disposed: str | None
    role_flags: tuple[str, ...]
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "accession_number": self.accession_number,
            "acquired_disposed": self.acquired_disposed,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "form_type": self.form_type,
            "narrative": self.narrative,
            "primary_source_url": self.primary_source_url,
            "reason_codes": list(self.reason_codes),
            "role_flags": list(self.role_flags),
            "semantic_class": self.semantic_class,
            "transaction_code": self.transaction_code,
            "uncertainty_flags": list(self.uncertainty_flags),
        }


def build_public_record_evidence(row: Mapping[str, Any]) -> PublicRecordEvidencePrep:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    insider = row.get("insider") if isinstance(row.get("insider"), Mapping) else {}

    role_flags: list[str] = []
    if insider.get("isDirector"):
        role_flags.append("REPORTING_PERSON_DIRECTOR")
    if insider.get("isOfficer"):
        role_flags.append("REPORTING_PERSON_OFFICER")
    if insider.get("isTenPctOwner"):
        role_flags.append("REPORTING_PERSON_TEN_PCT_OWNER")

    uncertainty: list[str] = ["FORM4_NOT_AUTO_DIRECTIONAL"]
    if row.get("code") in (None, ""):
        uncertainty.append("TRANSACTION_CODE_ABSENT")
    if row.get("isDerivative"):
        uncertainty.append("DERIVATIVE_TABLE_ROW")
    if provenance.get("needsReview"):
        uncertainty.append("UPSTREAM_NEEDS_REVIEW")

    code = row.get("code")
    ad = row.get("acquiredDisposed")
    form_type = str(row.get("formType") or "")

    return PublicRecordEvidencePrep(
        detector_id="imp.public_record.sec_form_345_row",
        detector_version=ADAPTER_PREP_VERSION,
        semantic_class="SEC_REGULATORY_OWNERSHIP_FACT",
        reason_codes=(
            "SEC_FORM_345_ROW",
            "PRIMARY_SOURCE_LINKED",
            "AGGREGATOR_ROW_REPLACEABLE",
        ),
        uncertainty_flags=tuple(dict.fromkeys(uncertainty)),
        primary_source_url=str(provenance.get("sourceUrl") or ""),
        accession_number=str(row.get("accessionNumber") or ""),
        form_type=form_type,
        transaction_code=str(code) if code is not None else None,
        acquired_disposed=str(ad) if ad is not None else None,
        role_flags=tuple(role_flags),
        narrative=(
            "Public ownership filing row; transaction code and A/D are reported facts only. "
            "No execution dependency; not a trade recommendation."
        ),
    )
