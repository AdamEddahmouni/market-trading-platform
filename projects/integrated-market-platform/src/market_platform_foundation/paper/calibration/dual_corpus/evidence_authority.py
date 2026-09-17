"""Canonical corpus-level evidence authority (dual-corpus contract).

Distinct from receipt-level classes such as ``PROSPECTIVE_BAR_OHLCV_1M`` or
``ADMITTED_HISTORICAL_FIXTURE``. Every historical development artifact must
declare ``HISTORICAL_DEVELOPMENT`` explicitly — directory placement alone is
never sufficient authority.
"""

from __future__ import annotations

from typing import Any, Mapping

CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT = "HISTORICAL_DEVELOPMENT"
CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE = "PROSPECTIVE_FEATURE_EVIDENCE"
CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE = (
    "POST_HORIZON_HISTORICAL_LABEL_EVIDENCE"
)
CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION = "UNTOUCHED_FORWARD_EVALUATION"

CORPUS_EVIDENCE_AUTHORITIES: frozenset[str] = frozenset(
    {
        CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
        CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
    }
)

AUTHORITY_UPGRADE_FORBIDDEN = "AUTHORITY_UPGRADE_FORBIDDEN"
AUTHORITY_AMBIGUOUS = "AUTHORITY_AMBIGUOUS"

_NON_UPGRADABLE = frozenset({CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT})


def _normalize_authority(value: object) -> str:
    return str(value or "").strip().upper()


def _collect_declared_authorities(
    *,
    manifest_authority: str | None = None,
    provenance_authority: str | None = None,
    record_authority: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    sources: list[str] = []
    if payload:
        for key in (
            "corpus_evidence_authority",
            "evidence_authority",
            "evidence_authority_class",
            "authority_class",
        ):
            text = _normalize_authority(payload.get(key))
            if text:
                sources.append(text)
        nested = payload.get("provenance")
        if isinstance(nested, Mapping):
            text = _normalize_authority(nested.get("corpus_evidence_authority"))
            if text:
                sources.append(text)
    for candidate in (manifest_authority, provenance_authority, record_authority):
        text = _normalize_authority(candidate)
        if text:
            sources.append(text)
    return tuple(sources)


def resolve_effective_corpus_evidence_authority(
    *,
    manifest_authority: str | None = None,
    provenance_authority: str | None = None,
    record_authority: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve authority fail-closed; raw provenance cannot be upgraded by manifest text."""

    declared = _collect_declared_authorities(
        manifest_authority=manifest_authority,
        provenance_authority=provenance_authority,
        record_authority=record_authority,
        payload=payload,
    )
    if not declared:
        return {
            "effective_authority": "",
            "ok": False,
            "reason_code": AUTHORITY_AMBIGUOUS,
            "declared_authorities": (),
        }
    unique = frozenset(declared)
    if CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT in unique:
        effective = CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
        if len(unique) > 1:
            return {
                "effective_authority": effective,
                "ok": False,
                "reason_code": AUTHORITY_UPGRADE_FORBIDDEN,
                "declared_authorities": declared,
            }
        return {
            "effective_authority": effective,
            "ok": True,
            "reason_code": None,
            "declared_authorities": declared,
        }
    if len(unique) > 1:
        return {
            "effective_authority": declared[0],
            "ok": False,
            "reason_code": AUTHORITY_AMBIGUOUS,
            "declared_authorities": declared,
        }
    effective = declared[0]
    if provenance_authority and manifest_authority:
        prov = _normalize_authority(provenance_authority)
        man = _normalize_authority(manifest_authority)
        if prov in _NON_UPGRADABLE and man != prov:
            return {
                "effective_authority": prov,
                "ok": False,
                "reason_code": AUTHORITY_UPGRADE_FORBIDDEN,
                "declared_authorities": declared,
            }
    if effective not in CORPUS_EVIDENCE_AUTHORITIES:
        return {
            "effective_authority": effective,
            "ok": False,
            "reason_code": AUTHORITY_AMBIGUOUS,
            "declared_authorities": declared,
        }
    return {
        "effective_authority": effective,
        "ok": True,
        "reason_code": None,
        "declared_authorities": declared,
    }


__all__ = [
    "AUTHORITY_AMBIGUOUS",
    "AUTHORITY_UPGRADE_FORBIDDEN",
    "CORPUS_EVIDENCE_AUTHORITIES",
    "CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT",
    "CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE",
    "CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE",
    "CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION",
    "resolve_effective_corpus_evidence_authority",
]
