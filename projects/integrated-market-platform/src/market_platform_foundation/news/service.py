"""Read-only observational news intelligence boundary for downstream strategy work."""

from __future__ import annotations

from typing import Any

from .contracts import NewsArticleEvent, PipelineConfig
from .fixture_provider import FixtureNewsProvider
from .observability import FilterPipelineStats
from .pipeline import NewsPipeline
from .replay import NewsReplayHarness, ReplayResult
from .timestamps import epoch_ns_from_iso, parse_utc_iso, to_utc_iso


class NewsIntelligenceService:
    """
    Observational read-only access to filtered canonical news events.

    This service has no broker, AI, or execution authority. It is intended as the
    downstream boundary for future Paper strategy and AI analysis layers.
    """

    def __init__(
        self,
        *,
        pipeline: NewsPipeline | None = None,
        replay: NewsReplayHarness | None = None,
    ) -> None:
        self._pipeline = pipeline or NewsPipeline()
        self._replay = replay or NewsReplayHarness(self._pipeline)

    def query_filtered_events(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of: str,
        config: PipelineConfig,
    ) -> dict[str, Any]:
        replay = self._replay.replay(events, as_of=as_of, config=config)
        return {
            "as_of": replay.as_of,
            "read_only": True,
            "execution_authority": False,
            "ai_authority": False,
            "items": [event.to_dict() for event in replay.accepted_events],
            "stats": replay.stats.to_dict(),
            "config": config.to_dict(),
        }

    def query_fixture_pack(
        self,
        *,
        as_of: str,
        config: PipelineConfig,
        fixture_provider: FixtureNewsProvider | None = None,
    ) -> dict[str, Any]:
        provider = fixture_provider or FixtureNewsProvider()
        events = provider.fetch_events()
        payload = self.query_filtered_events(events, as_of=as_of, config=config)
        payload["fixture"] = provider.fixture_metadata()
        return payload

    @staticmethod
    def as_of_ns(as_of: str) -> int:
        parsed = parse_utc_iso(as_of)
        if parsed is None:
            raise ValueError(f"AS_OF_INVALID:{as_of}")
        value = epoch_ns_from_iso(to_utc_iso(parsed))
        if value is None:
            raise ValueError(f"AS_OF_INVALID:{as_of}")
        return value


__all__ = ["NewsIntelligenceService"]
