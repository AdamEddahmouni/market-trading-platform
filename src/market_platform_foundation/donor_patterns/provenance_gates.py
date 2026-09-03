"""Provenance/freshness/missingness gates — reimplemented from short-squeeze screener patterns."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    FROZEN = "FROZEN"
    UNKNOWN = "UNKNOWN"


class MissingnessPolicy(str, Enum):
    UNKNOWN_NOT_ZERO = "UNKNOWN_NOT_ZERO"
    ABSENT = "ABSENT"


def evaluate_freshness(
    *,
    observed_at: str | None,
    max_age_seconds: int,
    now_epoch: int,
    frozen_mode: bool = False,
) -> FreshnessState:
    if frozen_mode:
        return FreshnessState.FROZEN
    if not observed_at:
        return FreshnessState.UNKNOWN
    # Caller supplies epoch for determinism in replay contexts.
    try:
        # ISO timestamps in donor payloads; simplified parse for Z suffix.
        normalized = observed_at.replace("Z", "+00:00")
        observed = datetime.fromisoformat(normalized)
        age = now_epoch - int(observed.timestamp())
        if age <= max_age_seconds:
            return FreshnessState.FRESH
        return FreshnessState.STALE
    except ValueError:
        return FreshnessState.UNKNOWN


def apply_missingness(value: Any, *, policy: MissingnessPolicy = MissingnessPolicy.UNKNOWN_NOT_ZERO) -> Any:
    if value is None or value == "":
        return "UNKNOWN" if policy == MissingnessPolicy.UNKNOWN_NOT_ZERO else None
    return value


def provenance_gate(
    row: dict[str, Any],
    *,
    required_fields: tuple[str, ...],
    frozen_mode: bool = False,
) -> tuple[bool, list[str]]:
    """Return (admissible, reason_codes). Missing required evidence fails closed."""
    reasons: list[str] = []
    for field in required_fields:
        raw = row.get(field)
        if raw is None or raw == "" or raw == "UNKNOWN":
            reasons.append(f"MISSING_{field.upper()}")
    if frozen_mode and row.get("data_mode") == "FROZEN_RESEARCH":
        reasons.append("FROZEN_AGGREGATE_ONLY")
    admissible = len([r for r in reasons if r.startswith("MISSING_")]) == 0
    return admissible, reasons


def readiness_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "INCOMPLETE": 0}
    for row in rows:
        outcome = row.get("outcome", {})
        status = outcome.get("status", "UNKNOWN") if isinstance(outcome, dict) else "UNKNOWN"
        key = str(status).upper()
        if key in totals:
            totals[key] += 1
        else:
            totals["UNKNOWN"] += 1
    return totals
