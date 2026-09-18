"""Deterministic IBP system-under-test stub (blind inputs only; no evaluator gold)."""

from __future__ import annotations

from typing import Any

from .blind_input import build_blind_case_input
from .contamination import assert_no_evaluator_gold_in_system_bundle
from .sut_profiles import IBP_SYNTHETIC_SUT_MODEL_ID, IBP_SYNTHETIC_SUT_PROFILE_ID


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
