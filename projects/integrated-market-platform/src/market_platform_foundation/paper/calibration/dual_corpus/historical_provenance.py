"""Historical development retrieval provenance (explicit HISTORICAL_DEVELOPMENT)."""

from __future__ import annotations

from typing import Any, Mapping

from .evidence_authority import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT

HISTORICAL_DEVELOPMENT_PROVENANCE_KIND = "historical_development_provenance_v1"
HISTORICAL_PROVENANCE_SCHEMA_VERSION = "dual_corpus.historical-provenance/1.0.0"

_REQUIRED_FIELDS: tuple[str, ...] = (
    "corpus_evidence_authority",
    "provider_id",
    "capability_id",
    "instrument_id",
    "request_params",
    "requested_interval_start_ns",
    "requested_interval_end_ns",
    "returned_interval_start_ns",
    "returned_interval_end_ns",
    "timezone_policy",
    "session_policy",
    "bar_resolution",
    "raw_timestamp_semantics",
    "availability_semantics",
    "retrieval_timestamp_ns",
    "provider_response_identity",
    "raw_payload_ref",
    "raw_payload_sha256",
    "schema_version",
    "dataset_id",
    "dataset_version",
    "code_sha",
    "transformation_lineage",
    "inclusion_reason",
    "exclusion_reason",
)

PROVENANCE_INCOMPLETE = "HISTORICAL_PROVENANCE_INCOMPLETE"
PROVENANCE_WRONG_AUTHORITY = "HISTORICAL_PROVENANCE_WRONG_AUTHORITY"


def validate_historical_development_provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in _REQUIRED_FIELDS if key not in record]
    authority = str(record.get("corpus_evidence_authority") or "").strip().upper()
    if authority != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return {
            "ok": False,
            "reason_code": PROVENANCE_WRONG_AUTHORITY,
            "missing_fields": missing,
        }
    if missing:
        return {"ok": False, "reason_code": PROVENANCE_INCOMPLETE, "missing_fields": missing}
    if str(record.get("schema_version") or "") != HISTORICAL_PROVENANCE_SCHEMA_VERSION:
        return {
            "ok": False,
            "reason_code": PROVENANCE_INCOMPLETE,
            "missing_fields": ["schema_version"],
        }
    return {"ok": True, "reason_code": None, "missing_fields": ()}


def build_historical_development_provenance(
    *,
    provider_id: str,
    capability_id: str,
    instrument_id: str,
    request_params: Mapping[str, Any],
    requested_interval_start_ns: int,
    requested_interval_end_ns: int,
    returned_interval_start_ns: int,
    returned_interval_end_ns: int,
    timezone_policy: str,
    session_policy: str,
    bar_resolution: str,
    raw_timestamp_semantics: str,
    availability_semantics: str,
    retrieval_timestamp_ns: int,
    provider_response_identity: str,
    raw_payload_ref: str,
    raw_payload_sha256: str,
    dataset_id: str,
    dataset_version: str,
    code_sha: str,
    transformation_lineage: tuple[str, ...],
    inclusion_reason: str,
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_kind": HISTORICAL_DEVELOPMENT_PROVENANCE_KIND,
        "schema_version": HISTORICAL_PROVENANCE_SCHEMA_VERSION,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "provider_id": provider_id,
        "capability_id": capability_id,
        "instrument_id": instrument_id,
        "request_params": dict(request_params),
        "requested_interval_start_ns": int(requested_interval_start_ns),
        "requested_interval_end_ns": int(requested_interval_end_ns),
        "returned_interval_start_ns": int(returned_interval_start_ns),
        "returned_interval_end_ns": int(returned_interval_end_ns),
        "timezone_policy": timezone_policy,
        "session_policy": session_policy,
        "bar_resolution": bar_resolution,
        "raw_timestamp_semantics": raw_timestamp_semantics,
        "availability_semantics": availability_semantics,
        "retrieval_timestamp_ns": int(retrieval_timestamp_ns),
        "provider_response_identity": provider_response_identity,
        "raw_payload_ref": raw_payload_ref,
        "raw_payload_sha256": raw_payload_sha256,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "code_sha": code_sha,
        "transformation_lineage": list(transformation_lineage),
        "inclusion_reason": inclusion_reason,
        "exclusion_reason": exclusion_reason,
    }


__all__ = [
    "HISTORICAL_DEVELOPMENT_PROVENANCE_KIND",
    "HISTORICAL_PROVENANCE_SCHEMA_VERSION",
    "PROVENANCE_INCOMPLETE",
    "PROVENANCE_WRONG_AUTHORITY",
    "build_historical_development_provenance",
    "validate_historical_development_provenance",
]
