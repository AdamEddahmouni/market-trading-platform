"""Opt-in observational live news ingress into canonical ``NewsArticleEvent``.

Scaffolding only: not auto-wired to ``paper_forward_bridge`` or forward-test
campaign flows. Manifest ``deferred_until_evidence`` keeps FTEP-ACT-04 /
FTEP-D038 campaign-scale connectivity owner-gated until de-deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .aggregator import NewsAggregator
from .aggregator_bridge import aggregator_items_to_events
from .config import (
    finnhub_live_enabled,
    newsapi_live_enabled,
    observational_news_ingress_enabled,
)
from .contracts import NewsArticleEvent
from .providers import FinnhubNewsClient, NewsApiClient

OBSERVATIONAL_SOURCE_ID = "observational_news_ingress"


@dataclass(frozen=True)
class ObservationalIngressResult:
    """Result of a single observational fetch (no side effects on Paper/Live)."""

    enabled: bool
    ready: bool
    reason: str | None
    events: tuple[NewsArticleEvent, ...]
    source_status: dict[str, dict[str, Any]]
    errors: dict[str, str]


def observational_provider_gates_active() -> bool:
    return newsapi_live_enabled() or finnhub_live_enabled()


def observational_ingress_ready() -> bool:
    return observational_news_ingress_enabled() and observational_provider_gates_active()


def build_observational_aggregator() -> NewsAggregator:
    """NewsAggregator limited to live-gated NewsAPI / Finnhub sources."""
    sources: list[Any] = []
    if newsapi_live_enabled():
        sources.append(NewsApiClient())
    if finnhub_live_enabled():
        sources.append(FinnhubNewsClient())
    return NewsAggregator(sources=tuple(sources))


def fetch_observational_news_events(
    symbol: str,
    *,
    aggregator: NewsAggregator | None = None,
) -> ObservationalIngressResult:
    """Fetch provider news and normalize through ``aggregator_bridge`` when gates allow."""
    if not observational_news_ingress_enabled():
        return ObservationalIngressResult(
            enabled=False,
            ready=False,
            reason="INGRESS_DISABLED",
            events=(),
            source_status={},
            errors={},
        )
    if not observational_provider_gates_active():
        return ObservationalIngressResult(
            enabled=True,
            ready=False,
            reason="NO_LIVE_PROVIDER_GATES",
            events=(),
            source_status={},
            errors={},
        )
    agg = aggregator if aggregator is not None else build_observational_aggregator()
    raw = agg.fetch_news(symbol)
    items = [
        item for item in (raw.get("items") or []) if isinstance(item, dict)
    ]
    events = aggregator_items_to_events(
        items,
        source_id=OBSERVATIONAL_SOURCE_ID,
    )
    source_status = {
        str(key): dict(value)
        for key, value in (raw.get("source_status") or {}).items()
        if isinstance(value, dict)
    }
    errors = {
        str(key): str(value)
        for key, value in (raw.get("errors") or {}).items()
    }
    return ObservationalIngressResult(
        enabled=True,
        ready=True,
        reason=None,
        events=events,
        source_status=source_status,
        errors=errors,
    )


def observational_ingress_diagnostics() -> dict[str, object]:
    """Secret-free status for operator probes and readiness tooling."""
    return {
        "ingress_gate": observational_news_ingress_enabled(),
        "newsapi_live_gate": newsapi_live_enabled(),
        "finnhub_live_gate": finnhub_live_enabled(),
        "ready": observational_ingress_ready(),
        "wired_to_forward_test_bridge": False,
        "campaign_connectivity_deferred": True,
        "deferral_keys": ("FTEP-ACT-04", "FTEP-D038"),
    }


__all__ = [
    "OBSERVATIONAL_SOURCE_ID",
    "ObservationalIngressResult",
    "build_observational_aggregator",
    "fetch_observational_news_events",
    "observational_ingress_diagnostics",
    "observational_ingress_ready",
    "observational_provider_gates_active",
]
