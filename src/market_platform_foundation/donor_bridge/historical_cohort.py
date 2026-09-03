"""Sanitized Phase 3F historical calibration cohort projection for IMP."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent / "data" / "historical_squeeze_cohort_v1.json"


@lru_cache(maxsize=1)
def load_historical_cohort() -> dict[str, Any]:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _entries_for_symbol(cohort: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    symbol_upper = symbol.strip().upper()
    entries = cohort.get("entries", [])
    if not isinstance(entries, list):
        return []
    matched = [
        entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("symbol", "")).upper() == symbol_upper
    ]
    return sorted(matched, key=lambda item: str(item.get("case_id", "")))


def build_historical_squeeze_context(symbol: str) -> dict[str, Any]:
    """Project per-symbol historical cohort context (always available, donor-independent)."""
    cohort = load_historical_cohort()
    symbol_upper = symbol.strip().upper()
    base: dict[str, Any] = {
        "cohort_id": cohort.get("cohort_id"),
        "case_boundary_count": cohort.get("case_boundary_count"),
        "unique_symbol_count": cohort.get("unique_symbol_count"),
        "independent_symbol_count": cohort.get("independent_symbol_count"),
        "policy_review_status": cohort.get("policy_review_status"),
        "policy_review_date": cohort.get("policy_review_date"),
        "detection_policy": cohort.get("detection_policy"),
        "outcome_policy": cohort.get("outcome_policy"),
        "policy_review_doc": cohort.get("policy_review_doc"),
        "disclaimer": cohort.get("disclaimer"),
        "epistemic_class": "RESEARCH_PROJECTION",
        "source": "phase_3f_historical_calibration_fixture",
    }

    matched = _entries_for_symbol(cohort, symbol_upper)
    if not matched:
        return {
            **base,
            "available": False,
            "membership": "NOT_IN_COHORT",
            "symbol": symbol_upper,
            "reason": (
                f"{symbol_upper} is not in the Phase 3F historical calibration cohort "
                f"(n={cohort.get('case_boundary_count', 30)} case boundaries)."
            ),
            "case_boundaries": [],
        }

    return {
        **base,
        "available": True,
        "membership": "IN_COHORT",
        "symbol": symbol_upper,
        "case_boundaries": matched,
        "primary_case": matched[0],
        "in_frozen_demo": any(entry.get("in_frozen_demo") for entry in matched),
    }


def build_historical_cohort_summary_panel() -> dict[str, Any]:
    """Cohort-level summary for research analytics."""
    cohort = load_historical_cohort()
    summary = cohort.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    outcome_counts = summary.get("outcome_label_counts", {})
    classification_counts = summary.get("research_classification_counts", {})
    detection_counts = summary.get("research_detection_status_counts", {})

    series: list[dict[str, object]] = []
    if isinstance(outcome_counts, dict):
        series.extend(
            {"label": f"outcome:{label}", "count": int(count)}
            for label, count in sorted(outcome_counts.items())
        )
    if isinstance(classification_counts, dict):
        series.extend(
            {"label": f"classification:{label}", "count": int(count)}
            for label, count in sorted(classification_counts.items())
        )

    return {
        "available": True,
        "provenance": {
            "source": str(cohort.get("cohort_id", "phase_3f_historical_calibration_v1")),
            "method": "historical_squeeze_cohort_v1 fixture projection",
            "case_boundary_count": cohort.get("case_boundary_count"),
            "policy_review_status": cohort.get("policy_review_status"),
            "policy_review_date": cohort.get("policy_review_date"),
        },
        "series": series,
        "cohort_metadata": {
            "case_boundary_count": cohort.get("case_boundary_count"),
            "unique_symbol_count": cohort.get("unique_symbol_count"),
            "independent_symbol_count": cohort.get("independent_symbol_count"),
            "frozen_demo_overlap_count": summary.get("frozen_demo_overlap_count"),
            "research_detection_status_counts": detection_counts,
        },
        "disclaimer": cohort.get("disclaimer"),
    }


__all__ = [
    "build_historical_cohort_summary_panel",
    "build_historical_squeeze_context",
    "load_historical_cohort",
]
