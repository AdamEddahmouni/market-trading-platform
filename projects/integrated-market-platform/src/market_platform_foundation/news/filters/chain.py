"""Composable deterministic filter chain: recency → source → catalyst."""

from __future__ import annotations

from typing import Protocol

from ..contracts import FilterDecision, NewsArticleEvent, PipelineConfig
from .catalyst_match import CatalystKeywordFilter
from .recency import RecencyFilter
from .source_policy import SourcePolicyFilter


class _Filter(Protocol):
    def evaluate(self, event: NewsArticleEvent, **kwargs: object) -> FilterDecision:
        ...


class FilterChain:
    VERSION = "news/filters/1.0.0"

    def __init__(self, filters: tuple[_Filter, ...] | None = None) -> None:
        self._filters = filters or (
            RecencyFilter(),
            SourcePolicyFilter(),
            CatalystKeywordFilter(),
        )

    def run(
        self,
        event: NewsArticleEvent,
        *,
        as_of_ns: int,
        config: PipelineConfig,
    ) -> tuple[bool, tuple[FilterDecision, ...]]:
        decisions: list[FilterDecision] = []
        for stage in self._filters:
            if isinstance(stage, RecencyFilter):
                decision = stage.evaluate(event, as_of_ns=as_of_ns, config=config)
            else:
                decision = stage.evaluate(event, config=config)
            decisions.append(decision)
            if not decision.accepted:
                return False, tuple(decisions)
        return True, tuple(decisions)


def default_filter_chain() -> FilterChain:
    return FilterChain()


__all__ = ["FilterChain", "default_filter_chain"]
