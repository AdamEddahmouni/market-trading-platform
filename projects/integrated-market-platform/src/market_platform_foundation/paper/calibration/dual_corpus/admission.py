"""Item 9 prospective corpus admission gates (contamination refusal)."""

from __future__ import annotations

from typing import Any, Mapping

from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    resolve_effective_corpus_evidence_authority,
)

ITEM9_ADMISSION_REFUSED = "REFUSED"
ITEM9_ADMISSION_ACCEPTED = "ACCEPTED"
REFUSAL_HISTORICAL_DEVELOPMENT = "HISTORICAL_DEVELOPMENT_NOT_PROSPECTIVE"
REFUSAL_AUTHORITY_INVALID = "CORPUS_EVIDENCE_AUTHORITY_INVALID"


def evaluate_item9_prospective_corpus_admission(
    *,
    payload: Mapping[str, Any] | None = None,
    corpus_evidence_authority: str | None = None,
) -> dict[str, Any]:
    """Machine refusal: historical development never enters Item 9 prospective corpus."""

    resolved = resolve_effective_corpus_evidence_authority(
        payload=payload,
        manifest_authority=corpus_evidence_authority,
        provenance_authority=(
            str((payload or {}).get("corpus_evidence_authority") or "")
            if payload
            else None
        ),
    )
    effective = str(resolved.get("effective_authority") or "")
    if effective == CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return {
            "disposition": ITEM9_ADMISSION_REFUSED,
            "reason_code": REFUSAL_HISTORICAL_DEVELOPMENT,
            "effective_authority": effective,
            "authority_resolution": resolved,
        }
    if not resolved.get("ok"):
        return {
            "disposition": ITEM9_ADMISSION_REFUSED,
            "reason_code": str(resolved.get("reason_code") or REFUSAL_AUTHORITY_INVALID),
            "effective_authority": effective,
            "authority_resolution": resolved,
        }
    if effective and effective != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return {
            "disposition": ITEM9_ADMISSION_ACCEPTED,
            "reason_code": None,
            "effective_authority": effective,
            "authority_resolution": resolved,
        }
    return {
        "disposition": ITEM9_ADMISSION_ACCEPTED,
        "reason_code": None,
        "effective_authority": effective,
        "authority_resolution": resolved,
    }


__all__ = [
    "ITEM9_ADMISSION_ACCEPTED",
    "ITEM9_ADMISSION_REFUSED",
    "REFUSAL_AUTHORITY_INVALID",
    "REFUSAL_HISTORICAL_DEVELOPMENT",
    "evaluate_item9_prospective_corpus_admission",
]
