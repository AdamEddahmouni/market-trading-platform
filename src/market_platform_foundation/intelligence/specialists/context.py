"""Specialist execution context — blind first-pass input boundary."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import (
    DetectionV1,
    EventV1,
    InferenceJobV1,
    RoutingDecisionV1,
    SignalV1,
    SnapshotV1,
)
from .policy import MicrostructureSpecialistPolicyV1


@dataclass(frozen=True, slots=True)
class SpecialistExecutionContext:
    """Immutable specialist input envelope.

    Contains only explicitly frozen upstream artifacts. No repository expansion,
    no other expert evidence, no baseline forecasts, and no future labels.
    """

    job: InferenceJobV1
    route: RoutingDecisionV1
    detection: DetectionV1
    snapshot: SnapshotV1
    signals: tuple[SignalV1, ...]
    events: tuple[EventV1, ...] = ()
    policy: MicrostructureSpecialistPolicyV1 | None = None


__all__ = ["SpecialistExecutionContext"]
