"""Replay scenario definition and fingerprinting (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .errors import ReplayConfigurationError
from .faults import ReplayFaultProfile, fault_profile_to_dict
from .models import REPLAY_SCENARIO_FINGERPRINT_VERSION, ReplayMode
from .schedule import ReplayDecisionSchedule


@dataclass(frozen=True, slots=True)
class ReplayScenario:
    """Immutable deterministic replay configuration."""

    scenario_version: str
    mode: ReplayMode
    source_start_time_ns: int
    source_end_time_ns: int
    decision_start_time_ns: int
    decision_end_time_ns: int
    decision_schedule: ReplayDecisionSchedule
    fault_profile: ReplayFaultProfile = field(default_factory=ReplayFaultProfile)
    instrument_id: str | None = None
    event_type: str | None = None
    provider_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_start_time_ns > self.source_end_time_ns:
            raise ReplayConfigurationError("SOURCE_RANGE_INVALID", "source_start_time_ns must be <= source_end_time_ns")
        if self.decision_start_time_ns > self.decision_end_time_ns:
            raise ReplayConfigurationError(
                "DECISION_RANGE_INVALID",
                "decision_start_time_ns must be <= decision_end_time_ns",
            )
        if self.source_start_time_ns > self.decision_start_time_ns:
            raise ReplayConfigurationError(
                "PREROLL_INVALID",
                "source_start_time_ns must be <= decision_start_time_ns",
            )
        if self.mode == ReplayMode.OBSERVED_REPLAY and self.fault_profile.has_faults():
            raise ReplayConfigurationError(
                "OBSERVED_WITH_FAULTS",
                "OBSERVED_REPLAY cannot include artificial fault rules",
            )
        if self.mode == ReplayMode.COUNTERFACTUAL and not self.fault_profile.has_faults():
            raise ReplayConfigurationError(
                "COUNTERFACTUAL_WITHOUT_FAULTS",
                "COUNTERFACTUAL mode requires at least one fault rule",
            )
        self.decision_schedule.validate_within_window(
            window_start_ns=self.decision_start_time_ns,
            window_end_ns=self.decision_end_time_ns,
        )
        if not isinstance(self.metadata, dict):
            raise ReplayConfigurationError("SCENARIO_METADATA_INVALID", "metadata must be a dict")

    @property
    def effective_mode(self) -> ReplayMode:
        if self.fault_profile.has_faults():
            return ReplayMode.COUNTERFACTUAL
        return ReplayMode.OBSERVED_REPLAY

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "fingerprint_version": REPLAY_SCENARIO_FINGERPRINT_VERSION,
            "scenario_version": self.scenario_version,
            "mode": self.mode.value,
            "source_start_time_ns": self.source_start_time_ns,
            "source_end_time_ns": self.source_end_time_ns,
            "decision_start_time_ns": self.decision_start_time_ns,
            "decision_end_time_ns": self.decision_end_time_ns,
            "decision_times_ns": list(self.decision_schedule.decision_times_ns),
            "instrument_id": self.instrument_id,
            "event_type": self.event_type,
            "provider_id": self.provider_id,
            "fault_profile": fault_profile_to_dict(self.fault_profile),
            "metadata": dict(sorted(self.metadata.items())),
        }

    def fingerprint(self) -> str:
        return sha256_bytes(canonical_bytes(self.semantic_payload()))


def observed_replay_scenario(
    *,
    source_start_time_ns: int,
    source_end_time_ns: int,
    decision_schedule: ReplayDecisionSchedule,
    instrument_id: str | None = None,
    event_type: str | None = None,
    provider_id: str | None = None,
) -> ReplayScenario:
    decision_times = decision_schedule.decision_times_ns
    if not decision_times:
        raise ReplayConfigurationError("DECISION_SCHEDULE_EMPTY", "decision schedule must not be empty")
    return ReplayScenario(
        scenario_version="1",
        mode=ReplayMode.OBSERVED_REPLAY,
        source_start_time_ns=source_start_time_ns,
        source_end_time_ns=source_end_time_ns,
        decision_start_time_ns=decision_times[0],
        decision_end_time_ns=decision_times[-1],
        decision_schedule=decision_schedule,
        instrument_id=instrument_id,
        event_type=event_type,
        provider_id=provider_id,
    )


def counterfactual_replay_scenario(
    *,
    source_start_time_ns: int,
    source_end_time_ns: int,
    decision_schedule: ReplayDecisionSchedule,
    fault_profile: ReplayFaultProfile,
    instrument_id: str | None = None,
    event_type: str | None = None,
    provider_id: str | None = None,
) -> ReplayScenario:
    decision_times = decision_schedule.decision_times_ns
    if not decision_times:
        raise ReplayConfigurationError("DECISION_SCHEDULE_EMPTY", "decision schedule must not be empty")
    return ReplayScenario(
        scenario_version="1",
        mode=ReplayMode.COUNTERFACTUAL,
        source_start_time_ns=source_start_time_ns,
        source_end_time_ns=source_end_time_ns,
        decision_start_time_ns=decision_times[0],
        decision_end_time_ns=decision_times[-1],
        decision_schedule=decision_schedule,
        fault_profile=fault_profile,
        instrument_id=instrument_id,
        event_type=event_type,
        provider_id=provider_id,
    )


__all__ = [
    "ReplayScenario",
    "counterfactual_replay_scenario",
    "observed_replay_scenario",
]
