"""Deterministic intelligence replay over curated news and fixture providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market_platform_foundation.news.config import default_pipeline_config
from market_platform_foundation.news.contracts import NewsArticleEvent, PipelineConfig
from market_platform_foundation.news.replay import NewsReplayHarness
from market_platform_foundation.news.service import NewsIntelligenceService

from .analyzer import AnalyzeOutcome, NewsIntelligenceAnalyzer
from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceTaskType
from .provider import FixtureInferenceProvider, InferenceProvider


@dataclass(frozen=True, slots=True)
class IntelligenceReplayResult:
    as_of: str
    pipeline_config: PipelineConfig
    inference_config: IntelligenceInferenceConfig
    curated_event_ids: tuple[str, ...]
    outcome: AnalyzeOutcome

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "pipeline_config": self.pipeline_config.to_dict(),
            "inference_config": self.inference_config.to_dict(),
            "curated_event_ids": list(self.curated_event_ids),
            "outcome": self.outcome.to_dict(),
        }


class IntelligenceReplayHarness:
    """Replay fixture events through deterministic news filtering then fixture inference."""

    def __init__(
        self,
        *,
        news_service: NewsIntelligenceService | None = None,
        analyzer: NewsIntelligenceAnalyzer | None = None,
        provider: InferenceProvider | None = None,
    ) -> None:
        provider = provider or FixtureInferenceProvider()
        self._news = news_service or NewsIntelligenceService()
        self._analyzer = analyzer or NewsIntelligenceAnalyzer(provider=provider)

    @property
    def analyzer(self) -> NewsIntelligenceAnalyzer:
        return self._analyzer

    def replay(
        self,
        events: list[NewsArticleEvent],
        *,
        as_of: str,
        pipeline_config: PipelineConfig | None = None,
        inference_config: IntelligenceInferenceConfig | None = None,
        task_type: IntelligenceTaskType | None = None,
    ) -> IntelligenceReplayResult:
        config = pipeline_config or default_pipeline_config()
        inf_config = inference_config or IntelligenceInferenceConfig()
        replay = NewsReplayHarness().replay(events, as_of=as_of, config=config)
        curated = list(replay.accepted_events)
        outcome = self._analyzer.analyze(
            curated,
            as_of=as_of,
            pipeline_config=config,
            inference_config=inf_config,
            task_type=task_type,
        )
        return IntelligenceReplayResult(
            as_of=replay.as_of,
            pipeline_config=config,
            inference_config=inf_config,
            curated_event_ids=tuple(event.event_id for event in curated),
            outcome=outcome,
        )


__all__ = ["IntelligenceReplayHarness", "IntelligenceReplayResult"]
