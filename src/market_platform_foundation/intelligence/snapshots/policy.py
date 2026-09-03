"""Snapshot composition request and policy types (BUILD 05)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import IntelligenceScope, validate_timestamp_ns
from ..quality.models import RequirementSet


BUILDER_COMPONENT_ID = "snapshot-builder"
BUILDER_COMPONENT_VERSION = "1"


@dataclass(frozen=True, slots=True)
class SnapshotCompositionPolicy:
    """Bounded, typed selection policy for snapshot assembly."""

    policy_id: str = "default"
    policy_version: str = "1"
    max_events: int = 1000
    max_signals: int = 100
    lookback_ns: int | None = None
    event_types: tuple[str, ...] = ()
    include_global_events: bool = False
    include_signals: bool = True
    allow_degraded: bool = True
    require_usable_events: bool = False

    def __post_init__(self) -> None:
        if self.max_events <= 0:
            raise ValueError("MAX_EVENTS_MUST_BE_POSITIVE")
        if self.max_signals <= 0:
            raise ValueError("MAX_SIGNALS_MUST_BE_POSITIVE")
        if self.lookback_ns is not None and self.lookback_ns < 0:
            raise ValueError("LOOKBACK_NS_NEGATIVE")
        object.__setattr__(
            self,
            "event_types",
            tuple(sorted({str(value).upper() for value in self.event_types})),
        )


@dataclass(frozen=True, slots=True)
class SnapshotBuildRequest:
    """Caller specification for immutable snapshot composition."""

    decision_time_ns: int
    scope: IntelligenceScope
    composition_policy: SnapshotCompositionPolicy = SnapshotCompositionPolicy()
    capability_requirements: RequirementSet = RequirementSet()

    def __post_init__(self) -> None:
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")


__all__ = [
    "BUILDER_COMPONENT_ID",
    "BUILDER_COMPONENT_VERSION",
    "SnapshotBuildRequest",
    "SnapshotCompositionPolicy",
]
