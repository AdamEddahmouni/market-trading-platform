"""Dispatch primary-source verification by public-record domain."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping

from ...congressional_ptr.primary_verification import (
    PtrPrimaryVerificationResult,
    verify_congressional_row_primary,
)
from ...sec_edgar.primary_verification import (
    SecPrimaryVerificationResult,
    verify_sec_insider_row_against_submissions,
)
from .artifact import build_verification_artifact


class PublicRecordDomain(StrEnum):
    SEC_INSIDER = "sec_insider"
    CONGRESSIONAL_PTR = "congressional_ptr"


def verify_market_trackers_row(
    domain: PublicRecordDomain | str,
    row: Mapping[str, Any],
    *,
    observed_time: str,
    submissions_payload: bytes | str | Mapping[str, Any] | None = None,
    ptr_primary_metadata: Mapping[str, Any] | None = None,
    document_body: bytes | None = None,
    document_retrieved_time: str = "",
    emit_artifact: bool = True,
) -> dict[str, Any]:
    domain_key = PublicRecordDomain(str(domain))
    live_network = False

    if domain_key == PublicRecordDomain.SEC_INSIDER:
        if submissions_payload is None:
            raise ValueError("SEC_SUBMISSIONS_PAYLOAD_REQUIRED")
        result: SecPrimaryVerificationResult | PtrPrimaryVerificationResult = (
            verify_sec_insider_row_against_submissions(
                row,
                submissions_payload=submissions_payload,
                observed_time=observed_time,
                document_body=document_body,
                document_retrieved_time=document_retrieved_time,
                live_retrieval=False,
            )
        )
    elif domain_key == PublicRecordDomain.CONGRESSIONAL_PTR:
        result = verify_congressional_row_primary(
            row,
            ptr_primary_metadata=ptr_primary_metadata,
            observed_time=observed_time,
        )
    else:
        raise ValueError(f"PUBLIC_RECORD_DOMAIN_UNSUPPORTED:{domain}")

    verification_dict = result.to_dict()
    out: dict[str, Any] = {
        "domain": domain_key.value,
        "verification": verification_dict,
    }
    if emit_artifact:
        out["artifact"] = build_verification_artifact(
            domain=domain_key.value,
            verification=verification_dict,
            generated_at=observed_time,
            live_network=live_network,
        )
    return out


__all__ = ["PublicRecordDomain", "verify_market_trackers_row"]
