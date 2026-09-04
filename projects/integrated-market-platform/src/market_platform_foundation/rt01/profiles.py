"""RT-01 named latency profiles."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import SamplingMode, TraceStage


@dataclass(frozen=True, slots=True)
class LatencyProfile:
    profile_id: str
    version: str
    root_stage: TraceStage
    terminal_stages: tuple[TraceStage, ...]
    clock_basis: str
    sampling: SamplingMode
    workload: str
    aggregation: str


PROFILE_RECEIVE_TO_CANONICAL = LatencyProfile(
    profile_id="receive_to_canonical_state",
    version="1",
    root_stage=TraceStage.PROVIDER_RECEIVE,
    terminal_stages=(TraceStage.CANONICAL_STATE,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="fixture_replay_short",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_RECEIVE_TO_QUALITY = LatencyProfile(
    profile_id="receive_to_quality",
    version="1",
    root_stage=TraceStage.PROVIDER_RECEIVE,
    terminal_stages=(TraceStage.QUALITY,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="fixture_replay_short",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_RECEIVE_TO_SIGNAL = LatencyProfile(
    profile_id="receive_to_signal",
    version="1",
    root_stage=TraceStage.PROVIDER_RECEIVE,
    terminal_stages=(TraceStage.SIGNAL,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="intelligence_replay_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_RECEIVE_TO_FEATURE = LatencyProfile(
    profile_id="receive_to_feature",
    version="1",
    root_stage=TraceStage.PROVIDER_RECEIVE,
    terminal_stages=(TraceStage.FEATURE,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="quality_feature_replay",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_QUEUE_WAIT = LatencyProfile(
    profile_id="queue_wait",
    version="1",
    root_stage=TraceStage.QUEUE,
    terminal_stages=(TraceStage.QUEUE,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="fixture_replay_short",
    aggregation="queue_wait_ns",
)

PROFILE_QUEUE_TO_SIGNAL = LatencyProfile(
    profile_id="queue_to_signal",
    version="1",
    root_stage=TraceStage.QUEUE,
    terminal_stages=(TraceStage.SIGNAL,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_strategy_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_SIGNAL_TO_DECISION = LatencyProfile(
    profile_id="signal_to_decision",
    version="1",
    root_stage=TraceStage.SIGNAL,
    terminal_stages=(TraceStage.RISK,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_strategy_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_DECISION_TO_SUBMISSION = LatencyProfile(
    profile_id="decision_to_submission",
    version="1",
    root_stage=TraceStage.RISK,
    terminal_stages=(TraceStage.ORDER_READY,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_strategy_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_SUBMISSION_TO_BROKER = LatencyProfile(
    profile_id="submission_to_broker",
    version="1",
    root_stage=TraceStage.ORDER_READY,
    terminal_stages=(TraceStage.BROKER,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_broker_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_BROKER_TO_RECONCILIATION = LatencyProfile(
    profile_id="broker_to_reconciliation",
    version="1",
    root_stage=TraceStage.BROKER,
    terminal_stages=(TraceStage.RECONCILIATION,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_broker_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

PROFILE_PAPER_END_TO_END = LatencyProfile(
    profile_id="paper_end_to_end",
    version="1",
    root_stage=TraceStage.TRACE_ROOT,
    terminal_stages=(TraceStage.RECONCILIATION,),
    clock_basis="process_monotonic_ns",
    sampling=SamplingMode.FULL,
    workload="paper_broker_fixture",
    aggregation="root_to_terminal_elapsed_ns",
)

ALL_PROFILES: tuple[LatencyProfile, ...] = (
    PROFILE_RECEIVE_TO_CANONICAL,
    PROFILE_RECEIVE_TO_QUALITY,
    PROFILE_RECEIVE_TO_SIGNAL,
    PROFILE_RECEIVE_TO_FEATURE,
    PROFILE_QUEUE_WAIT,
    PROFILE_QUEUE_TO_SIGNAL,
    PROFILE_SIGNAL_TO_DECISION,
    PROFILE_DECISION_TO_SUBMISSION,
    PROFILE_SUBMISSION_TO_BROKER,
    PROFILE_BROKER_TO_RECONCILIATION,
    PROFILE_PAPER_END_TO_END,
)


def profile_by_id(profile_id: str) -> LatencyProfile | None:
    for profile in ALL_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    return None


__all__ = [
    "ALL_PROFILES",
    "LatencyProfile",
    "PROFILE_BROKER_TO_RECONCILIATION",
    "PROFILE_DECISION_TO_SUBMISSION",
    "PROFILE_PAPER_END_TO_END",
    "PROFILE_QUEUE_WAIT",
    "PROFILE_QUEUE_TO_SIGNAL",
    "PROFILE_RECEIVE_TO_CANONICAL",
    "PROFILE_RECEIVE_TO_FEATURE",
    "PROFILE_RECEIVE_TO_QUALITY",
    "PROFILE_RECEIVE_TO_SIGNAL",
    "PROFILE_SIGNAL_TO_DECISION",
    "PROFILE_SUBMISSION_TO_BROKER",
    "profile_by_id",
]
