"""Deterministic news normalization, dedupe, and filter pipeline."""

from __future__ import annotations

from .contracts import (
    DuplicateRelationship,
    FilterDecision,
    FilterStage,
    NewsArticleEvent,
    PipelineConfig,
    PipelineEventResult,
)
from .dedupe import classify_duplicate, dedupe_events
from .filters import FilterChain, default_filter_chain
from .observability import FilterPipelineStats
from .timestamps import epoch_ns_from_iso, is_observable_at, observable_time_ns


def _observability_decision(event: NewsArticleEvent, as_of_ns: int) -> FilterDecision:
    if is_observable_at(event, as_of_ns):
        return FilterDecision(
            stage=FilterStage.OBSERVABILITY,
            accepted=True,
            reason_code="OBSERVABLE",
            detail="retrieved_time <= as_of",
        )
    observed = observable_time_ns(event)
    return FilterDecision(
        stage=FilterStage.OBSERVABILITY,
        accepted=False,
        reason_code="OBSERVABILITY_LOOKAHEAD",
        detail=f"retrieved_ns={observed} as_of_ns={as_of_ns}",
    )


def stable_event_order_key(event: NewsArticleEvent) -> tuple:
    observed = observable_time_ns(event) or 0
    published = epoch_ns_from_iso(event.published_time) or 0
    return (
        -observed,
        -published,
        event.source_id,
        event.event_id,
    )


def order_accepted_events(events: list[NewsArticleEvent]) -> list[NewsArticleEvent]:
    return sorted(events, key=stable_event_order_key)


class NewsPipeline:
    """Normalize, dedupe, and filter news events deterministically."""

    def __init__(self, filter_chain: FilterChain | None = None) -> None:
        self._filter_chain = filter_chain or default_filter_chain()

    def process(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of_ns: int,
        config: PipelineConfig,
        stats: FilterPipelineStats | None = None,
    ) -> list[PipelineEventResult]:
        tracker = stats or FilterPipelineStats()
        tracker.record_ingest(len(events))
        results: list[PipelineEventResult] = []
        observable: list[NewsArticleEvent] = []
        for event in events:
            # Only publication-time flags feed the timestamp metric — linkage
            # PROVIDER_LINKAGE_* warnings must not pollute it.
            if any(str(flag).startswith("PUBLICATION_") for flag in event.quality_flags):
                tracker.record_timestamp_quality_issue()
            obs = _observability_decision(event, as_of_ns)
            if not obs.accepted:
                results.append(
                    PipelineEventResult(event=event, accepted=False, decisions=(obs,))
                )
                tracker.record_result(results[-1])
                continue
            observable.append(event)
        unique, duplicate_map = dedupe_events(observable)
        for event in observable:
            if event.event_id in duplicate_map:
                results.append(
                    PipelineEventResult(
                        event=event,
                        accepted=False,
                        decisions=(
                            FilterDecision(
                                stage=FilterStage.DEDUPLICATION,
                                accepted=False,
                                reason_code="DUPLICATE",
                                detail=duplicate_map[event.event_id],
                            ),
                        ),
                        duplicate_of=duplicate_map[event.event_id],
                        duplicate_relationship=DuplicateRelationship.EXACT_DUPLICATE,
                    )
                )
                tracker.record_result(results[-1])
        for event in unique:
            accepted, decisions = self._filter_chain.run(
                event,
                as_of_ns=as_of_ns,
                config=config,
            )
            result = PipelineEventResult(event=event, accepted=accepted, decisions=decisions)
            results.append(result)
            tracker.record_result(result)
        return results

    def accepted_events(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of_ns: int,
        config: PipelineConfig,
        stats: FilterPipelineStats | None = None,
    ) -> tuple[list[NewsArticleEvent], FilterPipelineStats]:
        tracker = stats or FilterPipelineStats()
        results = self.process(events, as_of_ns=as_of_ns, config=config, stats=tracker)
        accepted = order_accepted_events(
            [result.event for result in results if result.accepted and not result.duplicate_of]
        )
        return accepted, tracker


__all__ = [
    "NewsPipeline",
    "order_accepted_events",
    "stable_event_order_key",
]
