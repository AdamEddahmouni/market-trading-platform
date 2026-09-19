"""Item 9 prospective corpus admission gates (contamination refusal)."""

from __future__ import annotations

from typing import Any, Mapping

from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    resolve_effective_corpus_evidence_authority,
)

ITEM9_ADMISSION_REFUSED = "REFUSED"
ITEM9_ADMISSION_ACCEPTED = "ACCEPTED"
REFUSAL_HISTORICAL_DEVELOPMENT = "HISTORICAL_DEVELOPMENT_NOT_PROSPECTIVE"
REFUSAL_AUTHORITY_INVALID = "CORPUS_EVIDENCE_AUTHORITY_INVALID"
REFUSAL_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT = "CORPUS_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT"

_ITEM9_PROSPECTIVE_RECEIPT_EVIDENCE = "PROSPECTIVE_BAR_OHLCV_1M"
_ITEM9_PROSPECTIVE_OPEND_NESTED = "PROSPECTIVE_OPEND_KLINE"
_ITEM9_PROOF_MODE_PROSPECTIVE = "PROSPECTIVE_BAR_OHLCV_1M"


def _payload_declares_item9_prospective_receipt(payload: Mapping[str, object]) -> bool:
    proof_mode = str(payload.get("proof_mode") or "")
    if proof_mode != _ITEM9_PROOF_MODE_PROSPECTIVE or payload.get("not_prospective_evidence"):
        return False
    declared = str(payload.get("evidence_class") or "")
    nested = str((payload.get("bar_provenance") or {}).get("evidence_class") or "")
    return declared == _ITEM9_PROSPECTIVE_RECEIPT_EVIDENCE and nested == _ITEM9_PROSPECTIVE_OPEND_NESTED


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
    prospective_shaped = bool(payload and _payload_declares_item9_prospective_receipt(payload))
    effective = str(resolved.get("effective_authority") or "")
    if effective == CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return {
            "disposition": ITEM9_ADMISSION_REFUSED,
            "reason_code": REFUSAL_HISTORICAL_DEVELOPMENT,
            "effective_authority": effective,
            "authority_resolution": resolved,
        }
    if not resolved.get("ok"):
        if prospective_shaped and not resolved.get("declared_authorities"):
            effective = CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE
        else:
            return {
                "disposition": ITEM9_ADMISSION_REFUSED,
                "reason_code": str(resolved.get("reason_code") or REFUSAL_AUTHORITY_INVALID),
                "effective_authority": effective,
                "authority_resolution": resolved,
            }
    if not effective:
        return {
            "disposition": ITEM9_ADMISSION_REFUSED,
            "reason_code": REFUSAL_AUTHORITY_INVALID,
            "effective_authority": effective,
            "authority_resolution": resolved,
        }
    if effective != CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE:
        if prospective_shaped:
            return {
                "disposition": ITEM9_ADMISSION_REFUSED,
                "reason_code": REFUSAL_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT,
                "effective_authority": effective,
                "authority_resolution": resolved,
            }
        return {
            "disposition": ITEM9_ADMISSION_REFUSED,
            "reason_code": REFUSAL_AUTHORITY_INVALID,
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
    "REFUSAL_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT",
    "REFUSAL_AUTHORITY_INVALID",
    "REFUSAL_HISTORICAL_DEVELOPMENT",
    "evaluate_item9_prospective_corpus_admission",
]
