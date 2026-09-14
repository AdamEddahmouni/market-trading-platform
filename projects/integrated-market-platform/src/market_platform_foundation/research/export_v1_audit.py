"""PIT audit, leakage firewall, and row-quality gates for Research Export v1."""

from __future__ import annotations

from typing import Any

_OUTCOME_FIELD_KEYS = frozenset(
    {
        "forward_return",
        "realized_return",
        "outcome_label",
        "label_value",
        "actual",
        "fill_price",
        "realized_pnl",
    }
)


def audit_duplicate_keys(
    rows: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> list[str]:
    seen: set[tuple[Any, ...]] = set()
    violations: list[str] = []
    for index, row in enumerate(rows):
        key = tuple(row.get(field) for field in key_fields)
        if key in seen:
            violations.append(f"DUPLICATE_KEY:{key_fields}:{index}")
        seen.add(key)
    return violations


def audit_impossible_times(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for index, row in enumerate(rows):
        source_time = row.get("source_time_ns")
        observed_at = row.get("observed_at_ns")
        if source_time is None or observed_at is None:
            continue
        if int(observed_at) < int(source_time):
            violations.append(f"IMPOSSIBLE_TIME:{index}")
    return violations


def audit_feature_decision_leakage(feature_rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for index, row in enumerate(feature_rows):
        decision_at = int(row.get("decision_at_ns") or 0)
        earliest = int(row.get("earliest_usable_at_ns") or row.get("available_time_ns") or 0)
        if decision_at <= 0:
            violations.append(f"MISSING_DECISION_AT:{index}")
        elif earliest > decision_at:
            violations.append(f"FEATURE_AFTER_DECISION:{index}")
        values = row.get("values") or row.get("feature_values") or {}
        if isinstance(values, dict):
            for key in values:
                if key in _OUTCOME_FIELD_KEYS:
                    violations.append(f"OUTCOME_IN_FEATURE:{key}:{index}")
        for key in row:
            if key in _OUTCOME_FIELD_KEYS and key not in {"earliest_usable_at_ns"}:
                violations.append(f"OUTCOME_FIELD_IN_FEATURE:{key}:{index}")
    return violations


def audit_outcome_separation(
    feature_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
) -> list[str]:
    violations = audit_feature_decision_leakage(feature_rows)
    for index, row in enumerate(outcome_rows):
        decision_at = int(row.get("decision_at_ns") or row.get("decision_time_ns") or 0)
        realized_at = int(row.get("label_available_time_ns") or row.get("realized_at_ns") or 0)
        if realized_at <= decision_at:
            violations.append(f"OUTCOME_NOT_AFTER_DECISION:{index}")
    return violations


def audit_effective_dates(instrument_rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for index, row in enumerate(instrument_rows):
        effective_from = row.get("effective_from_ns")
        effective_to = row.get("effective_to_ns")
        if effective_from is not None and effective_to is not None:
            if int(effective_from) >= int(effective_to):
                violations.append(f"INVALID_EFFECTIVE_INTERVAL:{index}")
    return violations


def run_leakage_firewall(
    feature_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    violations = audit_outcome_separation(feature_rows, outcome_rows)
    prohibited_hits = [code for code in violations if code.startswith("OUTCOME_")]
    return {
        "status": "PASS" if not violations else "FAIL",
        "violation_codes": sorted(set(violations)),
        "prohibited_outcome_in_features": sorted(set(prohibited_hits)),
    }


def run_pit_audit(
    *,
    market_observations: list[dict[str, Any]],
    feature_snapshots: list[dict[str, Any]],
    realized_outcomes: list[dict[str, Any]],
    instrument_rows: list[dict[str, Any]],
    information_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    violations: list[str] = []
    violations.extend(
        audit_duplicate_keys(
            market_observations,
            key_fields=("instrument_id", "source_time_ns", "observed_at_ns"),
        )
    )
    if information_events:
        violations.extend(
            audit_duplicate_keys(information_events, key_fields=("event_id", "release_time_ns"))
        )
    violations.extend(audit_impossible_times(market_observations))
    if information_events:
        violations.extend(audit_impossible_times(information_events))
    violations.extend(audit_effective_dates(instrument_rows))
    violations.extend(audit_outcome_separation(feature_snapshots, realized_outcomes))
    return {
        "status": "PASS" if not violations else "FAIL",
        "violation_codes": sorted(set(violations)),
    }


__all__ = [
    "audit_duplicate_keys",
    "audit_effective_dates",
    "audit_feature_decision_leakage",
    "audit_impossible_times",
    "audit_outcome_separation",
    "run_leakage_firewall",
    "run_pit_audit",
]
