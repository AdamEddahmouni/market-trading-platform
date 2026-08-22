"""Provider connection lifecycle — distinct from data health."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderConnectionState(StrEnum):
    DISABLED = "DISABLED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    CONNECTED_DEGRADED = "CONNECTED_DEGRADED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    ENTITLEMENT_MISSING = "ENTITLEMENT_MISSING"
    ERROR = "ERROR"


@dataclass
class ProviderLifecycle:
    provider_id: str = "moomoo.opend.observational"
    provider_role: str = "MARKET_DATA"
    connection_state: ProviderConnectionState = ProviderConnectionState.DISABLED
    provider_generation_id: int = 0
    last_successful_event_ns: int | None = None
    last_received_ns: int | None = None
    reconnect_count: int = 0
    last_error: str | None = None
    entitlement_state: str = "UNKNOWN"
    quota_used: int = 0
    quota_available: int = 100
    sdk_version: str | None = None
    opend_version: str | None = None
    execution_use: str = "DISPLAY_ONLY"
    active_subscriptions: list[dict[str, Any]] = field(default_factory=list)
    feed_metrics: dict[str, Any] = field(default_factory=dict)

    def mark_connected(self, *, quota_available: int | None = None, provider_generation_id: int | None = None) -> None:
        if provider_generation_id is not None:
            self.provider_generation_id = provider_generation_id
        if self.connection_state == ProviderConnectionState.RECONNECTING:
            self.reconnect_count += 1
        self.connection_state = ProviderConnectionState.CONNECTED_DEGRADED
        if quota_available is not None:
            self.quota_available = quota_available
        self.last_error = None

    def mark_degraded(self, reason: str) -> None:
        self.connection_state = ProviderConnectionState.CONNECTED_DEGRADED
        self.last_error = reason

    def mark_disconnected(self, reason: str) -> None:
        self.connection_state = ProviderConnectionState.DISCONNECTED
        self.last_error = reason

    def mark_reconnecting(self) -> None:
        self.connection_state = ProviderConnectionState.RECONNECTING

    def record_event(self, received_ns: int) -> None:
        self.last_received_ns = received_ns
        self.last_successful_event_ns = received_ns

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_subscriptions": list(self.active_subscriptions),
            "connection_state": self.connection_state.value,
            "entitlement_state": self.entitlement_state,
            "execution_use": self.execution_use,
            "feed_metrics": dict(self.feed_metrics),
            "last_error": self.last_error,
            "last_received_ns": self.last_received_ns,
            "last_successful_event_ns": self.last_successful_event_ns,
            "opend_version": self.opend_version,
            "provider_generation_id": self.provider_generation_id,
            "provider_id": self.provider_id,
            "provider_role": self.provider_role,
            "quota_available": self.quota_available,
            "quota_used": self.quota_used,
            "reconnect_count": self.reconnect_count,
            "sdk_version": self.sdk_version,
        }
