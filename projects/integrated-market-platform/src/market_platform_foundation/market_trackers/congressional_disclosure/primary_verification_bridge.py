"""Bridge Market Trackers congressional rows to chamber PTR primary verification."""

from __future__ import annotations

from typing import Any, Mapping

from ...research.public_record_primary_source import PublicRecordDomain, verify_market_trackers_row
from .pipeline import AdapterPrepBundle, build_adapter_prep_bundle


def build_adapter_prep_bundle_with_ptr_primary(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
    observed_time: str,
    ptr_primary_metadata: Mapping[str, Any] | None = None,
) -> tuple[AdapterPrepBundle, dict[str, Any], dict[str, str] | None]:
    bundle = build_adapter_prep_bundle(row, platform_received_time_ns=platform_received_time_ns)
    envelope = verify_market_trackers_row(
        PublicRecordDomain.CONGRESSIONAL_PTR,
        row,
        observed_time=observed_time,
        ptr_primary_metadata=ptr_primary_metadata,
    )
    ptr_primary = envelope["verification"].get("ptr_primary")
    return bundle, envelope, ptr_primary if isinstance(ptr_primary, dict) else None


__all__ = ["build_adapter_prep_bundle_with_ptr_primary"]
