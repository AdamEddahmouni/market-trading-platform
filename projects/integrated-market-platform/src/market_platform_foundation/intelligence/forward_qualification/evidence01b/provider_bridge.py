"""Provider bridge connecting market data to campaign observations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..evidence01a.types import CampaignEvidenceOrigin


class ProviderEventHandler(Protocol):
    def on_provider_event(
        self,
        *,
        instrument_id: str,
        quality_state: str,
        provider_connected: bool,
        event_time_ns: int,
        received_time_ns: int,
        provider_id: str,
        provider_capability: str,
        provider_event_id: str | None,
        metadata: dict[str, Any],
    ) -> None: ...


@dataclass
class ProviderEventV1:
    instrument_id: str
    quality_state: str
    provider_connected: bool
    event_time_ns: int
    received_time_ns: int
    provider_id: str
    provider_capability: str
    provider_event_id: str | None = None
    provider_sequence: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeProviderAdapter:
    """Deterministic fake provider for tests."""

    provider_id: str = "FAKE_PROVIDER"
    connected: bool = True
    _seen_event_ids: set[str] = field(default_factory=set)
    events_received: int = 0
    events_accepted: int = 0
    duplicate_events: int = 0

    def ingest_event(self, event: ProviderEventV1) -> bool:
        self.events_received += 1
        if not self.connected:
            return False
        dedup_key = event.provider_event_id or f"{event.instrument_id}:{event.event_time_ns}:{event.provider_capability}"
        if dedup_key in self._seen_event_ids:
            self.duplicate_events += 1
            return False
        self._seen_event_ids.add(dedup_key)
        self.events_accepted += 1
        return True

    def disconnect(self) -> None:
        self.connected = False

    def reconnect(self) -> None:
        self.connected = True


def map_runtime_admission_to_quality(admission_result: dict[str, Any]) -> tuple[str, bool]:
    """Map LiveObservationalRuntime admission result to campaign quality state."""
    admission = admission_result.get("admission") or {}
    display = str(admission.get("display") or "BLOCKED")
    quality = admission_result.get("quality") or {}
    quality_state = str(quality.get("state") or "GOOD")
    provider_connected = display != "BLOCKED" or quality_state != "PROVIDER_DISCONNECTED"
    if display == "BLOCKED":
        blocking = quality.get("blocking_reasons") or []
        if "CLOCK_DRIFT" in blocking:
            return "CLOCK_DRIFT", False
        if "PROVIDER_DISCONNECTED" in blocking:
            return "PROVIDER_DISCONNECTED", False
        return quality_state, False
    if quality_state in {"GOOD", "DEGRADED"}:
        return quality_state, provider_connected
    return quality_state, provider_connected


def build_provider_provenance(
    event: ProviderEventV1,
    *,
    campaign_id: str,
    session_id: str,
    evidence_origin: CampaignEvidenceOrigin,
) -> dict[str, Any]:
    return {
        "provider_id": event.provider_id,
        "provider_capability": event.provider_capability,
        "provider_event_timestamp": event.event_time_ns,
        "provider_received_timestamp": event.received_time_ns,
        "normalized_event_time": event.event_time_ns,
        "normalized_available_time": event.received_time_ns,
        "quality_state": event.quality_state,
        "symbol": event.instrument_id,
        "campaign_id": campaign_id,
        "session_id": session_id,
        "evidence_origin": evidence_origin.value,
        "provider_event_id": event.provider_event_id,
        "provider_sequence": event.provider_sequence,
    }


def ingest_runtime_record(
    record: dict[str, Any],
    admission_result: dict[str, Any],
    *,
    provider_id: str = "MOOMOO",
) -> ProviderEventV1 | None:
    clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
    event_time_ns = int(clocks.get("event_time_ns") or clocks.get("provider_event_time_ns") or 0)
    received_time_ns = int(clocks.get("received_time_ns") or time.time_ns())
    instrument_id = str(record.get("instrument_id") or "").upper()
    if not instrument_id:
        return None
    quality_state, provider_connected = map_runtime_admission_to_quality(admission_result)
    capability = str(record.get("capability") or record.get("record_type") or "QUOTE")
    return ProviderEventV1(
        instrument_id=instrument_id,
        quality_state=quality_state,
        provider_connected=provider_connected,
        event_time_ns=event_time_ns,
        received_time_ns=received_time_ns,
        provider_id=provider_id,
        provider_capability=capability,
        provider_event_id=record.get("provider_event_id"),
        provider_sequence=record.get("provider_sequence"),
        metadata={"admission": admission_result.get("admission")},
    )
