"""Live canary program policy — operational envelope, not order authorization (BUILD 30)."""

from __future__ import annotations

from ..live_execution_safety.types import CERTIFIED_ASSET_CLASSES
from .identity import derive_program_policy_id
from .policy import BUILD29_KNOWN_LIMITATIONS
from .types import (
    LIVE_CANARY_PROGRAM_IMPLEMENTATION_VERSION,
    LIVE_CANARY_SCHEMA_VERSION,
    DEFAULT_MAX_PROGRAM_NOTIONAL_MINOR,
    DEFAULT_MAX_PROGRAM_ORDER_COUNT,
    DEFAULT_MAX_PROGRAM_REALIZED_LOSS_MINOR,
    DEFAULT_MAX_PROGRAM_SESSIONS,
    DEFAULT_PROGRAM_COOLDOWN_NS,
    DEFAULT_PROGRAM_DURATION_NS,
    DEFAULT_SESSION_MAX_DURATION_NS,
    DEFAULT_STATUS_FEED_STALE_THRESHOLD_NS,
    LiveCanaryProgramPolicyV1,
)

BUILD30_KNOWN_LIMITATIONS: tuple[str, ...] = BUILD29_KNOWN_LIMITATIONS + (
    "BUILD30 supervises repeated canary sessions — not autonomous live trading.",
    "Program policy is an operational envelope; each session still requires fresh authorization.",
    "Per-order human confirmation remains mandatory across all sessions.",
    "Program caps accumulate across sessions and cannot increase from success.",
    "Critical incidents require manual resume approval before new sessions.",
    "Stale order confirmations are invalidated on restart.",
    "Cooldown expiry does not auto-start the next session.",
)


def build_default_program_policy(
    *,
    allowed_brokers: tuple[str, ...] = ("tradier.paper",),
    allowed_accounts: tuple[str, ...] = ("fp-canary-test",),
    allowed_canary_policy_refs: tuple[str, ...] = (),
    program_effective_from_ns: int,
    program_effective_until_ns: int | None = None,
) -> LiveCanaryProgramPolicyV1:
    """Conservative supervised-canary program envelope."""
    effective_until = program_effective_until_ns or (
        program_effective_from_ns + DEFAULT_PROGRAM_DURATION_NS
    )
    policy = LiveCanaryProgramPolicyV1(
        program_policy_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        allowed_brokers=allowed_brokers,
        allowed_accounts=allowed_accounts,
        allowed_asset_classes=CERTIFIED_ASSET_CLASSES,
        allowed_canary_policy_refs=allowed_canary_policy_refs,
        max_sessions=DEFAULT_MAX_PROGRAM_SESSIONS,
        max_program_order_count=DEFAULT_MAX_PROGRAM_ORDER_COUNT,
        max_program_live_notional_minor=DEFAULT_MAX_PROGRAM_NOTIONAL_MINOR,
        max_program_realized_loss_minor=DEFAULT_MAX_PROGRAM_REALIZED_LOSS_MINOR,
        max_consecutive_incidents=2,
        require_fresh_authorization_per_session=True,
        require_order_confirmation=True,
        require_clean_reconciliation_before_session=True,
        require_clean_reconciliation_after_session=True,
        minimum_cooldown_between_sessions_ns=DEFAULT_PROGRAM_COOLDOWN_NS,
        incident_halt_rules=("CRITICAL",),
        program_effective_from_ns=program_effective_from_ns,
        program_effective_until_ns=effective_until,
        manual_resume_required=True,
        session_max_duration_ns=DEFAULT_SESSION_MAX_DURATION_NS,
        status_feed_stale_threshold_ns=DEFAULT_STATUS_FEED_STALE_THRESHOLD_NS,
        invalidate_confirmation_on_restart=True,
        implementation_version=LIVE_CANARY_PROGRAM_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(policy, "program_policy_id", derive_program_policy_id(policy))
    return policy


def validate_program_policy_constraints(policy: LiveCanaryProgramPolicyV1) -> tuple[str, ...]:
    violations: list[str] = []
    if policy.max_sessions < 1:
        violations.append("INVALID_MAX_SESSIONS")
    if policy.max_program_order_count < 1:
        violations.append("INVALID_PROGRAM_ORDER_COUNT")
    if not policy.require_fresh_authorization_per_session:
        violations.append("FRESH_AUTHORIZATION_REQUIRED")
    if not policy.require_order_confirmation:
        violations.append("ORDER_CONFIRMATION_REQUIRED")
    return tuple(violations)
