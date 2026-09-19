"""Offline provider incident classification and fallback boundaries.

Software-only: fixtures and mocks. Never selects Yahoo as hop L1, never
fabricates ticks, never mutates Item 9 corpus status, and never enables Live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .adapters.yahoo_delayed_equity_quote import YAHOO_PROVIDER_ID, YAHOO_TIMELINESS
from .equity_quote_selection import OpenDReadiness
from .moomoo_opend_capability import MOOMOO_OPEND_PROVIDER_ID

# Canonical status tokens (operator-facing; backend-owned).
OPEND_UNAVAILABLE = "OPEND_UNAVAILABLE"
DELAYED_DATA = "DELAYED_DATA"
PARTIALLY_STALE = "PARTIALLY_STALE"
SOURCE_DISAGREEMENT = "SOURCE_DISAGREEMENT"
RECONNECTING = "RECONNECTING"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
EMPTY_PAYLOAD = "EMPTY_PAYLOAD"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
TEMPORARY_NETWORK_FAILURE = "TEMPORARY_NETWORK_FAILURE"
RESTART_RECOVERY = "RESTART_RECOVERY"
FALLBACK_BLOCKED = "FALLBACK_BLOCKED"
OVERLAY_ALLOWED = "OVERLAY_ALLOWED"
OPEND_REACHABLE = "OPEND_REACHABLE"
HEALTHY = "HEALTHY"

_MALFORMED_ALIASES = frozenset(
    {
        MALFORMED_RESPONSE,
        "MALFORMED_RECORD",
        "MOOMOO_PROTOCOL_ERROR",
        "MALFORMED_HISTORICAL_TRADES_PAYLOAD",
        "MALFORMED_HISTORICAL_TRADE_ROW",
    }
)
_TIMEOUT_ALIASES = frozenset({PROVIDER_TIMEOUT, "TIMEOUT", "REQUEST_TIMEOUT"})
_EMPTY_ALIASES = frozenset({EMPTY_PAYLOAD, "LIVE_CONNECTED_NO_DATA"})
_STALE_ALIASES = frozenset({PARTIALLY_STALE, "STALE", "DATA_STALE", "TTL_EXCEEDED"})
_DELAYED_ALIASES = frozenset({DELAYED_DATA, "DELAYED", "ENTITLED_DELAYED"})
_NETWORK_ALIASES = frozenset(
    {TEMPORARY_NETWORK_FAILURE, "PROVIDER_DISCONNECTED", "ECONNRESET", "CONNECTION_RESET"}
)

OPERATOR_MESSAGES: dict[str, str] = {
    OPEND_UNAVAILABLE: (
        "Moomoo OpenD is not reachable on loopback. Primary L1 quotes are "
        "unavailable. Yahoo delayed overlay is not hop L1 and is not substituted."
    ),
    DELAYED_DATA: (
        "Provider data is delayed, not real-time. It may be used only as an "
        "explicit delayed overlay, never as hop L1."
    ),
    PARTIALLY_STALE: (
        "Some quote fields are fresh while others are stale or missing. "
        "Incomplete fields are not filled from another source."
    ),
    SOURCE_DISAGREEMENT: (
        "Primary L1 and overlay snapshots disagree. Sources are kept distinct; "
        "values are not averaged or silently merged."
    ),
    RECONNECTING: (
        "The provider session dropped and is reconnecting. Prior-generation "
        "quotes are not treated as current."
    ),
    PROVIDER_TIMEOUT: (
        "The provider request timed out. No quote is invented; retry is observational only."
    ),
    EMPTY_PAYLOAD: (
        "The provider returned an empty payload. No last price is synthesized."
    ),
    MALFORMED_RESPONSE: (
        "The provider response could not be parsed. The payload is rejected fail-closed."
    ),
    TEMPORARY_NETWORK_FAILURE: (
        "A temporary network failure interrupted the provider. This is not a "
        "successful quote and does not authorize Live."
    ),
    RESTART_RECOVERY: (
        "The provider process or session restarted. Subscriptions must be "
        "re-established; recovered state is a new generation."
    ),
    FALLBACK_BLOCKED: (
        "Yahoo delayed overlay cannot replace OpenD as hop L1. Fallback to "
        "delayed-as-primary is blocked."
    ),
    OVERLAY_ALLOWED: (
        "Delayed overlay may be shown as overlay-only. It does not occupy the primary L1 slot."
    ),
    OPEND_REACHABLE: "Moomoo OpenD is reachable on loopback. Reachability is not a tick.",
    HEALTHY: "Primary observational provider connectivity looks healthy (software probe).",
    "OPEND_SDK_PRESENT": (
        "Moomoo OpenD is reachable and the vendor SDK is loadable. SDK presence is "
        "diagnostic only — not a quote and not FTEP evidence."
    ),
    "MOOMOO_SDK_MISSING": (
        "Moomoo OpenD is reachable on loopback but the vendor SDK is not available in "
        "this environment. Primary L1 quotes fail closed; Yahoo overlay is not hop L1."
    ),
    "OPEND_NON_LOOPBACK_BLOCKED": (
        "Moomoo OpenD must be configured on loopback only. Non-loopback endpoints are "
        "blocked for observational safety."
    ),
    "MOOMOO_AUTH_FAILURE": (
        "Moomoo OpenD rejected authentication. No quote is synthesized; check the "
        "operator session and entitlements."
    ),
    "MOOMOO_LAST_PRICE_MISSING": (
        "Moomoo OpenD returned a row without an honest last_price. Bid/ask/close are "
        "not substituted."
    ),
}

_ITEM9_UNTOUCHED = {
    "item9_sample_gate": "2/3",
    "item9_mode": "IDLE",
    "item9_calibration": "NOT_CALIBRATED",
    "live_execution": "OFF",
}


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    overlay_role_allowed: bool
    overlay_as_hop_l1: bool
    boundary_token: str
    overlay_provider_id: str = YAHOO_PROVIDER_ID
    primary_provider_id: str = MOOMOO_OPEND_PROVIDER_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary_token": self.boundary_token,
            "overlay_as_hop_l1": self.overlay_as_hop_l1,
            "overlay_provider_id": self.overlay_provider_id,
            "overlay_role_allowed": self.overlay_role_allowed,
            "primary_provider_id": self.primary_provider_id,
        }


@dataclass(frozen=True, slots=True)
class ProviderIncident:
    status_token: str
    operator_message: str
    fallback: FallbackDecision
    severity: str
    evidence_class: str = "SOFTWARE"
    details: dict[str, Any] = field(default_factory=dict)
    preserves_item9_idle: bool = True
    live_execution: str = "OFF"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status_token": self.status_token,
            "operator_message": self.operator_message,
            "severity": self.severity,
            "evidence_class": self.evidence_class,
            "fallback": self.fallback.to_dict(),
            "details": dict(self.details),
            "preserves_item9_idle": self.preserves_item9_idle,
            "live_execution": self.live_execution,
        }
        payload.update(_ITEM9_UNTOUCHED)
        return payload


@dataclass(frozen=True, slots=True)
class ProviderSessionState:
    generation: int
    connected: bool
    status_token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "connected": self.connected,
            "status_token": self.status_token,
        }


def operator_message_for(status_token: str) -> str:
    token = str(status_token or "").strip().upper()
    return OPERATOR_MESSAGES.get(
        token,
        f"Provider status {token or 'UNKNOWN'} — no fabricated market evidence.",
    )


def normalize_reason_token(reason_code: str | None) -> str | None:
    token = str(reason_code or "").strip().upper()
    if not token:
        return None
    if token in _MALFORMED_ALIASES:
        return MALFORMED_RESPONSE
    if token in _TIMEOUT_ALIASES:
        return PROVIDER_TIMEOUT
    if token in _EMPTY_ALIASES:
        return EMPTY_PAYLOAD
    if token in _STALE_ALIASES:
        return PARTIALLY_STALE
    if token in _DELAYED_ALIASES:
        return DELAYED_DATA
    if token in _NETWORK_ALIASES:
        return TEMPORARY_NETWORK_FAILURE
    if token in {"OPEND_UNAVAILABLE", "PROVIDER_UNREACHABLE", "PROVIDER_DOWN"}:
        return OPEND_UNAVAILABLE
    return token


def fallback_for_primary(
    *,
    primary_available: bool,
    promote_overlay_to_l1: bool = False,
    overlay_available: bool = False,
) -> FallbackDecision:
    if promote_overlay_to_l1:
        return FallbackDecision(
            overlay_role_allowed=overlay_available,
            overlay_as_hop_l1=False,
            boundary_token=FALLBACK_BLOCKED,
        )
    if primary_available:
        return FallbackDecision(
            overlay_role_allowed=True,
            overlay_as_hop_l1=False,
            boundary_token=OVERLAY_ALLOWED,
        )
    return FallbackDecision(
        overlay_role_allowed=overlay_available,
        overlay_as_hop_l1=False,
        boundary_token=FALLBACK_BLOCKED if not overlay_available else OVERLAY_ALLOWED,
    )


_PRIMARY_UNAVAILABLE_TOKENS = frozenset(
    {
        OPEND_UNAVAILABLE,
        PROVIDER_TIMEOUT,
        EMPTY_PAYLOAD,
        MALFORMED_RESPONSE,
        TEMPORARY_NETWORK_FAILURE,
        "MOOMOO_SDK_MISSING",
        "OPEND_NON_LOOPBACK_BLOCKED",
        "MOOMOO_AUTH_FAILURE",
        "MOOMOO_PROTOCOL_ERROR",
        "MOOMOO_LAST_PRICE_MISSING",
        FALLBACK_BLOCKED,
    }
)


def incident_for_reason_code(
    reason_code: str | None,
    *,
    promote_overlay_to_l1: bool = False,
    overlay_available: bool = True,
) -> ProviderIncident:
    """Map an adapter or discovery ``reason_code`` to an operator incident (offline-safe)."""

    token = normalize_reason_token(reason_code) or "UNKNOWN"
    primary_available = token not in _PRIMARY_UNAVAILABLE_TOKENS and token != "UNKNOWN"
    severity = "UNAVAILABLE"
    if token in {DELAYED_DATA}:
        severity = "DELAYED"
    elif token in {PARTIALLY_STALE}:
        severity = "STALE"
    elif token in {RECONNECTING, RESTART_RECOVERY}:
        severity = "RECOVERING"
    elif token in {OPEND_REACHABLE, HEALTHY, "OPEND_SDK_PRESENT"}:
        severity = "HEALTHY"
    return _incident(
        token,
        severity,
        primary_available=primary_available,
        overlay_available=overlay_available,
        promote=promote_overlay_to_l1,
    )


def classify_opend_connectivity(readiness: OpenDReadiness) -> ProviderIncident:
    if not readiness.loopback:
        token = "OPEND_NON_LOOPBACK_BLOCKED"
        return _incident(token, "UNAVAILABLE", primary_available=False)
    if not readiness.reachable:
        return _incident(
            OPEND_UNAVAILABLE,
            "UNAVAILABLE",
            primary_available=False,
            overlay_available=True,
        )
    return _incident(
        OPEND_REACHABLE,
        "HEALTHY",
        primary_available=True,
        overlay_available=True,
    )


def classify_provider_incident(incident: Mapping[str, Any]) -> ProviderIncident:
    """Classify a fixture/mock incident. Does not call the network."""

    scenario = str(incident.get("scenario") or "").strip().lower()
    reason = normalize_reason_token(
        str(incident.get("reason_code") or incident.get("status_token") or "")
    )
    promote = bool(incident.get("promote_overlay_to_l1"))
    overlay_available = bool(incident.get("overlay_available"))
    primary_available = bool(incident.get("primary_available"))

    if scenario in {"opend_unavailable", "opend-down"}:
        return _incident(OPEND_UNAVAILABLE, "UNAVAILABLE", primary_available=False, promote=promote)
    if scenario in {"delayed_data", "delayed"}:
        return _incident(
            DELAYED_DATA,
            "DELAYED",
            primary_available=primary_available,
            overlay_available=True,
            promote=promote,
        )
    if scenario in {"partially_stale", "partial-stale"}:
        return _incident(
            PARTIALLY_STALE,
            "STALE",
            primary_available=True,
            details={"fabricated_fields": False},
        )
    if scenario in {"source_disagreement", "disagreement"}:
        return classify_source_disagreement(incident)
    if scenario in {"reconnect", "reconnecting"}:
        return _incident(RECONNECTING, "RECOVERING", primary_available=False)
    if scenario in {"timeout"}:
        return _incident(PROVIDER_TIMEOUT, "UNAVAILABLE", primary_available=False)
    if scenario in {"empty_payload", "empty"}:
        return _incident(EMPTY_PAYLOAD, "UNAVAILABLE", primary_available=False)
    if scenario in {"malformed_response", "malformed"}:
        return _incident(MALFORMED_RESPONSE, "UNAVAILABLE", primary_available=False)
    if scenario in {"temporary_network_failure", "temp_network"}:
        return _incident(TEMPORARY_NETWORK_FAILURE, "UNAVAILABLE", primary_available=False)
    if scenario in {"restart_recovery", "restart"}:
        return _incident(RESTART_RECOVERY, "RECOVERING", primary_available=False)
    if scenario in {"fallback_blocked", "promote_overlay"}:
        return _incident(
            FALLBACK_BLOCKED,
            "UNAVAILABLE",
            primary_available=False,
            overlay_available=True,
            promote=True,
        )

    if reason:
        severity = "UNAVAILABLE"
        if reason in {DELAYED_DATA}:
            severity = "DELAYED"
        elif reason in {PARTIALLY_STALE}:
            severity = "STALE"
        elif reason in {RECONNECTING, RESTART_RECOVERY}:
            severity = "RECOVERING"
        elif reason in {OPEND_REACHABLE, HEALTHY}:
            severity = "HEALTHY"
        return _incident(
            reason,
            severity,
            primary_available=primary_available,
            overlay_available=overlay_available,
            promote=promote,
        )

    return _incident("UNKNOWN", "UNAVAILABLE", primary_available=False)


def classify_source_disagreement(incident: Mapping[str, Any]) -> ProviderIncident:
    primary = _as_float(incident.get("primary_last_price"))
    overlay = _as_float(incident.get("overlay_last_price"))
    tolerance = _as_float(incident.get("tolerance"))
    if tolerance is None:
        tolerance = 0.01
    disagree = (
        primary is not None
        and overlay is not None
        and abs(primary - overlay) > tolerance
    )
    if not disagree:
        return _incident(
            HEALTHY,
            "HEALTHY",
            primary_available=True,
            overlay_available=True,
            details={"merged": False, "disagreement": False},
        )
    return _incident(
        SOURCE_DISAGREEMENT,
        "DISAGREEMENT",
        primary_available=True,
        overlay_available=True,
        details={
            "merged": False,
            "disagreement": True,
            "primary_last_price": primary,
            "overlay_last_price": overlay,
            "primary_provider_id": MOOMOO_OPEND_PROVIDER_ID,
            "overlay_provider_id": YAHOO_PROVIDER_ID,
            "overlay_timeliness": YAHOO_TIMELINESS,
        },
    )


def note_disconnect(state: ProviderSessionState) -> ProviderSessionState:
    return ProviderSessionState(
        generation=state.generation,
        connected=False,
        status_token=RECONNECTING,
    )


def note_reconnect(state: ProviderSessionState) -> ProviderSessionState:
    return ProviderSessionState(
        generation=state.generation + 1,
        connected=True,
        status_token=RESTART_RECOVERY,
    )


def note_process_restart(state: ProviderSessionState) -> ProviderSessionState:
    return ProviderSessionState(
        generation=state.generation + 1,
        connected=False,
        status_token=RESTART_RECOVERY,
    )


def _incident(
    token: str,
    severity: str,
    *,
    primary_available: bool,
    overlay_available: bool = False,
    promote: bool = False,
    details: dict[str, Any] | None = None,
) -> ProviderIncident:
    fallback = fallback_for_primary(
        primary_available=primary_available,
        promote_overlay_to_l1=promote,
        overlay_available=overlay_available,
    )
    status = token
    if promote:
        status = FALLBACK_BLOCKED
    return ProviderIncident(
        status_token=status,
        operator_message=operator_message_for(status),
        fallback=fallback,
        severity=severity if not promote else "UNAVAILABLE",
        details=details or {},
    )


def _as_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


__all__ = [
    "DELAYED_DATA",
    "EMPTY_PAYLOAD",
    "FALLBACK_BLOCKED",
    "FallbackDecision",
    "HEALTHY",
    "MALFORMED_RESPONSE",
    "OPERATOR_MESSAGES",
    "OPEND_REACHABLE",
    "OPEND_UNAVAILABLE",
    "OVERLAY_ALLOWED",
    "PARTIALLY_STALE",
    "PROVIDER_TIMEOUT",
    "ProviderIncident",
    "ProviderSessionState",
    "RECONNECTING",
    "RESTART_RECOVERY",
    "SOURCE_DISAGREEMENT",
    "TEMPORARY_NETWORK_FAILURE",
    "classify_opend_connectivity",
    "classify_provider_incident",
    "incident_for_reason_code",
    "classify_source_disagreement",
    "fallback_for_primary",
    "normalize_reason_token",
    "note_disconnect",
    "note_process_restart",
    "note_reconnect",
    "operator_message_for",
]
