"""Project admitted factual gold cases to SUT-safe bundles (no evaluator fields)."""

from __future__ import annotations

from typing import Any

from ..contamination import BenchmarkContaminationError
from .constants import FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS


def strip_factual_gold_evaluator_fields(case: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a factual case without evaluator-only storage fields."""
    return {key: value for key, value in case.items() if key not in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS}


def assert_factual_case_safe_for_sut(bundle: dict[str, Any]) -> None:
    if "evaluator_gold_ref" in bundle:
        raise BenchmarkContaminationError("FACTUAL_EVALUATOR_GOLD_LEAK:evaluator_gold_ref")
    for key in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS:
        if key in bundle:
            raise BenchmarkContaminationError(f"FACTUAL_EVALUATOR_GOLD_LEAK:{key}")


def project_factual_case_for_sut(case: dict[str, Any]) -> dict[str, Any]:
    projected = strip_factual_gold_evaluator_fields(case)
    assert_factual_case_safe_for_sut(projected)
    return projected


__all__ = [
    "assert_factual_case_safe_for_sut",
    "project_factual_case_for_sut",
    "strip_factual_gold_evaluator_fields",
]
