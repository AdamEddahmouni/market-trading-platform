"""Per-capability live provider evidence (G11.1).

Separates safety-gate state from measured provider capability truth.
Evidence is applied to ``RuntimeCapabilityRegistry`` without inferring one
capability from another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .runtime_capability import (
    DataTimeliness,
    EntitlementState,
    ProviderHealth,
    ProviderRuntimeState,
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)


class LiveCapabilityResult(StrEnum):
    LIVE_PROVIDER_VERIFIED = "LIVE_PROVIDER_VERIFIED"
    LIVE_CONNECTED_NOT_ENTITLED = "LIVE_CONNECTED_NOT_ENTITLED"
    LIVE_CONNECTED_NO_DATA = "LIVE_CONNECTED_NO_DATA"
    LIVE_REQUEST_FAILED = "LIVE_REQUEST_FAILED"
    LIVE_DATA_STALE = "LIVE_DATA_STALE"
    LIVE_NORMALIZATION_FAILED = "LIVE_NORMALIZATION_FAILED"
    LIVE_NOT_ATTEMPTED = "LIVE_NOT_ATTEMPTED"


@dataclass(frozen=True, slots=True)
class CapabilityLiveEvidenceRow:
    capability_id: str
    connection: bool = False
    request_accepted: bool = False
    data_received: bool = False
    entitlement: str = "UNKNOWN"
    freshness: str = "UNKNOWN"
    canonical_normalization: bool = False
    result: LiveCapabilityResult = LiveCapabilityResult.LIVE_NOT_ATTEMPTED
    timeliness: DataTimeliness = DataTimeliness.UNKNOWN
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "connection": self.connection,
            "request_accepted": self.request_accepted,
            "data_received": self.data_received,
            "entitlement": self.entitlement,
            "freshness": self.freshness,
            "canonical_normalization": self.canonical_normalization,
            "result": self.result.value,
            "timeliness": self.timeliness.value,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class CapabilityRuntimeOverride:
    """Per-capability runtime axes — never inferred across capabilities."""

    live_verified: bool = False
    entitlement: EntitlementState = EntitlementState.UNKNOWN
    timeliness: DataTimeliness = DataTimeliness.UNKNOWN
    health: ProviderHealth = ProviderHealth.UNKNOWN
    runtime_state: RuntimeCapabilityState | None = None
    reason_code: str | None = None


def _entitlement_from_label(label: str) -> EntitlementState:
    normalized = (label or "").strip().upper()
    mapping = {
        "ENTITLED_REALTIME": EntitlementState.ENTITLED,
        "ENTITLED": EntitlementState.ENTITLED,
        "ENTITLED_DELAYED": EntitlementState.DELAYED,
        "DELAYED": EntitlementState.DELAYED,
        "NOT_ENTITLED": EntitlementState.NOT_ENTITLED,
        "ERROR": EntitlementState.ERROR,
    }
    return mapping.get(normalized, EntitlementState.UNKNOWN)


def _timeliness_from_row(row: CapabilityLiveEvidenceRow) -> DataTimeliness:
    if row.timeliness != DataTimeliness.UNKNOWN:
        return row.timeliness
    freshness = (row.freshness or "").strip().upper()
    if freshness in {"REALTIME", "REAL_TIME", "FRESH"}:
        return DataTimeliness.REAL_TIME
    if freshness in {"DELAYED", "DELAYED_DATA"}:
        return DataTimeliness.DELAYED
    if freshness in {"STALE", "TTL_EXCEEDED"}:
        return DataTimeliness.STALE
    entitlement = (row.entitlement or "").strip().upper()
    if entitlement == "ENTITLED_DELAYED":
        return DataTimeliness.DELAYED
    return DataTimeliness.UNKNOWN


def _runtime_state_from_result(result: LiveCapabilityResult) -> RuntimeCapabilityState:
    mapping = {
        LiveCapabilityResult.LIVE_PROVIDER_VERIFIED: RuntimeCapabilityState.READY,
        LiveCapabilityResult.LIVE_CONNECTED_NOT_ENTITLED: RuntimeCapabilityState.NOT_ENTITLED,
        LiveCapabilityResult.LIVE_CONNECTED_NO_DATA: RuntimeCapabilityState.UNAVAILABLE,
        LiveCapabilityResult.LIVE_REQUEST_FAILED: RuntimeCapabilityState.PROVIDER_UNAVAILABLE,
        LiveCapabilityResult.LIVE_DATA_STALE: RuntimeCapabilityState.STALE,
        LiveCapabilityResult.LIVE_NORMALIZATION_FAILED: RuntimeCapabilityState.DEGRADED,
        LiveCapabilityResult.LIVE_NOT_ATTEMPTED: RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED,
    }
    return mapping[result]


def override_from_evidence(row: CapabilityLiveEvidenceRow) -> CapabilityRuntimeOverride:
    entitlement = _entitlement_from_label(row.entitlement)
    timeliness = _timeliness_from_row(row)
    runtime_state = _runtime_state_from_result(row.result)
    health = ProviderHealth.HEALTHY if row.connection else ProviderHealth.UNKNOWN
    if row.result == LiveCapabilityResult.LIVE_REQUEST_FAILED:
        health = ProviderHealth.DOWN
    elif row.result in {
        LiveCapabilityResult.LIVE_CONNECTED_NO_DATA,
        LiveCapabilityResult.LIVE_NORMALIZATION_FAILED,
    }:
        health = ProviderHealth.DEGRADED
    live_verified = row.result is LiveCapabilityResult.LIVE_PROVIDER_VERIFIED
    return CapabilityRuntimeOverride(
        live_verified=live_verified,
        entitlement=entitlement,
        timeliness=timeliness,
        health=health,
        runtime_state=runtime_state,
        reason_code=row.result.value,
    )


def apply_live_evidence(
    registry: RuntimeCapabilityRegistry,
    provider_id: str,
    rows: Mapping[str, CapabilityLiveEvidenceRow],
) -> None:
    """Apply measured per-capability evidence to the runtime registry."""

    for capability_id, row in rows.items():
        registry.set_capability_override(
            provider_id,
            capability_id,
            override_from_evidence(row),
        )

    any_connected = any(row.connection for row in rows.values())
    any_verified = any(
        row.result is LiveCapabilityResult.LIVE_PROVIDER_VERIFIED for row in rows.values()
    )
    notes = "LIVE_PROVIDER_UNVERIFIED"
    if any_verified:
        notes = "LIVE_PARTIAL_VERIFIED"
    registry.set_runtime_state(
        ProviderRuntimeState(
            provider_id=provider_id,
            health=ProviderHealth.HEALTHY if any_connected else ProviderHealth.UNKNOWN,
            entitlement=EntitlementState.UNKNOWN,
            timeliness=DataTimeliness.UNKNOWN,
            live_verified=False,
            notes=notes,
        )
    )


__all__ = [
    "CapabilityLiveEvidenceRow",
    "CapabilityRuntimeOverride",
    "LiveCapabilityResult",
    "apply_live_evidence",
    "override_from_evidence",
]
