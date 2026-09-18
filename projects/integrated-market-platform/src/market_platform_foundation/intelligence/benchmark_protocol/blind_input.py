"""Blind case payloads visible to IBP SUT runners (no evaluator gold)."""

from __future__ import annotations

from typing import Any

from .contamination import EVALUATOR_ONLY_MANIFEST_KEYS, assert_no_evaluator_gold_in_system_bundle


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


__all__ = ["build_blind_case_input"]
