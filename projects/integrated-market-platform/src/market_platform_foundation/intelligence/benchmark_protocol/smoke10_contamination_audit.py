"""Post-run Smoke10 contamination checks (fail closed on insufficient provenance)."""

from __future__ import annotations

from typing import Any

from ..historical_research_harness.types import HISTORICAL_RESEARCH_RUN_MANIFEST_KIND
from .types import ITEM9_CALIBRATION_RESULT_KIND, SIMULATOR_RESEARCH_RESULT_KIND


def audit_smoke10_run_contamination(
    run_record: dict[str, Any],
    *,
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

    upstream = run_record.get("upstream_historical_manifest")
    if upstream is None:
        checks["DID_PROSPECTIVE_RECEIPTS_ENTER"] = "NOT_APPLICABLE"
        checks["DID_ITEM9_UPGRADE"] = "NOT_APPLICABLE"
    else:
        artifact_kind = upstream.get("artifact_kind")
        authority = upstream.get("corpus_evidence_authority") or upstream.get("evidence_class")
        if artifact_kind != HISTORICAL_RESEARCH_RUN_MANIFEST_KIND:
            checks["DID_PROSPECTIVE_RECEIPTS_ENTER"] = "FAIL"
            reasons["DID_PROSPECTIVE_RECEIPTS_ENTER"] = ["UPSTREAM_KIND_NOT_HISTORICAL"]
        elif authority != "HISTORICAL_DEVELOPMENT":
            checks["DID_PROSPECTIVE_RECEIPTS_ENTER"] = "FAIL"
            reasons["DID_PROSPECTIVE_RECEIPTS_ENTER"] = ["UPSTREAM_NOT_HISTORICAL_DEVELOPMENT"]
        else:
            checks["DID_PROSPECTIVE_RECEIPTS_ENTER"] = "PASS"
        simulator = upstream.get("simulator") or {}
        result_kind = simulator.get("result_kind")
        if result_kind == ITEM9_CALIBRATION_RESULT_KIND:
            checks["DID_ITEM9_UPGRADE"] = "FAIL"
            reasons["DID_ITEM9_UPGRADE"] = ["ITEM9_CALIBRATION_RESULT_KIND"]
        elif result_kind != SIMULATOR_RESEARCH_RESULT_KIND:
            checks["DID_ITEM9_UPGRADE"] = "FAIL"
            reasons["DID_ITEM9_UPGRADE"] = ["UNEXPECTED_SIMULATOR_RESULT_KIND"]
        else:
            governance = run_record.get("governance") or {}
            if governance.get("item9_effect") not in {None, "NONE"}:
                checks["DID_ITEM9_UPGRADE"] = "FAIL"
                reasons["DID_ITEM9_UPGRADE"] = ["ITEM9_EFFECT_NOT_NONE"]
            else:
                checks["DID_ITEM9_UPGRADE"] = "PASS"

    overall = "PASS" if all(v in {"PASS", "NOT_APPLICABLE"} for v in checks.values()) else "FAIL"
    return {
        "overall": overall,
        "checks": checks,
        "reasons": reasons,
    }


__all__ = ["audit_smoke10_run_contamination"]
