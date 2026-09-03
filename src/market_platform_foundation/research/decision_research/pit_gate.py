"""Hard PIT gate for decision research."""

from __future__ import annotations

from typing import Any


def validate_temporal_example(example: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    decision_ns = int(example.get("decision_time_ns") or 0)
    outcome_ns = example.get("outcome_time_ns")
    if decision_ns <= 0:
        reasons.append("MISSING_DECISION_TIME")
    features = example.get("features") or []
    for feature in features:
        available = int(feature.get("available_time_ns") or 0)
        if available > decision_ns:
            reasons.append(f"FEATURE_AFTER_DECISION:{feature.get('evidence_family')}")
    if outcome_ns is not None:
        if int(outcome_ns) <= decision_ns:
            reasons.append("OUTCOME_BEFORE_DECISION")
    return not reasons, reasons


def reject_historical_finviz_screen_without_capture(
    *,
    feature_source: str,
    capture_present: bool,
) -> tuple[bool, str | None]:
    if feature_source.upper().startswith("FINVIZ") and not capture_present:
        return False, "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION"
    return True, None


def chronological_split(
    examples: list[dict[str, Any]],
    *,
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(examples, key=lambda row: int(row.get("decision_time_ns") or 0))
    n = len(ordered)
    if n < 3:
        return {"train": ordered, "validation": [], "test": []}
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + validation_ratio))
    return {
        "train": ordered[:train_end],
        "validation": ordered[train_end:val_end],
        "test": ordered[val_end:],
    }
