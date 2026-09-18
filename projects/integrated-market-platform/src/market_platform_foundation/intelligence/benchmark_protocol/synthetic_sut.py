"""Deterministic IBP system-under-test stub (blind inputs only; no evaluator gold)."""

from __future__ import annotations

from typing import Any

from .contamination import EVALUATOR_ONLY_MANIFEST_KEYS, assert_no_evaluator_gold_in_system_bundle

IBP_SYNTHETIC_SUT_PROFILE_ID = "synthetic_intelligence_fixture_v1_baseline_v1"
IBP_SYNTHETIC_SUT_MODEL_ID = "ibp-deterministic-stub-v1"


def build_blind_case_input(case: dict[str, Any], *, context_reset_token: str) -> dict[str, Any]:
    """Case payload visible to the SUT — never includes evaluator gold paths or answers."""
    blind = {
        "case_id": case["case_id"],
        "blind_mode": case.get("blind_mode"),
        "input_profile": case.get("input_profile"),
        "context_reset_token": context_reset_token,
    }
    fixture = case.get("historical_harness_fixture")
    if fixture is not None:
        blind["historical_harness_fixture"] = fixture
    assert_no_evaluator_gold_in_system_bundle(blind)
    for key in EVALUATOR_ONLY_MANIFEST_KEYS:
        if key in blind:
            raise ValueError(f"BLIND_INPUT_GOLD_LEAK:{key}")
    return blind


def run_synthetic_intelligence_sut(blind_input: dict[str, Any]) -> dict[str, Any]:
    """Produce a bounded baseline answer without access to evaluator gold."""
    assert_no_evaluator_gold_in_system_bundle(blind_input)
    blind_mode = blind_input.get("blind_mode")
    return {
        "case_id": blind_input["case_id"],
        "sut_profile_id": IBP_SYNTHETIC_SUT_PROFILE_ID,
        "sut_model_id": IBP_SYNTHETIC_SUT_MODEL_ID,
        "blind_mode": blind_mode,
        "routing": blind_mode,
        "answer": "UNKNOWN",
        "freshness": "FIXTURE",
        "authority": "HISTORICAL_DEVELOPMENT",
        "provenance_complete": True,
        "final_state": "CLOSED",
        "operator_close": "SKIPPED_SYNTHETIC",
        "catastrophic": False,
        "context_reset_token": blind_input.get("context_reset_token"),
    }


__all__ = [
    "IBP_SYNTHETIC_SUT_MODEL_ID",
    "IBP_SYNTHETIC_SUT_PROFILE_ID",
    "build_blind_case_input",
    "run_synthetic_intelligence_sut",
]
