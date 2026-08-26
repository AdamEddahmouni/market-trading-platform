"""Two-phase canary authorization — prepare/preview then explicit human approve (BUILD 29)."""

from __future__ import annotations

from ..live_execution_safety.types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    CERTIFIED_ASSET_CLASSES,
    LiveAuthorizationState,
    LiveExecutionAuthorizationV1,
)
from .identity import (
    authorization_semantics_hash,
    derive_canary_authorization_id,
    derive_human_approval_id,
    derive_preview_hash,
    derive_preview_id,
)
from .policy import build_default_canary_policy
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    CanaryAuthorizationPreviewV1,
    HumanApprovalSource,
    HumanCanaryApprovalV1,
    LiveCanaryPolicyV1,
)

AUTHORIZED_STATES = frozenset(
    {LiveAuthorizationState.AUTHORIZED, LiveAuthorizationState.ENABLED}
)
SUBMITTABLE_STATES = AUTHORIZED_STATES
TERMINAL_STATES = frozenset(
    {
        LiveAuthorizationState.EXPIRED,
        LiveAuthorizationState.REVOKED,
        LiveAuthorizationState.CONSUMED,
        LiveAuthorizationState.DISABLED,
    }
)


class AuthorizationError(ValueError):
    pass


def prepare_canary_authorization_preview(
    *,
    policy: LiveCanaryPolicyV1,
    broker: str,
    account_ref: str,
    account_fingerprint: str,
    generated_at_ns: int,
    starting_positions: tuple[dict[str, object], ...] = (),
    starting_open_orders: tuple[dict[str, object], ...] = (),
    kill_switch_state: str = "ACTIVE_BLOCK",
    known_limitations: tuple[str, ...] = (),
) -> CanaryAuthorizationPreviewV1:
    """Phase 1: immutable preview for human review — no authorization granted."""
    preview = CanaryAuthorizationPreviewV1(
        preview_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        canary_policy_ref=policy.canary_policy_id,
        broker=broker,
        account_environment=policy.account_environment,
        account_fingerprint=account_fingerprint,
        symbol_universe=policy.allowed_instruments,
        allowed_sides=policy.allowed_sides,
        allowed_order_types=policy.allowed_order_types,
        max_single_order_notional_minor=policy.max_single_order_notional_minor,
        max_total_canary_notional_minor=policy.max_total_canary_notional_minor,
        max_order_count=policy.max_order_count,
        authorization_duration_ns=policy.authorization_duration_ns,
        starting_positions_summary=starting_positions,
        starting_open_orders_summary=starting_open_orders,
        execution_policy_ref=policy.required_execution_policy_ref,
        risk_policy_ref="BUILD22_RISK",
        broker_certification_ref=policy.required_broker_certification_ref,
        kill_switch_state=kill_switch_state,
        known_limitations=known_limitations,
        generated_at_ns=generated_at_ns,
    )
    object.__setattr__(preview, "preview_id", derive_preview_id(preview))
    return preview


def record_human_canary_approval(
    *,
    preview: CanaryAuthorizationPreviewV1,
    approved_at_ns: int,
    approved_by: str,
    approval_source: HumanApprovalSource,
    approval_statement: str = "Explicit human authorization for canary envelope",
) -> HumanCanaryApprovalV1:
    """Record explicit human approval of exact preview — Phase 2 gate."""
    approval = HumanCanaryApprovalV1(
        approval_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        preview_id=preview.preview_id,
        preview_hash=derive_preview_hash(preview),
        approved_at_ns=approved_at_ns,
        approved_by=approved_by,
        approval_source=approval_source,
        approval_statement=approval_statement,
    )
    object.__setattr__(approval, "approval_id", derive_human_approval_id(approval))
    return approval


def authorize_canary_from_human_approval(
    *,
    policy: LiveCanaryPolicyV1,
    preview: CanaryAuthorizationPreviewV1,
    human_approval: HumanCanaryApprovalV1,
    effective_from_ns: int,
    effective_until_ns: int,
) -> LiveExecutionAuthorizationV1:
    """Create AUTHORIZED LiveExecutionAuthorizationV1 bound to exact preview."""
    if human_approval.preview_id != preview.preview_id:
        raise AuthorizationError("PREVIEW_MISMATCH")
    if human_approval.preview_hash != derive_preview_hash(preview):
        raise AuthorizationError("PREVIEW_HASH_MISMATCH")
    if preview.canary_policy_ref != policy.canary_policy_id:
        raise AuthorizationError("POLICY_MISMATCH")
    if human_approval.approval_source == HumanApprovalSource.TEST_FIXTURE:
        issued_by = "TEST_FIXTURE"
    else:
        issued_by = human_approval.approved_by

    auth_id = derive_canary_authorization_id(
        policy=policy,
        preview_id=preview.preview_id,
        human_approval_id=human_approval.approval_id,
        effective_from_ns=effective_from_ns,
        effective_until_ns=effective_until_ns,
    )
    auth = LiveExecutionAuthorizationV1(
        authorization_id=auth_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope=f"CANARY_{policy.canary_policy_id}",
        broker=policy.broker,
        account_ref=policy.account_ref,
        allowed_instruments=policy.allowed_instruments,
        allowed_asset_classes=policy.allowed_asset_classes or CERTIFIED_ASSET_CLASSES,
        allowed_sides=policy.allowed_sides,
        allowed_order_types=policy.allowed_order_types,
        max_order_notional_minor=policy.max_single_order_notional_minor,
        max_daily_notional_minor=policy.max_total_canary_notional_minor,
        max_position_notional_minor=policy.max_gross_live_exposure_minor,
        max_open_orders=policy.max_order_count,
        effective_from_ns=effective_from_ns,
        effective_until_ns=effective_until_ns,
        required_runtime_activation_ref=policy.required_runtime_activation_ref,
        required_execution_policy_ref=policy.required_execution_policy_ref,
        required_risk_policy_ref="BUILD22_RISK",
        authorization_state=LiveAuthorizationState.AUTHORIZED,
        issued_by=issued_by,
        reason="BUILD29_HUMAN_AUTHORIZED_CANARY",
        lineage={
            "preview_id": preview.preview_id,
            "human_approval_id": human_approval.approval_id,
            "canary_policy_id": policy.canary_policy_id,
            "semantics_hash": authorization_semantics_hash(
                LiveExecutionAuthorizationV1(
                    authorization_id=auth_id,
                    schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
                    scope=f"CANARY_{policy.canary_policy_id}",
                    broker=policy.broker,
                    account_ref=policy.account_ref,
                    allowed_instruments=policy.allowed_instruments,
                    allowed_asset_classes=policy.allowed_asset_classes or CERTIFIED_ASSET_CLASSES,
                    allowed_sides=policy.allowed_sides,
                    allowed_order_types=policy.allowed_order_types,
                    max_order_notional_minor=policy.max_single_order_notional_minor,
                    max_daily_notional_minor=policy.max_total_canary_notional_minor,
                    max_position_notional_minor=policy.max_gross_live_exposure_minor,
                    max_open_orders=policy.max_order_count,
                    effective_from_ns=effective_from_ns,
                    effective_until_ns=effective_until_ns,
                    required_runtime_activation_ref=policy.required_runtime_activation_ref,
                    required_execution_policy_ref=policy.required_execution_policy_ref,
                    required_risk_policy_ref="BUILD22_RISK",
                    authorization_state=LiveAuthorizationState.AUTHORIZED,
                    issued_by=issued_by,
                    reason="BUILD29_HUMAN_AUTHORIZED_CANARY",
                )
            ),
        },
        metadata={
            "canary_policy_id": policy.canary_policy_id,
            "max_order_count": policy.max_order_count,
            "require_manual_order_confirmation": policy.require_manual_order_confirmation,
        },
    )
    return auth


def transition_authorization_state(
    auth: LiveExecutionAuthorizationV1,
    new_state: LiveAuthorizationState,
    *,
    reason: str,
) -> LiveExecutionAuthorizationV1:
    """Immutable state transition — new authorization identity required for scope changes."""
    return LiveExecutionAuthorizationV1(
        authorization_id=auth.authorization_id,
        schema_version=auth.schema_version,
        scope=auth.scope,
        broker=auth.broker,
        account_ref=auth.account_ref,
        allowed_instruments=auth.allowed_instruments,
        allowed_asset_classes=auth.allowed_asset_classes,
        allowed_sides=auth.allowed_sides,
        allowed_order_types=auth.allowed_order_types,
        max_order_notional_minor=auth.max_order_notional_minor,
        max_daily_notional_minor=auth.max_daily_notional_minor,
        max_position_notional_minor=auth.max_position_notional_minor,
        max_open_orders=auth.max_open_orders,
        effective_from_ns=auth.effective_from_ns,
        effective_until_ns=auth.effective_until_ns,
        required_runtime_activation_ref=auth.required_runtime_activation_ref,
        required_execution_policy_ref=auth.required_execution_policy_ref,
        required_risk_policy_ref=auth.required_risk_policy_ref,
        authorization_state=new_state,
        issued_by=auth.issued_by,
        reason=reason,
        lineage=dict(auth.lineage),
        metadata=dict(auth.metadata),
    )


def is_authorization_submittable(
    auth: LiveExecutionAuthorizationV1,
    *,
    decision_time_ns: int,
    orders_submitted: int,
) -> tuple[bool, str | None]:
    if auth.authorization_state not in SUBMITTABLE_STATES:
        return False, "NOT_AUTHORIZED"
    if decision_time_ns < auth.effective_from_ns or decision_time_ns >= auth.effective_until_ns:
        return False, "EXPIRED"
    if orders_submitted >= auth.max_open_orders:
        return False, "ORDER_COUNT_EXHAUSTED"
    return True, None


def consume_authorization(auth: LiveExecutionAuthorizationV1) -> LiveExecutionAuthorizationV1:
    return transition_authorization_state(
        auth, LiveAuthorizationState.CONSUMED, reason="CANARY_ORDER_LIMIT_REACHED"
    )


def revoke_authorization(auth: LiveExecutionAuthorizationV1) -> LiveExecutionAuthorizationV1:
    return transition_authorization_state(
        auth, LiveAuthorizationState.REVOKED, reason="CANARY_REVOKED"
    )


def expire_authorization(auth: LiveExecutionAuthorizationV1) -> LiveExecutionAuthorizationV1:
    return transition_authorization_state(
        auth, LiveAuthorizationState.EXPIRED, reason="CANARY_EXPIRED"
    )


def disable_authorization(auth: LiveExecutionAuthorizationV1) -> LiveExecutionAuthorizationV1:
    return transition_authorization_state(
        auth, LiveAuthorizationState.DISABLED, reason="CANARY_DISABLED"
    )
