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
    chamber: str
    doc_id: str
    disclosed_side: str
    amount_range_text: str
    asset_type: str
    owner: str | None
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount_range_text": self.amount_range_text,
            "asset_type": self.asset_type,
            "chamber": self.chamber,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "disclosed_side": self.disclosed_side,
            "doc_id": self.doc_id,
            "narrative": self.narrative,
            "owner": self.owner,
            "primary_source_url": self.primary_source_url,
            "reason_codes": list(self.reason_codes),
            "semantic_class": self.semantic_class,
            "uncertainty_flags": list(self.uncertainty_flags),
        }


def build_public_record_evidence(row: Mapping[str, Any]) -> PublicRecordEvidencePrep:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    amount = row.get("amountRange") if isinstance(row.get("amountRange"), Mapping) else {}

    uncertainty: list[str] = [
        "PTR_NOT_AUTO_DIRECTIONAL",
        "DISCLOSED_SIDE_NOT_EXECUTION_SIDE",
        "AMOUNT_IS_RANGE_NOT_EXACT",
        "STOCK_ACT_REPORTING_LAG_EXPECTED",
    ]
    if row.get("ticker") in (None, ""):
        uncertainty.append("TICKER_HEURISTIC_OR_ABSENT")
    if amount.get("max") is None:
        uncertainty.append("OPEN_ENDED_AMOUNT_RANGE")
    if provenance.get("needsReview"):
        uncertainty.append("UPSTREAM_NEEDS_REVIEW")
    if str(row.get("side") or "") == "exchange":
        uncertainty.append("EXCHANGE_NOT_SIMPLE_BUY_SELL")

    owner = row.get("owner")
    return PublicRecordEvidencePrep(
        detector_id="imp.public_record.congressional_ptr_row",
        detector_version=ADAPTER_PREP_VERSION,
        semantic_class="CONGRESSIONAL_REGULATORY_DISCLOSURE_FACT",
        reason_codes=(
            "CONGRESSIONAL_PTR_ROW",
            "PRIMARY_SOURCE_LINKED",
            "AGGREGATOR_ROW_REPLACEABLE",
        ),
        uncertainty_flags=tuple(dict.fromkeys(uncertainty)),
        primary_source_url=str(provenance.get("sourceUrl") or ""),
        chamber=str(row.get("chamber") or ""),
        doc_id=str(row.get("docId") or ""),
        disclosed_side=str(row.get("side") or ""),
        amount_range_text=str(amount.get("text") or ""),
        asset_type=str(row.get("assetType") or ""),
        owner=str(owner) if owner is not None else None,
        narrative=(
            "Periodic Transaction Report row; disclosed side and amount range are reported facts only. "
            "No execution dependency; not a trade recommendation."
        ),
    )
