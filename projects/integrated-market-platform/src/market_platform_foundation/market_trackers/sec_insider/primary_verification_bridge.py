"""Bridge Market Trackers SEC insider rows to EDGAR primary-source verification."""

from __future__ import annotations

from typing import Any, Mapping

from ...research.public_record_primary_source import PublicRecordDomain, verify_market_trackers_row
from .pipeline import AdapterPrepBundle, build_adapter_prep_bundle


def build_adapter_prep_bundle_with_edgar_primary(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
    submissions_payload: bytes | str | Mapping[str, Any],
    observed_time: str,
    document_body: bytes | None = None,
) -> tuple[AdapterPrepBundle, dict[str, Any], dict[str, str]]:
    """Return adapter prep, verification envelope, and reconcile-ready ``edgar_primary`` mapping."""
    bundle = build_adapter_prep_bundle(row, platform_received_time_ns=platform_received_time_ns)
    envelope = verify_market_trackers_row(
        PublicRecordDomain.SEC_INSIDER,
        row,
        observed_time=observed_time,
        submissions_payload=submissions_payload,
        document_body=document_body,
    )
    edgar_primary = dict(envelope["verification"]["edgar_primary"])
    return bundle, envelope, edgar_primary


__all__ = ["build_adapter_prep_bundle_with_edgar_primary"]
