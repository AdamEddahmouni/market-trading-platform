"""EvidenceArtifact schema and content hashing (not Phase 0 evidence records)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .dataset import AdmittedBarDataset
from .models import EDGE_STATS_QUERY_SCHEMA_VERSION, PIT_CLASS_HISTORICAL_BAR_END, EdgeStatsQueryV1

EDGE_STATS_ARTIFACT_SCHEMA_VERSION = "1.0.0"
EDGE_STATS_ENGINE_VERSION = "research.edge_stats/1.0.0"
AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION = "EVIDENCE_NOT_PREDICTION"
MATCHED_EXAMPLE_CAP = 8
SPLIT_MIN_SAMPLE = 12


def _iso_utc_from_ns(epoch_ns: int) -> str:
    return (
        datetime.fromtimestamp(epoch_ns / 1_000_000_000, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _redacted_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, example in enumerate(examples[:MATCHED_EXAMPLE_CAP]):
        rows.append(
            {
                "decision_time": _iso_utc_from_ns(int(example["decision_time_ns"])),
                "match_index": index,
                "outcome_time": _iso_utc_from_ns(int(example["outcome_time_ns"])),
            }
        )
    return rows


def _split_estimate(
    examples: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    if len(examples) < SPLIT_MIN_SAMPLE:
        return {"status": "INSUFFICIENT_DATA", "n": len(examples), "estimate": None}
    values = list(extract_outcome_values_from_examples(examples, metric))
    estimate = sum(values) / len(values)
    if metric == "positive_rate":
        estimate = round(estimate, 6)
    else:
        estimate = round(estimate, 3)
    return {"status": "OK", "n": len(examples), "estimate": estimate}


def extract_outcome_values_from_examples(
    examples: list[dict[str, Any]],
    metric: str,
) -> tuple[float, ...]:
    from .matching import extract_outcome_values

    return extract_outcome_values(examples, metric)


def _time_of_day_splits(
    examples: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    morning: list[dict[str, Any]] = []
    afternoon: list[dict[str, Any]] = []
    for example in examples:
        decision_ns = int(example["decision_time_ns"])
        hour = datetime.fromtimestamp(decision_ns / 1_000_000_000, tz=timezone.utc).hour
        if hour < 12:
            morning.append(example)
        else:
            afternoon.append(example)
    return {
        "utc_morning_before_12": _split_estimate(morning, metric),
        "utc_afternoon_from_12": _split_estimate(afternoon, metric),
    }


def _regime_splits(
    examples: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    from .matching import _squeeze_state

    buckets: dict[str, list[dict[str, Any]]] = {}
    for example in examples:
        state = _squeeze_state(example) or "UNKNOWN"
        buckets.setdefault(state, []).append(example)
    return {
        state: _split_estimate(rows, metric) for state, rows in sorted(buckets.items())
    }


def build_evidence_artifact(
    *,
    query: EdgeStatsQueryV1,
    dataset: AdmittedBarDataset,
    matched_examples: list[dict[str, Any]],
    estimate: float,
    ci: dict[str, Any],
    generated_at: str,
    n: int,
) -> dict[str, Any]:
    metric = query.outcome.metric
    midpoint = max(1, len(matched_examples) // 2)
    recent = matched_examples[midpoint:]
    full = matched_examples

    body: dict[str, Any] = {
        "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
        "authority_class": AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
        "ci": ci,
        "dataset": {
            "bar_count": dataset.bar_count,
            "collection_relative_path": dataset.collection_relative_path,
            "source_object_id": dataset.source_object_id,
            "source_sha256": dataset.source_sha256,
        },
        "engine_version": EDGE_STATS_ENGINE_VERSION,
        "estimate": estimate,
        "generated_at": generated_at,
        "matched_examples": _redacted_examples(matched_examples),
        "n": n,
        "outcome": query.outcome.to_dict(),
        "pit_class": PIT_CLASS_HISTORICAL_BAR_END,
        "query": {
            **query.to_dict(),
            "version_hash": query.version_hash(),
        },
        "recent_full_comparison": {
            "full": _split_estimate(full, metric),
            "recent_half": _split_estimate(recent, metric),
        },
        "regime_splits": _regime_splits(matched_examples, metric),
        "schema_version": EDGE_STATS_ARTIFACT_SCHEMA_VERSION,
        "time_splits": _time_of_day_splits(matched_examples, metric),
    }
    body["content_sha256"] = evidence_artifact_content_sha256(body)
    return body


def evidence_artifact_content_sha256(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "content_sha256"}
    return sha256_bytes(canonical_bytes(payload))
