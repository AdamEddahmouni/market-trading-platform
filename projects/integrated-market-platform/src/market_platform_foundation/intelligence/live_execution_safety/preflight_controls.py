"""Pre-submit Live safety control contracts (fail closed, never submit).

These evaluators close gaps that Paper already exercises but the Live path
must refuse while Live remains OFF. They do not open broker sessions or
mutate runtime Live flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LivePreflightControlId(StrEnum):
    IDEMPOTENCY = "idempotency"
    DUPLICATE_SUBMISSION_PREVENTION = "duplicate_submission_prevention"
    STALE_DECISION_REFUSAL = "stale_decision_refusal"
    PRICE_FRESHNESS = "price_freshness"
    MAXIMUM_ORDER_SIZE = "maximum_order_size"
    BUYING_POWER = "buying_power"
    MARKET_STATE = "market_state"
    MALFORMED_ORDER = "malformed_order"
    ORDER_ACKNOWLEDGEMENT = "order_acknowledgement"
    CANCELLATION = "cancellation"
    PARTIAL_FILLS = "partial_fills"
    REJECTED_ORDERS = "rejected_orders"
    DISCONNECT_BEHAVIOR = "disconnect_behavior"
    RECONCILIATION_AFTER_RESTART = "reconciliation_after_restart"
    OPERATOR_CONFIRMATION = "operator_confirmation"
    KILL_SWITCH = "kill_switch"
    FAIL_CLOSED = "fail_closed"
    AUDIT_TRAIL = "audit_trail"


class LivePreflightDisposition(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    FAIL_CLOSED = "FAIL_CLOSED"
    # Control is modeled / certified but Live submit remains forbidden.
    REFUSED_WHILE_LIVE_OFF = "REFUSED_WHILE_LIVE_OFF"


@dataclass(frozen=True)
class LivePreflightFindingV1:
    control_id: LivePreflightControlId
    disposition: LivePreflightDisposition
    reason_code: str
    detail: str = ""


@dataclass(frozen=True)
class LivePreflightReportV1:
    findings: tuple[LivePreflightFindingV1, ...]
    allows_network_submit: bool

    @property
    def blocked(self) -> bool:
        return not self.allows_network_submit


def evaluate_price_freshness(
    *,
    reference_price_minor: int | None,
    quote_as_of_ns: int | None,
    decision_time_ns: int,
    max_age_ns: int,
) -> LivePreflightFindingV1:
    if reference_price_minor is None or reference_price_minor <= 0:
        return LivePreflightFindingV1(
            LivePreflightControlId.PRICE_FRESHNESS,
            LivePreflightDisposition.FAIL_CLOSED,
            "REFERENCE_PRICE_MISSING",
        )
    if quote_as_of_ns is None:
        return LivePreflightFindingV1(
            LivePreflightControlId.PRICE_FRESHNESS,
            LivePreflightDisposition.FAIL_CLOSED,
            "QUOTE_AS_OF_UNAVAILABLE",
        )
    if decision_time_ns < quote_as_of_ns:
        return LivePreflightFindingV1(
            LivePreflightControlId.PRICE_FRESHNESS,
            LivePreflightDisposition.FAIL_CLOSED,
            "QUOTE_TIMESTAMP_IN_FUTURE",
        )
    if decision_time_ns - quote_as_of_ns > max_age_ns:
        return LivePreflightFindingV1(
            LivePreflightControlId.PRICE_FRESHNESS,
            LivePreflightDisposition.BLOCK,
            "QUOTE_STALE",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.PRICE_FRESHNESS,
        LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
        "PRICE_FRESH_BUT_LIVE_SUBMIT_FORBIDDEN",
    )


def evaluate_maximum_order_size(
    *,
    quantity: int,
    max_quantity: int,
) -> LivePreflightFindingV1:
    if quantity <= 0:
        return LivePreflightFindingV1(
            LivePreflightControlId.MAXIMUM_ORDER_SIZE,
            LivePreflightDisposition.FAIL_CLOSED,
            "QUANTITY_INVALID",
        )
    if max_quantity <= 0:
        return LivePreflightFindingV1(
            LivePreflightControlId.MAXIMUM_ORDER_SIZE,
            LivePreflightDisposition.FAIL_CLOSED,
            "MAX_ORDER_SIZE_UNSPECIFIED",
        )
    if quantity > max_quantity:
        return LivePreflightFindingV1(
            LivePreflightControlId.MAXIMUM_ORDER_SIZE,
            LivePreflightDisposition.BLOCK,
            "MAX_ORDER_SIZE_EXCEEDED",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.MAXIMUM_ORDER_SIZE,
        LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
        "SIZE_WITHIN_LIMIT_BUT_LIVE_SUBMIT_FORBIDDEN",
    )


def evaluate_buying_power(
    *,
    required_notional_minor: int,
    buying_power_minor: int | None,
) -> LivePreflightFindingV1:
    if buying_power_minor is None:
        return LivePreflightFindingV1(
            LivePreflightControlId.BUYING_POWER,
            LivePreflightDisposition.FAIL_CLOSED,
            "BUYING_POWER_UNAVAILABLE",
        )
    if buying_power_minor < 0 or required_notional_minor < 0:
        return LivePreflightFindingV1(
            LivePreflightControlId.BUYING_POWER,
            LivePreflightDisposition.FAIL_CLOSED,
            "BUYING_POWER_MALFORMED",
        )
    if required_notional_minor > buying_power_minor:
        return LivePreflightFindingV1(
            LivePreflightControlId.BUYING_POWER,
            LivePreflightDisposition.BLOCK,
            "BUYING_POWER_INSUFFICIENT",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.BUYING_POWER,
        LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
        "BUYING_POWER_OK_BUT_LIVE_SUBMIT_FORBIDDEN",
    )


def evaluate_market_state(
    *,
    session_state: str | None,
    allow_outside_rth: bool = False,
) -> LivePreflightFindingV1:
    if session_state is None or session_state in {"", "UNKNOWN", "UNAVAILABLE"}:
        return LivePreflightFindingV1(
            LivePreflightControlId.MARKET_STATE,
            LivePreflightDisposition.FAIL_CLOSED,
            "MARKET_STATE_UNAVAILABLE",
        )
    normalized = session_state.upper()
    if normalized == "RTH_OPEN":
        return LivePreflightFindingV1(
            LivePreflightControlId.MARKET_STATE,
            LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
            "MARKET_OPEN_BUT_LIVE_SUBMIT_FORBIDDEN",
        )
    if normalized in {"CLOSED", "HALTED", "PRE_OPEN", "AFTER_HOURS"} and not allow_outside_rth:
        return LivePreflightFindingV1(
            LivePreflightControlId.MARKET_STATE,
            LivePreflightDisposition.BLOCK,
            "MARKET_STATE_NOT_RTH_OPEN",
        )
    if allow_outside_rth:
        return LivePreflightFindingV1(
            LivePreflightControlId.MARKET_STATE,
            LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
            "OUTSIDE_RTH_PERMITTED_BUT_LIVE_SUBMIT_FORBIDDEN",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.MARKET_STATE,
        LivePreflightDisposition.FAIL_CLOSED,
        "MARKET_STATE_UNRECOGNIZED",
        detail=normalized,
    )


def evaluate_malformed_order(
    *,
    side: str | None,
    order_type: str | None,
    quantity: int | None,
    limit_price_minor: int | None,
) -> LivePreflightFindingV1:
    if side is None or str(side).upper() not in {"BUY", "SELL"}:
        return LivePreflightFindingV1(
            LivePreflightControlId.MALFORMED_ORDER,
            LivePreflightDisposition.FAIL_CLOSED,
            "ORDER_SIDE_INVALID",
        )
    if order_type is None or str(order_type).upper() not in {"MARKET", "LIMIT"}:
        return LivePreflightFindingV1(
            LivePreflightControlId.MALFORMED_ORDER,
            LivePreflightDisposition.FAIL_CLOSED,
            "ORDER_TYPE_INVALID",
        )
    if quantity is None or quantity <= 0:
        return LivePreflightFindingV1(
            LivePreflightControlId.MALFORMED_ORDER,
            LivePreflightDisposition.FAIL_CLOSED,
            "ORDER_QUANTITY_INVALID",
        )
    if str(order_type).upper() == "LIMIT" and (limit_price_minor is None or limit_price_minor <= 0):
        return LivePreflightFindingV1(
            LivePreflightControlId.MALFORMED_ORDER,
            LivePreflightDisposition.FAIL_CLOSED,
            "LIMIT_PRICE_REQUIRED",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.MALFORMED_ORDER,
        LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
        "ORDER_SHAPE_VALID_BUT_LIVE_SUBMIT_FORBIDDEN",
    )


def evaluate_operator_confirmation(
    *,
    confirmation_present: bool,
    confirmation_expired: bool,
    confirmation_matches_intent: bool,
) -> LivePreflightFindingV1:
    if not confirmation_present:
        return LivePreflightFindingV1(
            LivePreflightControlId.OPERATOR_CONFIRMATION,
            LivePreflightDisposition.BLOCK,
            "OPERATOR_CONFIRMATION_MISSING",
        )
    if confirmation_expired:
        return LivePreflightFindingV1(
            LivePreflightControlId.OPERATOR_CONFIRMATION,
            LivePreflightDisposition.BLOCK,
            "OPERATOR_CONFIRMATION_EXPIRED",
        )
    if not confirmation_matches_intent:
        return LivePreflightFindingV1(
            LivePreflightControlId.OPERATOR_CONFIRMATION,
            LivePreflightDisposition.BLOCK,
            "OPERATOR_CONFIRMATION_MISMATCH",
        )
    return LivePreflightFindingV1(
        LivePreflightControlId.OPERATOR_CONFIRMATION,
        LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
        "OPERATOR_CONFIRMED_BUT_LIVE_SUBMIT_FORBIDDEN",
    )


def evaluate_live_preflight_bundle(
    *,
    reference_price_minor: int | None,
    quote_as_of_ns: int | None,
    decision_time_ns: int,
    max_quote_age_ns: int,
    quantity: int,
    max_quantity: int,
    required_notional_minor: int,
    buying_power_minor: int | None,
    session_state: str | None,
    side: str | None,
    order_type: str | None,
    limit_price_minor: int | None,
    confirmation_present: bool,
    confirmation_expired: bool,
    confirmation_matches_intent: bool,
    allow_outside_rth: bool = False,
) -> LivePreflightReportV1:
    """Run the gap-closing Live preflight controls; never allows network submit."""
    findings = (
        evaluate_malformed_order(
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price_minor=limit_price_minor,
        ),
        evaluate_price_freshness(
            reference_price_minor=reference_price_minor,
            quote_as_of_ns=quote_as_of_ns,
            decision_time_ns=decision_time_ns,
            max_age_ns=max_quote_age_ns,
        ),
        evaluate_maximum_order_size(quantity=quantity, max_quantity=max_quantity),
        evaluate_buying_power(
            required_notional_minor=required_notional_minor,
            buying_power_minor=buying_power_minor,
        ),
        evaluate_market_state(session_state=session_state, allow_outside_rth=allow_outside_rth),
        evaluate_operator_confirmation(
            confirmation_present=confirmation_present,
            confirmation_expired=confirmation_expired,
            confirmation_matches_intent=confirmation_matches_intent,
        ),
        LivePreflightFindingV1(
            LivePreflightControlId.FAIL_CLOSED,
            LivePreflightDisposition.REFUSED_WHILE_LIVE_OFF,
            "BUILD28_LIVE_SUBMIT_FORBIDDEN",
            detail="Network submit remains forbidden while Live is OFF.",
        ),
    )
    # Hard invariant: this bundle never authorizes a network submit.
    return LivePreflightReportV1(findings=findings, allows_network_submit=False)
