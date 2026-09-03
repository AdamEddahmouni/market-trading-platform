"""Provider capability registry.

Tracks what each configured provider can and cannot do based on actual probe results,
not on the existence of adapter code. Every capability is independently tracked per
provider so the screener can select providers per field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Capability(StrEnum):
    """Granular provider capabilities, each independently tracked."""
    DISCOVERY = "DISCOVERY"
    REALTIME_QUOTE = "REALTIME_QUOTE"
    DELAYED_QUOTE = "DELAYED_QUOTE"
    HISTORICAL_BARS = "HISTORICAL_BARS"
    VOLUME = "VOLUME"
    RELATIVE_VOLUME = "RELATIVE_VOLUME"
    FLOAT = "FLOAT"
    SHARES_OUTSTANDING = "SHARES_OUTSTANDING"
    SHORT_FLOAT = "SHORT_FLOAT"
    SHORT_RATIO = "SHORT_RATIO"
    SHORT_INTEREST = "SHORT_INTEREST"
    DAYS_TO_COVER = "DAYS_TO_COVER"
    BORROW_FEE = "BORROW_FEE"
    SHORTABLE_SHARES = "SHORTABLE_SHARES"
    SHORTABILITY = "SHORTABILITY"
    NEWS = "NEWS"
    FILINGS = "FILINGS"
    HALTS = "HALTS"
    SENTIMENT = "SENTIMENT"
    FUNDAMENTALS = "FUNDAMENTALS"
    MARKET_CAP = "MARKET_CAP"


class CapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    PERMISSION_UNAVAILABLE = "PERMISSION_UNAVAILABLE"
    NOT_CONFIGURED = "NOT CONFIGURED"
    NOT_SUPPORTED = "NOT SUPPORTED"
    ERROR = "ERROR"
    STALE = "STALE"
    UNTESTED = "UNTESTED"


@dataclass(slots=True)
class CapabilityEntry:
    capability: Capability
    status: CapabilityStatus = CapabilityStatus.UNTESTED
    detail: str = ""
    last_probed_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": str(self.capability),
            "status": str(self.status),
            "detail": self.detail,
            "last_probed_at": self.last_probed_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
        }


@dataclass(slots=True)
class ProviderCapabilities:
    provider: str
    configured: bool = False
    connected: bool = False
    capabilities: dict[Capability, CapabilityEntry] = field(default_factory=dict)
    last_successful_call: str | None = None
    last_error: str | None = None
    missing_config_keys: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.capabilities:
            for cap in Capability:
                self.capabilities[cap] = CapabilityEntry(capability=cap)

    def set_available(self, *capabilities: Capability, detail: str = "") -> None:
        now = _now()
        for cap in capabilities:
            entry = self.capabilities.setdefault(cap, CapabilityEntry(capability=cap))
            entry.status = CapabilityStatus.AVAILABLE
            entry.detail = detail
            entry.last_success_at = now
            entry.last_probed_at = now

    def set_permission_unavailable(self, *capabilities: Capability, detail: str = "") -> None:
        now = _now()
        for cap in capabilities:
            entry = self.capabilities.setdefault(cap, CapabilityEntry(capability=cap))
            entry.status = CapabilityStatus.PERMISSION_UNAVAILABLE
            entry.detail = detail
            entry.last_error = detail
            entry.last_probed_at = now

    def set_not_supported(self, *capabilities: Capability, detail: str = "") -> None:
        for cap in capabilities:
            entry = self.capabilities.setdefault(cap, CapabilityEntry(capability=cap))
            entry.status = CapabilityStatus.NOT_SUPPORTED
            entry.detail = detail

    def set_not_configured(self, *capabilities: Capability, detail: str = "") -> None:
        for cap in capabilities:
            entry = self.capabilities.setdefault(cap, CapabilityEntry(capability=cap))
            entry.status = CapabilityStatus.NOT_CONFIGURED
            entry.detail = detail

    def set_error(self, capability: Capability, detail: str) -> None:
        entry = self.capabilities.setdefault(capability, CapabilityEntry(capability=capability))
        entry.status = CapabilityStatus.ERROR
        entry.detail = detail
        entry.last_error = detail
        entry.last_probed_at = _now()

    def status(self, capability: Capability) -> CapabilityStatus:
        return self.capabilities.get(capability, CapabilityEntry(capability=capability)).status

    def is_available(self, capability: Capability) -> bool:
        return self.status(capability) == CapabilityStatus.AVAILABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "connected": self.connected,
            "capabilities": {
                str(cap): entry.as_dict()
                for cap, entry in sorted(self.capabilities.items(), key=lambda x: str(x[0]))
            },
            "last_successful_call": self.last_successful_call,
            "last_error": self.last_error,
            "missing_config_keys": list(self.missing_config_keys),
        }


class ProviderCapabilityRegistry:
    """Central registry tracking all providers and their capabilities."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderCapabilities] = {}

    def register(self, provider: ProviderCapabilities) -> None:
        self._providers[provider.provider] = provider

    def get(self, provider: str) -> ProviderCapabilities | None:
        return self._providers.get(provider)

    def providers(self) -> dict[str, ProviderCapabilities]:
        return dict(self._providers)

    def find_available(self, capability: Capability) -> list[str]:
        return [
            p.provider for p in self._providers.values()
            if p.is_available(capability)
        ]

    def best_provider(self, capability: Capability, *, preferred: list[str] | None = None) -> str | None:
        available = self.find_available(capability)
        if not available:
            return None
        if preferred:
            for name in preferred:
                if name in available:
                    return name
        return available[0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "providers": {name: p.as_dict() for name, p in self._providers.items()},
            "generated_at": _now(),
        }


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


# -------------------------------------------------------- field selection


class FieldSelectionReason(StrEnum):
    FRESHER = "FRESHER"
    HIGHER_PRIORITY_CONFIGURED_SOURCE = "HIGHER_PRIORITY_CONFIGURED_SOURCE"
    BETTER_SEMANTIC_MATCH = "BETTER_SEMANTIC_MATCH"
    PRIMARY_SOURCE = "PRIMARY_SOURCE"
    ONLY_AVAILABLE = "ONLY_AVAILABLE"


@dataclass(frozen=True, slots=True)
class FieldSource:
    field: str
    provider: str
    value: Any
    event_time: str | None
    received_time: str | None
    freshness: str
    evidence_mode: str
    selection_reason: FieldSelectionReason
    status: str
    missing_reason: str | None = None


def field_source_dict(source: FieldSource) -> dict[str, Any]:
    return {
        "field": source.field,
        "provider": source.provider,
        "value": source.value,
        "event_time": source.event_time,
        "received_time": source.received_time,
        "freshness": source.freshness,
        "evidence_mode": source.evidence_mode,
        "selection_reason": str(source.selection_reason),
        "status": source.status,
        "missing_reason": source.missing_reason,
    }


__all__ = [
    "Capability",
    "CapabilityEntry",
    "CapabilityStatus",
    "FieldSelectionReason",
    "FieldSource",
    "ProviderCapabilities",
    "ProviderCapabilityRegistry",
    "field_source_dict",
]
