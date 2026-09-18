"""Answer normalization helpers for admitted factual gold scoring."""

from __future__ import annotations

import re
from typing import Any


def normalize_scalar(value: Any, *, normalization: dict[str, Any]) -> str:
    text = "" if value is None else str(value)
    if normalization.get("trim_whitespace"):
        text = text.strip()
    if normalization.get("case_folding"):
        text = text.casefold()
    if normalization.get("collapse_internal_whitespace"):
        text = re.sub(r"\s+", " ", text)
    if normalization.get("instrument_symbol_canonicalization") and "." in text:
        parts = text.split(".")
        if len(parts) == 2:
            text = f"{parts[0].casefold()}.{parts[1].casefold()}"
    return text


def values_equivalent(
    asserted: Any,
    expected: Any,
    *,
    normalization: dict[str, Any],
) -> bool:
    if isinstance(expected, (int, float)) and isinstance(asserted, (int, float, str)):
        try:
            asserted_num = float(asserted)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False
        tolerance = normalization.get("numeric_tolerance") or {}
        relative = float(tolerance.get("relative") or 0.0)
        if expected_num == 0:
            return abs(asserted_num - expected_num) <= relative
        return abs(asserted_num - expected_num) <= abs(expected_num * relative)
    return normalize_scalar(asserted, normalization=normalization) == normalize_scalar(
        expected, normalization=normalization
    )


def parse_structured_facts_from_answer(answer: str) -> list[dict[str, Any]]:
    """Best-effort parse of field=value tokens from a free-text SUT answer."""
    facts: list[dict[str, Any]] = []
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*([^,;\n]+)", answer):
        facts.append({"field": match.group(1), "value": match.group(2).strip()})
    return facts


def collect_asserted_facts(sut_response: dict[str, Any]) -> list[dict[str, Any]]:
    structured = sut_response.get("structured_facts")
    if isinstance(structured, list) and structured:
        return [row for row in structured if isinstance(row, dict) and row.get("field") is not None]
    answer = str(sut_response.get("answer") or "")
    if not answer or answer.upper() == "UNKNOWN":
        return []
    return parse_structured_facts_from_answer(answer)


__all__ = [
    "collect_asserted_facts",
    "normalize_scalar",
    "parse_structured_facts_from_answer",
    "values_equivalent",
]
