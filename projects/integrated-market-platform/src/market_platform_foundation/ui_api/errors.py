"""Canonical IMP API error taxonomy (BL-0702 / RC-010).

Additive layer: existing ``reason_code`` strings are preserved; responses also
emit ``error_category`` from the twelve WS05 categories.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class CanonicalErrorCategory(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    STALE_DATA = "STALE_DATA"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"
    RISK_BLOCKED = "RISK_BLOCKED"
    MODE_BLOCKED = "MODE_BLOCKED"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


CANONICAL_ERROR_CATEGORY_VALUES = frozenset(item.value for item in CanonicalErrorCategory)


# Explicit mappings for stable UI API and platform reason codes.
_REASON_CODE_TO_CATEGORY: dict[str, CanonicalErrorCategory] = {
    # Validation / client contract
    "UI_REQUEST_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_JSON_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_INSTRUMENT_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_ROUTE_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_ASSISTANT_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_ASSISTANT_PROMPT_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "UI_REPLAY_SCRUB_FAILED": CanonicalErrorCategory.VALIDATION_ERROR,
    "OPERATIONAL_IDENTITY_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "OPERATION_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "OPPORTUNITY_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "PAPER_TRACE_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "PAPER_ORDER_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "FORWARD_TEST_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "FORWARD_TEST_CAMPAIGN_ID_REQUIRED": CanonicalErrorCategory.VALIDATION_ERROR,
    "FORWARD_TEST_PREFLIGHT_FAILED": CanonicalErrorCategory.VALIDATION_ERROR,
    "OPERATOR_LIFECYCLE_ACTION_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "PAPER_ORDER_REPLACE_BELOW_FILLED": CanonicalErrorCategory.VALIDATION_ERROR,
    "PAPER_ORDER_PREVIEW_FAILED": CanonicalErrorCategory.VALIDATION_ERROR,
    # Account scope
    "OPERATIONAL_ACCOUNT_UNKNOWN": CanonicalErrorCategory.ACCOUNT_UNAVAILABLE,
    "ACCOUNT_ACCESS_DENIED": CanonicalErrorCategory.ACCOUNT_UNAVAILABLE,
    # Auth / authorization
    "AUTH_REQUIRED": CanonicalErrorCategory.AUTH_ERROR,
    "AUTH_INVALID": CanonicalErrorCategory.AUTH_ERROR,
    "CAPABILITY_DENIED": CanonicalErrorCategory.AUTH_ERROR,
    # Mode / authority gates
    "PAPER_EXECUTION_NOT_AUTHORIZED": CanonicalErrorCategory.MODE_BLOCKED,
    "PAPER_EXECUTION_MODE_INVALID": CanonicalErrorCategory.MODE_BLOCKED,
    "LIVE_OBSERVATIONAL_DISABLED": CanonicalErrorCategory.MODE_BLOCKED,
    "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE": CanonicalErrorCategory.MODE_BLOCKED,
    "LIVE_OBSERVATIONAL_NO_BROKER_EXECUTION": CanonicalErrorCategory.MODE_BLOCKED,
    "LIVE_OBSERVATIONAL_ACK_REQUIRES_LIVE_CLOCK": CanonicalErrorCategory.MODE_BLOCKED,
    "LIVE_OBSERVATIONAL_OPERATOR_ACK_DUPLICATE": CanonicalErrorCategory.MODE_BLOCKED,
    "DEMO_MUTATIONS_PROHIBITED": CanonicalErrorCategory.MODE_BLOCKED,
    # Operator control-plane HTTP (loopback 8767)
    "CONTROL_ROUTE_NOT_FOUND": CanonicalErrorCategory.VALIDATION_ERROR,
    "CONTROL_JSON_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    "CONTROL_ACTION_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
    # Provider connectivity
    "OPEND_UNAVAILABLE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "EMPTY_PAYLOAD": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "TEMPORARY_NETWORK_FAILURE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "FALLBACK_BLOCKED": CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
    "DELAYED_OVERLAY_NOT_HOP_L1": CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
    "MALFORMED_RESPONSE": CanonicalErrorCategory.PROVIDER_REJECTED,
    "MALFORMED_RECORD": CanonicalErrorCategory.PROVIDER_REJECTED,
    "SOURCE_DISAGREEMENT": CanonicalErrorCategory.PROVIDER_REJECTED,
    "PARTIALLY_STALE": CanonicalErrorCategory.STALE_DATA,
    "DELAYED_DATA": CanonicalErrorCategory.STALE_DATA,
    "PROVIDER_TIMEOUT": CanonicalErrorCategory.TIMEOUT,
    "PROVIDER_UNAVAILABLE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "PROVIDER_DOWN": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "LIVE_PROVIDER_UNAVAILABLE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "OPERATOR_PROVIDER_REFRESH_FAILED": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "PAPER_STRATEGY_RUNTIME_UNAVAILABLE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "MOOMOO_SDK_MISSING": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "MOOMOO_TRANSPORT_NOT_IMPLEMENTED": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "MOOMOO_PROTOCOL_ERROR": CanonicalErrorCategory.PROVIDER_REJECTED,
    "MOOMOO_LAST_PRICE_MISSING": CanonicalErrorCategory.PROVIDER_REJECTED,
    "MISSING_TIMESTAMP": CanonicalErrorCategory.PROVIDER_REJECTED,
    "RECONNECTING": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "RESTART_RECOVERY": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    "RATE_LIMIT": CanonicalErrorCategory.RATE_LIMITED,
    "NOT_ENTITLED": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
    # Provider / broker rejection
    "PROVIDER_REJECTED": CanonicalErrorCategory.PROVIDER_REJECTED,
    "PAPER_ORDER_SUBMIT_FAILED": CanonicalErrorCategory.PROVIDER_REJECTED,
    "PAPER_BROKER_POLL_FAILED": CanonicalErrorCategory.PROVIDER_REJECTED,
    "PAPER_BROKER_RECONCILIATION_FAILED": CanonicalErrorCategory.PROVIDER_REJECTED,
    # Capability gaps
    "PAPER_ORDER_CANCEL_NOT_SUPPORTED": CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
    "PAPER_ORDER_REPLACE_NOT_SUPPORTED": CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
    "UNSUPPORTED_CAPABILITY": CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
    # Risk
    "RISK_KILL_SWITCH_ACTIVE": CanonicalErrorCategory.RISK_BLOCKED,
    "RISK_MAX_ORDER_EXCEEDED": CanonicalErrorCategory.RISK_BLOCKED,
    "RISK_MAX_POSITION_EXCEEDED": CanonicalErrorCategory.RISK_BLOCKED,
    "RISK_MAX_OPEN_ORDERS": CanonicalErrorCategory.RISK_BLOCKED,
    "RISK_INVALID_INTENT": CanonicalErrorCategory.RISK_BLOCKED,
    "POSITION_LIMIT": CanonicalErrorCategory.RISK_BLOCKED,
    "ORDER_LIMIT": CanonicalErrorCategory.RISK_BLOCKED,
    "RISK_REJECTED": CanonicalErrorCategory.RISK_BLOCKED,
    # Stale inputs
    "STALE_DATA": CanonicalErrorCategory.STALE_DATA,
    "STALE_MARK": CanonicalErrorCategory.STALE_DATA,
    "STALE_PREVIEW": CanonicalErrorCategory.STALE_DATA,
    # Rate / time
    "RATE_LIMITED": CanonicalErrorCategory.RATE_LIMITED,
    "TIMEOUT": CanonicalErrorCategory.TIMEOUT,
    # Internal / unexpected
    "UI_INTERNAL_ERROR": CanonicalErrorCategory.INTERNAL_ERROR,
    "UI_SECRET_LEAK_BLOCKED": CanonicalErrorCategory.INTERNAL_ERROR,
    "INTERNAL_ERROR": CanonicalErrorCategory.INTERNAL_ERROR,
    "CANARY_COMMAND_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_ACK_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_LIFECYCLE_ACTION_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "PAPER_SESSION_OPEN_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "PAPER_SESSION_CLOSE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "PAPER_ORDER_CANCEL_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "PAPER_ORDER_REPLACE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_SESSION_CREATE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_DECISION_CREATE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_LOCK_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_SUBMIT_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_OBSERVE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "FORWARD_TEST_EVALUATE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_WATCHLIST_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_CONFIG_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_RECENT_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_WORKSPACE_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "OPERATOR_PREFERENCES_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
    "CAPTURE_REPLAY_FAILED": CanonicalErrorCategory.INTERNAL_ERROR,
}

_PREFIX_CATEGORY_RULES: tuple[tuple[str, CanonicalErrorCategory], ...] = (
    ("RISK_", CanonicalErrorCategory.RISK_BLOCKED),
    ("AUTH_", CanonicalErrorCategory.AUTH_ERROR),
    ("STALE_", CanonicalErrorCategory.STALE_DATA),
    ("PROVIDER_", CanonicalErrorCategory.PROVIDER_UNAVAILABLE),
    ("OPEND_", CanonicalErrorCategory.PROVIDER_UNAVAILABLE),
    ("LIVE_OBSERVATIONAL_", CanonicalErrorCategory.MODE_BLOCKED),
    ("DEMO_MUTATIONS_", CanonicalErrorCategory.MODE_BLOCKED),
    ("CONTROL_", CanonicalErrorCategory.VALIDATION_ERROR),
)

_SUFFIX_CATEGORY_RULES: tuple[tuple[str, CanonicalErrorCategory], ...] = (
    ("_TIMEOUT", CanonicalErrorCategory.TIMEOUT),
    ("_RATE_LIMITED", CanonicalErrorCategory.RATE_LIMITED),
    ("_NOT_AUTHORIZED", CanonicalErrorCategory.MODE_BLOCKED),
    ("_INVALID", CanonicalErrorCategory.VALIDATION_ERROR),
    ("_NOT_FOUND", CanonicalErrorCategory.VALIDATION_ERROR),
    ("_UNAVAILABLE", CanonicalErrorCategory.PROVIDER_UNAVAILABLE),
    ("_REJECTED", CanonicalErrorCategory.PROVIDER_REJECTED),
)


def canonical_error_category(reason_code: str) -> CanonicalErrorCategory:
    """Map a legacy or domain reason code to a canonical error category."""
    normalized = str(reason_code or "").strip().upper()
    if not normalized:
        return CanonicalErrorCategory.INTERNAL_ERROR
    if normalized in CANONICAL_ERROR_CATEGORY_VALUES:
        return CanonicalErrorCategory(normalized)
    exact = _REASON_CODE_TO_CATEGORY.get(normalized)
    if exact is not None:
        return exact
    for prefix, category in _PREFIX_CATEGORY_RULES:
        if normalized.startswith(prefix):
            return category
    for suffix, category in _SUFFIX_CATEGORY_RULES:
        if normalized.endswith(suffix):
            return category
    return CanonicalErrorCategory.INTERNAL_ERROR


def build_error_response_payload(reason_code: str, message: str) -> dict[str, Any]:
    category = canonical_error_category(reason_code)
    return {
        "error": message,
        "reason_code": str(reason_code),
        "error_category": category.value,
    }


def build_provider_error_payload(
    reason_code: str,
    message: str | None = None,
) -> dict[str, Any]:
    """Error envelope plus backend-owned provider resilience operator explanation."""

    from ..providers.resilience import incident_for_reason_code

    incident = incident_for_reason_code(reason_code)
    operator_explanation = incident.operator_message
    payload = build_error_response_payload(
        reason_code,
        message if message is not None else operator_explanation,
    )
    payload["operator_explanation"] = operator_explanation
    payload["provider_status_token"] = incident.status_token
    payload["fallback_boundary"] = incident.fallback.boundary_token
    payload["overlay_as_hop_l1"] = incident.fallback.overlay_as_hop_l1
    payload["live_execution"] = incident.live_execution
    payload["item9_mode"] = "IDLE"
    payload["item9_calibration"] = "NOT_CALIBRATED"
    return payload


__all__ = [
    "CANONICAL_ERROR_CATEGORY_VALUES",
    "CanonicalErrorCategory",
    "build_error_response_payload",
    "build_provider_error_payload",
    "canonical_error_category",
]
