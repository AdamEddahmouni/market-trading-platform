"""Independent risk evaluation for order intents."""

from __future__ import annotations

from typing import Any

from .kill_switch import KillSwitchState

REJECT_KILL_SWITCH = "RISK_KILL_SWITCH_ACTIVE"
REJECT_MAX_ORDER = "RISK_MAX_ORDER_EXCEEDED"
REJECT_MAX_POSITION = "RISK_MAX_POSITION_EXCEEDED"
REJECT_MAX_OPEN_ORDERS = "RISK_MAX_OPEN_ORDERS"
REJECT_INVALID_INTENT = "RISK_INVALID_INTENT"
REJECT_INSUFFICIENT_BUYING_POWER = "RISK_INSUFFICIENT_BUYING_POWER"
REJECT_INSUFFICIENT_POSITION = "RISK_INSUFFICIENT_POSITION"
REJECT_MAX_ORDER_NOTIONAL = "RISK_MAX_ORDER_NOTIONAL_EXCEEDED"
REJECT_MAX_POSITION_NOTIONAL = "RISK_MAX_POSITION_NOTIONAL_EXCEEDED"
REJECT_PRICE_UNAVAILABLE = "RISK_PRICE_UNAVAILABLE"


def evaluate_risk(
    *,
    intent: dict[str, Any],
    policy: dict[str, Any],
    kill_switch: KillSwitchState,
    current_position_shares: int,
    open_order_count: int,
    current_cash_minor: int | None = None,
    reserved_cash_minor: int = 0,
    reserved_sell_shares: int = 0,
    risk_price_minor: int | None = None,
    risk_price_source: str | None = None,
    risk_price_as_of_ns: int | None = None,
    risk_price_quality: str | None = None,
    risk_price_error: str | None = None,
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
            current_cash_minor=current_cash_minor,
            current_position_shares=current_position_shares,
            reserved_cash_minor=reserved_cash_minor,
            reserved_sell_shares=reserved_sell_shares,
            risk_price_minor=risk_price_minor,
            risk_price_source=risk_price_source,
            risk_price_as_of_ns=risk_price_as_of_ns,
            risk_price_quality=risk_price_quality,
        )

    if kill_switch.active:
        reasons.append(REJECT_KILL_SWITCH)
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=reasons,
            current_cash_minor=current_cash_minor,
            current_position_shares=current_position_shares,
            reserved_cash_minor=reserved_cash_minor,
            reserved_sell_shares=reserved_sell_shares,
            risk_price_minor=risk_price_minor,
            risk_price_source=risk_price_source,
            risk_price_as_of_ns=risk_price_as_of_ns,
            risk_price_quality=risk_price_quality,
        )

    if risk_price_error or risk_price_minor is None or int(risk_price_minor) <= 0:
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=[risk_price_error or REJECT_PRICE_UNAVAILABLE],
            current_cash_minor=current_cash_minor,
            current_position_shares=current_position_shares,
            reserved_cash_minor=reserved_cash_minor,
            reserved_sell_shares=reserved_sell_shares,
            risk_price_minor=risk_price_minor,
            risk_price_source=risk_price_source,
            risk_price_as_of_ns=risk_price_as_of_ns,
            risk_price_quality=risk_price_quality,
        )

    max_order = int(policy["max_order_shares"])
    max_position = int(policy["max_position_shares"])
    max_open = int(policy["max_open_orders"])
    if open_order_count >= max_open:
        return _decision(
            intent=intent,
            policy=policy,
            decision="REJECT",
            approved_quantity=0,
            reason_codes=[REJECT_MAX_OPEN_ORDERS],
            current_cash_minor=current_cash_minor,
            current_position_shares=current_position_shares,
            reserved_cash_minor=reserved_cash_minor,
            reserved_sell_shares=reserved_sell_shares,
            risk_price_minor=risk_price_minor,
            risk_price_source=risk_price_source,
            risk_price_as_of_ns=risk_price_as_of_ns,
            risk_price_quality=risk_price_quality,
        )

    price = int(risk_price_minor)
    commission_per_share = int(policy.get("commission_minor_per_share", 0))
    fee_minor = int(policy.get("fee_minor_per_order", 0))
    capacities: list[tuple[int, str]] = [
        (max_order, REJECT_MAX_ORDER),
        (int(policy["max_order_notional_minor"]) // price, REJECT_MAX_ORDER_NOTIONAL),
    ]
    if direction == "long":
        capacities.extend(
            [
                (max(0, max_position - current_position_shares), REJECT_MAX_POSITION),
                (
                    max(0, int(policy["max_position_notional_minor"]) // price - current_position_shares),
                    REJECT_MAX_POSITION_NOTIONAL,
                ),
            ]
        )
        if current_cash_minor is not None:
            available_cash = max(0, int(current_cash_minor) - int(reserved_cash_minor))
            per_share = price + commission_per_share
            cash_capacity = max(0, available_cash - fee_minor) // per_share if per_share > 0 else 0
            capacities.append((cash_capacity, REJECT_INSUFFICIENT_BUYING_POWER))
    else:
        capacities.append(
            (max(0, current_position_shares - int(reserved_sell_shares)), REJECT_INSUFFICIENT_POSITION)
        )

    approved = min([desired, *(capacity for capacity, _reason in capacities)])
    reasons = [reason for capacity, reason in capacities if desired > capacity]
    decision_name = "APPROVE" if approved == desired else ("RESIZE" if approved > 0 else "REJECT")

    return _decision(
        intent=intent,
        policy=policy,
        decision=decision_name,
        approved_quantity=approved,
        reason_codes=sorted(set(reasons)),
        current_cash_minor=current_cash_minor,
        current_position_shares=current_position_shares,
        reserved_cash_minor=reserved_cash_minor,
        reserved_sell_shares=reserved_sell_shares,
        risk_price_minor=risk_price_minor,
        risk_price_source=risk_price_source,
        risk_price_as_of_ns=risk_price_as_of_ns,
        risk_price_quality=risk_price_quality,
    )


def _decision(
    *,
    intent: dict[str, Any],
    policy: dict[str, Any],
    decision: str,
    approved_quantity: int,
    reason_codes: list[str],
    current_cash_minor: int | None = None,
    current_position_shares: int = 0,
    reserved_cash_minor: int = 0,
    reserved_sell_shares: int = 0,
    risk_price_minor: int | None = None,
    risk_price_source: str | None = None,
    risk_price_as_of_ns: int | None = None,
    risk_price_quality: str | None = None,
) -> dict[str, Any]:
    price = int(risk_price_minor or 0)
    direction = str(intent.get("direction", ""))
    commission = approved_quantity * int(policy.get("commission_minor_per_share", 0))
    fee = int(policy.get("fee_minor_per_order", 0)) if approved_quantity > 0 else 0
    reserved_order_cash = approved_quantity * price + commission + fee if direction == "long" else 0
    projected_available_cash = (
        None
        if current_cash_minor is None
        else int(current_cash_minor) - int(reserved_cash_minor) - reserved_order_cash
    )
    projected_position = current_position_shares + (approved_quantity if direction == "long" else -approved_quantity)
    return {
        "approved_quantity": approved_quantity,
        "approved_notional_minor": approved_quantity * price,
        "decision": decision,
        "direction": intent.get("direction"),
        "instrument_id": intent.get("instrument_id"),
        "intent_id": intent.get("intent_id"),
        "policy_version": policy["policy_version"],
        "reason_codes": sorted(reason_codes),
        "requested_notional_minor": int(intent.get("desired_quantity", 0)) * price,
        "requested_quantity": int(intent.get("desired_quantity", 0)),
        "reserved_cash_minor": int(reserved_cash_minor),
        "reserved_order_cash_minor": reserved_order_cash,
        "reserved_sell_shares": int(reserved_sell_shares),
        "risk_price_as_of_ns": risk_price_as_of_ns,
        "risk_price_minor": risk_price_minor,
        "risk_price_quality": risk_price_quality,
        "risk_price_source": risk_price_source,
        "projected_available_cash_minor": projected_available_cash,
        "projected_position_shares": projected_position,
        "risk_policy_identity_hash": policy["risk_policy_identity_hash"],
        "signal_prediction_cutoff": intent.get("signal_prediction_cutoff"),
    }
