"""Attach an empty IntelligenceRepository and unused ingress router to ReplayStore."""

from __future__ import annotations

from ..intelligence.observation_ingress.production_wire import (
    build_production_observation_ingress_router,
)
from ..intelligence.persistence import InMemoryIntelligenceRepository
from .store import ReplayStore


def bind_ui_api_intelligence(store: ReplayStore) -> ReplayStore:
    """Attach persistence helpers. This is not UI API request-path news admission.

    ``UiApiHandler`` does not call ``admit_news_article_event`` or ``put_event``.
    The EventV1 mapper and ``admit_news_article_event`` remain call-site helpers
    (tests / explicit callers). Binding a router is necessary for those helpers
    in this process and not sufficient for a live ranked book. Does not fetch
    Finviz, start enrichment, or enable Live execution.
    """

    if store.strategy_repository is None:
        store.strategy_repository = InMemoryIntelligenceRepository()
    if getattr(store, "observation_ingress_router", None) is None:
        store.observation_ingress_router = build_production_observation_ingress_router(
            store.strategy_repository
        )
    return store


__all__ = ["bind_ui_api_intelligence"]
