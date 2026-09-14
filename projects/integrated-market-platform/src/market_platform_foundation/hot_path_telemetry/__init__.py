"""Additive hot-path latency and quality telemetry (Phase 2 Lane D)."""

from .baseline import build_replay_latency_baseline
from .software_wired import build_software_wired_document
from .models import (
    HOT_PATH_TIMESTAMP_NAMES,
    HotPathQualityCounters,
    ReplayLatencyBaselineDocument,
    TimestampExerciseClass,
    timestamp_exercise_classes,
)
from .observer import HotPathTelemetryObserver

__all__ = [
    "HOT_PATH_TIMESTAMP_NAMES",
    "HotPathQualityCounters",
    "HotPathTelemetryObserver",
    "ReplayLatencyBaselineDocument",
    "TimestampExerciseClass",
    "build_replay_latency_baseline",
    "build_software_wired_document",
    "timestamp_exercise_classes",
]
