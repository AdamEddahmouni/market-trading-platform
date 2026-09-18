"""Run manifest for historical research harness (extends experiment ledger fields)."""

from __future__ import annotations

import time
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ..research_experiments.types import ExperimentManifestV1
from .types import (
    HISTORICAL_RESEARCH_HARNESS_VERSION,
    HISTORICAL_RESEARCH_RUN_MANIFEST_KIND,
    HISTORICAL_RESEARCH_RUN_SCHEMA_VERSION,
    HistoricalResearchRunConfig,
)


def derive_historical_research_run_id(
    *,
    experiment_id: str,
    dataset_fingerprint: str,
    config_fingerprint: str,
    research_code_sha: str,
) -> str:
    payload = {
        "identity_version": "historical-research-run-sha256-v1",
        "experiment_id": experiment_id,
        "dataset_fingerprint": dataset_fingerprint,
        "config_fingerprint": config_fingerprint,
        "research_code_sha": research_code_sha,
    }
    return sha256_bytes(canonical_bytes(payload))


def config_fingerprint(config: HistoricalResearchRunConfig) -> str:
    body = {
        "experiment_id": config.experiment_id,
        "hypothesis_id": config.hypothesis_id,
        "forward_horizon_bars": config.forward_horizon_bars,
        "split_policy": {
            "policy_id": config.split_policy.policy_id,
            "train_fraction": config.split_policy.train_fraction,
            "development_validate_fraction": config.split_policy.development_validate_fraction,
        },
        "strategy_id": config.strategy_id,
        "strategy_version": config.strategy_version,
        "simulator_version": config.simulator_version,
        "cost_slippage_bps": config.cost_slippage_bps,
        "parent_run_id": config.parent_run_id,
        "challenger_of_run_id": config.challenger_of_run_id,
        "metadata": config.metadata,
    }
    return sha256_bytes(canonical_bytes(body))


def build_historical_research_run_manifest(
    *,
    run_id: str,
    config: HistoricalResearchRunConfig,
    experiment_manifest: ExperimentManifestV1 | None,
    research_code_sha: str,
    source_dataset_id: str,
    dataset_fingerprint: str,
    instruments: tuple[str, ...],
    interval: str,
    feature_schema_version: str,
    target_label_kind: str,
    split_policy_id: str,
    split_assignments: list[dict[str, Any]],
    metrics: dict[str, Any],
    simulator_result: dict[str, Any],
    outputs: dict[str, Any],
    warnings: tuple[str, ...],
    contamination_status: str,
    config_fp: str,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "artifact_kind": HISTORICAL_RESEARCH_RUN_MANIFEST_KIND,
        "schema_version": HISTORICAL_RESEARCH_RUN_SCHEMA_VERSION,
        "harness_version": HISTORICAL_RESEARCH_HARNESS_VERSION,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "hypothesis_id": config.hypothesis_id,
        "research_code_sha": research_code_sha,
        "source_dataset_id": source_dataset_id,
        "dataset_fingerprint": dataset_fingerprint,
        "evidence_class": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "instruments": list(instruments),
        "interval": interval,
        "features": {"schema_version": feature_schema_version},
        "target_label_definition": {
            "label_kind": target_label_kind,
            "forward_horizon_bars": config.forward_horizon_bars,
            "not_post_horizon_label_evidence": True,
        },
        "split_policy": split_policy_id,
        "split_assignments": split_assignments,
        "model_strategy": {
            "strategy_id": config.strategy_id,
            "strategy_version": config.strategy_version,
        },
        "simulator": {
            "version": config.simulator_version,
            "cost_slippage_bps": config.cost_slippage_bps,
            "result_kind": simulator_result.get("result_kind"),
        },
        "parameters": {
            "forward_horizon_bars": config.forward_horizon_bars,
            "split_policy": config.split_policy.policy_id,
        },
        "metrics": metrics,
        "outputs": outputs,
        "warnings": list(warnings),
        "contamination_status": contamination_status,
        "lineage": {
            "parent_run_id": config.parent_run_id,
            "challenger_of_run_id": config.challenger_of_run_id,
        },
        "config_fingerprint": config_fp,
        "created_timestamp_ns": time.time_ns(),
        "governance": {
            "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
            "item7_effect": "NONE",
            "ftep_effect": "NONE",
            "live_authority": "NONE",
        },
    }
    if experiment_manifest is not None:
        manifest["experiment_manifest_ref"] = {
            "experiment_id": experiment_manifest.experiment_id,
            "schema_version": experiment_manifest.schema_version,
            "research_hypothesis_id": experiment_manifest.research_hypothesis_id,
            "implementation_version": experiment_manifest.implementation_version,
        }
    manifest["run_fingerprint"] = sha256_bytes(
        canonical_bytes(
            {
                "run_id": run_id,
                "dataset_fingerprint": dataset_fingerprint,
                "config_fingerprint": config_fp,
                "research_code_sha": research_code_sha,
                "metrics": metrics,
                "simulator_result_kind": simulator_result.get("result_kind"),
            }
        )
    )
    return manifest


__all__ = [
    "build_historical_research_run_manifest",
    "config_fingerprint",
    "derive_historical_research_run_id",
]
