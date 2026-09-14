"""Per-correlation hot-path clock snapshots (missing fields stay None)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HotPathClockRow:
    """One logical hot-path correlation; never zero-fills missing clocks."""

    correlation_id: str
    source_event_at: int | None = None
    provider_received_at: int | None = None
    imp_received_at: int | None = None
    normalized_at: int | None = None
    router_dispatched_at: int | None = None
    detected_at: int | None = None
    opportunity_created_at: int | None = None
    operator_surfaced_at: int | None = None

    def as_timestamp_map(self) -> dict[str, int | None]:
        return {
            "source_event_at": self.source_event_at,
            "provider_received_at": self.provider_received_at,
            "imp_received_at": self.imp_received_at,
            "normalized_at": self.normalized_at,
            "router_dispatched_at": self.router_dispatched_at,
            "detected_at": self.detected_at,
            "opportunity_created_at": self.opportunity_created_at,
            "operator_surfaced_at": self.operator_surfaced_at,
        }


__all__ = ["HotPathClockRow"]
