"""Evaluator-only scoring for IBP_FACTUAL_SMOKE_V1 (structured facts + UNKNOWN semantics)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..smoke10_evaluator import CASE_DIMENSIONS
from .fact_normalization import collect_asserted_facts, values_equivalent
from .types import FactualFactVerdict, FactualUnknownVerdict

FACTUAL_CASE_DIMENSIONS = CASE_DIMENSIONS


def load_factual_evaluator_gold(repository_root: Path, evaluator_gold_ref: str) -> dict[str, Any]:
    path = repository_root / "tests/fixtures/intelligence_benchmark" / evaluator_gold_ref
    if not path.is_file():
        raise FileNotFoundError(f"IBP_FACTUAL_EVALUATOR_GOLD_MISSING:{evaluator_gold_ref}")
    return json.loads(path.read_text(encoding="utf-8"))


def _score_unknown_handling(
    *,
    sut_response: dict[str, Any],
    gold: dict[str, Any],
) -> tuple[str, list[str], str | None]:
    policy = gold.get("UNKNOWN_POLICY") or {}
    verdict = str(policy.get("correct_unknown_verdict") or "")
    answer = str(sut_response.get("answer") or "")
    is_unknown = answer.upper() == "UNKNOWN" or bool(sut_response.get("inference_abstention_reason"))
    if verdict == FactualUnknownVerdict.CORRECT_UNKNOWN.value:
        if is_unknown:
            return ("PASS", [], FactualFactVerdict.CORRECT_UNKNOWN.value)
        return ("FAIL", ["UNNECESSARY_ASSERTION"], FactualFactVerdict.UNNECESSARY_UNKNOWN.value)
    if is_unknown:
        return ("FAIL", ["UNNECESSARY_UNKNOWN"], FactualFactVerdict.UNNECESSARY_UNKNOWN.value)
    return ("PASS", [], None)


def score_factual_case_dimensions(
    *,
    sut_response: dict[str, Any],
    gold: dict[str, Any],
) -> dict[str, Any]:
    failure_reasons: list[str] = []
    dimensions: dict[str, str] = {}
    fact_verdicts: list[dict[str, Any]] = []

    normalization = gold.get("ANSWER_NORMALIZATION") or {}
    expected_rows = gold.get("EXPECTED_FACTS") or []
    asserted_facts = collect_asserted_facts(sut_response)
    asserted_by_field = {str(row["field"]): row.get("value") for row in asserted_facts}

    unknown_dim, unknown_reasons, unknown_fact_verdict = _score_unknown_handling(
        sut_response=sut_response,
        gold=gold,
    )
    dimensions["unknown_handling"] = unknown_dim
    failure_reasons.extend(unknown_reasons)
    if unknown_fact_verdict:
        fact_verdicts.append({"field": "_unknown", "verdict": unknown_fact_verdict})

    for row in expected_rows:
        expected_fact = (row.get("expected_fact") or {}) if isinstance(row, dict) else {}
        field = str(expected_fact.get("field") or "")
        expected_value = expected_fact.get("value")
        if not field:
            continue
        if unknown_fact_verdict == FactualFactVerdict.CORRECT_UNKNOWN.value:
            fact_verdicts.append({"field": field, "verdict": FactualFactVerdict.CORRECT_UNKNOWN.value})
            continue
        if field not in asserted_by_field:
            if unknown_dim == "PASS" and not asserted_facts and expected_value is not None:
                fact_verdicts.append({"field": field, "verdict": FactualFactVerdict.FACT_MISMATCH.value})
                failure_reasons.append(f"FACT_MISSING:{field}")
            continue
        asserted_value = asserted_by_field[field]
        if values_equivalent(asserted_value, expected_value, normalization=normalization):
            fact_verdicts.append({"field": field, "verdict": FactualFactVerdict.SUPPORTED_FACT.value})
        else:
            fact_verdicts.append({"field": field, "verdict": FactualFactVerdict.FACT_MISMATCH.value})
            failure_reasons.append(f"FACT_MISMATCH:{field}")

    extra_fields = set(asserted_by_field) - {str((row.get("expected_fact") or {}).get("field") or "") for row in expected_rows}
    for field in sorted(extra_fields):
        fact_verdicts.append({"field": field, "verdict": FactualFactVerdict.UNSUPPORTED_ASSERTION.value})
        failure_reasons.append(f"UNSUPPORTED_ASSERTION:{field}")

    freshness = sut_response.get("freshness")
    if freshness in {"FIXTURE", "HISTORICAL_DEVELOPMENT", "ADMITTED_EVIDENCE_FIXED"}:
        dimensions["freshness"] = "PASS"
    else:
        dimensions["freshness"] = "FAIL"
        failure_reasons.append("FRESHNESS_NOT_ADMITTED_BACKED")

    if sut_response.get("provenance_complete") and sut_response.get("authority") in {
        "HISTORICAL_DEVELOPMENT",
        "ADMITTED_EVIDENCE_FIXED",
    }:
        dimensions["provenance"] = "PASS"
    else:
        dimensions["provenance"] = "FAIL"
        failure_reasons.append("PROVENANCE_INCOMPLETE")
        fact_verdicts.append({"field": "_provenance", "verdict": FactualFactVerdict.PROVENANCE_MISSING.value})

    routing = gold.get("ROUTING_EXPECTATION") or {}
    expected_template = routing.get("template")
    if sut_response.get("routing_template") == expected_template or sut_response.get("routing") == expected_template:
        dimensions["routing"] = "PASS"
    else:
        dimensions["routing"] = "FAIL"
        failure_reasons.append("ROUTING_TEMPLATE_MISMATCH")

    fact_failures = [
        row
        for row in fact_verdicts
        if row["verdict"]
        in {
            FactualFactVerdict.FACT_MISMATCH.value,
            FactualFactVerdict.UNSUPPORTED_ASSERTION.value,
            FactualFactVerdict.UNNECESSARY_UNKNOWN.value,
        }
    ]
    if not fact_failures and dimensions["unknown_handling"] == "PASS":
        dimensions["facts"] = "PASS"
    else:
        dimensions["facts"] = "FAIL"
        if "FACTS_MISMATCH" not in failure_reasons:
            failure_reasons.append("FACTS_DIMENSION_FAIL")

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
        "fact_verdicts": fact_verdicts,
        "evaluator_gold_loaded_for_sut": False,
        "scores_executed": True,
    }


__all__ = [
    "FACTUAL_CASE_DIMENSIONS",
    "load_factual_evaluator_gold",
    "score_factual_case_dimensions",
]
