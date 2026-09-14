"""Side collector for production-path hot-path clocks (aggregate-only, optional)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from market_platform_foundation.intelligence.contracts.detection import DetectionV1
from market_platform_foundation.intelligence.contracts.event import EventV1
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.observation_ingress.types import (
    IngressDispatchContext,
    IngressDispatchReceiptV1,
)

from .clock_row import HotPathClockRow


@runtime_checkable
class HotPathIngressDispatchObserver(Protocol):
    def on_dispatch(
        self,
        event: EventV1,
        receipt: IngressDispatchReceiptV1,
        context: IngressDispatchContext,
    ) -> None: ...


@dataclass
class HotPathClockCollector(HotPathIngressDispatchObserver):
    """In-memory side observer; safe to attach to ingress dispatch."""

    rows: dict[str, HotPathClockRow] = field(default_factory=dict)
    detection_rows: list[HotPathClockRow] = field(default_factory=list)

    def row_for_event(self, event_id: str) -> HotPathClockRow:
        existing = self.rows.get(event_id)
        if existing is not None:
            return existing
        row = HotPathClockRow(correlation_id=event_id)
        self.rows[event_id] = row
        return row

    def note_normalized_event(self, event: EventV1, *, normalized_at_ns: int | None = None) -> None:
        row = self.row_for_event(event.event_id)
        row.source_event_at = event.event_time_ns
        row.provider_received_at = event.provider_time_ns
        row.imp_received_at = event.received_time_ns
        row.normalized_at = normalized_at_ns if normalized_at_ns is not None else event.available_time_ns

    def on_dispatch(
        self,
        event: EventV1,
        receipt: IngressDispatchReceiptV1,
        context: IngressDispatchContext,
    ) -> None:
        row = self.row_for_event(event.event_id)
        self.note_normalized_event(event)
        row.router_dispatched_at = receipt.dispatch_time_ns

    def note_detection(self, detection: DetectionV1, *, correlation_id: str | None = None) -> None:
        key = correlation_id or detection.detection_id
        row = HotPathClockRow(correlation_id=key, detected_at=detection.detected_at_ns)
        self.detection_rows.append(row)

    def note_opportunity(self, opportunity: OpportunityV1) -> None:
        row = HotPathClockRow(
            correlation_id=opportunity.opportunity_id,
            opportunity_created_at=opportunity.created_at_ns,
        )
        self.detection_rows.append(row)

    def note_operator_surfaced(self, opportunity_id: str, surfaced_at_ns: int) -> None:
        row = HotPathClockRow(
            correlation_id=opportunity_id,
            operator_surfaced_at=surfaced_at_ns,
        )
        self.detection_rows.append(row)

    def all_rows(self) -> tuple[HotPathClockRow, ...]:
        return tuple(self.rows.values()) + tuple(self.detection_rows)


__all__ = ["HotPathClockCollector", "HotPathIngressDispatchObserver"]
