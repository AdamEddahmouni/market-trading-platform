"""Evaluator-only scoring for IBP Smoke10 (gold loaded here, never in the SUT path)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CASE_DIMENSIONS = (
    "freshness",
    "facts",
    "provenance",
    "unknown_handling",
    "routing",
    "final_state",
    "operator_close",
    "catastrophic",
)


def load_evaluator_gold(repository_root: Path, evaluator_gold_ref: str) -> dict[str, Any]:
    path = repository_root / "tests/fixtures/intelligence_benchmark" / evaluator_gold_ref
    if not path.is_file():
        raise FileNotFoundError(f"IBP_EVALUATOR_GOLD_MISSING:{evaluator_gold_ref}")
    return json.loads(path.read_text(encoding="utf-8"))


def score_case_dimensions(
    *,
    sut_response: dict[str, Any],
    gold: dict[str, Any],
    blind_mode: str | None,
) -> dict[str, Any]:
    failure_reasons: list[str] = []
    dimensions: dict[str, str] = {}

    freshness = sut_response.get("freshness")
    if freshness in {"FIXTURE", "HISTORICAL_DEVELOPMENT"}:
        dimensions["freshness"] = "PASS"
    else:
        dimensions["freshness"] = "FAIL"
        failure_reasons.append("FRESHNESS_NOT_FIXTURE_BACKED")

    gold_answer = gold.get("gold_answer")
    if sut_response.get("answer") == gold_answer:
        dimensions["facts"] = "PASS"
    else:
        dimensions["facts"] = "FAIL"
        failure_reasons.append("FACTS_MISMATCH")

    if sut_response.get("provenance_complete") and sut_response.get("authority") == "HISTORICAL_DEVELOPMENT":
        dimensions["provenance"] = "PASS"
    else:
        dimensions["provenance"] = "FAIL"
        failure_reasons.append("PROVENANCE_INCOMPLETE")

    if sut_response.get("answer") == "UNKNOWN":
        dimensions["unknown_handling"] = "PASS"
    else:
        dimensions["unknown_handling"] = "FAIL"
        failure_reasons.append("UNKNOWN_NOT_USED")

    if sut_response.get("routing") == blind_mode:
        dimensions["routing"] = "PASS"
    else:
        dimensions["routing"] = "FAIL"
        failure_reasons.append("ROUTING_MODE_MISMATCH")

    if sut_response.get("final_state") == "CLOSED":
        dimensions["final_state"] = "PASS"
    else:
        dimensions["final_state"] = "FAIL"
        failure_reasons.append("FINAL_STATE_NOT_CLOSED")

    operator_close = sut_response.get("operator_close")
    if operator_close in {"SKIPPED_SYNTHETIC", "OK"}:
        dimensions["operator_close"] = "PASS"
    else:
        dimensions["operator_close"] = "FAIL"
        failure_reasons.append("OPERATOR_CLOSE_UNEXPECTED")

    if sut_response.get("catastrophic"):
        dimensions["catastrophic"] = "FAIL"
        failure_reasons.append("CATASTROPHIC_FLAG")
    else:
        dimensions["catastrophic"] = "PASS"

    return {
        "dimensions": dimensions,
        "failure_reasons": failure_reasons,
        "evaluator_gold_loaded_for_sut": False,
        "scores_executed": True,
    }


__all__ = ["CASE_DIMENSIONS", "load_evaluator_gold", "score_case_dimensions"]
