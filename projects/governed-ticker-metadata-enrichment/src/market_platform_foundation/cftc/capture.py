"""Bounded canonical capture envelopes for CFTC COT evidence."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

ENVELOPE_SCHEMA = "cftc.cot_envelope/1.0.0"


def build_cot_envelope(
    *,
    dataset_id: str,
    report_family: str,
    position_scope: str,
    position_date: str,
    row_count: int,
    raw_payload_hash: str,
    retrieved_time: str,
    first_observed_time: str,
    query_identity: str,
    lifecycle: str = "CAPTURED",
) -> dict[str, Any]:
    return {
        "schema": ENVELOPE_SCHEMA,
        "provider": "cftc_cot",
        "dataset": dataset_id,
        "report_family": report_family,
        "position_scope": position_scope,
        "position_date": position_date,
        "lifecycle": lifecycle,
        "row_count": row_count,
        "raw_payload_hash": raw_payload_hash,
        "retrieved_time": retrieved_time,
        "first_observed_time": first_observed_time,
        "query_identity": query_identity,
    }


def hash_rows(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_bytes({"rows": rows}))


__all__ = ["ENVELOPE_SCHEMA", "build_cot_envelope", "hash_rows"]
