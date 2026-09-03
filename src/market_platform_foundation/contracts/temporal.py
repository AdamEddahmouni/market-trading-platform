"""Temporal correctness checks for TC-001 through TC-003."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes


def check_tc001(
    consumed_inputs: list[dict[str, Any]],
    decision_time: int,
) -> tuple[str, list[str]]:
    violations = [
        input_row
        for input_row in consumed_inputs
        if int(input_row["available_time"]) > decision_time
    ]
    if violations:
        return "FAIL", ["TC001_AVAILABLE_TIME_AFTER_DECISION"]
    return "PASS", []


def check_tc002(events: list[dict[str, Any]], acquisition_mode: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for event in events:
        if acquisition_mode == "historical" and event.get("live_received_time") is not None:
            reasons.append("TC002_HISTORICAL_FABRICATED_LIVE_RECEIVED_TIME")
        if acquisition_mode == "live" and event.get("historical_ingested_time") is not None:
            reasons.append("TC002_LIVE_FABRICATED_HISTORICAL_INGESTED_TIME")
    if reasons:
        return "FAIL", sorted(set(reasons))
    return "PASS", []


def check_tc003(
    *,
    prior_decision_hash: str,
    post_correction_hash: str,
    correction_available_time: int,
    replay_clock_at_apply: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if replay_clock_at_apply < correction_available_time:
        reasons.append("TC003_CORRECTION_APPLIED_BEFORE_AVAILABLE_TIME")
    if prior_decision_hash != post_correction_hash and replay_clock_at_apply < correction_available_time:
        reasons.append("TC003_PRIOR_DECISION_MUTATED_EARLY")
    if reasons:
        return "FAIL", sorted(set(reasons))
    return "PASS", []


def decision_hash(decision: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(decision))
