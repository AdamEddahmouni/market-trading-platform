"""Operational provider and capability registry."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


class ProviderRegistryError(ValueError):
    """Raised when provider metadata is invalid or ambiguous."""


_LICENSE_CLASSES = frozenset(
    {"PUBLIC", "RESEARCH_ONLY", "COMMERCIAL", "INTERNAL_ONLY", "RESTRICTED", "UNKNOWN"}
)
_CREDENTIAL_REF = re.compile(r"^(?:ENV|FILE|SECRET_REF):[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    asset_classes: tuple[str, ...]
    venues: tuple[str, ...]
    interfaces: tuple[str, ...]
    supports_history: bool
    supports_pit: bool
    freshness_sla_ns: int | None
    license_class: str
    rate_policy_id: str
    normalizer_version: str


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: tuple[CapabilityDescriptor, ...]
    health_state: str
    credential_refs: tuple[str, ...]
    schema_versions: tuple[str, ...]
    priority: int = 100


class ProviderRegistry:
    """Validated, deterministic metadata registry independent of composition."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderDescriptor] = {}

    def register(self, provider: ProviderDescriptor) -> None:
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ProviderRegistryError("PROVIDER_ID_REQUIRED")
        if provider_id in self._providers:
            raise ProviderRegistryError("PROVIDER_ID_DUPLICATE")
        if provider.priority < 0:
            raise ProviderRegistryError("PROVIDER_PRIORITY_INVALID")
        self._validate_provider(provider)
        self._providers[provider_id] = provider

    def providers_for(self, capability_id: str) -> list[ProviderDescriptor]:
        result = [
            provider
            for provider in self._providers.values()
            if any(capability.capability_id == capability_id for capability in provider.capabilities)
        ]
        return sorted(result, key=lambda item: (item.priority, item.provider_id))

    def validate(self) -> dict[str, int | str]:
        for provider in self._providers.values():
            self._validate_provider(provider)
        return {
            "provider_count": len(self._providers),
            "capability_count": sum(len(item.capabilities) for item in self._providers.values()),
            "schema_version": "1.0",
        }

    def manifest(self) -> dict[str, Any]:
        return {
            "logical_id": "providers.operational_registry",
            "schema_version": "1.0",
            "providers": [
                {
                    "capabilities": sorted(cap.capability_id for cap in provider.capabilities),
                    "health_state": provider.health_state,
                    "priority": provider.priority,
                    "provider_id": provider.provider_id,
                }
                for provider in sorted(self._providers.values(), key=lambda item: item.provider_id)
            ],
        }

    def _validate_provider(self, provider: ProviderDescriptor) -> None:
        if not provider.display_name.strip():
            raise ProviderRegistryError("PROVIDER_DISPLAY_NAME_REQUIRED")
        for credential_ref in provider.credential_refs:
            if not _CREDENTIAL_REF.fullmatch(credential_ref):
                raise ProviderRegistryError("CREDENTIAL_REF_INVALID")
        if not provider.schema_versions:
            raise ProviderRegistryError("SCHEMA_VERSION_REQUIRED")
        capability_ids = [item.capability_id for item in provider.capabilities]
        if any(not item for item in capability_ids):
            raise ProviderRegistryError("CAPABILITY_ID_REQUIRED")
        if len(capability_ids) != len(set(capability_ids)):
            raise ProviderRegistryError("CAPABILITY_ID_DUPLICATE")
        for capability in provider.capabilities:
            if capability.freshness_sla_ns is not None and capability.freshness_sla_ns < 0:
                raise ProviderRegistryError("CAPABILITY_FRESHNESS_INVALID")
            if not capability.license_class.strip():
                raise ProviderRegistryError("CAPABILITY_LICENSE_REQUIRED")
            if capability.license_class.strip().upper() not in _LICENSE_CLASSES:
                raise ProviderRegistryError("CAPABILITY_LICENSE_INVALID")
            if not capability.rate_policy_id.strip():
                raise ProviderRegistryError("CAPABILITY_RATE_POLICY_REQUIRED")
            if not capability.normalizer_version.strip():
                raise ProviderRegistryError("CAPABILITY_NORMALIZER_VERSION_REQUIRED")


__all__ = [
    "CapabilityDescriptor",
    "ProviderDescriptor",
    "ProviderRegistry",
    "ProviderRegistryError",
]
