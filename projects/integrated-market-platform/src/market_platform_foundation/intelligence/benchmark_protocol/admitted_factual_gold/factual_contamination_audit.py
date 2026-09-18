"""Post-run IBP_FACTUAL_SMOKE_V1 contamination checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .admitted_evidence_context import admitted_artifacts_accessible


def audit_factual_smoke_run_contamination(
    run_record: dict[str, Any],
    *,
    repository_root: Path,
    frozen_config_fingerprint: str,
) -> dict[str, Any]:
    checks: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}

    case_results = run_record.get("case_results") or []
    if not case_results:
        checks["DID_SYSTEM_SEE_GOLD"] = "FAIL"
        reasons["DID_SYSTEM_SEE_GOLD"] = ["NO_CASE_RESULTS"]
    elif any(row.get("evaluator_gold_loaded_for_sut") for row in case_results):
        checks["DID_SYSTEM_SEE_GOLD"] = "FAIL"
        reasons["DID_SYSTEM_SEE_GOLD"] = ["GOLD_LOADED_FOR_SUT"]
    elif any(row.get("sut_response_includes_gold") for row in case_results):
        checks["DID_SYSTEM_SEE_GOLD"] = "FAIL"
        reasons["DID_SYSTEM_SEE_GOLD"] = ["SUT_RESPONSE_INCLUDES_GOLD"]
    else:
        checks["DID_SYSTEM_SEE_GOLD"] = "PASS"

    tokens = [row.get("context_reset_token") for row in case_results]
    if len(tokens) != len(set(tokens)):
        checks["DID_CASE_CONTEXT_LEAK"] = "FAIL"
        reasons["DID_CASE_CONTEXT_LEAK"] = ["DUPLICATE_CONTEXT_RESET_TOKEN"]
    elif any(row.get("prior_case_ids_visible_to_sut") for row in case_results):
        checks["DID_CASE_CONTEXT_LEAK"] = "FAIL"
        reasons["DID_CASE_CONTEXT_LEAK"] = ["PRIOR_CASE_IDS_VISIBLE"]
    else:
        checks["DID_CASE_CONTEXT_LEAK"] = "PASS"

    config_fp = run_record.get("frozen_config_fingerprint")
    if config_fp != frozen_config_fingerprint:
        checks["DID_CONFIG_CHANGE_MID_RUN"] = "FAIL"
        reasons["DID_CONFIG_CHANGE_MID_RUN"] = ["FROZEN_CONFIG_FINGERPRINT_MISMATCH"]
    elif run_record.get("config_change_detected"):
        checks["DID_CONFIG_CHANGE_MID_RUN"] = "FAIL"
        reasons["DID_CONFIG_CHANGE_MID_RUN"] = ["CONFIG_CHANGE_FLAG"]
    else:
        checks["DID_CONFIG_CHANGE_MID_RUN"] = "PASS"

    access_failures: list[str] = []
    replay_violations: list[str] = []
    for row in case_results:
        sut = row.get("sut_response") or {}
        if sut.get("evidence_data_mode") == "LIVE":
            replay_violations.append(str(row.get("case_id")))
        evidence_set = row.get("evidence_set") or {}
        if evidence_set:
            ok, missing = admitted_artifacts_accessible(repository_root, evidence_set)
            if not ok:
                access_failures.extend(missing)
            loaded = set(sut.get("admitted_evidence_artifacts_loaded") or ())
            for ref in evidence_set.get("sources") or []:
                artifact_ref = str(ref.get("artifact_ref") or "")
                if artifact_ref and artifact_ref not in loaded:
                    access_failures.append(artifact_ref)

    if access_failures:
        checks["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = "FAIL"
        reasons["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = sorted(set(access_failures))
    else:
        checks["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = "PASS"

    if replay_violations:
        checks["FIXTURE_REPLAY_NOT_PROMOTED_TO_LIVE"] = "FAIL"
        reasons["FIXTURE_REPLAY_NOT_PROMOTED_TO_LIVE"] = replay_violations
    else:
        checks["FIXTURE_REPLAY_NOT_PROMOTED_TO_LIVE"] = "PASS"

    overall = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
    return {"overall": overall, "checks": checks, "reasons": reasons}


__all__ = ["audit_factual_smoke_run_contamination"]
