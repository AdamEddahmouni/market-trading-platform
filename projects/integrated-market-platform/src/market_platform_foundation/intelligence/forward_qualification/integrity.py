"""Run-freeze integrity checks (BUILD 26)."""

from __future__ import annotations

from .types import IntegrityFailureCode


def detect_run_freeze_violation(
    *,
    initial_champion_ref: str,
    current_champion_ref: str,
    initial_policy_ref: str,
    current_policy_ref: str,
    initial_feature_schema_ref: str,
    current_feature_schema_ref: str,
) -> str | None:
    if initial_champion_ref != current_champion_ref:
        return IntegrityFailureCode.CHAMPION_CHANGED_MID_RUN.value
    if initial_policy_ref != current_policy_ref:
        return IntegrityFailureCode.POLICY_CHANGED_MID_RUN.value
    if initial_feature_schema_ref != current_feature_schema_ref:
        return IntegrityFailureCode.FEATURE_SCHEMA_CHANGED_MID_RUN.value
    return None
