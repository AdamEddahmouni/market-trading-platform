"""Options-flow replay EvidenceArtifact (transparent decomposition, not ranking score)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...research.edge_stats.artifact import AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
from .models import (
    PIT_CLASS_REPLAY_FIXTURE_AVAILABLE_TIME,
    REPLAY_MODE_SYNTHETIC_FIXTURE_ONLY,
    OptionsFlowReplayQueryV1,
)
from .dataset import AdmittedOptionsFlowReplayDataset

OPTIONS_FLOW_REPLAY_ARTIFACT_SCHEMA_VERSION = "1.0.0"
OPTIONS_FLOW_REPLAY_ENGINE_VERSION = "research.options_flow_replay/1.0.0"
ARTIFACT_TYPE = "OPTIONS_FLOW_REPLAY_EVIDENCE_ARTIFACT"


def build_evidence_artifact(
    *,
    query: OptionsFlowReplayQueryV1,
    dataset: AdmittedOptionsFlowReplayDataset,
    decomposed_prints: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    trade_counts: dict[str, int] = {}
    missing_union: set[str] = set()
    for row in decomposed_prints:
        trade_class = (
            (row.get("trade_classification") or {}).get("trade_class") or "unknown"
        )
        trade_counts[trade_class] = trade_counts.get(trade_class, 0) + 1
        for field in row.get("missing_data_fields") or []:
            missing_union.add(str(field))

    body: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        "replay_mode": REPLAY_MODE_SYNTHETIC_FIXTURE_ONLY,
        "live_feed_claim": "NOT_CLAIMED",
        "dataset": {
            "admission_id": dataset.admission_id,
            "fixture_id": dataset.fixture_id,
            "instrument_id": dataset.symbol,
            "source_object_id": dataset.admission_id,
            "source_sha256": dataset.source_sha256,
            "collection_relative_path": dataset.collection_relative_path,
            "activity_count": dataset.activity_count,
        },
        "decomposed_prints": decomposed_prints,
        "aggregate": {
            "print_count": len(decomposed_prints),
            "trade_class_counts": trade_counts,
            "missing_data_fields_union": sorted(missing_union),
        },
        "explicit_exclusions": [
            "vendor_composite_score",
            "confirmation_score",
            "opaque_whale_score",
        ],
        "engine_version": OPTIONS_FLOW_REPLAY_ENGINE_VERSION,
        "generated_at": generated_at,
        "pit_class": PIT_CLASS_REPLAY_FIXTURE_AVAILABLE_TIME,
        "query": {
            **query.to_dict(),
            "version_hash": query.version_hash(),
        },
        "schema_version": OPTIONS_FLOW_REPLAY_ARTIFACT_SCHEMA_VERSION,
    }
    body["content_sha256"] = evidence_artifact_content_sha256(body)
    return body


def evidence_artifact_content_sha256(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "content_sha256"}
    return sha256_bytes(canonical_bytes(payload))


__all__ = [
    "ARTIFACT_TYPE",
    "OPTIONS_FLOW_REPLAY_ARTIFACT_SCHEMA_VERSION",
    "OPTIONS_FLOW_REPLAY_ENGINE_VERSION",
    "build_evidence_artifact",
    "evidence_artifact_content_sha256",
]
