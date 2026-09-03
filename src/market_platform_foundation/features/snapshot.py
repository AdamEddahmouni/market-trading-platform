"""Point-in-time feature snapshot contract."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

FEATURE_DEFINITION_VERSION = "1.0.0"


def build_feature_snapshot(
    *,
    prediction_cutoff: int,
    bar_features: list[dict[str, Any]],
    institutional_evidence: list[dict[str, Any]],
) -> dict[str, object]:
    snapshot = {
        "bar_features": sorted(bar_features, key=lambda row: str(row["feature_id"])),
        "feature_definition_version": FEATURE_DEFINITION_VERSION,
        "institutional_evidence": sorted(
            institutional_evidence, key=lambda row: str(row["family"])
        ),
        "prediction_cutoff": prediction_cutoff,
    }
    return {**snapshot, "snapshot_hash": feature_snapshot_hash(snapshot)}


def feature_snapshot_hash(snapshot: dict[str, object]) -> str:
    body = dict(snapshot)
    body.pop("snapshot_hash", None)
    return sha256_bytes(canonical_bytes(body))
