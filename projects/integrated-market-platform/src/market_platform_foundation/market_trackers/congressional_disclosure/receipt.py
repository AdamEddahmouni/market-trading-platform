"""IMP external source receipt shell (pre-normalization boundary)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from .pin import ADAPTER_PREP_VERSION, UPSTREAM_PIN


@dataclass(frozen=True, slots=True)
class ExternalSourceReceipt:
    """Receipt before canonical identity + EventV1 normalization."""

    receipt_id: str
    source_bundle: str
    upstream_row_id: str
    upstream_dataset_id: str
    raw_payload_hash: str
    primary_source_url: str
    upstream_parser: str
    upstream_retrieved_at: str
    platform_received_time_ns: int
    adapter_prep_version: str
    upstream_pin: dict[str, Any]
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_prep_version": self.adapter_prep_version,
            "platform_received_time_ns": self.platform_received_time_ns,
            "primary_source_url": self.primary_source_url,
            "quality_flags": list(self.quality_flags),
            "raw_payload_hash": self.raw_payload_hash,
            "receipt_id": self.receipt_id,
            "source_bundle": self.source_bundle,
            "upstream_dataset_id": self.upstream_dataset_id,
            "upstream_parser": self.upstream_parser,
            "upstream_pin": self.upstream_pin,
            "upstream_retrieved_at": self.upstream_retrieved_at,
            "upstream_row_id": self.upstream_row_id,
        }


def build_external_source_receipt(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
) -> ExternalSourceReceipt:
    row_id = str(row.get("id") or "").strip()
    if not row_id:
        raise ValueError("MARKET_TRACKERS_ROW_ID_REQUIRED")

    provenance = row.get("provenance") or {}
    if not isinstance(provenance, Mapping):
        raise ValueError("MARKET_TRACKERS_PROVENANCE_REQUIRED")

    flags: list[str] = ["REPLACEABLE_AGGREGATOR", "NOT_TRADE_RECOMMENDATION"]
    if provenance.get("needsReview"):
        flags.append("UPSTREAM_NEEDS_REVIEW")
    confidence = provenance.get("confidence")
    if confidence is not None and float(confidence) < 1:
        flags.append("UPSTREAM_PARSER_CONFIDENCE_BELOW_STRUCTURED")

    payload_hash = sha256_bytes(canonical_bytes(dict(row)))
    receipt_id = sha256_bytes(
        canonical_bytes(
            {
                "bundle": "market_trackers.congress_trades",
                "row_id": row_id,
                "hash": payload_hash,
                "prep": ADAPTER_PREP_VERSION,
            }
        )
    )

    return ExternalSourceReceipt(
        receipt_id=receipt_id,
        source_bundle="market_trackers.congress_trades",
        upstream_row_id=row_id,
        upstream_dataset_id=UPSTREAM_PIN.dataset_id,
        raw_payload_hash=payload_hash,
        primary_source_url=str(provenance.get("sourceUrl") or ""),
        upstream_parser=str(provenance.get("parser") or ""),
        upstream_retrieved_at=str(provenance.get("retrievedAt") or ""),
        platform_received_time_ns=platform_received_time_ns,
        adapter_prep_version=ADAPTER_PREP_VERSION,
        upstream_pin=UPSTREAM_PIN.to_dict(),
        quality_flags=tuple(dict.fromkeys(flags)),
    )
