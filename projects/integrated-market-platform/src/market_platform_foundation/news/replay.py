"""Event-time-safe deterministic replay harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import NewsArticleEvent, PipelineConfig, PipelineEventResult
from .observability import FilterPipelineStats
from .pipeline import NewsPipeline, order_accepted_events
from .timestamps import epoch_ns_from_iso, to_utc_iso
from .timestamps import parse_utc_iso


@dataclass(frozen=True, slots=True)
class ReplayResult:
    as_of: str
    as_of_ns: int
    config: PipelineConfig
    results: tuple[PipelineEventResult, ...]
    accepted_events: tuple[NewsArticleEvent, ...]
    stats: FilterPipelineStats

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "config": self.config.to_dict(),
            "accepted_count": len(self.accepted_events),
            "accepted_event_ids": [event.event_id for event in self.accepted_events],
            "stats": self.stats.to_dict(),
            "results": [
                {
                    "event_id": result.event.event_id,
                    "accepted": result.accepted,
                    "duplicate_of": result.duplicate_of,
                    "decisions": [
                        {
                            "stage": decision.stage.value,
                            "accepted": decision.accepted,
                            "reason_code": decision.reason_code,
                            "detail": decision.detail,
                            "matched_catalyst_ids": list(decision.matched_catalyst_ids),
                        }
                        for decision in result.decisions
                    ],
                }
                for result in self.results
            ],
        }


class NewsReplayHarness:
    """Replay fixture events against an explicit as-of timeline without look-ahead."""

    def __init__(self, pipeline: NewsPipeline | None = None) -> None:
        self._pipeline = pipeline or NewsPipeline()

    def replay(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of: str,
        config: PipelineConfig,
    ) -> ReplayResult:
        parsed = parse_utc_iso(as_of)
        if parsed is None:
            raise ValueError(f"REPLAY_AS_OF_INVALID:{as_of}")
        as_of_ns = epoch_ns_from_iso(to_utc_iso(parsed))
        if as_of_ns is None:
            raise ValueError(f"REPLAY_AS_OF_INVALID:{as_of}")
        stats = FilterPipelineStats()
        results = tuple(
            self._pipeline.process(events, as_of_ns=as_of_ns, config=config, stats=stats)
        )
        accepted = tuple(
            order_accepted_events(
                [result.event for result in results if result.accepted and not result.duplicate_of]
            )
        )
        return ReplayResult(
            as_of=to_utc_iso(parsed),
            as_of_ns=as_of_ns,
            config=config,
            results=results,
            accepted_events=accepted,
            stats=stats,
        )


__all__ = ["NewsReplayHarness", "ReplayResult"]
