"""Independent risk evaluation for order intents."""

from __future__ import annotations

from typing import Any

from .kill_switch import KillSwitchState

REJECT_KILL_SWITCH = "RISK_KILL_SWITCH_ACTIVE"
REJECT_MAX_ORDER = "RISK_MAX_ORDER_EXCEEDED"
REJECT_MAX_POSITION = "RISK_MAX_POSITION_EXCEEDED"
REJECT_MAX_OPEN_ORDERS = "RISK_MAX_OPEN_ORDERS"
REJECT_INVALID_INTENT = "RISK_INVALID_INTENT"


def evaluate_risk(
    *,
    intent: dict[str, Any],
    policy: dict[str, Any],
    kill_switch: KillSwitchState,
    current_position_shares: int,
    open_order_count: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    desired = int(intent.get("desired_quantity", 0))
    direction = str(intent.get("direction", ""))
    instrument_id = str(intent.get("instrument_id", ""))

    if desired <= 0 or direction not in {"long", "short"} or not instrument_id:
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=[REJECT_INVALID_INTENT],
        )

    if kill_switch.active:
        reasons.append(REJECT_KILL_SWITCH)
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=reasons,
        )

    max_order = int(policy["max_order_shares"])
    max_position = int(policy["max_position_shares"])
    max_open = int(policy["max_open_orders"])

    if desired > max_order:
        reasons.append(REJECT_MAX_ORDER)

    signed_delta = desired if direction == "long" else -desired
    projected = current_position_shares + signed_delta
    if abs(projected) > max_position:
        reasons.append(REJECT_MAX_POSITION)

    if open_order_count >= max_open:
        reasons.append(REJECT_MAX_OPEN_ORDERS)

    if reasons:
        if REJECT_MAX_ORDER in reasons and desired > max_order:
            approved = max_order
            resize_reasons = [r for r in reasons if r != REJECT_MAX_ORDER]
            if resize_reasons:
                return _decision(
                    intent=intent,
                    policy=policy,
                    decision="REJECT",
                    approved_quantity=0,
                    reason_codes=sorted(set(reasons)),
                )
            return _decision(
                intent=intent,
                policy=policy,
                decision="RESIZE",
                approved_quantity=approved,
                reason_codes=[REJECT_MAX_ORDER],
            )
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=sorted(set(reasons)),
        )

    return _decision(
        intent=intent,
        policy=policy,
        decision="APPROVE",
        approved_quantity=desired,
        reason_codes=[],
    )


def _decision(
    *,
    intent: dict[str, Any],
    policy: dict[str, Any],
    decision: str,
    approved_quantity: int,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "approved_quantity": approved_quantity,
        "decision": decision,
        "direction": intent.get("direction"),
        "instrument_id": intent.get("instrument_id"),
        "intent_id": intent.get("intent_id"),
        "policy_version": policy["policy_version"],
        "reason_codes": sorted(reason_codes),
        "risk_policy_identity_hash": policy["risk_policy_identity_hash"],
        "signal_prediction_cutoff": intent.get("signal_prediction_cutoff"),
    }
