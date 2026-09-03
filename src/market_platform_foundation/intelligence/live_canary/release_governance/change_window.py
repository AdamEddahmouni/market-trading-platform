"""Change window policy (BUILD 35)."""

from __future__ import annotations

from .identity import derive_change_window_policy_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ChangeWindowPolicyV1,
    ChangeWindowResult,
)

# 24h observation after change (fixture qualification)
POST_CHANGE_OBSERVATION_NS = 5 * 60 * 1_000_000_000


def build_change_window_policy() -> ChangeWindowPolicyV1:
    policy = ChangeWindowPolicyV1(
        change_window_policy_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        environment_scope=("TEST", "QUALIFICATION", "SUPERVISED_PILOT", "SUPERVISED_LIVE"),
        allowed_windows=(
            {"kind": "ALWAYS", "environments": ("TEST", "QUALIFICATION")},
            {"kind": "MARKET_CLOSED", "environments": ("SUPERVISED_PILOT", "SUPERVISED_LIVE")},
        ),
        market_session_restrictions=("no_change_during_active_market_session_for_supervised_live",),
        emergency_change_rules=(
            "emergency_requires_change_record",
            "emergency_requires_rollback_target",
            "emergency_requires_post_change_qualification",
        ),
        required_pre_change_reconciliation=True,
        required_pre_change_backup=True,
        required_operator_state=("no_active_incident", "live_submissions_blocked"),
        required_post_change_observation_duration_ns=POST_CHANGE_OBSERVATION_NS,
        required_rollback_availability=True,
        active_order_behavior="BLOCK",
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    )
    return ChangeWindowPolicyV1(
        change_window_policy_id=derive_change_window_policy_id(policy),
        schema_version=policy.schema_version,
        environment_scope=policy.environment_scope,
        allowed_windows=policy.allowed_windows,
        market_session_restrictions=policy.market_session_restrictions,
        emergency_change_rules=policy.emergency_change_rules,
        required_pre_change_reconciliation=policy.required_pre_change_reconciliation,
        required_pre_change_backup=policy.required_pre_change_backup,
        required_operator_state=policy.required_operator_state,
        required_post_change_observation_duration_ns=policy.required_post_change_observation_duration_ns,
        required_rollback_availability=policy.required_rollback_availability,
        active_order_behavior=policy.active_order_behavior,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )


def evaluate_change_window(
    *,
    policy: ChangeWindowPolicyV1,
    environment_kind: str,
    inside_window: bool,
    active_ambiguous_orders: bool,
    reconciled: bool,
    backup_verified: bool,
    emergency: bool = False,
) -> tuple[str, list[str]]:
    violations: list[str] = []
    if environment_kind not in policy.environment_scope:
        violations.append(f"environment {environment_kind} not in policy scope")
        return ChangeWindowResult.BLOCKED.value, violations

    if active_ambiguous_orders and policy.active_order_behavior == "BLOCK":
        violations.append("active ambiguous orders block non-emergency change")
        if not emergency:
            return ChangeWindowResult.BLOCKED.value, violations

    if policy.required_pre_change_reconciliation and not reconciled:
        violations.append("reconciliation prerequisite not met")
        if not emergency:
            return ChangeWindowResult.BLOCKED.value, violations

    if policy.required_pre_change_backup and not backup_verified:
        violations.append("backup prerequisite not met")
        if not emergency:
            return ChangeWindowResult.BLOCKED.value, violations

    if not inside_window and not emergency:
        violations.append("outside allowed change window")
        return ChangeWindowResult.BLOCKED.value, violations

    if emergency:
        return ChangeWindowResult.EMERGENCY_ALLOWED.value, violations
    return ChangeWindowResult.ALLOWED.value, violations
