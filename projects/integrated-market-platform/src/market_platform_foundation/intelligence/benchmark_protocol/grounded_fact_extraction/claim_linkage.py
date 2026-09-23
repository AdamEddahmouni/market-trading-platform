"""Evidence-to-claim linkage and polarity (absent vs negative evidence)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .evidence_projection import ProjectedArtifact


class EvidencePolarity(StrEnum):
    """Polarity of a structured claim relative to admitted evidence."""

    POSITIVE = "POSITIVE"  # value present and non-empty / non-zero where numeric zero is meaningful
    NEGATIVE = "NEGATIVE"  # explicit zero/false/empty collection observed in evidence
    ABSENT = "ABSENT"  # field/path not observed in evidence


def polarity_for_value(value: Any) -> EvidencePolarity:
    if value is None:
        return EvidencePolarity.ABSENT
    if isinstance(value, bool):
        return EvidencePolarity.NEGATIVE if value is False else EvidencePolarity.POSITIVE
    if isinstance(value, (int, float)):
        return EvidencePolarity.NEGATIVE if value == 0 else EvidencePolarity.POSITIVE
    if isinstance(value, (list, tuple, set, dict)):
        return EvidencePolarity.NEGATIVE if len(value) == 0 else EvidencePolarity.POSITIVE
    if isinstance(value, str) and not value.strip():
        return EvidencePolarity.NEGATIVE
    return EvidencePolarity.POSITIVE


def link_claim_to_evidence(
    *,
    field: str,
    value: Any,
    artifact: ProjectedArtifact,
    source_path: str,
    confidence: str = "ADMITTED_ARTIFACT",
) -> dict[str, Any]:
    """Build a provenance-preserving structured fact row with claim linkage."""
    polarity = polarity_for_value(value)
    return {
        "field": field,
        "value": value,
        "source_artifact": artifact.artifact_ref,
        "source_path": source_path,
        "support_hash": artifact.support_hash,
        "confidence": confidence,
        "evidence_polarity": polarity.value,
        "claim_link": {
            "artifact_ref": artifact.artifact_ref,
            "source_path": source_path,
            "support_hash": artifact.support_hash,
            "polarity": polarity.value,
        },
    }


def facts_include_negative(facts: list[dict[str, Any]]) -> bool:
    return any(str(row.get("evidence_polarity") or "") == EvidencePolarity.NEGATIVE.value for row in facts)


def facts_preserve_provenance(facts: list[dict[str, Any]]) -> bool:
    for row in facts:
        link = row.get("claim_link") if isinstance(row.get("claim_link"), dict) else {}
        if not row.get("source_artifact") or not row.get("source_path") or not row.get("support_hash"):
            return False
        if link and (
            link.get("artifact_ref") != row.get("source_artifact")
            or link.get("source_path") != row.get("source_path")
            or link.get("support_hash") != row.get("support_hash")
        ):
            return False
    return True


__all__ = [
    "EvidencePolarity",
    "facts_include_negative",
    "facts_preserve_provenance",
    "link_claim_to_evidence",
    "polarity_for_value",
]
