"""Bounded Smoke10 baseline execution under a frozen configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from .blind_input import build_blind_case_input
from .smoke10 import build_smoke10_invocation_contract
from .smoke10_contamination_audit import audit_smoke10_run_contamination
from .smoke10_evaluator import CASE_DIMENSIONS, load_evaluator_gold, score_case_dimensions
from .suite_catalog import load_suite_catalog, smoke10_case_ids, suite_catalog_fingerprint
from .sut_dispatch import resolve_sut_runner
from .sut_profiles import (
    IBP_FACTS_SUT_PROFILE_ID,
    IBP_SYNTHETIC_SUT_MODEL_ID,
    IBP_SYNTHETIC_SUT_PROFILE_ID,
    resolve_sut_profile,
    sut_profile_documentation,
)
from .types import (
    IBP_PROTOCOL_ID,
    IBP_PROTOCOL_SCHEMA_VERSION,
    IBP_SMOKE10_CASE_COUNT,
    IBP_SMOKE10_CONTRACT_ID,
)

IBP_SMOKE10_RUN_KIND = "intelligence_benchmark_smoke10_run_v1"
IBP_SMOKE10_RUN_SCHEMA_VERSION = "imp.intelligence-benchmark-smoke10-run/1.0.0"
CONTEXT_RESET_POLICY = "one_fresh_context_per_case_v1"
IBP_NONSTUB_SMOKE10_FREEZE_ARTIFACT_KIND = "ibp_smoke10_nonstub_sut_freeze_v1"


def freeze_smoke10_run_configuration(
    repository_root: Path,
    *,
    historical_run_record: dict[str, Any] | None = None,
    code_sha: str | None = None,
    sut_profile_id: str = IBP_SYNTHETIC_SUT_PROFILE_ID,
) -> dict[str, Any]:
    """Capture immutable run configuration before case 1."""
    catalog = load_suite_catalog(repository_root)
    resolved_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    profile = resolve_sut_profile(sut_profile_id)
    case_ids = list(smoke10_case_ids(catalog))
    contract = build_smoke10_invocation_contract(
        repository_root,
        historical_run_record=historical_run_record,
    )
    config_body = {
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_schema_version": IBP_PROTOCOL_SCHEMA_VERSION,
        "smoke10_contract_id": IBP_SMOKE10_CONTRACT_ID,
        "suite_id": catalog.get("suite_id"),
        "suite_catalog_fingerprint": suite_catalog_fingerprint(catalog),
        "case_ids": case_ids,
        "case_count": IBP_SMOKE10_CASE_COUNT,
        "context_reset_policy": CONTEXT_RESET_POLICY,
        "sut_profile_id": profile.profile_id,
        "sut_model_id": profile.model_id,
        "evaluator_only_gold_prefix": "evaluator_only/",
        "code_sha": resolved_sha,
        "invocation_contract": contract,
    }
    if profile.hypothesis_id is not None:
        config_body["sut_hypothesis_id"] = profile.hypothesis_id
        config_body["sut_definition"] = sut_profile_documentation(profile, code_sha=resolved_sha)
        config_body["tool_policy"] = {
            "tools_available": list(profile.tools_available),
            "evaluator_gold_access": "DENY",
            "network_llm_access": "DENY",
        }
        config_body["context_rules"] = list(profile.context_rules)
        if profile.limitation_class:
            config_body["sut_limitation_class"] = profile.limitation_class
    fingerprint = sha256_bytes(canonical_bytes(config_body))
    return {
        **config_body,
        "frozen_config_fingerprint": fingerprint,
        "frozen_at_utc": "BASELINE_V1_NO_WALL_CLOCK",
    }


def _context_reset_token(case_id: str, frozen_config_fingerprint: str) -> str:
    return sha256_bytes(canonical_bytes({"case_id": case_id, "config": frozen_config_fingerprint}))


def execute_smoke10_case(
    *,
    repository_root: Path,
    case: dict[str, Any],
    frozen_config_fingerprint: str,
    sut_runner,
) -> dict[str, Any]:
    """Run one Smoke10 case: SUT first, evaluator gold loaded only after response."""
    case_id = case["case_id"]
    token = _context_reset_token(case_id, frozen_config_fingerprint)
    blind_input = build_blind_case_input(case, context_reset_token=token)
    sut_response = sut_runner(blind_input)
    gold = load_evaluator_gold(repository_root, case["evaluator_gold_ref"])
    scoring = score_case_dimensions(
        sut_response=sut_response,
        gold=gold,
        blind_mode=case.get("blind_mode"),
    )
    return {
        "case_id": case_id,
        "blind_mode": case.get("blind_mode"),
        "context_reset_token": token,
        "prior_case_ids_visible_to_sut": False,
        "evaluator_gold_loaded_for_sut": False,
        "sut_response_includes_gold": "gold_answer" in sut_response,
        "sut_profile_id": sut_response.get("sut_profile_id"),
        "sut_model_id": sut_response.get("sut_model_id"),
        "sut_response": sut_response,
        "dimension_scores": scoring["dimensions"],
        "failure_reasons": scoring["failure_reasons"],
        "scores_executed": True,
    }


def execute_smoke10_baseline(
    repository_root: Path,
    *,
    frozen_config: dict[str, Any],
    historical_run_record: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Run Smoke10 once: SUT answers on blind inputs, then evaluator scores."""
    catalog = load_suite_catalog(repository_root)
    frozen_fp = frozen_config["frozen_config_fingerprint"]
    if frozen_config.get("suite_catalog_fingerprint") != suite_catalog_fingerprint(catalog):
        raise ValueError("FROZEN_CONFIG_SUITE_CATALOG_MISMATCH")
    if list(frozen_config.get("case_ids", ())) != list(smoke10_case_ids(catalog)):
        raise ValueError("FROZEN_CONFIG_CASE_LIST_MISMATCH")

    profile_id = str(frozen_config.get("sut_profile_id") or IBP_SYNTHETIC_SUT_PROFILE_ID)
    sut_runner = resolve_sut_runner(profile_id, repository_root=repository_root)

    run_id = f"ibp-smoke10-{frozen_fp[:16]}"
    case_results: list[dict[str, Any]] = []
    cases_by_id = {row["case_id"]: row for row in catalog["cases"]}

    for case_id in frozen_config["case_ids"]:
        case = cases_by_id[case_id]
        case_results.append(
            execute_smoke10_case(
                repository_root=repository_root,
                case=case,
                frozen_config_fingerprint=frozen_fp,
                sut_runner=sut_runner,
            )
        )

    governance = {
        "authority": "HISTORICAL_DEVELOPMENT",
        "item9_effect": "NONE",
        "item7_effect": "NONE",
        "ftep_effect": "NONE",
        "live_authority": "NONE",
    }
    upstream_manifest = None
    if historical_run_record is not None:
        upstream_manifest = historical_run_record.get("system_under_test_input")
        governance = dict(historical_run_record.get("governance") or governance)

    run_record: dict[str, Any] = {
        "artifact_kind": IBP_SMOKE10_RUN_KIND,
        "schema_version": IBP_SMOKE10_RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_version": IBP_PROTOCOL_SCHEMA_VERSION,
        "smoke10_contract_id": IBP_SMOKE10_CONTRACT_ID,
        "frozen_config_fingerprint": frozen_fp,
        "config": frozen_config,
        "code_sha": frozen_config.get("code_sha"),
        "case_ids": list(frozen_config["case_ids"]),
        "case_count": len(case_results),
        "case_results": case_results,
        "scores_executed": True,
        "full30_executed": False,
        "evaluator_invoked": True,
        "governance": governance,
        "upstream_historical_manifest": upstream_manifest,
        "config_change_detected": False,
        "contamination_audit": audit_smoke10_run_contamination(
            {
                "case_results": case_results,
                "frozen_config_fingerprint": frozen_fp,
                "config_change_detected": False,
                "upstream_historical_manifest": upstream_manifest,
                "governance": governance,
            },
            frozen_config_fingerprint=frozen_fp,
        ),
        "summaries": summarize_smoke10_run(case_results),
    }
    run_record["run_fingerprint"] = sha256_bytes(
        canonical_bytes(
            {
                "run_id": run_id,
                "frozen_config_fingerprint": frozen_fp,
                "case_ids": frozen_config["case_ids"],
                "dimension_outcomes": [
                    (row["case_id"], row["dimension_scores"]) for row in case_results
                ],
            }
        )
    )

    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)
        (artifact_root / "frozen_config.json").write_text(
            json.dumps(frozen_config, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (artifact_root / "smoke10_run_record.json").write_text(
            json.dumps(run_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (artifact_root / "contamination_audit.json").write_text(
            json.dumps(run_record["contamination_audit"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return run_record


def summarize_smoke10_run(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_dimension: dict[str, dict[str, int]] = {dim: {"PASS": 0, "FAIL": 0} for dim in CASE_DIMENSIONS}
    by_failure_type: dict[str, int] = {}
    by_mode: dict[str, dict[str, int]] = {}
    by_system: dict[str, dict[str, int]] = {}

    for row in case_results:
        mode = str(row.get("blind_mode") or "UNKNOWN")
        system = str(row.get("sut_profile_id") or "UNKNOWN")
        by_mode.setdefault(mode, {"cases": 0, "dimension_failures": 0})
        by_system.setdefault(system, {"cases": 0, "dimension_failures": 0})
        by_mode[mode]["cases"] += 1
        by_system[system]["cases"] += 1

        for dim, outcome in (row.get("dimension_scores") or {}).items():
            if dim in by_dimension and outcome in by_dimension[dim]:
                by_dimension[dim][outcome] += 1
            if outcome == "FAIL":
                by_mode[mode]["dimension_failures"] += 1
                by_system[system]["dimension_failures"] += 1
        for reason in row.get("failure_reasons") or []:
            by_failure_type[reason] = by_failure_type.get(reason, 0) + 1

    return {
        "by_dimension": by_dimension,
        "by_failure_type": by_failure_type,
        "by_mode": by_mode,
        "by_system": by_system,
    }


__all__ = [
    "CONTEXT_RESET_POLICY",
    "IBP_NONSTUB_SMOKE10_FREEZE_ARTIFACT_KIND",
    "IBP_SMOKE10_RUN_KIND",
    "IBP_SMOKE10_RUN_SCHEMA_VERSION",
    "execute_smoke10_baseline",
    "execute_smoke10_case",
    "freeze_smoke10_run_configuration",
    "summarize_smoke10_run",
]
