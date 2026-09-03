"""Deterministic replay runtime coordinator (BUILD 07)."""

from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..contracts.common import ComponentLineage, QualityState, QualitySummary
from ..contracts.run_manifest import RunManifestV1
from ..persistence.memory import InMemoryIntelligenceRepository
from ..persistence.repository import IntelligenceRepository
from .clock import ReplayClock
from .errors import ReplayIsolationError
from .faults import build_delivery_schedule
from .models import (
    REPLAY_RUNTIME_COMPONENT_ID,
    REPLAY_RUNTIME_COMPONENT_VERSION,
    DeliveryAction,
    ReplayDecisionResult,
    ReplayMode,
    ReplayRunResult,
    ReplayTraceSummary,
)
from .observer import NullReplayObserver, ReplayObserver, ReplayTraceRecorder
from .pipeline import ReplayPipelineConfig, process_replay_decision
from .scenario import ReplayScenario
from .visibility import ReplayVisibilityIndex, ReplayVisibleRepository
from ..routing import EventDetectorEngine, SmartRouter


class _ScheduleKind(IntEnum):
    PROVIDER_STATE = 0
    DELIVERY = 1
    DECISION = 2
    CHECKPOINT = 3


@dataclass(frozen=True, slots=True, order=True)
class _ScheduledItem:
    time_ns: int
    kind: int
    tie_breaker: int
    payload: Any


def _same_repository_identity(left: IntelligenceRepository, right: IntelligenceRepository) -> bool:
    return left is right


def _assert_repository_isolation(
    source_repository: IntelligenceRepository,
    output_repository: IntelligenceRepository,
) -> None:
    if _same_repository_identity(source_repository, output_repository):
        raise ReplayIsolationError(
            "REPLAY_SOURCE_OUTPUT_ALIAS",
            "source and output repositories must not be the same object",
        )


def _build_run_manifest(
    *,
    scenario: ReplayScenario,
    run_id: str,
    created_at_ns: int,
    code_revision: str | None,
) -> RunManifestV1:
    data_mode = "HISTORICAL_CAPTURE" if scenario.effective_mode == ReplayMode.OBSERVED_REPLAY else "FIXTURE_REPLAY"
    lineage = ComponentLineage(
        component_id=REPLAY_RUNTIME_COMPONENT_ID,
        component_version=REPLAY_RUNTIME_COMPONENT_VERSION,
        code_revision=code_revision,
    )
    return RunManifestV1(
        run_id=run_id,
        schema_version="1",
        created_at_ns=created_at_ns,
        quality=QualitySummary(state=QualityState.GOOD),
        run_window_start_ns=scenario.decision_start_time_ns,
        run_window_end_ns=scenario.decision_end_time_ns,
        data_mode=data_mode,
        execution_mode="NONE",
        execution_authority="BLOCKED",
        code_revision=code_revision,
        config_identity=scenario.fingerprint(),
        component_lineage=lineage,
        metadata={
            "replay_mode": scenario.effective_mode.value,
            "scenario_fingerprint": scenario.fingerprint(),
            "scenario_version": scenario.scenario_version,
            "source_start_time_ns": scenario.source_start_time_ns,
            "source_end_time_ns": scenario.source_end_time_ns,
            "decision_times_ns": list(scenario.decision_schedule.decision_times_ns),
            "replay_classification": scenario.effective_mode.value,
        },
    )


class ReplayRuntime:
    """Deterministic replay coordinator with virtual clock and visibility boundary."""

    def __init__(
        self,
        *,
        observer: ReplayObserver | None = None,
        trace_recorder: ReplayTraceRecorder | None = None,
    ) -> None:
        self._observer = observer or NullReplayObserver()
        self._trace = trace_recorder

    def run(
        self,
        scenario: ReplayScenario,
        source_repository: IntelligenceRepository,
        *,
        output_repository: IntelligenceRepository | None = None,
        pipeline_config: ReplayPipelineConfig | None = None,
        run_id: str | None = None,
        code_revision: str | None = None,
        persist_manifest: bool = True,
    ) -> ReplayRunResult:
        output = output_repository or InMemoryIntelligenceRepository()
        _assert_repository_isolation(source_repository, output)

        source_events = source_repository.iter_events_by_availability(
            start_time_ns=scenario.source_start_time_ns,
            end_time_ns=scenario.source_end_time_ns,
            instrument_id=scenario.instrument_id,
            event_type=scenario.event_type,
            provider_id=scenario.provider_id,
        )
        envelopes = build_delivery_schedule(
            source_events,
            mode=scenario.effective_mode,
            fault_profile=scenario.fault_profile,
            replay_end_ns=scenario.decision_end_time_ns,
        )
        visibility_index = ReplayVisibilityIndex.from_envelopes(envelopes)

        clock = ReplayClock(scenario.source_start_time_ns)
        trace = self._trace or ReplayTraceRecorder(max_entries=1000)
        scheduled = self._build_schedule(scenario, envelopes)
        decision_results: list[ReplayDecisionResult] = []
        detector_engine = (
            EventDetectorEngine(pipeline_config.detection_policy)
            if pipeline_config is not None and pipeline_config.enable_build_09
            else None
        )
        smart_router = (
            SmartRouter(pipeline_config.routing_policy)
            if pipeline_config is not None and pipeline_config.enable_build_09
            else None
        )
        active_run_id = run_id or f"REPLAY-{uuid.uuid5(uuid.NAMESPACE_URL, scenario.fingerprint()).hex.upper()}"

        while scheduled:
            item = heapq.heappop(scheduled)
            clock.advance_to(item.time_ns)
            if item.kind == _ScheduleKind.DELIVERY:
                envelope = item.payload
                if envelope.delivery_action in {
                    DeliveryAction.DROP,
                    DeliveryAction.DISCONNECT_DROP,
                }:
                    trace.on_drop(envelope)
                    self._observer.on_drop(envelope)
                else:
                    trace.on_delivery(envelope)
                    self._observer.on_delivery(envelope)
            elif item.kind == _ScheduleKind.DECISION:
                decision_time_ns = item.payload
                trace.on_decision(decision_time_ns)
                self._observer.on_decision(decision_time_ns)
                visible_repo = ReplayVisibleRepository(
                    source_repository=source_repository,
                    output_repository=output,
                    visibility_index=visibility_index,
                    decision_time_ns=decision_time_ns,
                )
                if pipeline_config is not None:
                    result = process_replay_decision(
                        visible_repo,
                        output,
                        decision_time_ns=decision_time_ns,
                        config=pipeline_config,
                        detector_engine=detector_engine,
                        smart_router=smart_router,
                    )
                    decision_results.append(result)
                    if result.snapshot_ref is not None:
                        snapshot = output.get_snapshot(result.snapshot_ref.id)
                        if snapshot is not None:
                            self._observer.on_snapshot(snapshot)
                    for signal_ref in result.signal_refs:
                        signal = output.get_signal(signal_ref.id)
                        if signal is not None:
                            self._observer.on_signal(signal)

        undelivered = sum(
            1
            for envelope in envelopes
            if envelope.delivery_action not in {DeliveryAction.DROP, DeliveryAction.DISCONNECT_DROP}
            and envelope.effective_delivery_time_ns > scenario.decision_end_time_ns
        )
        trace.record_undelivered(undelivered)

        manifest = _build_run_manifest(
            scenario=scenario,
            run_id=active_run_id,
            created_at_ns=scenario.decision_start_time_ns,
            code_revision=code_revision,
        )
        if persist_manifest:
            output.put_run_manifest(manifest)

        return ReplayRunResult(
            scenario_fingerprint=scenario.fingerprint(),
            run_id=active_run_id,
            replay_mode=scenario.effective_mode,
            start_time_ns=scenario.decision_start_time_ns,
            end_time_ns=scenario.decision_end_time_ns,
            source_event_count=len(source_events),
            trace_summary=trace.summary,
            decision_results=tuple(decision_results),
            metadata={
                "replay_classification": scenario.effective_mode.value,
                "manifest_run_id": manifest.run_id,
            },
        )

    def _build_schedule(
        self,
        scenario: ReplayScenario,
        envelopes: tuple,
    ) -> list[_ScheduledItem]:
        items: list[_ScheduledItem] = []
        delivery_counter = 0
        for envelope in envelopes:
            if envelope.delivery_action in {DeliveryAction.DROP, DeliveryAction.DISCONNECT_DROP}:
                items.append(
                    _ScheduledItem(
                        envelope.recorded_available_time_ns,
                        _ScheduleKind.DELIVERY,
                        delivery_counter,
                        envelope,
                    )
                )
            else:
                items.append(
                    _ScheduledItem(
                        envelope.effective_delivery_time_ns,
                        _ScheduleKind.DELIVERY,
                        delivery_counter,
                        envelope,
                    )
                )
            delivery_counter += 1

        for index, decision_time_ns in enumerate(scenario.decision_schedule.decision_times_ns):
            if decision_time_ns < scenario.decision_start_time_ns:
                continue
            items.append(
                _ScheduledItem(
                    decision_time_ns,
                    _ScheduleKind.DECISION,
                    index,
                    decision_time_ns,
                )
            )

        heapq.heapify(items)
        return items


__all__ = ["ReplayRuntime"]
