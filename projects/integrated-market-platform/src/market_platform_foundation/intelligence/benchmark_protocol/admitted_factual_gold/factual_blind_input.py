"""Blind factual case payloads for IBP_FACTUAL_SMOKE_V1 (no evaluator gold)."""

from __future__ import annotations

from typing import Any

from ..contamination import EVALUATOR_ONLY_MANIFEST_KEYS, assert_no_evaluator_gold_in_system_bundle
from .sut_projection import project_factual_case_for_sut
from .types import IBP_FACTUAL_SMOKE_PROTOCOL_VERSION


def build_factual_blind_case_input(case: dict[str, Any], *, context_reset_token: str) -> dict[str, Any]:
    """Project a frozen factual case to the SUT-visible blind envelope."""
    sut_case = project_factual_case_for_sut(case)
    evidence_set = sut_case["EVIDENCE_SET"]
    blind: dict[str, Any] = {
        "case_id": sut_case["CASE_ID"],
        "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "mode": sut_case.get("MODE"),
        "question": sut_case.get("QUESTION"),
        "evidence_set": evidence_set,
        "evidence_fingerprint": sut_case.get("EVIDENCE_FINGERPRINT"),
        "temporal_cutoff": sut_case.get("TEMPORAL_CUTOFF"),
        "answer_normalization": sut_case.get("ANSWER_NORMALIZATION"),
        "unknown_policy": sut_case.get("UNKNOWN_POLICY"),
        "provenance_requirements": sut_case.get("PROVENANCE_REQUIREMENTS"),
        "routing_expectation": sut_case.get("ROUTING_EXPECTATION"),
        "scoring_gate": sut_case.get("SCORING_GATE"),
        "evidence_access_mode": sut_case.get("EVIDENCE_ACCESS_MODE"),
        "context_reset_token": context_reset_token,
        "admitted_evidence_artifact_refs": [
            str(row["artifact_ref"])
            for row in evidence_set.get("sources", [])
            if isinstance(row, dict) and row.get("artifact_ref")
        ],
    }
    assert_no_evaluator_gold_in_system_bundle(blind)
    for key in EVALUATOR_ONLY_MANIFEST_KEYS:
        if key in blind:
            raise ValueError(f"FACTUAL_BLIND_INPUT_GOLD_LEAK:{key}")
    return blind


__all__ = ["build_factual_blind_case_input"]
