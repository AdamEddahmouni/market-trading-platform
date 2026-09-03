"""Live execution authorization contract (BUILD 28 design-only)."""

from __future__ import annotations

from .identity import derive_authorization_id
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    CERTIFIED_ASSET_CLASSES,
    CERTIFIED_ORDER_TYPES,
    LiveAuthorizationState,
    LiveExecutionAuthorizationV1,
)


def production_authorization_absent() -> None:
    """BUILD 28 invariant: no production enabled authorization exists."""
    return None


def build_design_only_authorization(
    *,
    broker: str,
    account_ref: str,
    effective_from_ns: int,
    effective_until_ns: int,
    runtime_activation_ref: str = "DESIGN_ONLY",
    execution_policy_ref: str = "DESIGN_ONLY",
    risk_policy_ref: str = "DESIGN_ONLY",
) -> LiveExecutionAuthorizationV1:
    """Test fixture authorization — always DISABLED/NOT_AUTHORIZED in BUILD 28."""
    auth = LiveExecutionAuthorizationV1(
        authorization_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope="US_EQUITY_DRY_RUN_TEST",
        broker=broker,
        account_ref=account_ref,
        allowed_instruments=("inst-aapl", "inst-msft", "inst-spy"),
        allowed_asset_classes=CERTIFIED_ASSET_CLASSES,
        allowed_sides=("BUY", "SELL"),
        allowed_order_types=CERTIFIED_ORDER_TYPES,
        max_order_notional_minor=10_000_00,
        max_daily_notional_minor=50_000_00,
        max_position_notional_minor=100_000_00,
        max_open_orders=5,
        effective_from_ns=effective_from_ns,
        effective_until_ns=effective_until_ns,
        required_runtime_activation_ref=runtime_activation_ref,
        required_execution_policy_ref=execution_policy_ref,
        required_risk_policy_ref=risk_policy_ref,
        authorization_state=LiveAuthorizationState.DISABLED,
        issued_by="BUILD28_TEST_FIXTURE",
        reason="Design-only authorization for adversarial gate tests",
    )
    object.__setattr__(auth, "authorization_id", derive_authorization_id(auth))
    return auth


def build_test_enabled_authorization_fixture(
    *,
    broker: str,
    account_ref: str,
    effective_from_ns: int,
    effective_until_ns: int,
) -> LiveExecutionAuthorizationV1:
    """Isolated test-only ENABLED authorization — never used in production config."""
    auth = LiveExecutionAuthorizationV1(
        authorization_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope="US_EQUITY_DRY_RUN_TEST",
        broker=broker,
        account_ref=account_ref,
        allowed_instruments=("inst-aapl", "inst-msft", "inst-spy"),
        allowed_asset_classes=CERTIFIED_ASSET_CLASSES,
        allowed_sides=("BUY", "SELL"),
        allowed_order_types=CERTIFIED_ORDER_TYPES,
        max_order_notional_minor=10_000_00,
        max_daily_notional_minor=50_000_00,
        max_position_notional_minor=100_000_00,
        max_open_orders=5,
        effective_from_ns=effective_from_ns,
        effective_until_ns=effective_until_ns,
        required_runtime_activation_ref="TEST_RUNTIME",
        required_execution_policy_ref="TEST_EXEC_POLICY",
        required_risk_policy_ref="TEST_RISK_POLICY",
        authorization_state=LiveAuthorizationState.ENABLED,
        issued_by="BUILD28_ISOLATED_TEST",
        reason="Test-only enabled authorization for dry-run gate path",
        metadata={"isolated_test_fixture": True},
    )
    # Fix the allowed_order_types assignment
    object.__setattr__(
        auth,
        "allowed_order_types",
        ("MARKET", "LIMIT"),
    )
    object.__setattr__(auth, "authorization_id", derive_authorization_id(auth))
    return auth
