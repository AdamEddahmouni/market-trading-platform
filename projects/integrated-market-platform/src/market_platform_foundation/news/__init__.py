"""Canonical deterministic news/event ingestion, filtering, and replay."""

from .aggregator import NewsAggregator, aggregate_news_items
from .config import default_pipeline_config, verify_news_config
from .contracts import (
    FilterDecision,
    FilterStage,
    NewsArticleEvent,
    PipelineConfig,
    PipelineEventResult,
    PublicationTimeQuality,
)
from .fixture_provider import FixtureNewsProvider
from .pipeline import NewsPipeline, order_accepted_events
from .providers import FinnhubNewsClient, NewsApiClient
from .replay import NewsReplayHarness, ReplayResult
from .service import NewsIntelligenceService

__all__ = [
    "FilterDecision",
    "FilterStage",
    "FinnhubNewsClient",
    "FixtureNewsProvider",
    "NewsAggregator",
    "NewsApiClient",
    "NewsArticleEvent",
    "NewsIntelligenceService",
    "NewsPipeline",
    "NewsReplayHarness",
    "PipelineConfig",
    "PipelineEventResult",
    "PublicationTimeQuality",
    "ReplayResult",
    "aggregate_news_items",
    "default_pipeline_config",
    "order_accepted_events",
    "verify_news_config",
]
