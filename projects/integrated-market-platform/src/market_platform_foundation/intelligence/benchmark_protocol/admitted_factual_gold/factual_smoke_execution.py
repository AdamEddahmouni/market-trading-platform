"""Bounded IBP_FACTUAL_SMOKE_V1 execution (distinct from legacy ibp-smoke10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ....canonical import canonical_bytes, sha256_bytes
from ....paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ..types import IBP_PROTOCOL_ID, IBP_PROTOCOL_SCHEMA_VERSION
from .factual_blind_input import build_factual_blind_case_input
from .factual_contamination_audit import audit_factual_smoke_run_contamination
from .factual_evaluator import load_factual_evaluator_gold, score_factual_case_dimensions
from .protocol import load_candidate_factual_gold_protocol
from .types import (
    IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID,
    IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
)

IBP_FACTUAL_SMOKE_RUN_KIND = "intelligence_benchmark_factual_smoke_run_v1"
IBP_FACTUAL_SMOKE_RUN_SCHEMA_VERSION = "imp.intelligence-benchmark-factual-smoke-run/1.0.0"
IBP_FACTUAL_SMOKE_CONTRACT_ID = "ibp-factual-smoke-invocation-v1"
CONTEXT_RESET_POLICY = "one_fresh_context_per_case_v1"


def scored_factual_case_ids(protocol: dict[str, Any]) -> list[str]:
    return [
        str(row["CASE_ID"])
        for row in protocol.get("cases", [])
        if row.get("SCORING_GATE") == "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
    ]


def freeze_factual_smoke_run_configuration(
    repository_root: Path,
    *,
    code_sha: str | None = None,
    sut_profile_id: str,
) -> dict[str, Any]:
    protocol = load_candidate_factual_gold_protocol(repository_root)
    if protocol.get("freeze", {}).get("status") != "FROZEN":
        raise ValueError("FACTUAL_PROTOCOL_NOT_FROZEN")
    resolved_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    case_ids = scored_factual_case_ids(protocol)
    config_body = {
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_schema_version": IBP_PROTOCOL_SCHEMA_VERSION,
        "factual_smoke_contract_id": IBP_FACTUAL_SMOKE_CONTRACT_ID,
        "factual_gold_schema_version": IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
        "factual_gold_hypothesis_id": IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID,
        "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "caseset_hash": protocol.get("caseset_hash"),
        "goldset_hash": protocol.get("goldset_hash"),
        "case_ids": case_ids,
        "case_count": len(case_ids),
        "context_reset_policy": CONTEXT_RESET_POLICY,
        "sut_profile_id": sut_profile_id,
        "evaluator_only_gold_prefix": "evaluator_only/admitted_factual_gold/",
        "code_sha": resolved_sha,
        "legacy_smoke10_run_id_preserved": "ibp-smoke10-76DDD188CD080365",
    }
    fingerprint = sha256_bytes(canonical_bytes(config_body))
    return {
        **config_body,
        "frozen_config_fingerprint": fingerprint,
        "frozen_at_utc": "FACTUAL_SMOKE_V1_NO_WALL_CLOCK",
    }


def _context_reset_token(case_id: str, frozen_config_fingerprint: str) -> str:
    return sha256_bytes(canonical_bytes({"case_id": case_id, "config": frozen_config_fingerprint}))


def execute_factual_smoke_case(
    *,
    repository_root: Path,
    case: dict[str, Any],
    frozen_config_fingerprint: str,
    sut_runner: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    case_id = case["CASE_ID"]
    token = _context_reset_token(case_id, frozen_config_fingerprint)
    blind_input = build_factual_blind_case_input(case, context_reset_token=token)
    sut_response = sut_runner(blind_input)
    gold = load_factual_evaluator_gold(repository_root, case["evaluator_gold_ref"])
    scoring = score_factual_case_dimensions(sut_response=sut_response, gold=gold)
    return {
        "case_id": case_id,
        "context_reset_token": token,
        "prior_case_ids_visible_to_sut": False,
        "evaluator_gold_loaded_for_sut": False,
        "sut_response_includes_gold": any(key in sut_response for key in ("gold_answer", "EXPECTED_FACTS", "GOLD_HASH")),
        "evidence_set": case.get("EVIDENCE_SET"),
        "sut_response": sut_response,
        "dimension_scores": scoring["dimensions"],
        "fact_verdicts": scoring["fact_verdicts"],
        "failure_reasons": scoring["failure_reasons"],
        "scores_executed": True,
    }


def execute_factual_smoke_baseline(
    repository_root: Path,
    *,
    frozen_config: dict[str, Any],
    sut_runner: Callable[[dict[str, Any]], dict[str, Any]],
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    protocol = load_candidate_factual_gold_protocol(repository_root)
    frozen_fp = frozen_config["frozen_config_fingerprint"]
    if frozen_config.get("caseset_hash") != protocol.get("caseset_hash"):
        raise ValueError("FROZEN_CONFIG_CASESET_HASH_MISMATCH")
    if frozen_config.get("goldset_hash") != protocol.get("goldset_hash"):
        raise ValueError("FROZEN_CONFIG_GOLDSET_HASH_MISMATCH")

    cases_by_id = {row["CASE_ID"]: row for row in protocol.get("cases", [])}
    case_results = [
        execute_factual_smoke_case(
            repository_root=repository_root,
            case=cases_by_id[case_id],
            frozen_config_fingerprint=frozen_fp,
            sut_runner=sut_runner,
        )
        for case_id in frozen_config["case_ids"]
    ]

    run_id = f"ibp-factual-smoke-{frozen_fp[:16]}"
    run_record: dict[str, Any] = {
        "artifact_kind": IBP_FACTUAL_SMOKE_RUN_KIND,
        "schema_version": IBP_FACTUAL_SMOKE_RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "factual_smoke_contract_id": IBP_FACTUAL_SMOKE_CONTRACT_ID,
        "frozen_config_fingerprint": frozen_fp,
        "config": frozen_config,
        "case_ids": list(frozen_config["case_ids"]),
        "case_count": len(case_results),
        "case_results": case_results,
        "scores_executed": True,
        "smoke10_executed": False,
        "legacy_smoke10_run_id": "ibp-smoke10-76DDD188CD080365",
        "evaluator_invoked": True,
        "config_change_detected": False,
        "contamination_audit": audit_factual_smoke_run_contamination(
            {"case_results": case_results, "frozen_config_fingerprint": frozen_fp, "config_change_detected": False},
            repository_root=repository_root,
            frozen_config_fingerprint=frozen_fp,
        ),
    }
    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)
        out = artifact_root / f"{run_id}.json"
        out.write_text(json.dumps(run_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run_record["artifact_path"] = str(out)
    return run_record


__all__ = [
    "CONTEXT_RESET_POLICY",
    "IBP_FACTUAL_SMOKE_CONTRACT_ID",
    "IBP_FACTUAL_SMOKE_RUN_KIND",
    "IBP_FACTUAL_SMOKE_RUN_SCHEMA_VERSION",
    "execute_factual_smoke_baseline",
    "execute_factual_smoke_case",
    "freeze_factual_smoke_run_configuration",
    "scored_factual_case_ids",
]
