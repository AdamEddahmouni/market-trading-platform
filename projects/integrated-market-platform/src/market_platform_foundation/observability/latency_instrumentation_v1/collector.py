"""In-memory sidecar collector for latency instrumentation v1.

Attach only when measuring. Unbound hot paths skip all marks after a cheap
ContextVar/store lookup (see context.resolve_latency_collector).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .clocks import capture_stage_stamp
from .types import (
    EligibilityClockId,
    LatencyStageId,
    LatencyTraceV1,
    StageStamp,
    UNAVAILABLE_OPERATOR_STAGES,
)


@dataclass
class LatencyInstrumentationCollector:
    """Side observer for news→opportunity software processing clocks."""

    evidence_class: str = "SOFTWARE_CONTROLLED"
    traces: dict[str, LatencyTraceV1] = field(default_factory=dict)
    opportunity_index: dict[str, str] = field(default_factory=dict)
    summary_requests: list[dict[str, Any]] = field(default_factory=list)

    def trace_for(self, correlation_id: str) -> LatencyTraceV1:
        existing = self.traces.get(correlation_id)
        if existing is not None:
            return existing
        trace = LatencyTraceV1(
            correlation_id=correlation_id,
            evidence_class=self.evidence_class,
        )
        self.traces[correlation_id] = trace
        return trace

    def mark_stage(
        self,
        correlation_id: str,
        stage_id: LatencyStageId | str,
        *,
        stamp: StageStamp | None = None,
    ) -> StageStamp:
        """Record a real stamp; does not overwrite an already-observed stage."""

        trace = self.trace_for(correlation_id)
        key = str(stage_id)
        current = trace.stage(key)
        if current.wall_ns is not None or current.mono_ns is not None:
            return current
        observed = stamp if stamp is not None else capture_stage_stamp()
        current.wall_ns = observed.wall_ns
        current.mono_ns = observed.mono_ns
        return current

    def note_eligibility(
        self,
        correlation_id: str,
        *,
        source_publication_ns: int | None = None,
        provider_retrieved_ns: int | None = None,
        imp_server_received_ns: int | None = None,
    ) -> None:
        """Record information-eligibility clocks (distinct from processing stages)."""

        trace = self.trace_for(correlation_id)
        mapping = {
            str(EligibilityClockId.SOURCE_PUBLICATION): source_publication_ns,
            str(EligibilityClockId.PROVIDER_RETRIEVED): provider_retrieved_ns,
            str(EligibilityClockId.IMP_SERVER_RECEIVED): imp_server_received_ns,
        }
        for key, value in mapping.items():
            if value is None:
                # Keep explicit absence; do not invent.
                trace.eligibility_ns.setdefault(key, None)
            else:
                trace.eligibility_ns[key] = int(value)

    def attach_opportunity_id(self, correlation_id: str, opportunity_id: str) -> None:
        trace = self.trace_for(correlation_id)
        trace.opportunity_id = opportunity_id
        self.opportunity_index[opportunity_id] = correlation_id

    def mark_stages_for_opportunity_ids(
        self,
        opportunity_ids: Iterable[str],
        stage_id: LatencyStageId | str,
        *,
        stamp: StageStamp | None = None,
    ) -> tuple[str, ...]:
        """Stamp correlated traces for known opportunity ids; skips unknowns."""

        observed = stamp if stamp is not None else capture_stage_stamp()
        correlated: list[str] = []
        for opportunity_id in opportunity_ids:
            correlation_id = self.opportunity_index.get(str(opportunity_id))
            if correlation_id is None:
                continue
            self.mark_stage(correlation_id, stage_id, stamp=observed)
            correlated.append(correlation_id)
        return tuple(correlated)

    def note_summary_request(
        self,
        *,
        correlated_event_ids: tuple[str, ...],
        rank_stamp: StageStamp,
        api_payload_stamp: StageStamp,
        ranked_opportunity_ids: tuple[str, ...] = (),
    ) -> None:
        self.summary_requests.append(
            {
                "evidence_class": self.evidence_class,
                "correlated_event_ids": list(correlated_event_ids),
                "ranked_opportunity_ids": list(ranked_opportunity_ids),
                "rank_generated": rank_stamp.to_dict(),
                "api_payload_generated": api_payload_stamp.to_dict(),
                "operator_ui_stages": {
                    name: "UNAVAILABLE" for name in UNAVAILABLE_OPERATOR_STAGES
                },
            }
        )

    def get_trace(self, correlation_id: str) -> LatencyTraceV1 | None:
        return self.traces.get(correlation_id)

    def all_traces(self) -> tuple[LatencyTraceV1, ...]:
        return tuple(self.traces.values())

    def mono_delta_ns(
        self,
        correlation_id: str,
        start_stage: LatencyStageId | str,
        end_stage: LatencyStageId | str,
    ) -> int | None:
        """Software duration between two observed stages (monotonic domain only)."""

        trace = self.traces.get(correlation_id)
        if trace is None:
            return None
        start = trace.stages.get(str(start_stage))
        end = trace.stages.get(str(end_stage))
        if start is None or end is None:
            return None
        if start.mono_ns is None or end.mono_ns is None:
            return None
        return int(end.mono_ns) - int(start.mono_ns)


__all__ = ["LatencyInstrumentationCollector"]
