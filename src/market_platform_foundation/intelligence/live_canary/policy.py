"""Live canary policy — absolute micro-notional caps (BUILD 29)."""

from __future__ import annotations

from ..live_execution_safety.types import CERTIFIED_ASSET_CLASSES, CERTIFIED_ORDER_TYPES, KillSwitchState
from .identity import derive_canary_policy_id
from .types import (
    LIVE_CANARY_IMPLEMENTATION_VERSION,
    LIVE_CANARY_SCHEMA_VERSION,
    DEFAULT_AUTHORIZATION_DURATION_NS,
    DEFAULT_MAX_FILL_COUNT,
    DEFAULT_MAX_ORDER_COUNT,
    DEFAULT_MAX_SINGLE_ORDER_NOTIONAL_MINOR,
    DEFAULT_MAX_TOTAL_CANARY_NOTIONAL_MINOR,
    LiveCanaryPolicyV1,
)

BUILD29_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "First canary uses absolute micro-notional caps, not NAV-scaled limits.",
    "Only US cash equities LONG-only in default first-canary policy.",
    "No margin, shorting, derivatives, or outside-RTH in default policy.",
    "Real broker submission requires explicit human authorization per session.",
    "Per-order human confirmation required for first canary.",
    "Successful canary does not enable autonomous live trading.",
    "Global live kill switch remains ACTIVE_BLOCK; canary is narrowly scoped permit.",
    "No certified live broker available by default — real canary may not execute.",
)


def build_default_canary_policy(
    *,
    broker: str,
    account_ref: str,
    allowed_instruments: tuple[str, ...] = ("inst-aapl",),
    required_broker_certification_ref: str = "BUILD28_ZERO_SUBMIT",
    required_execution_policy_ref: str = "BUILD22_DEFAULT",
    required_runtime_activation_ref: str = "BUILD23_RUNTIME",
) -> LiveCanaryPolicyV1:
    """Conservative first-canary policy with absolute micro-notional caps."""
    policy = LiveCanaryPolicyV1(
        canary_policy_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        broker=broker,
        account_ref=account_ref,
        account_environment="LIVE",
        allowed_asset_classes=CERTIFIED_ASSET_CLASSES,
        allowed_instruments=allowed_instruments,
        allowed_sides=("BUY",),
        allowed_order_types=("MARKET", "LIMIT"),
        max_single_order_notional_minor=DEFAULT_MAX_SINGLE_ORDER_NOTIONAL_MINOR,
        max_total_canary_notional_minor=DEFAULT_MAX_TOTAL_CANARY_NOTIONAL_MINOR,
        max_net_live_exposure_minor=DEFAULT_MAX_TOTAL_CANARY_NOTIONAL_MINOR,
        max_gross_live_exposure_minor=DEFAULT_MAX_TOTAL_CANARY_NOTIONAL_MINOR,
        max_order_count=DEFAULT_MAX_ORDER_COUNT,
        max_fill_count=DEFAULT_MAX_FILL_COUNT,
        allow_fractional=False,
        allow_margin=False,
        allow_short=False,
        allow_outside_rth=False,
        authorization_duration_ns=DEFAULT_AUTHORIZATION_DURATION_NS,
        max_order_lifetime_ns=DEFAULT_AUTHORIZATION_DURATION_NS,
        require_flat_start=True,
        require_flat_end=False,
        require_manual_authorization=True,
        require_manual_order_confirmation=True,
        required_broker_certification_ref=required_broker_certification_ref,
        required_execution_policy_ref=required_execution_policy_ref,
        required_runtime_activation_ref=required_runtime_activation_ref,
        kill_switch_default=KillSwitchState.ACTIVE_BLOCK.value,
        implementation_version=LIVE_CANARY_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(policy, "canary_policy_id", derive_canary_policy_id(policy))
    return policy


def effective_canary_quantity_cap(
    *,
    policy: LiveCanaryPolicyV1,
    risk_approved_quantity: int,
    reference_price_minor: int,
    account_buying_power_minor: int | None = None,
    model_confidence: float | None = None,
) -> int:
    """Return most restrictive quantity — account/model can only reduce, never increase."""
    if risk_approved_quantity <= 0 or reference_price_minor <= 0:
        return 0
    policy_cap_qty = policy.max_single_order_notional_minor // reference_price_minor
    if policy_cap_qty <= 0:
        return 0
    cap = min(risk_approved_quantity, policy_cap_qty)
    if account_buying_power_minor is not None:
        account_cap_qty = account_buying_power_minor // reference_price_minor
        cap = min(cap, account_cap_qty)
    if model_confidence is not None and model_confidence > 0:
        # Model confidence must never increase live size.
        pass
    return max(0, cap)


def validate_policy_constraints(policy: LiveCanaryPolicyV1) -> tuple[str, ...]:
    violations: list[str] = []
    if policy.allow_margin:
        violations.append("MARGIN_NOT_ALLOWED_FIRST_CANARY")
    if policy.allow_short:
        violations.append("SHORT_NOT_ALLOWED_FIRST_CANARY")
    if "US_EQUITY" not in policy.allowed_asset_classes:
        violations.append("DERIVATIVE_OR_NON_EQUITY_SCOPE")
    if policy.max_order_count < 1:
        violations.append("INVALID_ORDER_COUNT")
    if policy.max_single_order_notional_minor > policy.max_total_canary_notional_minor:
        violations.append("SINGLE_EXCEEDS_TOTAL")
    return tuple(violations)
