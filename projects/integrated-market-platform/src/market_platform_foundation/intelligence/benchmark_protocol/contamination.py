"""IBP contamination controls — evaluator gold must not reach systems under test."""

from __future__ import annotations

from typing import Any

from ..historical_research_harness.types import HISTORICAL_RESEARCH_RUN_MANIFEST_KIND
from .types import ITEM9_CALIBRATION_RESULT_KIND, SIMULATOR_RESEARCH_RESULT_KIND

EVALUATOR_ONLY_OUTPUT_KEYS = frozenset(
    {
        "labels_path",
        "evaluator_gold_path",
        "gold_answer",
        "expected_label",
        "expected_labels",
        "evaluator_rubric",
        "rubric_answer_key",
    }
)

EVALUATOR_ONLY_MANIFEST_KEYS = frozenset(
    {
        "gold_answer",
        "expected_label",
        "evaluator_only_gold",
        "answer_key",
    }
)

SYSTEM_UNDER_TEST_STRIPPED_PATH_KEYS = frozenset({"labels_path"})


class BenchmarkContaminationError(ValueError):
    """Raised when gold or wrong evidence class would leak to the SUT."""


def strip_evaluator_only_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for systems under evaluation (no evaluator-only keys)."""
    cleaned = {key: value for key, value in payload.items() if key not in EVALUATOR_ONLY_MANIFEST_KEYS}
    outputs = cleaned.get("outputs")
    if isinstance(outputs, dict):
        cleaned["outputs"] = {
            key: value
            for key, value in outputs.items()
            if key not in SYSTEM_UNDER_TEST_STRIPPED_PATH_KEYS
        }
    return cleaned


def assert_historical_manifest_admissible(manifest: dict[str, Any]) -> None:
    if manifest.get("artifact_kind") != HISTORICAL_RESEARCH_RUN_MANIFEST_KIND:
        raise BenchmarkContaminationError("HISTORICAL_MANIFEST_KIND_MISMATCH")
    authority = manifest.get("corpus_evidence_authority") or manifest.get("evidence_class")
    if authority != "HISTORICAL_DEVELOPMENT":
        raise BenchmarkContaminationError("HISTORICAL_AUTHORITY_REQUIRED")
    simulator = manifest.get("simulator") or {}
    result_kind = simulator.get("result_kind")
    if result_kind == ITEM9_CALIBRATION_RESULT_KIND:
        raise BenchmarkContaminationError("ITEM9_CALIBRATION_RESULT_FORBIDDEN")
    if result_kind is not None and result_kind != SIMULATOR_RESEARCH_RESULT_KIND:
        raise BenchmarkContaminationError("UNEXPECTED_SIMULATOR_RESULT_KIND")


def assert_no_evaluator_gold_in_system_bundle(bundle: dict[str, Any]) -> None:
    for key in EVALUATOR_ONLY_MANIFEST_KEYS:
        if key in bundle:
            raise BenchmarkContaminationError(f"EVALUATOR_GOLD_LEAK:{key}")
    outputs = bundle.get("outputs")
    if isinstance(outputs, dict):
        for key in EVALUATOR_ONLY_OUTPUT_KEYS:
            if key in outputs:
                raise BenchmarkContaminationError(f"EVALUATOR_GOLD_LEAK:outputs.{key}")


__all__ = [
    "BenchmarkContaminationError",
    "EVALUATOR_ONLY_MANIFEST_KEYS",
    "EVALUATOR_ONLY_OUTPUT_KEYS",
    "assert_historical_manifest_admissible",
    "assert_no_evaluator_gold_in_system_bundle",
    "strip_evaluator_only_fields",
]
