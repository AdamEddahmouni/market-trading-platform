"""Immutable research dataset manifest per ADR-RDATA-001."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..features.bar_features import SUPPORTED_CAPABILITY

DATASET_SCHEMA_VERSION = "1.0.0"
ADMISSION_REFERENCE = "phase0a.admitted_source_decision"


def materialize_dataset_rows(
    events: list[dict[str, Any]],
    *,
    decision_times: list[int] | None = None,
) -> list[dict[str, object]]:
    del decision_times  # rows are materialized per canonical bar event
    rows: list[dict[str, object]] = []
    for event in sorted(events, key=lambda row: (str(row["instrument_id"]), int(row["available_time"]))):
        if str(event.get("event_type")) != "BAR_OHLCV_1M":
            continue
        payload = event.get("bar_payload", {})
        if not isinstance(payload, dict):
            continue
        available_time = int(event["available_time"])
        rows.append(
            {
                "available_time": available_time,
                "capability": SUPPORTED_CAPABILITY,
                "feature_id": "bar_close",
                "instrument_id": str(event["instrument_id"]),
                "prediction_cutoff": available_time,
                "value": str(payload.get("close", "0")),
            }
        )
    return rows


def build_dataset_manifest(
    rows: list[dict[str, object]],
    *,
    member_filename: str = "research-rows.json",
) -> dict[str, object]:
    body = {
        "admission_reference": ADMISSION_REFERENCE,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "member_files": [
            {
                "content_hash": sha256_bytes(canonical_bytes(rows)),
                "logical_name": member_filename,
                "row_count": len(rows),
            }
        ],
        "row_count": len(rows),
    }
    fingerprint = dataset_fingerprint(body)
    return {**body, "dataset_fingerprint": fingerprint}


def dataset_fingerprint(manifest_body: dict[str, object]) -> str:
    body = dict(manifest_body)
    body.pop("dataset_fingerprint", None)
    return sha256_bytes(canonical_bytes(body))
