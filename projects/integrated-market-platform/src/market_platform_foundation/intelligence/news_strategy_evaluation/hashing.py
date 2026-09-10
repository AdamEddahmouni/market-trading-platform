"""Deterministic hashes for evaluation reproducibility."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .contracts import EvaluationReport, StrategyFeatureSnapshot


def feature_snapshot_hash(snapshot: StrategyFeatureSnapshot) -> str:
    body = snapshot.to_dict()
    body.pop("snapshot_hash", None)
    body.pop("snapshot_id", None)
    return sha256_bytes(canonical_bytes(body))


def evaluation_config_hash(config_body: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(config_body))


def evaluation_run_hash(run_body: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(run_body))


def evaluation_report_hash(report: EvaluationReport) -> str:
    body = report.to_dict()
    body.pop("report_hash", None)
    return sha256_bytes(canonical_bytes(body))


def shadow_record_hash(body: dict[str, Any]) -> str:
    payload = dict(body)
    payload.pop("shadow_hash", None)
    payload.pop("shadow_id", None)
    return sha256_bytes(canonical_bytes(payload))


__all__ = [
    "evaluation_config_hash",
    "evaluation_report_hash",
    "evaluation_run_hash",
    "feature_snapshot_hash",
    "shadow_record_hash",
]
