"""ReplayObserver hook for hot-path delivery and quality telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field

from market_platform_foundation.intelligence.contracts.signal import SignalV1
from market_platform_foundation.intelligence.contracts.snapshot import SnapshotV1
from market_platform_foundation.intelligence.replay.models import ReplayDeliveryEnvelope
from market_platform_foundation.intelligence.replay.observer import ReplayObserver

from .models import HotPathQualityCounters
from .quality_mapping import apply_delivery_action


@dataclass
class HotPathTelemetryObserver:
    """Collects replay delivery actions for offline baseline aggregation."""

    inner: ReplayObserver | None = None
    deliveries: list[ReplayDeliveryEnvelope] = field(default_factory=list)
    drops: list[ReplayDeliveryEnvelope] = field(default_factory=list)
    decision_times_ns: list[int] = field(default_factory=list)
    quality_counters: HotPathQualityCounters = field(default_factory=HotPathQualityCounters)

    def on_delivery(self, envelope: ReplayDeliveryEnvelope) -> None:
        self.deliveries.append(envelope)
        self.quality_counters = apply_delivery_action(self.quality_counters, envelope.delivery_action)
        if self.inner is not None:
            self.inner.on_delivery(envelope)

    def on_drop(self, envelope: ReplayDeliveryEnvelope) -> None:
        self.drops.append(envelope)
        self.quality_counters = apply_delivery_action(self.quality_counters, envelope.delivery_action)
        if self.inner is not None:
            self.inner.on_drop(envelope)

    def on_decision(self, decision_time_ns: int) -> None:
        self.decision_times_ns.append(decision_time_ns)
        if self.inner is not None:
            self.inner.on_decision(decision_time_ns)

    def on_snapshot(self, snapshot: SnapshotV1) -> None:
        if self.inner is not None:
            self.inner.on_snapshot(snapshot)

    def on_signal(self, signal: SignalV1) -> None:
        if self.inner is not None:
            self.inner.on_signal(signal)

    def snapshot_quality_counters(self) -> HotPathQualityCounters:
        return self.quality_counters


__all__ = ["HotPathTelemetryObserver"]
