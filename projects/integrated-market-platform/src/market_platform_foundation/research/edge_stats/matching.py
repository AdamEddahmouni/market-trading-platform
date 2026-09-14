"""Condition matching and PIT validation for edge-stats rows."""

from __future__ import annotations

from typing import Any

from ..decision_research.examples import build_short_squeeze_examples
from ..decision_research.pit_gate import validate_temporal_example
from .models import EdgeStatsQueryV1


def _squeeze_state(example: dict[str, Any]) -> str | None:
    for feature in example.get("features") or []:
        if feature.get("evidence_family") == "SQUEEZE_STATE":
            value = feature.get("value") or {}
            state = value.get("state")
            return str(state) if state is not None else None
    return None


def _forward_return_bps(example: dict[str, Any]) -> float | None:
    outcome = example.get("outcome") or {}
    raw = outcome.get("forward_return_bps")
    if raw is None:
        return None
    return float(raw)


def build_candidate_examples(
    bars: list[dict[str, Any]],
    query: EdgeStatsQueryV1,
) -> list[dict[str, Any]]:
    horizon = query.outcome.horizon_bars
    examples = build_short_squeeze_examples(bars, horizon_bars=horizon)
    allowed = set(query.squeeze_states)
    matched: list[dict[str, Any]] = []
    for example in examples:
        if query.instrument_id and example.get("instrument_id") != query.instrument_id:
            continue
        state = _squeeze_state(example)
        if state not in allowed:
            continue
        decision_ns = int(example.get("decision_time_ns") or 0)
        if query.pit_max_decision_time_ns is not None and decision_ns > query.pit_max_decision_time_ns:
            continue
        ok, reasons = validate_temporal_example(example)
        if not ok:
            raise ValueError(f"PIT_VALIDATION_FAILED:{','.join(reasons)}")
        matched.append(example)
    matched.sort(key=lambda row: int(row["decision_time_ns"]))
    if query.sample_cap is not None and len(matched) > query.sample_cap:
        matched = matched[: query.sample_cap]
    return matched


def extract_outcome_values(
    examples: list[dict[str, Any]],
    metric: str,
) -> tuple[float, ...]:
    values: list[float] = []
    for example in examples:
        if metric == "mean_forward_return_bps":
            value = _forward_return_bps(example)
            if value is None:
                raise ValueError("MISSING_FORWARD_RETURN_BPS")
            values.append(value)
        elif metric == "positive_rate":
            outcome = example.get("outcome") or {}
            values.append(1.0 if outcome.get("positive") else 0.0)
        else:
            raise ValueError(f"UNSUPPORTED_OUTCOME_METRIC:{metric}")
    return tuple(values)
