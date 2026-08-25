"""BUILD 09 runtime request, result, and support models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..contracts import DetectionV1, EventV1, ForecastV1, SemanticEventType, SignalV1, SnapshotV1
from ..quality import QualityDecision
from .errors import DetectionInputError


class DetectorSupportStatus(StrEnum):
    IMPLEMENTED = "IMPLEMENTED"
    IMPLEMENTED_WITH_EXTERNAL_CONTEXT = "IMPLEMENTED_WITH_EXTERNAL_CONTEXT"
    INACTIVE_INPUT_UNAVAILABLE = "INACTIVE_INPUT_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DetectorSupport:
    semantic_event_type: SemanticEventType
    required_input: str
    status: DetectorSupportStatus
    implementation: str
    limitation: str = ""


@dataclass(frozen=True, slots=True)
class RegimeContext:
    previous_regime_key: str
    current_regime_key: str
    source_context_version: str

    def __post_init__(self) -> None:
        if not self.previous_regime_key or not self.current_regime_key:
            raise ValueError("REGIME_KEYS_REQUIRED")
        if not self.source_context_version:
            raise ValueError("REGIME_CONTEXT_VERSION_REQUIRED")


@dataclass(frozen=True, slots=True)
class DetectionFrame:
    snapshot: SnapshotV1
    signals: tuple[SignalV1, ...] = ()
    events: tuple[EventV1, ...] = ()
    quality_decision: QualityDecision | None = None
    regime_context: RegimeContext | None = None
    baseline_forecasts: tuple[ForecastV1, ...] = ()

    def __post_init__(self) -> None:
        if self.quality_decision is None:
            raise DetectionInputError("QUALITY_DECISION_REQUIRED")
        decision_time = self.snapshot.decision_time_ns
        if self.quality_decision.assessment.decision_time_ns != decision_time:
            raise DetectionInputError("QUALITY_DECISION_TIME_MISMATCH")
        snapshot_event_ids = {ref.id for ref in self.snapshot.source_event_refs}
        canonical_signals = tuple(sorted(self.signals, key=lambda row: (row.signal_type, row.signal_id)))
        canonical_events = tuple(sorted(self.events, key=lambda row: (row.available_time_ns, row.event_id)))
        canonical_forecasts = tuple(sorted(self.baseline_forecasts, key=lambda row: row.forecast_id))
        for signal in canonical_signals:
            ref = signal.source_snapshot_ref
            if ref is None or ref.id != self.snapshot.snapshot_id or ref.kind != "snapshot":
                raise DetectionInputError("SIGNAL_SNAPSHOT_MISMATCH")
            if signal.as_of_time_ns > decision_time:
                raise DetectionInputError("SIGNAL_TIME_VIOLATION")
        for event in canonical_events:
            if event.event_id not in snapshot_event_ids:
                raise DetectionInputError("EVENT_NOT_IN_SNAPSHOT")
            if event.available_time_ns > decision_time:
                raise DetectionInputError("EVENT_TIME_VIOLATION")
        for forecast in canonical_forecasts:
            if forecast.snapshot_id != self.snapshot.snapshot_id:
                raise DetectionInputError("FORECAST_SNAPSHOT_MISMATCH")
            if forecast.decision_time_ns > decision_time:
                raise DetectionInputError("FORECAST_TIME_VIOLATION")
        object.__setattr__(self, "signals", canonical_signals)
        object.__setattr__(self, "events", canonical_events)
        object.__setattr__(self, "baseline_forecasts", canonical_forecasts)


@dataclass(frozen=True, slots=True)
class DetectionEngineResult:
    detections: tuple[DetectionV1, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DetectorStateSnapshot:
    scope_count: int
    scope_keys: tuple[str, ...]
    seen_news_event_count: int = 0


__all__ = [
    "DetectionEngineResult",
    "DetectionFrame",
    "DetectorStateSnapshot",
    "DetectorSupport",
    "DetectorSupportStatus",
    "RegimeContext",
]
