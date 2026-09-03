"""Replay observer hooks and bounded trace recording (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from .models import DeliveryAction, ReplayDeliveryEnvelope, ReplayTraceSummary


@runtime_checkable
class ReplayObserver(Protocol):
    def on_delivery(self, envelope: ReplayDeliveryEnvelope) -> None: ...

    def on_drop(self, envelope: ReplayDeliveryEnvelope) -> None: ...

    def on_decision(self, decision_time_ns: int) -> None: ...

    def on_snapshot(self, snapshot: SnapshotV1) -> None: ...

    def on_signal(self, signal: SignalV1) -> None: ...


@dataclass
class ReplayTraceRecorder:
    """Bounded optional trace with always-accurate summary counters."""

    max_entries: int | None = 1000
    summary: ReplayTraceSummary = field(default_factory=ReplayTraceSummary)
    deliveries: list[ReplayDeliveryEnvelope] = field(default_factory=list)
    drops: list[ReplayDeliveryEnvelope] = field(default_factory=list)

    def on_delivery(self, envelope: ReplayDeliveryEnvelope) -> None:
        if envelope.delivery_action in {DeliveryAction.DROP, DeliveryAction.DISCONNECT_DROP}:
            self.on_drop(envelope)
            return
        self.summary = ReplayTraceSummary(
            delivered_count=self.summary.delivered_count + 1,
            dropped_count=self.summary.dropped_count,
            delayed_count=self.summary.delayed_count
            + (1 if envelope.delivery_action in {DeliveryAction.DELAY, DeliveryAction.THROTTLE_DELAY} else 0),
            undelivered_count=self.summary.undelivered_count,
            decision_count=self.summary.decision_count,
            provider_disconnect_transitions=self.summary.provider_disconnect_transitions,
        )
        if self.max_entries is None or len(self.deliveries) < self.max_entries:
            self.deliveries.append(envelope)

    def on_drop(self, envelope: ReplayDeliveryEnvelope) -> None:
        self.summary = ReplayTraceSummary(
            delivered_count=self.summary.delivered_count,
            dropped_count=self.summary.dropped_count + 1,
            delayed_count=self.summary.delayed_count,
            undelivered_count=self.summary.undelivered_count,
            decision_count=self.summary.decision_count,
            provider_disconnect_transitions=self.summary.provider_disconnect_transitions,
        )
        if self.max_entries is None or len(self.drops) < self.max_entries:
            self.drops.append(envelope)

    def on_decision(self, decision_time_ns: int) -> None:
        _ = decision_time_ns
        self.summary = ReplayTraceSummary(
            delivered_count=self.summary.delivered_count,
            dropped_count=self.summary.dropped_count,
            delayed_count=self.summary.delayed_count,
            undelivered_count=self.summary.undelivered_count,
            decision_count=self.summary.decision_count + 1,
            provider_disconnect_transitions=self.summary.provider_disconnect_transitions,
        )

    def on_snapshot(self, snapshot: SnapshotV1) -> None:
        _ = snapshot

    def on_signal(self, signal: SignalV1) -> None:
        _ = signal

    def record_undelivered(self, count: int) -> None:
        self.summary = ReplayTraceSummary(
            delivered_count=self.summary.delivered_count,
            dropped_count=self.summary.dropped_count,
            delayed_count=self.summary.delayed_count,
            undelivered_count=self.summary.undelivered_count + count,
            decision_count=self.summary.decision_count,
            provider_disconnect_transitions=self.summary.provider_disconnect_transitions,
        )


class NullReplayObserver:
    def on_delivery(self, envelope: ReplayDeliveryEnvelope) -> None:
        _ = envelope

    def on_drop(self, envelope: ReplayDeliveryEnvelope) -> None:
        _ = envelope

    def on_decision(self, decision_time_ns: int) -> None:
        _ = decision_time_ns

    def on_snapshot(self, snapshot: SnapshotV1) -> None:
        _ = snapshot

    def on_signal(self, signal: SignalV1) -> None:
        _ = signal


__all__ = [
    "NullReplayObserver",
    "ReplayObserver",
    "ReplayTraceRecorder",
]
